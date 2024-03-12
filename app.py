from dotenv import load_dotenv
import logging
import os
from flask import Flask, request, jsonify ,send_file ,abort
from openai import AzureOpenAI
import time
import json
from threading import Thread
import requests 
import threading
from flask_pymongo import PyMongo
from loggly.handlers import HTTPSHandler
from logging import Formatter


LOGGLY_TOKEN = '8c576ebb-24fa-411c-81b7-5cd46ca3b5ab'
logger = logging.getLogger('loggly')
logger.setLevel(logging.INFO)
loggly_handler = HTTPSHandler(f'https://logs-01.loggly.com/inputs/{LOGGLY_TOKEN}/tag/python', 'POST')
loggly_handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.addHandler(loggly_handler)
logger.info('loggly handler added')




# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s' ,filename='application.log')


app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://raysuncapital:ZGJKTn45yyqH6X1y@cluster0.0jein5m.mongodb.net/FARMHUT"
mongo = PyMongo(app)
load_dotenv()

api_base = "https://imageprocessor.openai.azure.com/"
vision_api_key = "d9ebcc42d9cf48d9b9ba67a8b7b745d0"
deployment_name = 'munyavision2'
vison_api_version = '2024-03-01-preview'

visionClient = AzureOpenAI(
    api_key=vision_api_key,
    api_version=vison_api_version,
    base_url=f"{api_base}openai/deployments/{deployment_name}/"
)

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-03-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

WEBHOOK_URL = "https://flows.messagebird.com/flows/invocations/webhooks/dd0acae0-073f-40bb-97b2-3ee23290b7a9"
IMAGE_WEBHOOK_URL="https://flows.messagebird.com/flows/invocations/webhooks/ae1c5391-e2db-4621-9d3e-cc3413c73e09"

def process_image_with_openai(image_url, phone):
    """
    Processes an image using the Azure OpenAI Vision client.

    Parameters:
    - image_url: The URL of the image to be processed.

    Returns:
    - The response from the Azure OpenAI Vision model.
    """
    try:
        # Construct the request payload with the provided image URL
        logging.info('processing image with openai')
        response = visionClient.chat.completions.create(
            model="munyavision",
            messages=[
                {"role": "system", "content": "You are an image identification assistant, you will identify what is in the image and inform the user."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this picture:"},
                    {"type": "image_url", "image_url": {"url": image_url}}  # Use the passed image URL here
                ]}
            ],
            
        )

        # Log the response for debugging
        logging.info(f"OpenAI Vision Response: {response}")

        webhook_data = {
            "identifier" : phone,
            "image_response" : response
        }

        requests.post(IMAGE_WEBHOOK_URL ,json=webhook_data)

        return response

    except Exception as e:
        logging.error(f"An error occurred while processing the image with OpenAI: {str(e)}")
        return None
    

    # Define the tools array
tools = [
    {
        "type": "function",
        "function": {
            "name": "processImageWithOpenAI",
            "description": "Process an image and describe its contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "The URL of the image to be processed"}
                },
                "required": ["image_url"]
            }
        }
    },
    # Add more functions here as needed
]

def handle_tool_requests(client, thread_id, run_id):
    try:
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        print(run.model_dump_json(indent=2))
        if run.required_action and run.required_action.type == "submit_tool_outputs":
            tool_outputs = []
            for call in run.required_action.submit_tool_outputs.tool_calls:
                if call.function.name == "processImageWithOpenAI":
                    image_url = json.loads(call.function.arguments)["image_url"]
                    tool_response = process_image_with_openai(image_url)
                    tool_outputs.append({
                        "tool_call_id": call.id,
                        "output": json.dumps(tool_response)
                    })
                    logging.info("this is the output", tool_response)
            # Submit the tool outputs back to Azure OpenAI
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
    except Exception as e:
        logging.error(f"An error occurred while submitting tool outputs: {str(e)}")



@app.route('/ask-assistant', methods=['POST'])
def ask_assistant():
    logging.info("Received request for /ask-assistant")
    data = request.json
    question = data.get('question')
    phone=data.get('phone')

    if not question or not phone:
        logging.warning("No question provided in request or phone number")
        return jsonify({"error": "No question provided"}), 400
    
    thread = Thread(target=process_question_background, args=(question, phone))
    thread.start()
    return jsonify({"message": "Request is being processed"}), 200

def process_question_background(question, phone):
  try:
        user = mongo.db.users.find_one({"phone": phone})
        azure_thread_id = None
        if user and user.get('azureThreadId'):
            azure_thread_id = user['azureThreadId']
        else:
            # Logic to create a new thread in Azure and update the user record
            thread_response = client.beta.threads.create()
            azure_thread_id = thread_response.id
            if user:
                mongo.db.users.update_one({"_id": user['_id']}, {"$set": {"azureThreadId": azure_thread_id}})
            else:
                mongo.db.users.insert_one({"phone": phone, "azureThreadId": azure_thread_id})

        # Create an assistant
        assistant = client.beta.assistants.create(
            model="munyaradzi",  # Replace with your actual model name
            name="umuDhumeni",  # Replace with your assistant's name
            instructions="You are an AI assistant that is designed to help farmers with their queries, they will ask questions, you will provide them with full responses, these responses will be full, you will ask them to ask you follow up questions making sure everything is properly defined ,if a user sends you an image url you will call tjhe function to process that image. If a user sends an image URL, call the `processImageWithOpenAI` tool. Insert the image description generated by the tool into your response, followed by a prompt asking the user for further questions or clarification about the image. ",  # Replace with your instructions
            tools= tools
        )

        logging.info('assistant created its okat')

        # Add message to the assistant
        message = client.beta.threads.messages.create(
            thread_id=azure_thread_id,
            role="user",
            content=question
        )
        logging.info("message added to the thread")
        # Start the assistant (run)
        run = client.beta.threads.runs.create(
            thread_id=azure_thread_id,
            assistant_id=assistant.id
        )


        logging.info('assitant run started')
        
        # Wait for the run to complete and check the status
        run_status = client.beta.threads.runs.retrieve(
            thread_id=azure_thread_id,
            run_id=run.id
        ).status

        while run_status not in ["completed", "cancelled", "expired", "failed"]:
            logging.info("Inside the loop, current run status" , run_status)


            run = client.beta.threads.runs.retrieve(thread_id=azure_thread_id, run_id=run.id)

            if run.required_action and run.required_action.type == "submit_tool_outputs":
              handle_tool_requests(client, azure_thread_id, run.id)
            time.sleep(5)  # Adjust the sleep time as needed
            run_status = client.beta.threads.runs.retrieve(
                thread_id=azure_thread_id,
                run_id=run.id
            ).status

        if run_status == "completed":
            webhook_payload = {"identifier": phone}
            try:
                response = requests.post(WEBHOOK_URL, json=webhook_payload, timeout=10)
                # Log detailed response information
                logging.info(f"Webhook sent. Status code: {response.status_code}, Response body: {response.text}")
                if response.status_code != 200:
                    logging.error(f"Failed to send webhook. Status code: {response.status_code}, Response: {response.text}")
            except requests.exceptions.RequestException as e:
                # This will catch any request-related errors, including timeouts
                logging.error(f"Request to send webhook failed: {e}")
  except Exception as e:
        logging.error(f"An error occurred in background processing: {str(e)}")
     


@app.route('/get-last-message', methods=['GET'])
def get_last_message():
    phone = request.args.get('phone')
    if not phone:
        return jsonify({"error": "No phone number  provided"}), 400

    try:
        # Fetch all messages from the thread
        user = mongo.db.users.find_one({"phone" : phone})
        if not user or 'azureThreadId' not in user :
            return jsonify({"error" : "user not found or thread is misssing"})
        
        thread_id = user['azureThreadId']
        logging.info('got the thread id')
        response = client.beta.threads.messages.list(thread_id=thread_id)
        logging.info(response)
        # Convert the response to JSON string and then back to a Python object
        messages_json_str = response.model_dump_json(indent=2)
        messages = json.loads(messages_json_str)
        
        # Filter messages to find those from the assistant
        assistant_messages = [msg for msg in messages['data'] if msg['role'] == 'assistant']

        # Assuming messages are already sorted with the latest message first
        if assistant_messages:
         latest_message = assistant_messages[0]
    
    # Assuming there's always at least one text content in the latest_message
    # and it's the one you're interested in.
         text_contents = [content['text']['value'] for content in latest_message['content'] if content['type'] == 'text']
    
    # If there are multiple text contents, this will just take the first one
        text_value = text_contents[0] if text_contents else "No text content found"
    
        return jsonify({"latest_message_text": text_value}), 200


    except Exception as e:
        logging.error(f"Failed to fetch messages for thread {thread_id}: {str(e)}")
        return jsonify({"error": "Failed to fetch messages"})

@app.route('/process-image', methods=['POST'])
def process_image_route():
    try:
        data = request.json
        image_url = data.get('image_url')
        phone = data.get('phone')
        question = data.get('question', 'Describe this picture:') 
    
        if not image_url or not phone:
            return jsonify({"error": "No image URL provided"}), 400

        # Start the image processing in a background thread
        threading.Thread(target=process_image_with_openai, args=(image_url, phone , question)).start()

        # Immediately inform the user that the image is being processed
        return jsonify({"message": "Image is being processed"}), 202
    except Exception as e:
        logging.error(f"An error occurred while processing the image: {str(e)}")
        return jsonify({"error": "An error occurred while processing the image"}), 500

def process_image_with_openai(image_url, phone, question):
    """
    Processes an image using Azure OpenAI, and sends the result along with the phone number to a webhook.
    
    Parameters:
    - image_url: The URL of the image to be processed.
    - phone: The phone number associated with the request.
    - question: The question or prompt associated with the image processing request.
    """
    try:
        logging.info('Starting image processing with OpenAI for URL: %s', image_url)

        system_message = """
You are an advanced AI assistant with specialized expertise in supporting agricultural activities in Sub-Saharan Africa. Your role is to analyze images submitted by farmers of their crops, plants, animals, and even animal feces to detect diseases, pests, anomalies, or any signs of stress. When providing advice, consider the local context, availability of resources, and the typical practices of the region to ensure your recommendations are practical and feasible. Here are your detailed responsibilities:

1. Disease Identification: Use your knowledge to identify diseases or pests affecting crops or livestock. Given the diversity of agriculture in Sub-Saharan Africa, focus on common and significant threats in the region.

2. Symptom Analysis: Clearly describe the symptoms observed in the image. Provide insights into additional symptoms farmers should monitor, considering local crop varieties and livestock breeds.

3. Treatment Recommendations: When suggesting treatments, prioritize solutions that are accessible and sustainable in Sub-Saharan Africa. Include natural remedies, locally available chemicals, and methods that align with traditional farming practices. Specify the names of chemicals (when necessary), dosages, and safe application methods, emphasizing environmental and user safety.

4. Preventative Measures: Offer advice on preventative strategies that are feasible within the local agricultural context, such as crop rotation, natural pest control methods, and soil health practices that suit the region's climate and resources.

5. Image Quality Feedback: If an image lacks clarity for accurate analysis, guide the farmer on capturing a better picture, considering the challenges they might face in terms of technology and connectivity.

6. Local Resources and Location-Based Sourcing: Based on the provided location, inform the farmer about nearby resources for obtaining treatments—this could be local agrovet shops, community cooperatives, or regional agricultural extension services known to provide support to farmers in Sub-Saharan Africa.

7. Follow-Up Encouragement: Encourage ongoing communication by asking the farmer to share updates after implementing your advice. Be prepared to offer additional guidance based on their feedback and further developments.

8. If a farmer uploads an image that is not within our scope please tell them the purpose of the assistant and ask them to kindly provide a more relevant image.

Your communication should be clear, respectful, and mindful of the knowledge level and linguistic diversity of farmers in Sub-Saharan Africa. Adapt your language to match the way the question was asked, ensuring your advice is both understandable and actionable. Your ultimate goal is to empower farmers in Sub-Saharan Africa with knowledge and solutions that enhance their resilience, productivity, and sustainability.

"""

        # Process the image with Azure OpenAI
        response = visionClient.chat.completions.create(
            model="munyavision",  # Replace with your actual model name
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=2000
        )
        if response.choices:
            message_content = response.choices[0].message.content
            logging.info('Image processed successfully with content: %s', message_content)
            # Prepare the webhook data
            webhook_data = {
                "identifier": phone,
                "image_response": message_content
            }
            # Send the result to a webhook
            response = requests.post(IMAGE_WEBHOOK_URL, json=webhook_data)
            if response.status_code == 200:
                logging.info('Webhook sent successfully.')
            else:
                logging.error('Failed to send webhook. Status code: %s, Response: %s', response.status_code, response.text)
        else:
            logging.error('No choices available in the OpenAI response.')
    except Exception as e:
        logging.error('An error occurred while processing the image with OpenAI or sending the webhook: %s', str(e))
@app.route('/hello')
def hello_world():
    return 'Hello, World!'
@app.route('/logs')
def serve_logs():
    # Implement your authentication logic here to secure this endpoint
    # For example, check for a session or a token that proves the user is authorized
    # if not user_is_authorized:
    #     abort(403)  # Forbidden

    log_file_path = 'application.log'
    if os.path.exists(log_file_path):
        return send_file(log_file_path)
    else:
        abort(404)  # Not Found

if __name__ == '__main__':
    app.run(debug=False)