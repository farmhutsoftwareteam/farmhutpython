from flask import Blueprint, request, jsonify
from threading import Thread

from .functions import ask_assistant,  serve_logs, hello_world ,process_image_with_openai ,search_truckers

main = Blueprint('main', __name__)

@main.route('/hello')
def hello():
    return hello_world()

@main.route('/ask-assistant', methods=['POST'])
def ask():
    
    return ask_assistant()

@main.route('/search-trucks', methods=['POST'])
def search_trucks():
    data = request.json
    location = data.get('location')
    size = data.get('size', 5)  # Default size to 0 if not provided

    if not location:
        return jsonify({"error": "Location parameter is required"}), 400

    result = search_truckers(location, size)
    return jsonify(result)


@main.route('/process-image', methods=['POST'])
def process_image_route():
    data = request.json
    image_url = data.get('image_url')
    phone = data.get('phone')
    question = data.get('question', 'Describe this picture:')

    if not image_url or not phone:
        return jsonify({"error": "Missing image URL or phone number"}), 400
    
    # Start the background processing
    Thread(target=process_image_with_openai, args=(image_url, phone, question)).start()
    
    return jsonify({"message": "Image being processed"}), 200

@main.route('/logs', methods=['GET'])
def logs():
    return serve_logs()
