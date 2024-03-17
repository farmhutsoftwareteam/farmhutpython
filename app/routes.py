from flask import Blueprint, request, jsonify
from .functions import ask_assistant,  serve_logs, hello_world ,process_image_with_openai

main = Blueprint('main', __name__)

@main.route('/hello')
def hello():
    return hello_world()

@main.route('/ask-assistant', methods=['POST'])
def ask():
    
    return ask_assistant()


@main.route('/process-image', methods=['POST'])
def process_image_route():
    # Extract data from the incoming request
    data = request.json
    image_url = data.get('image_url')
    phone = data.get('phone')
    question = data.get('question', 'Describe this picture:')

    if not image_url or not phone:
        return jsonify({"error": "Missing image URL or phone number"}), 400
    
    # Call the function to process the image and return the response
    return process_image_with_openai(image_url, phone, question)

@main.route('/logs', methods=['GET'])
def logs():
    return serve_logs()
