from flask import Flask
from flask_cors import CORS
from app.database.db import init_db

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=app.instance_path + '/fantasy_baseball.sqlite',
    )
    
    # Enable CORS for frontend
    CORS(app)
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    from app.api import routes
    app.register_blueprint(routes.bp)
    
    return app