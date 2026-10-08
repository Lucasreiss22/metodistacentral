"""Painel administrativo com login simulado, sem rede."""

import io

import pytest

from app import create_app
from app.auth import ResultadoLogin, autenticar
from app.extensions import db
from app.models import Administrador, Congregado, Subsede
from app.services.brevo import ResultadoEnvio
from app.services.mensagens import html_comunicado
from app.services.storage import enviar_midia


class ConfigAdmin:
    SECRET_KEY = "apenas-para-teste"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SUPABASE_URL = "https://projeto.supabase.co"
    SUPABASE_ANON_KEY = "chave-publica-de-teste"
    SUPABASE_SERVICE_KEY = ""
    BREVO_API_KEY = "chave-de-teste"
    EMAIL_REMETENTE = "igreja@exemplo.com"
    NOME_REMETENTE = "Igreja Metodista Central"
    URL_PUBLICA = "https://metodistacentral.onrender.com"


def _auth(email, senha):
    if senha == "correta":
        return ResultadoLogin(True, email=email)
    return ResultadoLogin(False, erro="E-mail ou senha não conferem.")


@pytest.fixture
def enviados():
    return []


@pytest.fixture
def app(enviados):
    aplicacao = create_app(ConfigAdmin)
    aplicacao.config["CLIENTE_AUTH"] = _auth
    aplicacao.config["CLIENTE_BREVO"] = lambda corpo: enviados.append(corpo) or ResultadoEnvio(True)
    with aplicacao.app_context():
        db.create_all()
        yield aplicacao
        db.session.rollback()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def cliente(app):
    return app.test_client()


def _admin(ativo=True):
    pessoa = Administrador(email="pastor@igreja.com", nome="Pastor", ativo=ativo)
    db.session.add(pessoa)
    db.session.commit()


def _entrar(cliente):
    return cliente.post(
        "/admin/entrar",
        data={"email": "Pastor@Igreja.com", "senha": "correta"},
        follow_redirects=True,
    )


def test_login_sem_rede_quando_falta_configuracao():
    resultado = autenticar("a@igreja.com", "segredo", "", "", cliente=None)
    assert not resultado.ok
    assert "não está configurado" in resultado.erro


def test_o_site_mostra_o_link_e_o_formulario_de_senha(cliente):
    inicio = cliente.get("/")
    assert inicio.status_code == 200
    assert 'href="/admin/entrar"' in inicio.get_data(as_text=True)
    painel = cliente.get("/admin/")
    assert painel.status_code == 302
    assert painel.headers["Location"].endswith("/admin/entrar")
    pagina = cliente.get("/admin/entrar")
    texto = pagina.get_data(as_text=True)
    assert 'type="password"' in texto
    assert 'name="email"' in texto
    assert "Entrar no painel" in texto
    assert "Ainda não há administrador" in texto


def test_senha_errada_e_email_fora_da_tabela_nao_entram(cliente, app):
    errada = cliente.post("/admin/entrar", data={"email": "pastor@igreja.com", "senha": "outra"})
    assert "não conferem" in errada.get_data(as_text=True)
    assert cliente.get("/admin/").status_code == 302
    with app.app_context():
        _admin()
    estranho = cliente.post("/admin/entrar", data={"email": "outra@igreja.com", "senha": "correta"})
    assert "não está autorizado" in estranho.get_data(as_text=True)


def test_administrador_inativo_nao_entra(cliente, app):
    with app.app_context():
        _admin(ativo=False)
    resposta = cliente.post("/admin/entrar", data={"email": "pastor@igreja.com", "senha": "correta"})
    assert "desativado" in resposta.get_data(as_text=True)


def test_login_abre_o_painel_e_sair_fecha(cliente, app):
    with app.app_context():
        _admin()
    pagina = _entrar(cliente)
    assert "Congregados que recebem notícias" in pagina.get_data(as_text=True)
    cliente.post("/admin/sair")
    assert cliente.get("/admin/").status_code == 302


def test_gif_publicado_aparece_animado_na_home(cliente, app):
    with app.app_context():
        _admin()
    _entrar(cliente)

    def storage(caminho, conteudo, mime):
        assert caminho.endswith(".gif")
        assert mime == "image/gif"
        assert conteudo.startswith(b"GIF89a")
        return ""

    app.config["CLIENTE_STORAGE"] = storage
    resposta = cliente.post(
        "/admin/informativos",
        data={
            "titulo": "Culto animado",
            "tipo": "foto",
            "ativo": "on",
            "arquivo": (io.BytesIO(b"GIF89a"), "culto.gif"),
        },
        follow_redirects=True,
    )
    assert "Informativo salvo." in resposta.get_data(as_text=True)
    home = cliente.get("/").get_data(as_text=True)
    assert "<img" in home
    assert "/storage/v1/object/public/midia/" in home
    assert ".gif" in home


def test_csv_e_email_e_whatsapp(cliente, app, enviados):
    with app.app_context():
        _admin()
        sede = Subsede(nome="Igreja Metodista Central", cidade="Teresópolis", uf="RJ", eh_sede=True)
        db.session.add(sede)
        db.session.flush()
        db.session.add(Congregado(nome="Ana Silva", email="ana@igreja.com", whatsapp="21999998888", subsede_id=sede.id, recebe_noticias=True, token_descadastro="token-ana"))
        db.session.add(Congregado(nome="Bruno", email="bruno@igreja.com", whatsapp="21988887777", subsede_id=sede.id, recebe_noticias=False, token_descadastro="token-bruno"))
        db.session.commit()
    bloqueado = cliente.get("/admin/congregados.csv")
    assert bloqueado.status_code == 302
    _entrar(cliente)
    csv = cliente.get("/admin/congregados.csv")
    texto = csv.get_data(as_text=True)
    assert "ana@igreja.com" in texto
    assert "token-ana" not in texto
    envio = cliente.post(
        "/admin/comunicados",
        data={"assunto": "Culto de domingo", "mensagem": "Venha <script> ao culto"},
        follow_redirects=True,
    )
    assert "E-mail enviado para 1 pessoa" in envio.get_data(as_text=True)
    assert len(enviados) == 1
    corpo = enviados[0]
    assert "messageVersions" in corpo
    assert "to" not in corpo
    html = corpo["messageVersions"][0]["htmlContent"]
    assert "token-ana" in html
    assert "/descadastrar/" in html
    assert "<script>" not in html
    assert "token-bruno" not in html
    conversas = cliente.post(
        "/admin/comunicados/whatsapp",
        data={"mensagem": "Olá, {nome}. Paz!"},
        follow_redirects=True,
    )
    assert "wa.me/5521999998888" in conversas.get_data(as_text=True)


def test_arquivo_executavel_e_recusado():
    resultado = enviar_midia(
        supabase_url="https://projeto.supabase.co",
        service_key="segredo",
        nome_arquivo="virus.exe",
        conteudo=b"abc",
        cliente=lambda *args: "",
    )
    assert not resultado.ok


def test_html_do_comunicado_escapa_o_texto():
    html = html_comunicado("Ana", "<script>alerta</script>", "https://site/descadastrar/abc")
    assert "<script>" not in html
    assert "descadastrar/abc" in html
