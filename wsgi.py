"""Ponto de entrada do gunicorn (Procfile: web: gunicorn wsgi:app)."""

from app import create_app

app = create_app()
