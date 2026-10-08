"""As tabelas sobem no SQLite e as regras do banco seguram dados inválidos."""

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import Campanha, Congregado, Subsede


class ConfigTeste:
    """Banco só na memória. Não lê o .env e não chama a internet."""

    SECRET_KEY = "apenas-para-teste"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    aplicacao = create_app(ConfigTeste)
    with aplicacao.app_context():
        db.create_all()
        yield aplicacao
        db.session.rollback()
        db.session.remove()
        db.drop_all()


def test_create_all_registra_as_nove_tabelas(app):
    assert set(db.metadata.tables) == {
        "subsedes",
        "congregados",
        "campanhas",
        "eventos",
        "informativos",
        "feriados_locais",
        "configuracoes",
        "administradores",
        "comunicados",
    }


def test_so_uma_subsede_pode_ser_a_sede(app):
    db.session.add(Subsede(nome="Sede", cidade="Teresópolis", uf="RJ", eh_sede=True))
    db.session.commit()
    db.session.add(Subsede(nome="Outra", cidade="Teresópolis", uf="RJ", eh_sede=True))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_email_do_congregado_nao_diferencia_maiusculas(app):
    db.session.add(Congregado(nome="Ana", email="ana@igreja.com", whatsapp="21999999999"))
    db.session.commit()
    db.session.add(Congregado(nome="Ana Maria", email="Ana@igreja.com", whatsapp="21988888888"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_campanha_rejeita_status_desconhecido(app):
    db.session.add(Campanha(titulo="Cestas", status="pausada"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def _config_de_teste(**extras):
    class ConfigDoTeste:
        SECRET_KEY = "apenas-para-teste"
        TESTING = True
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        WTF_CSRF_ENABLED = False
        DATABASE_URL = ""
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_ENGINE_OPTIONS = {}

    for chave, valor in extras.items():
        setattr(ConfigDoTeste, chave, valor)
    return ConfigDoTeste


def test_comando_avisa_url_vazia_sem_tentar_conexao():
    aplicacao = create_app(_config_de_teste())
    resultado = aplicacao.test_cli_runner().invoke(args=["testar-conexao"])
    assert resultado.exit_code == 1
    assert "DATABASE_URL está vazia" in resultado.output


def test_comando_nao_mostra_a_senha_quando_a_conexao_falha():
    # Valor fictício, só para provar que a mensagem de erro não o repete.
    senha_falsa = "senha-ficticia-do-teste"
    url = f"postgresql://user:{senha_falsa}@127.0.0.1:1/postgres"
    aplicacao = create_app(
        _config_de_teste(
            DATABASE_URL=url,
            SQLALCHEMY_DATABASE_URI=f"postgresql+psycopg://user:{senha_falsa}@127.0.0.1:1/postgres",
            SQLALCHEMY_ENGINE_OPTIONS={
                "pool_pre_ping": True,
                "connect_args": {"connect_timeout": 2},
            },
        )
    )
    resultado = aplicacao.test_cli_runner().invoke(args=["testar-conexao"])
    assert resultado.exit_code == 1
    assert senha_falsa not in resultado.output
    assert "Não foi possível conectar" in resultado.output
