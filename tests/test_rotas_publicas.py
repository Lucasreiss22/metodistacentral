"""Rotas públicas com SQLite e com Brevo/Bíblia simulados."""

import json
from datetime import datetime, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import Campanha, Congregado, Evento, FeriadoLocal, Subsede
from app.services.biblia import limpar_cache
from app.services.brevo import ResultadoEnvio


class ConfigRotas:
    SECRET_KEY = "apenas-para-teste"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    BREVO_API_KEY = "chave-de-teste"
    EMAIL_REMETENTE = "igreja@exemplo.com"
    NOME_REMETENTE = "Igreja Metodista Central"
    URL_PUBLICA = "https://metodistacentral.onrender.com"


@pytest.fixture
def enviados():
    return []


@pytest.fixture
def app(enviados):
    aplicacao = create_app(ConfigRotas)
    aplicacao.config["CLIENTE_BREVO"] = lambda corpo: enviados.append(corpo) or ResultadoEnvio(True)
    aplicacao.config["CLIENTE_BIBLIA"] = lambda url: json.dumps(
        {"verses": [{"verse": 1, "text": "No princípio Deus criou"}]}
    )
    with aplicacao.app_context():
        db.create_all()
        limpar_cache()
        yield aplicacao
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        limpar_cache()


@pytest.fixture
def cliente(app):
    return app.test_client()


def _sede():
    sede = Subsede(nome="Igreja Metodista Central", cidade="Teresópolis", uf="RJ", eh_sede=True)
    db.session.add(sede)
    db.session.commit()
    return sede


def test_pagina_inicial_responde(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert "Seja um congregado" in resposta.get_data(as_text=True)
    assert "Bíblia online" in resposta.get_data(as_text=True)


def test_cadastro_grava_e_chama_o_brevo(cliente, app, enviados):
    with app.app_context():
        sede = _sede()
        sede_id = sede.id
    resposta = cliente.post(
        "/congregado",
        data={
            "nome": "Ana Silva",
            "email": "Ana@Igreja.com",
            "whatsapp": "(21) 99999-8888",
            "subsede_id": sede_id,
            "consentimento": "y",
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Cadastro salvo" in resposta.get_data(as_text=True)
    with app.app_context():
        pessoa = Congregado.query.one()
        assert pessoa.email == "ana@igreja.com"
        assert pessoa.recebe_noticias is True
        assert pessoa.subsede_id == sede_id
        token = pessoa.token_descadastro
    assert enviados[0]["to"][0]["email"] == "ana@igreja.com"
    assert token in enviados[0]["htmlContent"]
    assert token in enviados[0]["textContent"]


def test_email_repetido_atualiza_e_reativa(cliente, app):
    with app.app_context():
        sede = _sede()
        db.session.add(
            Congregado(
                nome="Ana",
                email="ana@igreja.com",
                whatsapp="21911111111",
                subsede_id=sede.id,
                recebe_noticias=False,
            )
        )
        db.session.commit()
        sede_id = sede.id
    cliente.post(
        "/congregado",
        data={
            "nome": "Ana Maria",
            "email": "ANA@igreja.com",
            "whatsapp": "21922222222",
            "subsede_id": sede_id,
            "consentimento": "y",
        },
    )
    with app.app_context():
        pessoas = Congregado.query.all()
        assert len(pessoas) == 1
        assert pessoas[0].nome == "Ana Maria"
        assert pessoas[0].recebe_noticias is True


def test_sem_consentimento_nao_grava(cliente, app):
    with app.app_context():
        sede = _sede()
        sede_id = sede.id
    cliente.post(
        "/congregado",
        data={
            "nome": "Ana Silva",
            "email": "ana@igreja.com",
            "whatsapp": "21999998888",
            "subsede_id": sede_id,
        },
    )
    with app.app_context():
        assert Congregado.query.count() == 0


def test_honeypot_nao_grava(cliente, app, enviados):
    with app.app_context():
        sede = _sede()
        sede_id = sede.id
    cliente.post(
        "/congregado",
        data={
            "nome": "Robô",
            "email": "robo@igreja.com",
            "whatsapp": "21999998888",
            "subsede_id": sede_id,
            "consentimento": "y",
            "empresa": "spam",
        },
        follow_redirects=True,
    )
    with app.app_context():
        assert Congregado.query.count() == 0
    assert enviados == []


def test_falha_do_brevo_mantem_o_cadastro(cliente, app):
    app.config["CLIENTE_BREVO"] = lambda corpo: ResultadoEnvio(False, "sem rede")
    with app.app_context():
        sede = _sede()
        sede_id = sede.id
    resposta = cliente.post(
        "/congregado",
        data={
            "nome": "Ana Silva",
            "email": "ana@igreja.com",
            "whatsapp": "21999998888",
            "subsede_id": sede_id,
            "consentimento": "y",
        },
        follow_redirects=True,
    )
    assert "não pôde ser enviado" in resposta.get_data(as_text=True)
    with app.app_context():
        assert Congregado.query.count() == 1


def test_descadastro_interrompe_os_comunicados(cliente, app):
    with app.app_context():
        db.session.add(
            Congregado(nome="Ana", email="ana@igreja.com", whatsapp="21999998888", recebe_noticias=True)
        )
        db.session.commit()
        token = Congregado.query.one().token_descadastro
    resposta = cliente.get(f"/descadastrar/{token}")
    assert resposta.status_code == 200
    assert "Descadastro feito" in resposta.get_data(as_text=True)
    with app.app_context():
        assert Congregado.query.one().recebe_noticias is False
    assert cliente.get("/descadastrar/token-inexistente").status_code == 404


def test_calendario_junta_evento_feriado_nacional_e_local(cliente, app):
    with app.app_context():
        db.session.add(FeriadoLocal(nome="São Jorge", dia=23, mes=4, tipo="estadual"))
        db.session.add(
            Evento(
                titulo="Culto de domingo",
                data_evento=datetime(2026, 4, 12, 18, 0, tzinfo=timezone.utc),
                local="Templo",
                status="ativo",
            )
        )
        db.session.commit()
    resposta = cliente.get("/calendario/eventos.json?start=2026-01-01&end=2026-12-31")
    dados = resposta.get_json()
    nomes = {item["title"] for item in dados}
    assert "Culto de domingo" in nomes
    assert "São Jorge" in nomes
    assert "Tiradentes" in nomes
    assert "Sexta-feira Santa" in nomes
    tipos = {item["extendedProps"]["tipo"] for item in dados}
    assert "evento" in tipos
    assert "estadual" in tipos
    assert "feriado_nacional" in tipos
    assert "ponto_facultativo" in tipos


def test_campanha_e_biblia(cliente, app):
    with app.app_context():
        db.session.add(
            Campanha(titulo="Cestas básicas", descricao="Alimentos", meta=200, arrecadado=50, unidade="cestas")
        )
        db.session.commit()
        campanha_id = Campanha.query.one().id
    lista = cliente.get("/campanhas")
    assert "Cestas básicas" in lista.get_data(as_text=True)
    assert "50 cestas" in lista.get_data(as_text=True)
    detalhe = cliente.get(f"/campanhas/{campanha_id}")
    assert detalhe.status_code == 200
    assert cliente.get("/campanhas/999").status_code == 404

    biblia = cliente.get("/biblia/genesis/1")
    texto = biblia.get_data(as_text=True)
    assert biblia.status_code == 200
    assert "No princípio Deus criou" in texto

    app.config["CLIENTE_BIBLIA"] = lambda url: (_ for _ in ()).throw(TimeoutError())
    falha = cliente.get("/biblia/joao/3")
    assert "bibliaonline.com.br" in falha.get_data(as_text=True)
