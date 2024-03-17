import os
from dotenv import load_dotenv
from loggly.handlers import HTTPSHandler


load_dotenv()

class Config:
    WEATHER_API_KEY = '7fb56127555443a5b1193037241203'  # Replace with your actual API key
    MONGO_URI = "mongodb+srv://raysuncapital:ZGJKTn45yyqH6X1y@cluster0.0jein5m.mongodb.net/FARMHUT"
    AZURE_OPENAI_KEY = os.getenv("AZURE_OPENAI_KEY")  # Ensure this is in your .env
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")  # Ensure this is in your .env
    VISION_API_KEY = "d9ebcc42d9cf48d9b9ba67a8b7b745d0"
    API_BASE = "https://imageprocessor.openai.azure.com/"
    DEPLOYMENT_NAME = 'munyavision'
    VISION_API_VERSION = '2024-03-01-preview'
    IMAGE_WEBHOOK_URL = "https://flows.messagebird.com/flows/invocations/webhooks/ae1c5391-e2db-4621-9d3e-cc3413c73e09"
    WEBHOOK_URL = "https://flows.messagebird.com/flows/invocations/webhooks/dd0acae0-073f-40bb-97b2-3ee23290b7a9"

    


   