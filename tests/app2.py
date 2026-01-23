import os
import io
import base64
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, request, jsonify, render_template_string

# --- Configuration ---
IMAGE_SIZE = 224
MODEL_PATH = 'trained_model.keras'
CLASS_NAMES = ['normal', 'cheating', 'good']
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)

# --- Model Loading ---
MODEL = None

def load_inference_model():
    """Loads the pre-trained Keras model from the .keras file."""
    global MODEL
    if MODEL is None:
        if not os.path.exists(MODEL_PATH):
            print(f"ERROR: Model file not found at {MODEL_PATH}. Run app.py first!")
            return False 

        try:
            MODEL = load_model(MODEL_PATH, compile=False)
            
            expected_shape = (None, IMAGE_SIZE, IMAGE_SIZE, 3)
            actual_shape = tuple(MODEL.input_shape)
            if actual_shape != expected_shape:
                print(f"WARNING: Model input shape mismatch! Expected {expected_shape}, got {actual_shape}.")

            print(f"Successfully loaded model from {MODEL_PATH}")
            return True
        except Exception as e:
            print(f"FATAL ERROR loading model: {e}")
            return False
    return True

def preprocess_image(image_file):
    """
    Takes an uploaded file stream, preprocesses it to match the model's expected input (224x224x3).
    """
    img = Image.open(io.BytesIO(image_file.read())).convert('RGB')
    img = img.resize((IMAGE_SIZE, IMAGE_SIZE))
    img_array = tf.keras.utils.img_to_array(img)
    
    if img_array.shape != (IMAGE_SIZE, IMAGE_SIZE, 3):
        raise ValueError(f"Image array produced incorrect shape after preprocessing: {img_array.shape}. Expected ({IMAGE_SIZE}, {IMAGE_SIZE}, 3).")

    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0
    
    return img_array

def annotate_image(image_bytes, prediction, confidence):
    """
    Annotates the image with prediction results.
    Returns base64 encoded annotated image.
    """
    # Open image
    img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    
    # Create a copy for annotation
    annotated = img.copy()
    draw = ImageDraw.Draw(annotated)
    
    # Get image dimensions
    width, height = annotated.size
    
    # Define colors based on prediction
    colors = {
        'normal': '#f39c12',      # Orange
        'cheating': '#e74c3c',    # Red
        'good': '#2ecc71'         # Green
    }
    
    color = colors.get(prediction, '#3498db')
    
    # Draw border around image
    border_width = max(10, width // 50)
    for i in range(border_width):
        draw.rectangle(
            [(i, i), (width - i - 1, height - i - 1)],
            outline=color,
            width=2
        )
    
    # Prepare text
    text = f"{prediction.upper()}"
    confidence_text = f"Confidence: {confidence}%"
    
    # Try to use a better font, fallback to default
    try:
        # Try different font sizes based on image size
        font_size = max(20, height // 15)
        small_font_size = max(16, height // 20)
        
        # Try to load a truetype font (you might need to adjust the path)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
            small_font = ImageFont.truetype("arial.ttf", small_font_size)
        except:
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Calculate text position and size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    bbox_conf = draw.textbbox((0, 0), confidence_text, font=small_font)
    conf_width = bbox_conf[2] - bbox_conf[0]
    conf_height = bbox_conf[3] - bbox_conf[1]
    
    # Draw background rectangle for text
    padding = 15
    rect_height = text_height + conf_height + padding * 3
    rect_width = max(text_width, conf_width) + padding * 2
    
    # Position at top center
    rect_x = (width - rect_width) // 2
    rect_y = border_width + 10
    
    # Draw semi-transparent background
    draw.rectangle(
        [(rect_x, rect_y), (rect_x + rect_width, rect_y + rect_height)],
        fill=(0, 0, 0, 200)
    )
    
    # Draw text
    text_x = rect_x + (rect_width - text_width) // 2
    text_y = rect_y + padding
    
    draw.text((text_x, text_y), text, fill=color, font=font)
    
    # Draw confidence text
    conf_x = rect_x + (rect_width - conf_width) // 2
    conf_y = text_y + text_height + padding // 2
    
    draw.text((conf_x, conf_y), confidence_text, fill='white', font=small_font)
    
    # Convert to base64
    buffered = io.BytesIO()
    annotated.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return img_str

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Flask Routes ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exam Cheating Detector</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .container { 
            background-color: #ffffff;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            max-width: 800px;
            width: 100%;
        }
        h1 { 
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2em;
            text-align: center;
        }
        .subtitle {
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
            font-size: 0.9em;
        }
        .upload-section {
            text-align: center;
            margin-bottom: 30px;
        }
        input[type="file"] { display: none; }
        .file-label { 
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 30px;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: bold;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .file-label:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        #fileName {
            display: block;
            margin-top: 15px;
            color: #7f8c8d;
            font-size: 0.9em;
        }
        button { 
            background: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
            color: white;
            border: none;
            padding: 15px 40px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: bold;
            margin-top: 20px;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(46, 204, 113, 0.4);
        }
        button:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(46, 204, 113, 0.6);
        }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .image-preview {
            margin: 30px 0;
            text-align: center;
            display: none;
        }
        .image-preview.show {
            display: block;
        }
        .image-container {
            position: relative;
            display: inline-block;
            max-width: 100%;
        }
        .preview-image {
            max-width: 100%;
            height: auto;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .result-section {
            margin-top: 30px;
            padding: 25px;
            border-radius: 15px;
            background-color: #ecf0f1;
            display: none;
        }
        .result-section.show {
            display: block;
            animation: slideIn 0.5s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .result-header {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            text-align: center;
        }
        .result-details {
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
            gap: 20px;
        }
        .result-item {
            flex: 1;
            min-width: 150px;
            text-align: center;
        }
        .result-label {
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        .result-value {
            font-size: 1.5em;
            font-weight: bold;
        }
        .error { 
            color: #e74c3c;
            font-weight: bold;
            text-align: center;
            padding: 20px;
            background-color: #fadbd8;
            border-radius: 10px;
            margin-top: 20px;
        }
        .loading { 
            color: #f39c12;
            text-align: center;
            padding: 20px;
            font-size: 1.1em;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #f39c12;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 20px auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .status-normal { color: #f39c12; }
        .status-cheating { color: #e74c3c; }
        .status-good { color: #2ecc71; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎓 Exam Cheating Detector</h1>
        <p class="subtitle">AI-powered exam monitoring system</p>
        
        <div class="upload-section">
            <form id="uploadForm" onsubmit="event.preventDefault(); predictImage();">
                <input type="file" name="file" id="imageFile" accept="image/*" required>
                <label for="imageFile" class="file-label">📁 Choose Image</label>
                <span id="fileName">No file chosen</span>
                <br>
                <button type="submit" id="analyzeBtn">🔍 Analyze Image</button>
            </form>
        </div>

        <div class="image-preview" id="imagePreview">
            <div class="image-container">
                <img id="previewImg" class="preview-image" alt="Preview">
            </div>
        </div>

        <div class="result-section" id="resultSection">
            <div class="result-header" id="resultHeader">Analysis Complete</div>
            <div class="result-details">
                <div class="result-item">
                    <div class="result-label">Status</div>
                    <div class="result-value" id="predictionValue">-</div>
                </div>
                <div class="result-item">
                    <div class="result-label">Confidence</div>
                    <div class="result-value" id="confidenceValue">-</div>
                </div>
            </div>
        </div>

        <div id="loadingSection" style="display: none;">
            <div class="loading">
                <div class="spinner"></div>
                Processing image...
            </div>
        </div>

        <div id="errorSection" style="display: none;" class="error"></div>
    </div>

    <script>
        const imageFile = document.getElementById('imageFile');
        const fileName = document.getElementById('fileName');
        const imagePreview = document.getElementById('imagePreview');
        const previewImg = document.getElementById('previewImg');
        const resultSection = document.getElementById('resultSection');
        const loadingSection = document.getElementById('loadingSection');
        const errorSection = document.getElementById('errorSection');
        const analyzeBtn = document.getElementById('analyzeBtn');

        imageFile.addEventListener('change', function() {
            if (this.files.length > 0) {
                const file = this.files[0];
                fileName.textContent = file.name;
                
                // Show preview of original image
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewImg.src = e.target.result;
                    imagePreview.classList.add('show');
                    resultSection.classList.remove('show');
                    errorSection.style.display = 'none';
                }
                reader.readAsDataURL(file);
            } else {
                fileName.textContent = 'No file chosen';
                imagePreview.classList.remove('show');
            }
        });

        function predictImage() {
            const form = document.getElementById('uploadForm');
            
            if (imageFile.files.length === 0) {
                showError('Please select an image file.');
                return;
            }

            // Show loading
            loadingSection.style.display = 'block';
            resultSection.classList.remove('show');
            errorSection.style.display = 'none';
            analyzeBtn.disabled = true;

            const formData = new FormData(form);

            fetch('/predict', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                loadingSection.style.display = 'none';
                analyzeBtn.disabled = false;

                if (data.error) {
                    showError('Prediction Error: ' + data.error);
                } else {
                    // Update preview with annotated image
                    previewImg.src = 'data:image/png;base64,' + data.annotated_image;
                    
                    // Show results
                    const predictionValue = document.getElementById('predictionValue');
                    const confidenceValue = document.getElementById('confidenceValue');
                    
                    predictionValue.textContent = data.prediction.toUpperCase();
                    predictionValue.className = 'result-value status-' + data.prediction;
                    confidenceValue.textContent = data.confidence + '%';
                    
                    resultSection.classList.add('show');
                }
            })
            .catch(error => {
                console.error('Fetch error:', error);
                loadingSection.style.display = 'none';
                analyzeBtn.disabled = false;
                showError('Network or Server Error.');
            });
        }

        function showError(message) {
            errorSection.textContent = message;
            errorSection.style.display = 'block';
            resultSection.classList.remove('show');
        }
    </script>
</body>
</html>
"""


@app.route('/', methods=['GET'])
def index():
    """Returns the HTML page for image upload."""
    return render_template_string(HTML_TEMPLATE)

@app.route('/predict', methods=['POST'])
def predict():
    """Handles the image upload and returns the prediction with annotated image."""
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        try:
            # Read the image bytes
            image_bytes = file.read()
            
            # Reset file pointer for preprocessing
            file.seek(0)
            
            # 1. Preprocess image for model
            image_tensor = preprocess_image(file)
            
            # 2. Make prediction
            predictions = MODEL.predict(image_tensor, verbose=0)
            
            # 3. Post-process result
            predicted_class_index = np.argmax(predictions[0])
            predicted_class = CLASS_NAMES[predicted_class_index]
            confidence = float(predictions[0][predicted_class_index] * 100)
            
            # 4. Create annotated image
            annotated_image_base64 = annotate_image(image_bytes, predicted_class, f"{confidence:.2f}")
            
            response = {
                'prediction': predicted_class,
                'confidence': f"{confidence:.2f}",
                'annotated_image': annotated_image_base64
            }
            return jsonify(response)
            
        except ValueError as e:
            return jsonify({'error': f'Image processing failed: {e}'}), 500
        except Exception as e:
            return jsonify({'error': f'An error occurred during prediction: {e}'}), 500
    
    return jsonify({'error': 'File type not allowed'}), 400


if __name__ == '__main__':
    if load_inference_model():
        print("Starting Flask server...")
        print("Open your browser and go to: http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)