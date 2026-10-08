"""Links wa.me para abrir uma conversa. Não envia mensagem sozinho."""

import re
from urllib.parse import quote

from app.utils import primeiro_nome


def numero_whatsapp(telefone: str | None) -> str | None:
    """DDI 55 mais DDD e número. Devolve None se o telefone não servir."""
    digitos = re.sub(r"\D", "", telefone or "")
    digitos = digitos.lstrip("0")
    if digitos.startswith("55") and len(digitos) in {12, 13}:
        return digitos
    if len(digitos) in {10, 11}:
        return "55" + digitos
    return None


def link_wa_me(telefone: str | None, mensagem: str | None, nome: str | None = "") -> str | None:
    """Link que abre a conversa com o texto pronto. {nome} vira o primeiro nome."""
    numero = numero_whatsapp(telefone)
    if not numero:
        return None
    texto = (mensagem or "").replace("{nome}", primeiro_nome(nome))
    return f"https://wa.me/{numero}?text={quote(texto)}"
