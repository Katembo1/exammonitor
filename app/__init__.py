from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
import logging
import os



# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize extensions
db = SQLAlchemy()
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invigilation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

def create_app():

    # Initialize extensions
    db.init_app(app)
    socketio.init_app(app)

    # Import and register blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Initialize the system
    initialize_system()

    return app

def initialize_system():
    """Initialize the invigilation system."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized")
    from app.video_processing import load_detection_model, load_label_map
    
    load_detection_model()
    load_label_map()
    
    logger.info("System initialization complete")

def cleanup():
    """Cleanup resources on shutdown."""
    logger.info("Shutting down cameras...")
    # Implement cleanup logic here

import atexit
atexit.register(cleanup)
#from app import routes, sockets, video_processing,models