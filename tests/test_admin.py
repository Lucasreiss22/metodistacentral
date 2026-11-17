"""Painel administrativo com login simulado, sem rede."""

import io

import pytest

from app import create_app
from app.auth import hash_senha, senha_confere
from app.extensions import db
from app.models import Administrador, AdministradorPermissao, Congregado, Evento, SolicitacaoLgpd, Subsede
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


@pytest.fixture
def enviados():
    return []


@pytest.fixture
def app(enviados):
    aplicacao = create_app(ConfigAdmin)
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


def _admin(ativo=True, **extras):
    senha = extras.pop("senha", "correta")
    permissoes = extras.pop("permissoes", ())
    pessoa = Administrador(
        email=extras.pop("email", "pastor@igreja.com"),
        nome=extras.pop("nome", "Pastor"),
        ativo=ativo,
        senha_hash=hash_senha(senha),
        eh_super_admin=extras.pop("eh_super_admin", True),
        ministerio=extras.pop("ministerio", "Administração"),
    )
    db.session.add(pessoa)
    db.session.flush()
    for codigo in permissoes:
        db.session.add(AdministradorPermissao(administrador_id=pessoa.id, codigo=codigo))
    db.session.commit()
    return pessoa


def _entrar(cliente):
    return cliente.post(
        "/admin/entrar",
        data={"email": "Pastor@Igreja.com", "senha": "correta"},
        follow_redirects=True,
    )


def test_hash_nao_e_a_senha_em_claro():
    senha_hash = hash_senha("correta")
    assert "correta" not in senha_hash
    assert senha_confere("correta", senha_hash)
    assert not senha_confere("outra", senha_hash)
    assert not senha_confere("correta", "")


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
    assert "não conferem" in estranho.get_data(as_text=True)


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


def test_ministerio_so_ve_o_que_foi_marcado(cliente, app):
    with app.app_context():
        _admin()
        _admin(
            email="midia@igreja.com",
            nome="Mídia",
            eh_super_admin=False,
            ministerio="Ministério de Mídia",
            permissoes=("gerenciar_fotos",),
        )
        _admin(
            email="emp@igreja.com",
            nome="Empreendedores",
            eh_super_admin=False,
            ministerio="Ministério de Empreendedores",
            permissoes=("gerenciar_eventos_empreendedores", "divulgar_empreendedores"),
        )
    cliente.post("/admin/entrar", data={"email": "midia@igreja.com", "senha": "correta"})
    painel = cliente.get("/admin/").get_data(as_text=True)
    assert 'href="/admin/informativos"' in painel
    assert 'href="/admin/campanhas"' not in painel
    assert 'href="/admin/equipe"' not in painel
    aviso = cliente.post(
        "/admin/informativos",
        data={"titulo": "Aviso geral", "tipo": "aviso", "texto": "Culto"},
        follow_redirects=True,
    )
    assert "só altera fotos" in aviso.get_data(as_text=True)
    foto = cliente.post(
        "/admin/informativos",
        data={"titulo": "Altar", "tipo": "foto", "conteudo_url": "https://exemplo.com/altar.jpg", "ativo": "on"},
        follow_redirects=True,
    )
    assert "Informativo salvo." in foto.get_data(as_text=True)
    equipe = cliente.get("/admin/equipe", follow_redirects=True)
    assert "Só o administrador master" in equipe.get_data(as_text=True)

    cliente.post("/admin/sair")
    cliente.post("/admin/entrar", data={"email": "pastor@igreja.com", "senha": "correta"})
    cliente.post(
        "/admin/eventos",
        data={"titulo": "Culto", "data_evento": "2026-12-01T19:00", "status": "ativo", "categoria": "geral"},
    )
    cliente.post("/admin/sair")
    cliente.post("/admin/entrar", data={"email": "emp@igreja.com", "senha": "correta"})
    with app.app_context():
        culto_id = Evento.query.filter_by(titulo="Culto").one().id
    assert cliente.get(f"/admin/eventos/{culto_id}").status_code == 404
    feira = cliente.post(
        "/admin/eventos",
        data={"titulo": "Feira", "data_evento": "2026-12-02T19:00", "status": "ativo", "categoria": "geral"},
        follow_redirects=True,
    )
    assert "Evento salvo." in feira.get_data(as_text=True)
    with app.app_context():
        assert Evento.query.filter_by(titulo="Feira").one().categoria == "empreendedores"
    email = cliente.post(
        "/admin/comunicados",
        data={"assunto": "Divulgação", "mensagem": "Feira de empreendedores"},
        follow_redirects=True,
    )
    assert "não envia o e-mail geral" in email.get_data(as_text=True)


def test_editar_congregado_conclui_o_pedido_e_a_remocao_fica_embaixo(cliente, app):
    with app.app_context():
        _admin()
        ativo = Congregado(
            nome="Ana Silva",
            email="ana@igreja.com",
            whatsapp="21999998888",
            whatsapp_e164="5521999998888",
            recebe_noticias=True,
        )
        removido = Congregado(
            nome="Cadastro removido",
            email="removido-2@anonimo.invalid",
            whatsapp="",
            anonimizado=True,
            motivo_exclusao="Mudei de cidade",
        )
        db.session.add_all([ativo, removido])
        db.session.flush()
        db.session.add(
            SolicitacaoLgpd(
                tipo="alteracao",
                congregado_id=ativo.id,
                email_hash="abc",
                whatsapp_hash="def",
                motivo="Corrigir o nome",
                resultado="pendente",
            )
        )
        db.session.commit()
        ativo_id = ativo.id
        removido_id = removido.id
    _entrar(cliente)
    pagina = cliente.get("/admin/congregados").get_data(as_text=True)
    assert "Editar" in pagina
    assert "Remoções feitas" in pagina
    assert "removido-2@anonimo.invalid" in pagina
    assert "Pedido de alteração cadastral" in pagina
    assert "aguardando edição" in pagina
    edicao = cliente.get(f"/admin/congregados/{ativo_id}")
    assert "Editar congregado" in edicao.get_data(as_text=True)
    assert "Corrigir o nome" in edicao.get_data(as_text=True)
    assert cliente.get(f"/admin/congregados/{removido_id}").status_code == 404
    salvo = cliente.post(
        f"/admin/congregados/{ativo_id}",
        data={
            "nome": "Ana Lima",
            "email": "ana@igreja.com",
            "whatsapp": "21999998888",
            "recebe_noticias": "on",
        },
        follow_redirects=True,
    )
    assert "Congregado salvo." in salvo.get_data(as_text=True)
    assert "alteração feita" in salvo.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Congregado, ativo_id).nome == "Ana Lima"
        assert SolicitacaoLgpd.query.filter_by(tipo="alteracao").one().resultado == "concluida"


def test_html_do_comunicado_escapa_o_texto():
    html = html_comunicado("Ana", "<script>alerta</script>", "https://site/descadastrar/abc")
    assert "<script>" not in html
    assert "descadastrar/abc" in html
