# app/main.py
from flask import Flask
from app.controllers.health_controller import bp as health_bp
from app.core.logging import setup_logging

from app.core.db import engine
from app.models.models import Base

def create_app():
    app = Flask(__name__)
    setup_logging()

    # registrar rotas
    app.register_blueprint(health_bp)

    # criar tabelas (atalho sem Alembic)
    Base.metadata.create_all(bind=engine)

    return app

app = create_app()
