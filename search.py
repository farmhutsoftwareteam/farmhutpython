import json
import logging

def search_truckers(location, size):
    try:
        with open('data/truckers.json', 'r') as file:
            truckers = json.load(file)

        # Case-insensitive search and convert size to float for comparison
        size = float(size) if size else 0
        matched_truckers = [
            trucker for trucker in truckers
            if trucker['Location'].lower() == location.lower() and (not size or float(trucker['Size(tonnes)']) >= size)
        ]

        if matched_truckers:
            logging.info(f"Found {len(matched_truckers)} truckers matching criteria in {location} with size {size}.")
            return matched_truckers
        else:
            logging.info(f"No truckers found matching criteria in {location} with size {size}.")
            return {"message": "No truckers found matching your criteria."}
    except Exception as e:
        logging.error(f"An error occurred while searching truckers: {e}")
        return {"error": "An error occurred while processing your request."}
