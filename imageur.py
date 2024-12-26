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
    """Converts a PNG image to JPG format and returns the new file path."""
    img = Image.open(image_path)
    # Handle transparency by converting to RGB
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    # Create new path with .jpg extension
    new_path = os.path.splitext(image_path)[0] + '.jpg'
    img.save(new_path, 'JPEG')
    return new_path


@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        data = request.get_json()
        image_url = data.get('image_url')

        if not image_url:
            return jsonify({"error": "No image URL provided"}), 400

        # Download image
        response = requests.get(image_url, stream=True)
        if response.status_code != 200:
            return jsonify({"error": "Failed to download image"}), 400

        parsed_url = urlparse(image_url)
        filename = secure_filename(os.path.basename(parsed_url.path))
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # Save image
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)

        # Check if PNG and convert to JPG
        if filename.lower().endswith('.png'):
            converted_path = convert_png_to_jpg(file_path)
            final_filename = os.path.basename(converted_path)
            os.remove(file_path)  # Remove PNG
        else:
            final_filename = unique_filename
            converted_path = file_path

        # Record metadata
        metadata[final_filename] = time.time()

        # Return link
        image_link = request.url_root + 'images/' + final_filename
        return jsonify({"image_link": image_link})

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "details": traceback.format_exc()}), 500



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
