"""Senha do painel. O hash fica na tabela administradores.

A conferência usa PBKDF2-SHA256. A senha em claro não é gravada.
"""

from werkzeug.security import check_password_hash, generate_password_hash

_METODO = "pbkdf2:sha256"
_HASH_DE_MENTIRA = generate_password_hash("comparacao-sem-usuario", method=_METODO)


def hash_senha(senha: str) -> str:
    """Hash para gravar no banco. Não devolve a senha original."""
    return generate_password_hash(senha, method=_METODO)


def senha_confere(senha: str, senha_hash: str | None) -> bool:
    """Confere a senha. Sem hash gravado, ainda gasta o tempo de uma conferência."""
    if not senha_hash:
        check_password_hash(_HASH_DE_MENTIRA, senha or "")
        return False
    return check_password_hash(senha_hash, senha)


def validar_senha_nova(senha: str) -> str:
    if len(senha or "") < 8:
        return "A senha precisa ter pelo menos 8 caracteres."
    return ""
