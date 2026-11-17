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
    "administrador_permissoes",
    "solicitacoes_lgpd",
    "comunicados",
)

EMAIL_ADMIN_INICIAL = "admin@metodistacentral.local"
SENHA_ADMIN_INICIAL = "Central@2026"


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
    from app.routes.admin import bp as admin_bp
    from app.routes.publico import bp as publico_bp

    aplicacao.register_blueprint(publico_bp)
    aplicacao.register_blueprint(admin_bp)
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
                                'administradores', 'administrador_permissoes',
                                'solicitacoes_lgpd', 'comunicados'
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
            click.echo(f"Tabelas do site: as {len(TABELAS_DO_SITE)} foram encontradas.")

        avisar_variaveis()

    @aplicacao.cli.command("criar-super-admin")
    def criar_super_admin():
        """Cria ou atualiza o administrador master. A senha é gravada como hash."""
        from sqlalchemy import func

        from app.auth import hash_senha, validar_senha_nova
        from app.models import Administrador
        from app.utils import normalizar_email

        email = normalizar_email(aplicacao.config.get("ADMIN_EMAIL") or EMAIL_ADMIN_INICIAL)
        senha_env = aplicacao.config.get("ADMIN_SENHA") or ""
        with aplicacao.app_context():
            admin = Administrador.query.filter(func.lower(Administrador.email) == email).one_or_none()
            if admin is None:
                admin = Administrador(email=email, nome="Administrador", ativo=True, ministerio="Administração")
                db.session.add(admin)
            senha = senha_env
            if admin.senha_hash and not senha_env:
                admin.ativo = True
                admin.eh_super_admin = True
                db.session.commit()
                click.echo(f"Super administrador mantido: {email}")
                click.echo("A senha já existia e não foi trocada. Para trocar, preencha ADMIN_SENHA e rode de novo.")
                return
            if not senha:
                senha = SENHA_ADMIN_INICIAL
            erro = validar_senha_nova(senha)
            if erro:
                click.echo(erro)
                raise click.exceptions.Exit(1)
            admin.nome = admin.nome or "Administrador"
            admin.ministerio = admin.ministerio or "Administração"
            admin.ativo = True
            admin.eh_super_admin = True
            admin.senha_hash = hash_senha(senha)
            db.session.commit()
        click.echo(f"Super administrador pronto: {email}")
        if senha_env:
            click.echo("Senha definida pela variável ADMIN_SENHA.")
        else:
            click.echo("Senha inicial: a documentada em README_ATUALIZACOES.md. Troque no painel depois do primeiro acesso.")

    @aplicacao.cli.command("preparar-congregados")
    def preparar_congregados():
        """Preenche o número internacional e o opt-in dos cadastros antigos."""
        from app.models import Congregado
        from app.services.whatsapp import numero_whatsapp

        with aplicacao.app_context():
            ajustados = 0
            for pessoa in Congregado.query.all():
                mudou = False
                if not pessoa.whatsapp_e164:
                    numero = numero_whatsapp(pessoa.whatsapp)
                    if numero:
                        pessoa.whatsapp_e164 = numero
                        mudou = True
                if (
                    pessoa.recebe_noticias
                    and not pessoa.anonimizado
                    and pessoa.opt_in_status == "pendente"
                    and not pessoa.opt_in_origem
                ):
                    pessoa.opt_in_status = "confirmado"
                    pessoa.opt_in_origem = "cadastro_anterior"
                    pessoa.consentimento_em = pessoa.consentimento_em or pessoa.data_cadastro
                    mudou = True
                if mudou:
                    ajustados += 1
            db.session.commit()
        click.echo(f"Congregados ajustados: {ajustados}.")
