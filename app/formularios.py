"""Formulários públicos. As regras também existem como funções puras."""

import re

from flask_wtf import FlaskForm
from wtforms import BooleanField, SelectField, StringField
from wtforms.validators import DataRequired, ValidationError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def erro_nome(nome: str | None) -> str:
    texto = (nome or "").strip()
    if len(texto) < 2:
        return "Informe o nome."
    return ""


def erro_email(email: str | None) -> str:
    texto = (email or "").strip()
    if not _EMAIL.fullmatch(texto):
        return "Informe um e-mail válido."
    return ""


def erro_whatsapp(telefone: str | None) -> str:
    from app.services.whatsapp import numero_whatsapp

    if numero_whatsapp(telefone) is None:
        return "Informe um WhatsApp com DDD."
    return ""


def erro_consentimento(consentiu: bool) -> str:
    if not consentiu:
        return "O consentimento é obrigatório para concluir o cadastro."
    return ""


def _validar_nome(form, field):
    erro = erro_nome(field.data)
    if erro:
        raise ValidationError(erro)


def _validar_email(form, field):
    erro = erro_email(field.data)
    if erro:
        raise ValidationError(erro)


def _validar_whatsapp(form, field):
    erro = erro_whatsapp(field.data)
    if erro:
        raise ValidationError(erro)


class FormularioCongregado(FlaskForm):
    """Cadastro de congregado. O campo empresa é o honeypot contra robôs."""

    nome = StringField("Nome", validators=[_validar_nome])
    email = StringField("E-mail", validators=[_validar_email])
    whatsapp = StringField("WhatsApp", validators=[_validar_whatsapp])
    subsede_id = SelectField(
        "Subsede",
        coerce=int,
        validators=[DataRequired(message="Escolha a subsede.")],
    )
    consentimento = BooleanField(
        "Autorizo o uso dos meus dados para receber comunicados da igreja.",
        validators=[DataRequired(message="O consentimento é obrigatório para concluir o cadastro.")],
    )
    empresa = StringField("Empresa")

    def __init__(self, subsedes, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subsede_id.choices = [(item.id, item.nome) for item in subsedes]
