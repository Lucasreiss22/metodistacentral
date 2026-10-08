"""Textos de e-mail. O HTML completo fica em templates/emails."""

from app.utils import primeiro_nome


def link_de_descadastro(url_publica: str | None, token: str) -> str:
    """Endereço absoluto do descadastro. Sem URL pública, fica só o caminho."""
    base = (url_publica or "").rstrip("/")
    caminho = f"/descadastrar/{token}"
    return f"{base}{caminho}" if base else caminho


def assunto_boas_vindas(nome_igreja: str) -> str:
    igreja = (nome_igreja or "Igreja Metodista Central").strip()
    return f"Bem-vindo à {igreja}"


def texto_boas_vindas(nome: str, nome_igreja: str, link: str) -> str:
    """Versão em texto puro, para quem não abre HTML."""
    igreja = (nome_igreja or "Igreja Metodista Central").strip()
    saudacao = primeiro_nome(nome) or "olá"
    return (
        f"{saudacao}, seu cadastro na {igreja} foi recebido.\n\n"
        "Você passará a receber os comunicados da igreja.\n\n"
        f"Se não quiser mais esses e-mails, use este link: {link}\n"
    )
