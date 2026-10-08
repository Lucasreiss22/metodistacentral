"""Leitura das variáveis de ambiente. Valores ficam no .env, nunca aqui."""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

from app.utils import normalizar_database_url, opcoes_do_banco

PASTA_RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(PASTA_RAIZ / ".env")

VARIAVEIS_AMBIENTE = (
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_KEY",
    "BREVO_API_KEY",
    "EMAIL_REMETENTE",
    "NOME_REMETENTE",
    "SECRET_KEY",
    "URL_PUBLICA",
)

# URI inválida de propósito, para o Flask não cair no SQLite em memória
# quando a DATABASE_URL ainda não foi preenchida.
_URI_NAO_CONFIGURADA = "postgresql+psycopg://invalido:invalido@127.0.0.1:1/invalido"


def ler_variavel(nome: str) -> str:
    """Valor da variável, sem espaços nas pontas. Vazio se não existir."""
    return os.environ.get(nome, "").strip()


def variaveis_vazias() -> list[str]:
    """Nomes ainda em branco. Não devolve os valores."""
    return [nome for nome in VARIAVEIS_AMBIENTE if not ler_variavel(nome)]


class Config:
    """Configuração lida do ambiente no momento em que o processo sobe."""

    SECRET_KEY = ler_variavel("SECRET_KEY")
    DATABASE_URL = ler_variavel("DATABASE_URL")
    SQLALCHEMY_DATABASE_URI = normalizar_database_url(DATABASE_URL) or _URI_NAO_CONFIGURADA
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = opcoes_do_banco(SQLALCHEMY_DATABASE_URI)

    SUPABASE_URL = ler_variavel("SUPABASE_URL").rstrip("/")
    SUPABASE_ANON_KEY = ler_variavel("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_KEY = ler_variavel("SUPABASE_SERVICE_KEY")
    BREVO_API_KEY = ler_variavel("BREVO_API_KEY")
    EMAIL_REMETENTE = ler_variavel("EMAIL_REMETENTE")
    NOME_REMETENTE = ler_variavel("NOME_REMETENTE")
    URL_PUBLICA = ler_variavel("URL_PUBLICA").rstrip("/")

    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = URL_PUBLICA.startswith("https://")
