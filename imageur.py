from flask import Flask, request, jsonify, send_from_directory
import os
import uuid
import time
from werkzeug.utils import secure_filename
from flask_cors import CORS  # Import CORS

app = Flask(__name__)

# Enable CORS for all routes
CORS(app)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'temp_uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Create the folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Metadata to track file upload times
metadata = {}
EXPIRY_TIME = 60  # Time in seconds (1 minute)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


@app.route('/upload-image', methods=['POST'])
def upload_image():
    try:
        # Check if the post request has the file part
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        if file and allowed_file(file.filename):
            # Make the filename secure and add a unique identifier
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

            # Save the file to the upload folder
            file.save(file_path)

            # Record the upload time for cleanup
            metadata[unique_filename] = time.time()

            # Generate link to access the image
            image_link = request.url_root + 'images/' + unique_filename
            return jsonify({"image_link": image_link})

        else:
            return jsonify({"error": "File type not allowed"}), 400

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
