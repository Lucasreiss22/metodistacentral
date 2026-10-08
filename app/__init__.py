"""Aplicação Flask da Igreja Metodista Central de Teresópolis."""

import click
from flask import Flask
from sqlalchemy import text

from app.config import Config
from app.extensions import csrf, db
from app.utils import (
    avisos_da_database_url,
    host_da_database_url,
    mensagem_sem_senha,
    problemas_da_database_url,
)

TABELAS_DO_SITE = (
    "subsedes",
    "congregados",
    "campanhas",
    "eventos",
    "informativos",
    "feriados_locais",
    "configuracoes",
    "administradores",
    "comunicados",
)


def create_app(classe_config=None):
    """Monta o app. Os testes passam outra classe no lugar de Config."""
    from secrets import token_hex

    aplicacao = Flask(__name__)
    aplicacao.config.from_object(classe_config or Config)

    if not aplicacao.config.get("SECRET_KEY"):
        # Vale só para este processo, até a SECRET_KEY existir no .env.
        aplicacao.config["SECRET_KEY"] = token_hex(32)

    db.init_app(aplicacao)
    csrf.init_app(aplicacao)

    # Registra os models no SQLAlchemy. Não cria tabelas.
    from app import models  # noqa: F401

    registrar_comandos(aplicacao)
    return aplicacao


def registrar_comandos(aplicacao: Flask) -> None:
    @aplicacao.cli.command("testar-conexao")
    def testar_conexao():
        """Conecta no Supabase e confere se as tabelas do site existem."""
        from app.config import variaveis_vazias

        def avisar_variaveis() -> None:
            vazias = variaveis_vazias()
            if vazias:
                click.echo("Variáveis ainda vazias no .env: " + ", ".join(vazias))
            else:
                click.echo("Variáveis de ambiente: todas preenchidas.")

        url = aplicacao.config.get("DATABASE_URL", "")
        problemas = problemas_da_database_url(url)
        for problema in problemas:
            click.echo(problema)
        if problemas:
            avisar_variaveis()
            raise click.exceptions.Exit(1)

        for aviso in avisos_da_database_url(url):
            click.echo(f"Aviso: {aviso}")

        uri = aplicacao.config.get("SQLALCHEMY_DATABASE_URI", "")
        try:
            with aplicacao.app_context():
                db.session.execute(text("SELECT 1"))
                encontradas = set(
                    db.session.execute(
                        text(
                            """
                            SELECT table_name
                            FROM information_schema.tables
                            WHERE table_schema = 'public'
                              AND table_name IN (
                                'subsedes', 'congregados', 'campanhas', 'eventos',
                                'informativos', 'feriados_locais', 'configuracoes',
                                'administradores', 'comunicados'
                              )
                            """
                        )
                    ).scalars()
                )
        except Exception as erro:
            click.echo("Não foi possível conectar ao Supabase.")
            click.echo(mensagem_sem_senha(str(erro), url, uri))
            avisar_variaveis()
            raise click.exceptions.Exit(1) from None

        host = host_da_database_url(url)
        destino = f" ({host})" if host else ""
        click.echo(f"Conexão com o Supabase: ok{destino}.")

        faltando = [nome for nome in TABELAS_DO_SITE if nome not in encontradas]
        if faltando:
            click.echo(
                "As tabelas do site ainda não estão todas no banco. "
                "Abra o SQL Editor do Supabase e rode supabase/schema.sql."
            )
            click.echo("Faltam: " + ", ".join(faltando))
        else:
            click.echo("Tabelas do site: as 9 foram encontradas.")

        avisar_variaveis()
