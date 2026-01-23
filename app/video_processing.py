import os
import sys
import time
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from threading import Thread, Lock
from collections import deque
from datetime import datetime
from app import db, socketio
from config import Config
from app.models import Incident

# --- GLOBAL VARIABLES ---
detection_model = None
camera_streams = {}
processing_active = True
frame_lock = Lock()
latest_frames = {}
alert_queue = deque(maxlen=100)  # For quick in-memory access/display
class_names = Config.CLASS_NAMES
# ------------------------

# ================== MODEL LOADING ==================
def load_detection_model():
    """Load the trained Keras classification model."""
    global detection_model

    try:
        if os.path.exists(Config.MODEL_PATH):
            print(f"Loading Keras classification model from {Config.MODEL_PATH}...")
            detection_model = load_model(Config.MODEL_PATH, compile=False)
            print("Model loaded successfully!")
        else:
            print(f"Warning: Model not found at {Config.MODEL_PATH}")
            detection_model = None

    except Exception as e:
        print(f"Error loading model: {e}")
        detection_model = None

def load_label_map():
    """Load the label map for the classification model."""
    global class_names

    try:
        if os.path.exists(Config.LABEL_MAP_PATH):
            print(f"Loading label map from {Config.LABEL_MAP_PATH}...")
            with open(Config.LABEL_MAP_PATH, 'r') as file:
                class_names = [line.strip() for line in file.readlines()]
            print("Label map loaded successfully!")
        else:
            print(f"Warning: Label map not found at {Config.LABEL_MAP_PATH}")
            class_names = []

    except Exception as e:
        print(f"Error loading label map: {e}")
        class_names = []

# ================== VIDEO PROCESSING CLASS ==================

class CameraStream:
    def __init__(self, camera_id, source=6):
        self.camera_id = camera_id
        self.source = source
        self.cap = None
        self.running = False
        self.frame = None
        self.lock = Lock()

    def start(self):
        """Start the camera stream"""
        try:
            print(f"Attempting to open camera {self.camera_id} with source {self.source}")
            self.cap = cv2.VideoCapture(self.source)
            if not self.cap.isOpened():
                print(f"Error: Camera {self.camera_id} could not be opened.")
                return False
                
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.running = True
            Thread(target=self._update_frame, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error starting camera {self.camera_id}: {e}")
            return False

    def _update_frame(self):
        """Continuously read frames from camera"""
        while self.running:
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                    print(f"Frame captured from camera {self.camera_id}.")  # Debugging line
                else:
                    print(f"Warning: Failed to read frame from camera {self.camera_id}.")
            time.sleep(0.03)

    def get_frame(self):
        """Get the latest frame"""
        with self.lock:
            if self.frame is not None:
                print(f"Returning frame from camera {self.camera_id}.")  # Debugging line
                return self.frame.copy()
            else:
                print(f"No frame available from camera {self.camera_id}.")  # Debugging line
                return None

    def stop(self):
        """Stop the camera stream"""
        self.running = False
        if self.cap:
            self.cap.release()

    def get_status(self):
        """Get the current status of the camera"""
        with self.lock:
            status = {
                'camera_id': self.camera_id,
                'running': self.running,
                'frame_available': self.frame is not None,
                'frame_shape': self.frame.shape if self.frame is not None else None
            }
        return status

# ================== INFERENCE AND FRAME PROCESSING ==================

def run_inference(frame):
    """Run image classification inference on a frame."""
    if detection_model is None or frame is None:
        print("No model loaded or frame is None.")
        return None

    try:
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized_frame = cv2.resize(rgb_frame, (Config.IMAGE_SIZE, Config.IMAGE_SIZE))
        input_tensor = tf.convert_to_tensor(resized_frame, dtype=tf.float32) / 255.0
        input_tensor = tf.expand_dims(input_tensor, axis=0)
        predictions = detection_model.predict(input_tensor, verbose=0)
        return predictions[0]

    except Exception as e:
        print(f"Inference error: {e}")
        return None

def process_frame(frame, camera_id):
    """Process a single frame and detect cheating behavior using classification."""
    if frame is None or detection_model is None:
        return frame, []

    predictions = run_inference(frame)

    if predictions is None:
        return frame, []

    height, width = frame.shape[:2]
    alerts = []

    predicted_index = np.argmax(predictions)
    confidence = float(predictions[predicted_index])
    predicted_class = class_names[predicted_index]  # Use class_names loaded earlier

    # --- Drawing and Alert Logic ---
    color, text_color = (0, 0, 0), (255, 255, 255)  # Default colors
    if predicted_class == 'cheating':
        color = (0, 0, 255)
        text_color = (255, 255, 255)
    elif predicted_class == 'good':
        color = (0, 200, 0)
    else:  # normal
        color = (255, 165, 0)

    cv2.rectangle(frame, (0, 0), (width, height), color, 4)
    label = f'Pred: {predicted_class} ({confidence:.2f})'
    cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 4, cv2.LINE_AA)
    cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, text_color, 2, cv2.LINE_AA)

    if predicted_class == 'cheating' and confidence >= Config.CONFIDENCE_THRESHOLD:
        alert_data = {
            'student_id': f'CAM_{camera_id}',
            'behavior': 'Cheating Detected (Whole Frame)',
            'confidence': confidence,
            'timestamp': datetime.utcnow().isoformat(),
            'camera_id': camera_id,
            'bbox': {
                'x': 0, 'y': 0, 'w': 0, 'h': 0
            }
        }
        alerts.append(alert_data)

    return frame, alerts

def process_camera_stream(camera_id, app):
    """Continuously process frames from a camera"""
    camera = camera_streams.get(camera_id)
    if not camera:
        print(f"Camera {camera_id} not found.")
        return

    while processing_active:
        frame = camera.get_frame()

        if frame is not None:
            processed_frame, alerts = process_frame(frame, camera_id)

            with frame_lock:
                latest_frames[camera_id] = processed_frame

            for alert in alerts:
                # Need app context for SQLAlchemy operations in a thread
                with app.app_context():
                    incident = Incident(
                        student_id=alert['student_id'],
                        behavior=alert['behavior'],
                        confidence=alert['confidence'],
                        camera_id=alert['camera_id'],
                        bbox_x=alert['bbox']['x'],
                        bbox_y=alert['bbox']['y'],
                        bbox_w=alert['bbox']['w'],
                        bbox_h=alert['bbox']['h']
                    )
                    db.session.add(incident)
                    db.session.commit()

                    socketio.emit('new_alert', incident.to_dict())  # Send the full DB object
                    alert_queue.append(incident.to_dict())

        time.sleep(0.1)

def generate_frames(camera_id):
    """Generate video frames for streaming"""
    while True:
        with frame_lock:
            frame = latest_frames.get(camera_id)

        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        time.sleep(0.03)

# Load the model and label map when the script starts
load_detection_model()
load_label_map()
