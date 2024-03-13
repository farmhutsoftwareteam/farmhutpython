tools = [
    {
        "type": "function",
        "function": {
            "name": "process_image_with_openai",
            "description": "Process an image and describe its contents, along with handling phone and question",
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
    # Add more functions here as needed
]