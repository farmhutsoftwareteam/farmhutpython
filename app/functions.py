import requests
from .config import Config
from flask import current_app , jsonify, request, send_file, abort
from threading import Thread
import logging
import json
import time
import os
from openai import AzureOpenAI


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


visionClient = AzureOpenAI(
    api_key=Config.VISION_API_KEY,
    api_version=Config.VISION_API_VERSION,
    base_url=f"{Config.API_BASE}openai/deployments/{Config.DEPLOYMENT_NAME}/"
)
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-03-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)


def fetch_weather(location):
    api_key = Config.WEATHER_API_KEY
    base_url = "https://api.weatherapi.com/v1/current.json"
    complete_url = f"{base_url}?key={api_key}&q={location}&aqi=no"
    
    response = requests.get(complete_url)
    weather_data = response.json()
    
    if response.status_code == 200:
        print(weather_data)
        return weather_data
    
    else:
        return "Could not fetch weather data."


def ask_assistant():
    logging.info("Received request to ask assistant")
    
    data = request.json
    question = data.get('question')
    phone = data.get('phone')

    if not question or not phone:
        logging.warning("No question provided in request or phone number")
        return jsonify({"error": "No question or phone number provided"}), 400

    logging.info(f"Processing question: '{question}' for phone number: {phone}")
    
    # Start the background processing
    app_context = current_app._get_current_object()
    thread = Thread(target=process_question_background, args=(question, phone, app_context))
    thread.start()

    logging.info("Background thread started for processing the question")
    return jsonify({"message": "Request is being processed"}), 200

def hello_world():
    return 'Hello, World! New server Running BiTCHES'
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

def process_image_with_openai(image_url, phone, question):
    """
    Processes an image using Azure OpenAI, and sends the result along with the phone number to a webhook.
    
    Parameters:
    - image_url: The URL of the image to be processed.
    - phone: The phone number associated with the request.
    - question: The question or prompt associated with the image processing request.
    """
    try:
     
        logging.info(f"Calling process_image_with_openai with image_url: {image_url}, phone: {phone}, question: {question}")

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
            
            logging.info('Image processed successfully with content: %s', str(message_content))

            # Prepare the webhook data
            webhook_data = {
                "identifier": phone,
                "image_response": message_content
            }

            # Send the result to a webhook
            response = requests.post(Config.IMAGE_WEBHOOK_URL, json=webhook_data)

            
            if response.status_code == 200:
               logging.info('webhook sent')
            else:
                logging
        else:
            logging.error('No choices available in the OpenAI response.')
    except Exception as e:
        logging.info('An error occurred while processing the image with OpenAI or sending the webhook: %s', str(e))


def process_question_background(question, phone, app):
    # Ensure that we are within the Flask application context
    with app.app_context():
        logging.info("Entering app context")
        mongo = current_app.mongo # Assuming the Azure client is also attached to `current_app`
        client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-03-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

        try:
            user = mongo.db.users.find_one({"phone": phone})
            logging.info(f"User retrieved: {user}")
            azure_thread_id = None

            if user and user.get('azureThreadId'):
                azure_thread_id = user['azureThreadId']
                logging.info(f"Existing Azure thread ID found: {azure_thread_id}")
            else:
                thread_response = client.beta.threads.create()
                azure_thread_id = thread_response.id

                if user:
                    mongo.db.users.update_one({"_id": user['_id']}, {"$set": {"azureThreadId": azure_thread_id}})
                else:
                    mongo.db.users.insert_one({"phone": phone, "azureThreadId": azure_thread_id})
            logging.info("Creating assistant")
            assistant = client.beta.assistants.create(
                model="munyaradzi",
                name="umuDhumeni",
                instructions="""You are a specialized AI agronomist assistant, trained to provide expert guidance to farmers. Your expertise encompasses a vast array of agricultural knowledge, including crop and livestock management, disease diagnosis, and sustainable farming practices.
                                In your interactions with users, offer detailed, evidence-based, and actionable advice to help them enhance agricultural productivity. Respond to their inquiries with clarity and depth, and encourage users to engage in a dialogue for comprehensive understanding.
                                When a user inquires about the weather, leverage this opportunity to give agronomically sound advice. Based on the current and forecasted weather conditions, suggest best farming practices. For example, if rain is expected, advise on soil erosion prevention or the best time to plant or fertilize. If a dry spell is forecasted, offer guidance on water conservation techniques or drought-resistant crops.
                                Each piece of advice should be tailored to the user's specific agricultural context, considering factors like crop type, soil conditions, and local climate patterns. Your goal is to support the user in making informed decisions that lead to better crop yield and farm management.
                                Invite users to share more about their farming situation so you can provide personalized recommendations. Conclude your interactions by encouraging further questions, emphasizing that your purpose is to assist them with knowledge that translates into tangible benefits for their farms and community well-being.
""",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "process_image_with_openai",
                            "description": "Processes an image and provides information.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "image_url": {"type": "string", "description": "The URL of the image to be processed"},
                                    "phone": {"type": "string", "description": "The phone number associated with the request"},
                                    "question": {"type": "string", "description": "The question or prompt associated with the image processing request"}
                                },
                                "required": ["image_url", "phone", "question"]
                            }
                        }
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "fetch_weather",
                            "description": "Fetches current weather based on a user's location.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string", "description": "The location to fetch weather for"}
                                },
                                "required": ["location"]
                            }
                        }
                    },
                     {
                "type": "function",
                "function": {
                    "name": "search_truckers",
                    "description": "Searches for truckers based on location and size.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string", "description": "Location to search for truckers"},
                            "size": {"type": "string", "description": "Minimum truck size required"}
                        },
                        "required": ["location", "size"]
                    }
                }
            },
                    {"type": "code_interpreter"}
                ]
            )

            logging.info('Assistant created successfully.')

            # Creating a message in the thread
            message = client.beta.threads.messages.create(
                thread_id=azure_thread_id,
                role="user",
                content=question
            )

            logging.info("Message added to the thread.")

            # Starting the assistant run
            run = client.beta.threads.runs.create(
                thread_id=azure_thread_id,
                assistant_id=assistant.id
            )

            logging.info(f"Assistant run started: {run.id}")

            # Wait for the run to complete, checking the status periodically
            status = run.status
            while status not in ["completed", "cancelled", "expired", "failed"]:
                time.sleep(5)  # Wait before checking the status again to avoid excessive requests
                run = client.beta.threads.runs.retrieve(thread_id=azure_thread_id, run_id=run.id)
                status = run.status
                logging.info(f"Run status checked: {status}")
                if status == "requires_action":
                    perform_required_actions(client, azure_thread_id, run.id)
                
                if status == "completed":
                    logging.info("Run completed, processing messages.")

                    # Retrieve the list of messages from the thread after completion
                    messages_response = client.beta.threads.messages.list(thread_id=azure_thread_id)
                    messages = messages_response.data if messages_response else []
                    
                    # Find the most recent assistant message
                    latest_assistant_message = None
                    for message in messages:
                        if message.role == 'assistant':
                            latest_assistant_message = message
                            break  # Since we are assuming the first message in the list is the latest one

                    if latest_assistant_message:
                        logging.info(f"Latest assistant message: {latest_assistant_message.content[0].text.value}")
                        message_content = latest_assistant_message.content[0].text.value
                        send_webhook_with_latest_message(client, azure_thread_id, phone, message_content)
            else:
                logging.error("No latest assistant message found.")
                

            # Retrieve the list of messages from the thread after completion
            messages = client.beta.threads.messages.list(thread_id=azure_thread_id)
            logging.info(f"Messages retrieved: {messages}")
            print(latest_assistant_message)
            return latest_assistant_message
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return None
        
     



def perform_required_actions(client, thread_id, run_id):
    logging.info(f"Retrieving run for thread_id={thread_id} and run_id={run_id}")
    
    run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    
    if run.required_action and run.required_action.type == "submit_tool_outputs":
        logging.info(f"Handling required action for thread_id={thread_id} and run_id={run_id}")

        tool_outputs = []
        for call in run.required_action.submit_tool_outputs.tool_calls:
            func_name = call.function.name
            function_arguments = json.loads(call.function.arguments)
            logging.info(f"Function name: {func_name}")
            logging.info(f"Function arguments: {function_arguments}")

            try:
                if func_name == "fetch_weather":
                    location = function_arguments["location"]
                    logging.info(f"Fetching weather for location: {location}")
                    output = fetch_weather(location)
                    tool_outputs.append({"tool_call_id": call.id, "output": json.dumps(output)})

                elif func_name == "search_truckers":
                    location = function_arguments["location"]
                    size = function_arguments["size"]
                    logging.info(f"Searching truckers in location: {location} with size: {size}")
                    output = search_truckers(location, size)
                    tool_outputs.append({"tool_call_id": call.id, "output": json.dumps(output)})

            except Exception as e:
                logging.error(f"Error in {func_name}: {e}")

        if tool_outputs:
            logging.info("Submitting tool outputs.")
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
            logging.info("Tool outputs submitted successfully.")
        else:
            logging.warning("No tool outputs to submit.")
    else:
        logging.info("No required action found.")


def send_webhook_with_latest_message(client, thread_id, phone, message_content):
    # Set up your webhook data and headers
    webhook_data = {
        "response": message_content,
        "identifier": phone
    }
    headers = {'Content-Type': 'application/json'}

    # Send the webhook
    response = requests.post(Config.WEBHOOK_URL, json=webhook_data, headers=headers)
    if response.status_code == 200:
        logging.info("Webhook sent successfully.")
    else:
        logging.error(f"Failed to send webhook, status code: {response.status_code} - Response: {response.text}")



def search_truckers(location, size):
    try:
        with open('data/truckers.json', 'r') as file:
            truckers = json.load(file)

        # Ensure size is a float or 0 if not provided
        try:
            size = float(size) if size else 0
        except ValueError:
            logging.error("Size must be a number.")
            return {"error": "Size must be a number."}

        matched_truckers = []
        for trucker in truckers:
            trucker_size = trucker.get('Size(tonnes)', 0)
            
            try:
                trucker_size = float(trucker_size) if trucker_size else 0
            except ValueError:
                logging.error(f"Invalid size value in truckers data: {trucker_size}")
                continue

            if trucker['Location'].lower() == location.lower() and trucker_size >= size:
                matched_truckers.append(trucker)

        if matched_truckers:
            logging.info(f"Found {len(matched_truckers)} truckers matching criteria in {location} with size {size}.")
            return matched_truckers
        else:
            logging.info(f"No truckers found matching criteria in {location} with size {size}.")
            return {"message": "No truckers found matching your criteria."}
    except Exception as e:
        logging.error(f"An error occurred while searching truckers: {e}")
        return {"error": "An error occurred while processing your request."}
