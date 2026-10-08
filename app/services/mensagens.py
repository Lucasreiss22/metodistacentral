"""Textos de e-mail. O HTML completo fica em templates/emails."""

from markupsafe import escape

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


def html_comunicado(nome: str, mensagem: str, link: str) -> str:
    """HTML de um comunicado. O texto da igreja entra escapado, com o descadastro."""
    saudacao = escape(primeiro_nome(nome) or "olá")
    corpo = "<br>".join(escape(mensagem or "").splitlines())
    endereco = escape(link)
    return (
        f"<p>{saudacao},</p>"
        f"<p>{corpo}</p>"
        f'<p><a href="{endereco}">Não quero mais receber esses e-mails</a></p>'
    )


def texto_comunicado(nome: str, mensagem: str, link: str) -> str:
    """Versão em texto puro do comunicado, com o link de descadastro."""
    saudacao = primeiro_nome(nome) or "olá"
    return f"{saudacao},\n\n{mensagem or ''}\n\nSe não quiser mais esses e-mails, use este link: {link}\n"


def montar_comunicados(pessoas, url_publica: str, mensagem: str) -> list[dict]:
    """Uma versão por pessoa, cada uma com o próprio link de descadastro."""
    lista = []
    for pessoa in pessoas:
        link = link_de_descadastro(url_publica, pessoa.token_descadastro)
        lista.append(
            {
                "email": pessoa.email,
                "nome": pessoa.nome,
                "html": html_comunicado(pessoa.nome, mensagem, link),
                "texto": texto_comunicado(pessoa.nome, mensagem, link),
            }
        )
    return lista
