from flask import Blueprint, request, jsonify, send_file, url_for, current_app, send_from_directory
import requests
import os
from werkzeug.utils import secure_filename
from .functions import ask_assistant, serve_logs, hello_world, process_image_with_openai_simple, search_truckers, convert_image_to_pdf, pdf_to_images_from_url, pdf_to_combined_image_from_url
from .ocr import process_file_task

main = Blueprint('main', __name__)

# Define the upload folders
BASE_FOLDER = 'public'
UPLOAD_FOLDER = os.path.join(BASE_FOLDER, 'uploads')
PDF_FOLDER = os.path.join(BASE_FOLDER, 'pdfs')
IMAGE_FOLDER = os.path.join(BASE_FOLDER, 'images')

# Create the directories if they do not exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)

@main.route('/convert-image-to-pdf', methods=['POST'])
def convert_image_to_pdf_route():
    data = request.json
    image_url = data.get('image_url')
    pdf_filename = data.get('pdf_filename', 'output.pdf')  # Default PDF filename if not provided

    if not image_url:
        return jsonify({"error": "Image URL is required"}), 400

    # Download the image from the URL
    image_response = requests.get(image_url)
    if image_response.status_code != 200:
        return jsonify({"error": "Failed to download image"}), 400

    # Save the image to a temporary file
    image_path = os.path.join(UPLOAD_FOLDER, secure_filename('temp_image.jpg'))
    with open(image_path, 'wb') as f:
        f.write(image_response.content)

    # Define the PDF path
    pdf_path = os.path.join(PDF_FOLDER, secure_filename(pdf_filename))

    # Convert the image to PDF
    pdf_file_path = convert_image_to_pdf(image_path, pdf_path)
    if not pdf_file_path:
        return jsonify({"error": "Failed to convert image to PDF"}), 500

    pdf_url = url_for('main.get_pdf', filename=secure_filename(pdf_filename), _external=True)
    return jsonify({"pdf_url": pdf_url}), 200

@main.route('/pdfs/<filename>', methods=['GET'])
def get_pdf(filename):
    pdf_path = os.path.join(PDF_FOLDER, filename)
    if os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

@main.route('/hello')
def hello():
    return hello_world()

@main.route('/pdf-to-images', methods=['POST'])
def pdf_to_images_route():
    data = request.json
    pdf_url = data.get('pdf_url')
    
    if not pdf_url:
        return jsonify({"error": "PDF URL is required"}), 400

    # Convert PDF to images
    image_files = pdf_to_images_from_url(pdf_url, IMAGE_FOLDER)

    if image_files:
        image_urls = [url_for('main.get_image', filename=os.path.basename(image_file), _external=True) for image_file in image_files]
        return jsonify({"message": "PDF converted to images", "image_urls": image_urls}), 200
    else:
        return jsonify({"error": "Failed to convert PDF to images"}), 500

@main.route('/images/<filename>', methods=['GET'])
def get_image(filename):
    image_path = os.path.join(IMAGE_FOLDER, filename)
    if os.path.exists(image_path):
        return send_from_directory(IMAGE_FOLDER, filename, as_attachment=True)
    else:
        return jsonify({"error": "File not found"}), 404

@main.route('/ask-assistant', methods=['POST'])
def ask():
    return ask_assistant()

@main.route('/search-trucks', methods=['POST'])
def search_trucks():
    data = request.json
    location = data.get('location')
    size = data.get('size', 5)  # Default size to 5 if not provided

    if not location:
        return jsonify({"error": "Location parameter is required"}), 400

    result = search_truckers(location, size)
    return jsonify(result)

@main.route('/process-image-simple', methods=['POST'])
def process_image_simple_route():
    data = request.json
    image_url = data.get('image_url')
    question = data.get('question', 'Define this image, please')

    if not image_url:
        return jsonify({"error": "Image URL is required"}), 400
    
    # Process the image with OpenAI
    result = process_image_with_openai_simple(image_url, question)
    
    return jsonify({"message": "Image processed", "result": result}), 200

@main.route('/pdf-to-combined-image', methods=['POST'])
def pdf_to_combined_image_route():
    data = request.json
    pdf_url = data.get('pdf_url')
    combined_image_filename = data.get('combined_image_filename', 'combined_image.png')  # Default image filename if not provided
    
    if not pdf_url:
        return jsonify({"error": "PDF URL is required"}), 400

    # Convert PDF to combined image
    combined_image_path = pdf_to_combined_image_from_url(pdf_url, IMAGE_FOLDER, combined_image_filename)

    if combined_image_path:
        combined_image_url = url_for('main.get_image', filename=os.path.basename(combined_image_path), _external=True)
        return jsonify({"message": "PDF converted to combined image", "combined_image_url": combined_image_url}), 200
    else:
        return jsonify({"error": "Failed to convert PDF to combined image"}), 500

@main.route('/process-file', methods=['POST'])
def process_file_route():
    data = request.json
    file_url = data.get('file_url')

    if not file_url:
        return jsonify({"error": "File URL is required"}), 400
    
    # Process the file
    result = process_file_task(file_url)
    
    if "error" in result:
        return jsonify(result), 500
    else:
        return jsonify(result), 200

@main.route('/logs', methods=['GET'])
def logs():
    return serve_logs()

def create_app():
    from flask import Flask

    app = Flask(__name__)
    
    # Register the blueprint
    app.register_blueprint(main)
    
    # Serve the static files from the 'public' directory
    app.static_folder = 'public'
    
    return app
