"""Funções puras de texto, URL do banco e datas.

Não acessam a rede nem leem o .env. Os testes cobrem este módulo.
"""

from datetime import datetime, timezone
from secrets import token_urlsafe
from urllib.parse import quote, unquote, urlsplit, urlunsplit

# Marcadores que o painel do Supabase deixa na URI de exemplo.
_MARCADORES_DE_SENHA = (
    "[YOUR-PASSWORD]",
    "[SENHA]",
    "SUA-SENHA",
    "COLOQUE_A_SENHA",
)


def agora_utc() -> datetime:
    """Instante atual com fuso, para gravar no banco."""
    return datetime.now(timezone.utc)


def gerar_token_descadastro() -> str:
    """Token opaco do link de descadastro. Não é uma senha de acesso."""
    return token_urlsafe(32)


def normalizar_email(email: str | None) -> str:
    """E-mail sem espaços e em minúsculas, para o índice único do banco."""
    if not email:
        return ""
    return email.strip().lower()


def normalizar_database_url(url: str | None) -> str:
    """Adapta a URI do Supabase ao driver psycopg do SQLAlchemy.

    O painel entrega postgresql:// ou postgres://. O driver explícito
    evita o SQLAlchemy escolher outro adaptador.
    """
    if not url:
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def problemas_da_database_url(url: str | None) -> list[str]:
    """Erros de preenchimento que impedem a conexão. Não devolve a URL."""
    if not url or not url.strip():
        return ["A variável DATABASE_URL está vazia. Preencha o arquivo .env."]

    texto = url.strip()
    problemas: list[str] = []
    if any(marca in texto for marca in _MARCADORES_DE_SENHA):
        problemas.append(
            "A DATABASE_URL ainda tem o marcador de senha do painel. "
            "Troque pela senha nova do banco."
        )
    if "#" in texto:
        problemas.append(
            "A DATABASE_URL contém #. Esse caractere corta a URL. "
            "Codifique a senha: # vira %23."
        )
    if texto.count("@") > 1:
        problemas.append(
            "A DATABASE_URL tem mais de um @. Se a senha contém @, "
            "codifique como %40."
        )
    return problemas


def avisos_da_database_url(url: str | None) -> list[str]:
    """Avisos quando a URI conecta, mas não é a que o Render consegue usar."""
    if not url or not url.strip():
        return []
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return []

    avisos: list[str] = []
    host = (partes.hostname or "").lower()
    if host.startswith("db.") and host.endswith(".supabase.co"):
        avisos.append(
            "Esta URL é a conexão direta do Supabase. O Render não alcança "
            "esse endereço. Copie a URI do Session pooler (porta 5432)."
        )
    if partes.port == 6543:
        avisos.append(
            "A porta 6543 é o Transaction pooler. Use o Session pooler na porta 5432."
        )
    return avisos


def host_da_database_url(url: str | None) -> str:
    """Host e porta, sem usuário e sem senha, para mostrar no teste."""
    if not url:
        return ""
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return ""
    if not partes.hostname:
        return ""
    if partes.port:
        return f"{partes.hostname}:{partes.port}"
    return partes.hostname


def opcoes_do_banco(url: str | None) -> dict:
    """Opções do SQLAlchemy. Na porta 6543 desliga prepared statements."""
    conecta: dict = {"connect_timeout": 10}
    if url:
        try:
            porta = urlsplit(url.strip()).port
        except ValueError:
            porta = None
        if porta == 6543:
            conecta["prepare_threshold"] = None
    return {"pool_pre_ping": True, "connect_args": conecta}


def ocultar_senha_na_url(url: str | None) -> str:
    """Devolve a URL com a senha trocada por ***, para mensagem de erro."""
    if not url:
        return ""
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return ""
    if not partes.hostname or partes.password is None:
        return url.strip()
    usuario = partes.username or ""
    porta = f":{partes.port}" if partes.port else ""
    netloc = f"{usuario}:***@{partes.hostname}{porta}"
    return urlunsplit((partes.scheme, netloc, partes.path, partes.query, ""))


def variantes_da_senha(senha: str | None) -> list[str]:
    """Forma crua, decodificada e codificada, da mais longa para a mais curta.

    O urllib às vezes devolve a senha ainda com %23. O driver às vezes
    mostra a mesma senha já com #. As duas precisam sair da mensagem.
    """
    if not senha:
        return []
    encontradas: list[str] = []
    for candidata in (senha, unquote(senha)):
        if candidata and candidata not in encontradas:
            encontradas.append(candidata)
        codificada = quote(candidata, safe="") if candidata else ""
        if codificada and codificada not in encontradas:
            encontradas.append(codificada)
    return sorted(encontradas, key=len, reverse=True)


def mensagem_sem_senha(texto: str | None, *urls: str) -> str:
    """Tira senha e URL crua de um texto de erro antes de mostrar na tela."""
    if not texto:
        return ""
    limpo = texto
    for url in urls:
        if not url:
            continue
        limpo = limpo.replace(url, ocultar_senha_na_url(url))
        try:
            senha = urlsplit(url.strip()).password
        except ValueError:
            senha = None
        for variante in variantes_da_senha(senha):
            # Senha muito curta não é apagada solta no texto, para não
            # comer letras de outras palavras. Dentro da URL ela já saiu.
            if len(variante) >= 4:
                limpo = limpo.replace(variante, "***")
    return limpo
