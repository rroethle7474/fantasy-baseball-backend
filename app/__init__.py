from flask import Flask
from flask_cors import CORS
from app.api.routes import NumpyEncoder

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=app.instance_path + '/fantasy_baseball.sqlite',
    )
    
    # Set custom JSON encoder to handle NumPy types
    app.json_encoder = NumpyEncoder
    
    # Enable CORS for frontend
    CORS(app)
    
    # Initialize database connection and register CLI commands
    from app.database import db
    db.init_app(app)
    
    # Register migration command
    from app.database import migrate
    migrate.init_app(app)
    
    # Register blueprints
    from app.api import routes
    app.register_blueprint(routes.bp)
    
    return app