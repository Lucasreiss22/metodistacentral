"""Extensões do Flask, criadas aqui para os models importarem sem ciclo."""

from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()
