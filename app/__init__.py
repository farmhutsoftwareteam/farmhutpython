from flask import Flask
from flask_pymongo import PyMongo
from .config import Config



def create_app():
    # Configure logging as per Config
    
    
    app = Flask(__name__)
    # Load configuration from `config.py`
    app.config.from_object(Config)
    
    # Initialize MongoDB
    mongo = PyMongo(app)
    app.mongo = mongo
    
    # Import and register blueprints from `routes.py`
    from .routes import main as main_routes
    app.register_blueprint(main_routes)
    
    return app
