from flask import Flask
from app.core.logging import setup_logging
from app.controllers.health_controller import bp as health_bp

def create_app():
    setup_logging()
    app = Flask(__name__)
    app.register_blueprint(health_bp)
    return app
