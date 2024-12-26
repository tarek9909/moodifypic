from flask import Flask, request, jsonify, send_from_directory
import os
import requests
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
import uuid
import time
from threading import Thread
from flask_cors import CORS  # Import CORS
from PIL import Image  # Import Pillow for image processing

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'temp_uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Metadata to track file upload times
metadata = {}
EXPIRY_TIME = 60  # Time in seconds (1 minute)

def convert_png_to_jpg(image_path):
    """Convert PNG to JPG if needed."""
    if image_path.lower().endswith('.png'):
        img = Image.open(image_path).convert('RGB')  # Handle transparency
        jpg_path = image_path.replace('.png', '.jpg')  # Change extension
        img.save(jpg_path, 'JPEG')  # Save as JPG
        os.remove(image_path)  # Delete original PNG
        return jpg_path
    return image_path


@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        # Parse JSON request
        data = request.get_json()
        image_url = data.get('image_url')

        if not image_url:
            return jsonify({"error": "No image URL provided"}), 400

        # Download the image
        response = requests.get(image_url, stream=True)
        if response.status_code != 200:
            return jsonify({"error": "Failed to download image"}), 400

        # Extract filename and make it secure
        parsed_url = urlparse(image_url)
        filename = secure_filename(os.path.basename(parsed_url.path))

        # Add a unique identifier to avoid conflicts
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # Save image to the temporary folder
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        # Check if the image is PNG and convert it to JPG
        converted_path = convert_png_to_jpg(file_path)
        final_filename = os.path.basename(converted_path)

        # Record the upload time for cleanup
        metadata[final_filename] = time.time()

        # Generate link to access the image
        image_link = request.url_root + 'images/' + final_filename
        return jsonify({"image_link": image_link})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/images/<filename>', methods=['GET'])
def serve_image(filename):
    """Serve the saved image if it exists."""
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    return jsonify({"error": "File not found"}), 404


# Background thread to delete expired files
def cleanup_files():
    while True:
        now = time.time()
        for filename, upload_time in list(metadata.items()):
            # Check if the file has expired
            if now - upload_time > EXPIRY_TIME:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                metadata.pop(filename)
        time.sleep(5)  # Check every 5 seconds


# Start the cleanup thread
Thread(target=cleanup_files, daemon=True).start()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
