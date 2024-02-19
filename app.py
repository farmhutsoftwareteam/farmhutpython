from dotenv import load_dotenv
import logging
import os
from flask import Flask, request, jsonify
from openai import AzureOpenAI
import time
import json
from flask_pymongo import PyMongo

# Configure logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb+srv://raysuncapital:ZGJKTn45yyqH6X1y@cluster0.0jein5m.mongodb.net/FARMHUT"
mongo = PyMongo(app)
load_dotenv()

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-02-15-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

@app.route('/ask-assistant', methods=['POST'])
def ask_assistant():
    logging.info("Received request for /ask-assistant")
    data = request.json
    question = data.get('question')
    phone=data.get('phone')

    if not question or not phone:
        logging.warning("No question provided in request or phone number")
        return jsonify({"error": "No question provided"}), 400

    # Check if the user exists and has an azureThreadId
    user = mongo.db.users.find_one({"phone": phone})
    if user and user.get('azureThreadId'):
        azure_thread_id = user['azureThreadId']
        # Logic to add more messages to the existing thread
        # You would use the azure_thread_id to interact with the Azure API
    else:
        # Logic to create a new thread in Azure and update the user record
        # This is a placeholder for creating a new thread and getting its ID
        new_azure_thread_id = client.beta.threads.create()
        logging.info(new_azure_thread_id)
        if user:
            # Update existing user with the new azureThreadId
            mongo.db.users.update_one(
                {"_id": user['_id']},
                {"$set": {"azureThreadId": new_azure_thread_id.id}}
            )
        else:
            # Create a new user with the azureThreadId
            mongo.db.users.insert_one({
                "phone": phone,
                "azureThreadId": new_azure_thread_id,
                # Add other user fields as necessary
            })
        
        azure_thread_id = new_azure_thread_id
        logging.info(azure_thread_id)
    try:
        # Create an assistant
        logging.info("Creating assistant")
        assistant = client.beta.assistants.create(
            model="munyaradzi",  # Or another model you have access to
            name="Math Assist",
            instructions="You are an AI assistant ",
            tools=[]
        )
        logging.info("Assistant created successfully")
        
    

       
        message = client.beta.threads.messages.create(
            thread_id=azure_thread_id,
            role="user",
            content=question
        )
        logging.info("Message created successfully")

        run = client.beta.threads.runs.create(
            thread_id=azure_thread_id,
            assistant_id=assistant.id
        )
        logging.info("Run created successfully")

        run = client.beta.threads.runs.retrieve(
            thread_id=azure_thread_id,
            run_id=run.id
        )
        logging.info("Run retrieved successfully")

        status = run.status

        while status not in ["completed", "cancelled", "expired", "failed"]:
            time.sleep(5)
            run = client.beta.threads.runs.retrieve(
                thread_id=azure_thread_id,
                run_id=run.id
            )
            status = run.status

            

        messages = client.beta.threads.messages.list(
            thread_id=azure_thread_id
        )

        # Assuming messages.model_dump_json() returns a JSON serializable Python object
        response = messages.model_dump_json(indent=2)
        return jsonify({"response": response})
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/hello')
def hello_world():
    return 'Hello, World!'

if __name__ == '__main__':
    app.run(debug=False)