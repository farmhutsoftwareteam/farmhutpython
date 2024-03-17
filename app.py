from app import create_app
import logging

app = create_app()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    # Run the application
    app.run(debug=False)  # Make sure to turn off debug mode in production
