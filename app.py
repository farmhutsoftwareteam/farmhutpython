from dotenv import load_dotenv
import logging
import os
from flask import Flask, request, jsonify
from openai import AzureOpenAI
import time
import json
from threading import Thread
import requests 
import threading
from flask_pymongo import PyMongo

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://raysuncapital:ZGJKTn45yyqH6X1y@cluster0.0jein5m.mongodb.net/FARMHUT"
mongo = PyMongo(app)
load_dotenv()

api_base = "https://imageprocessor.openai.azure.com/"
vision_api_key = "d9ebcc42d9cf48d9b9ba67a8b7b745d0"
deployment_name = 'munyavision'
vison_api_version = '2024-02-15-preview'

visionClient = AzureOpenAI(
    api_key=vision_api_key,
    api_version=vison_api_version,
    base_url=f"{api_base}openai/deployments/{deployment_name}/"
)

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

WEBHOOK_URL = "https://flows.messagebird.com/flows/invocations/webhooks/dd0acae0-073f-40bb-97b2-3ee23290b7a9"
IMAGE_WEBHOOK_URL="https://flows.messagebird.com/flows/invocations/webhooks/0570b558-77ea-487e-933b-b1de96356adb"

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
    
        if not image_url or not phone:
            return jsonify({"error": "No image URL provided"}), 400

        # Start the image processing in a background thread
        threading.Thread(target=process_image_with_openai, args=(image_url, phone)).start()

        # Immediately inform the user that the image is being processed
        return jsonify({"message": "Image is being processed"}), 202
    except Exception as e:
        logging.error(f"An error occurred while processing the image: {str(e)}")
        return jsonify({"error": "An error occurred while processing the image"}), 500

def process_image_with_openai(image_url):
    """
    Processes an image using the Azure OpenAI Vision client.

    Parameters:
    - image_url: The URL of the image to be processed.

    Returns:
    - The response from the Azure OpenAI Vision model.
    """
    try:
        logging.info('Processing image with OpenAI')
        response = visionClient.chat.completions.create(
            model="munyavision",  # Replace with your actual model name
            messages=[
                {"role": "system", "content": "You are aan image identifying assistant fully describe the image that you will be sent to, the user will ask a follow up question on the image make sure you full answer in depth.."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Describe this picture:"},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}
            ],
            max_tokens=2000
        )

        if response.choices:
            message_content = response.choices[0].message.content
            # Construct a response dictionary
            response_data = {
                "message_content": message_content
            }
            logging.info(f"OpenAI Vision Response: {response_data}")
            return response_data
        else:
            logging.error("No choices available in the response.")
            return {"error": "No choices available in the response."}

    except Exception as e:
        logging.error(f"An error occurred while processing the image with OpenAI: {str(e)}")
        return {"error": str(e)}
@app.route('/hello')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=False)