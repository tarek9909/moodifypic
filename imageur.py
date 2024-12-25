from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # Import CORS
import os
import requests
from urllib.parse import urlparse
from werkzeug.utils import secure_filename
import uuid
import time
from threading import Thread

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'temp_uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create the folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Metadata to track file upload times
metadata = {}
EXPIRY_TIME = 60  # Time in seconds (1 minute)


@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        # Check if the file is present in the request
        if 'image' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        # Secure the filename
        filename = secure_filename(file.filename)

        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

        # Save the file to the server
        file.save(file_path)

        # Record upload time for cleanup
        metadata[unique_filename] = time.time()

        # Generate the URL to access the uploaded image
        image_link = request.url_root + 'images/' + unique_filename
        return jsonify({ image_link})

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
