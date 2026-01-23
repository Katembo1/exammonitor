from threading import Thread
from flask import Blueprint, render_template, Response, jsonify, request, send_file
from app.models import Incident
from app import db
from app.video_processing import CameraStream, generate_frames, process_camera_stream, process_frame
from datetime import datetime
import logging
from app.video_processing import camera_streams, frame_lock, latest_frames
import cv2
import io
import os

main = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

def list_available_cameras():
    """Return a list of available camera indices."""
    available_cameras = []
    for i in range(10):  # Check the first 10 indices
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
    return available_cameras

@main.route('/api/available_cameras', methods=['GET'])
def available_cameras():
    """Return a list of available camera indices."""
    available_cams = list_available_cameras()
    return jsonify({"cameras": available_cams})

@main.route('/')
def index():
    """Render the main dashboard."""
    return render_template('invig1.html')

@main.route('/video_feed/<int:camera_id>')
def video_feed(camera_id):
    """Video streaming route."""
    logger.info(f"Video feed requested for camera {camera_id}")
    if camera_id not in camera_streams:
        logger.error(f"Camera {camera_id} not found for video feed.")
        return jsonify({'error': 'Camera not found'}), 404
    return Response(generate_frames(camera_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@main.route('/api/alerts')
def get_alerts():
    """Get recent alerts."""
    limit = request.args.get('limit', 50, type=int)
    incidents = Incident.query.order_by(Incident.timestamp.desc()).limit(limit).all()
    return jsonify([inc.to_dict() for inc in incidents])

@main.route('/api/alerts/<int:incident_id>/review', methods=['POST'])
def review_alert(incident_id):
    """Mark an alert as reviewed."""
    incident = Incident.query.get(incident_id)
    if incident:
        incident.reviewed_status = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Incident not found'}), 404

@main.route('/api/stats')
def get_stats():
    """Get system statistics."""
    total_alerts = Incident.query.count()
    cheating_alerts = Incident.query.filter_by(behavior='Cheating Detected').count()
    unreviewed = Incident.query.filter_by(reviewed_status=False).count()

    return jsonify({
        'total_alerts': total_alerts,
        'cheating_alerts': cheating_alerts,
        'unreviewed_alerts': unreviewed,
        'active_cameras': len([c for c in camera_streams.values() if c.running])
    })

@main.route('/api/cameras', methods=['GET', 'POST'])
def manage_cameras():
    """Manage camera streams."""
    try:
        if request.method == 'POST':
            data = request.json
            camera_id = data.get('camera_id')
            location = data.get('location')
            source = data.get('source', 0)

            if camera_id is None:
                return jsonify({'success': False, 'error': 'Camera ID is required'}), 400

            if camera_id in camera_streams:
                return jsonify({'success': False, 'error': f'Camera {camera_id} already exists'}), 400

            logger.info(f"Adding camera {camera_id} with source {source} at location {location}")

            # Try to create and start the camera
            camera = CameraStream(camera_id, source)
            if camera.start():
                camera_streams[camera_id] = camera

                # Start processing thread
                process_thread = Thread(target=process_camera_stream, args=(camera_id,), 
                                        daemon=True, name=f"Camera-{camera_id}-Process")
                process_thread.start()

                logger.info(f"Camera {camera_id} added successfully at {location}")
                return jsonify({
                    'success': True, 
                    'message': f'Camera {camera_id} started successfully',
                    'camera': camera.get_status()
                })
            else:
                logger.error(f"Failed to start camera {camera_id}")
                return jsonify({'success': False, 'error': 'Failed to start camera'}), 500

        # GET request - return camera list
        cameras_info = []
        for cam_id, cam in camera_streams.items():
            cameras_info.append(cam.get_status())

        return jsonify({'cameras': cameras_info})

    except Exception as e:
        logger.exception("An unexpected error occurred while managing cameras.")
        return jsonify({'success': False, 'error': 'An unexpected error occurred'}), 500

@main.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
def remove_camera(camera_id):
    """Remove a camera stream."""
    if camera_id in camera_streams:
        camera = camera_streams[camera_id]
        camera.stop()
        del camera_streams[camera_id]

        # Remove from latest frames
        with frame_lock:
            if camera_id in latest_frames:
                del latest_frames[camera_id]

        logger.info(f"Camera {camera_id} removed")
        return jsonify({'success': True, 'message': f'Camera {camera_id} removed'})

    return jsonify({'success': False, 'error': 'Camera not found'}), 404

@main.route('/api/cameras/<int:camera_id>/status')
def camera_status(camera_id):
    """Get detailed camera status."""
    if camera_id in camera_streams:
        camera = camera_streams[camera_id]
        return jsonify(camera.get_status())

    return jsonify({'error': 'Camera not found'}), 404

@main.route('/api/cameras/<int:camera_id>/frame', methods=['GET'])
def get_camera_frame(camera_id):
    """Serve the latest frame from the specified camera."""
    if camera_id in camera_streams:
        camera = camera_streams[camera_id]
        frame = camera.get_frame()
        if frame is not None:
            # Convert the frame to a format that can be sent (e.g., JPEG)
            _, buffer = cv2.imencode('.jpg', frame)
            return send_file(io.BytesIO(buffer), mimetype='image/jpeg')
        else:
            return jsonify({'success': False, 'error': 'No frame available'}), 404
    return jsonify({'error': 'Camera not found'}), 404

# @main.route('/api/upload_video', methods=['POST'])
# def upload_video():
#     """Handle video upload and process it."""
#     if 'video' not in request.files:
#         return jsonify({'success': False, 'error': 'No video file provided'}), 400

#     video = request.files['video']
#     if video.filename == '':
#         return jsonify({'success': False, 'error': 'No selected file'}), 400

#     # Save the uploaded video
#     upload_folder = 'uploads/'  # Ensure this directory exists
#     os.makedirs(upload_folder, exist_ok=True)
#     video_path = os.path.join(upload_folder, video.filename)

#     try:
#         video.save(video_path)

#         # Process the video to detect activities
#         results = process_uploaded_video(video_path)

#         return jsonify({'success': True, 'results': results})
#     except Exception as e:
#         logger.exception("Error processing video upload")
#         return jsonify({'success': False, 'error': str(e)}), 500

# def process_uploaded_video(video_path):
#     """Process the uploaded video and return results."""
#     # Open the video file
#     cap = cv2.VideoCapture(video_path)
#     alerts = []

#     if not cap.isOpened():
#         raise Exception("Could not open video file.")

#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break  # End of video

#         # Process the frame and detect any activities
#         processed_frame, frame_alerts = process_frame(frame, camera_id=0)  # Assuming a default camera_id
#         alerts.extend(frame_alerts)

#     cap.release()

#     # Return the alerts detected during the video processing
#     return {
#         'processed_alerts': alerts,
#         'message': f"Processed video at {video_path} successfully."
#     }


# =======================================================================
# --- HELPER FUNCTION FOR UPLOADED VIDEO PROCESSING ---
# =======================================================================

def process_uploaded_video(video_path):
    """
    Processes the uploaded video file, frame by frame, using the
    classification model and aggregates all detected alerts.
    """
    
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    alerts = []
    frame_count = 0
    
    if not cap.isOpened():
        raise Exception("Could not open video file.")

    # Process every Nth frame to speed up analysis (e.g., process 1 frame per second at 30fps)
    FRAME_SKIP = 30 

    while True:
        ret, frame = cap.read()
        if not ret:
            break  # End of video
        
        # Apply frame skip logic
        if frame_count % FRAME_SKIP == 0:
            # Process the frame and detect any activities
            # We use a default camera_id (0) for a standalone uploaded file analysis
            processed_frame, frame_alerts = process_frame(frame, camera_id=0)
            
            # The alert data generated by process_frame is already JSON-safe
            alerts.extend(frame_alerts)

        frame_count += 1

    cap.release()

    # The alerts list contains the behavior, confidence, and timestamp for each incident.
    return {
        'processed_alerts': alerts,
        'total_incidents': len(alerts),
        'video_path': video_path,
        'status': "Processed successfully."
    }


# =======================================================================
# --- FLASK ROUTE ---
# =======================================================================

@main.route('/api/upload_video', methods=['POST'])
def upload_video():
    """Handle video upload and process it."""
    
    # 1. Input Validation
    if 'video' not in request.files:
        return jsonify({'success': False, 'error': 'No video file provided'}), 400

    video = request.files['video']
    if video.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'}), 400

    video_path = None
    try:
        # 2. Save the uploaded video
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        video_path = os.path.join(upload_folder, video.filename)
        video.save(video_path)

        # 3. Process the video
        # This will call process_uploaded_video which returns the results dictionary
        results = process_uploaded_video(video_path)

        # 4. Return success response
        # The 'results' dictionary contains the detailed output required by the user
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        # 5. Handle errors
        logger.exception("Error processing video upload")
        
        # Clean up the file if an error occurred after saving
        if video_path and os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception as cleanup_e:
                logger.warning(f"Failed to clean up uploaded file {video_path}: {cleanup_e}")

        return jsonify({'success': False, 'error': str(e)}), 500