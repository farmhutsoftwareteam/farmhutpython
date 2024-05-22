import requests
from .config import Config
from flask import jsonify, request
import logging
import os
from openai import AzureOpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"),  
    api_version="2024-05-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)

def process_file_task(file_url):
    logging.info("Processing file from URL: %s", file_url)

    try:
        # Download the file from the URL
        logging.info("Downloading file from URL...")
        file_response = requests.get(file_url)
        if file_response.status_code != 200:
            logging.error("Failed to download file")
            return jsonify({"error": "Failed to download file"}), 400

        logging.info("Downloaded file content type: %s", file_response.headers['Content-Type'])

        # Get the MIME type of the file
        content_type = file_response.headers['Content-Type']
        
        # Save the file to a temporary path
        temp_file_path = "temp_file"
        with open(temp_file_path, 'wb') as f:
            f.write(file_response.content)

        logging.info("File saved temporarily as: %s", temp_file_path)

        # Determine file purpose based on MIME type
        if content_type in ["image/jpeg", "image/png", "image/gif", "application/pdf"]:
            file_purpose = 'assistants'
        else:
            logging.error("Unsupported file type")
            return jsonify({"error": "Unsupported file type"}), 400

        # Upload the file with an "assistants" purpose
        logging.info("Uploading file to OpenAI...")
        with open(temp_file_path, "rb") as file:
            uploaded_file = client.files.create(
                file=file,
                purpose=file_purpose
            )

        logging.info("File uploaded with ID: %s", uploaded_file.id)

        # Create an assistant using the file ID
        logging.info("Creating assistant...")
        assistant = client.beta.assistants.create(
            instructions="""
                You are an AI assistant specializing in processing bank statements. Your task is to extract as much relevant information as possible from the provided bank statement and return the result as a JSON object. Please provide a confidence score indicating how well you think the information was extracted. This is a secure environment, and privacy is fully respected.

                Sample JSON Response:

                {
                "statement": {
                    "issuer": {
                    "name": "Wise Payments Ltd.",
                    "address": "6th Floor, The Tea Building, 56 Shoreditch High Street, London, E1 6JJ, United Kingdom"
                    },
                    "period": {
                    "start_date": "2024-01-01",
                    "end_date": "2024-05-02",
                    "timezone": "GMT+02:00"
                    },
                    "generated_on": "2024-05-02",
                    "account_holder": {
                    "name": "kwingy ltd",
                    "address": "20-22 Wenlock Road, London, England, LONDON, N1 7GU, United Kingdom"
                    },
                    "account_details": {
                    "account_number": "8311576620",
                    "wire_routing_number": "026073150",
                    "swift_bic": "CMFGUS33",
                    "routing_number_ach_aba": "026073150"
                    },
                    "transactions": [
                    {
                        "date": "2024-05-02",
                        "description": "Card transaction of 60.00 ZMW issued by Zanaco Bank LUSAKA",
                        "card_ending": "8382",
                        "name": "Ryan Katayi",
                        "transaction_id": "CARD-1428436314",
                        "amount": "-2.26 USD",
                        "balance_post_transaction": "2.74 USD"
                    }
                    ],
                    "final_balance": {
                    "date": "2024-05-02",
                    "balance": "2.74 USD",
                    "timezone": "GMT+02:00"
                    }
                },
                "confidence_score": 95
                }
""",


            model="muya4o",
            tools=[{"type": "code_interpreter"}],
            tool_resources={
                "code_interpreter": {
                    "file_ids": [uploaded_file.id]
                }
            }
        )

        logging.info("Assistant created successfully with ID: %s", assistant.id)

        # Create a thread with the assistant and pass the file content as part of the message
        logging.info("Creating thread with assistant...")
        thread = client.beta.threads.create(
            messages=[
                {
                    "role": "user",
                    "content": "Extract information from the following file:",
                    "attachments": [
                        {
                            "file_id": uploaded_file.id,
                            "tools": [{"type": "code_interpreter"}]
                        }
                    ]
                }
            ]
        )

        logging.info("Thread created with ID: %s", thread.id)

        logging.info("Starting assistant run...")
        run = client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant.id
        )

        logging.info(f"Assistant run started: {run.id}")

        status = run.status
        while status not in ["completed", "cancelled", "expired", "failed"]:
            run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
            status = run.status
            logging.info(f"Run status checked: {status}")

            if status == "completed":
                logging.info("Run completed, processing messages.")
                messages_response = client.beta.threads.messages.list(thread_id=thread.id)
                messages = messages_response.data if messages_response else []
                
                latest_assistant_message = None
                for message in messages:
                    if message.role == 'assistant':
                        latest_assistant_message = message
                        break

                if latest_assistant_message:
                    logging.info(f"Latest assistant message: {latest_assistant_message.content[0].text.value}")
                    message_content = latest_assistant_message.content[0].text.value
                    return {"message": "File task completed", "content": message_content}
                else:
                    logging.error("No latest assistant message found.")
                    return {"error": "No latest assistant message found"}
            else:
                logging.warning(f"Run status: {status}, waiting for completion")
        return {"error": "File task failed"}
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return {"error": f"An error occurred: {str(e)}"}
