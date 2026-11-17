"""Painel da igreja. A senha é um hash local, conferido em app.auth."""

import csv
import io
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.auth import hash_senha, senha_confere, validar_senha_nova
from app.extensions import db
from app.formularios import erro_email, erro_nome, erro_whatsapp
from app.models import (
    Administrador,
    AdministradorPermissao,
    Campanha,
    Comunicado,
    Congregado,
    Configuracao,
    Evento,
    FeriadoLocal,
    Informativo,
    SolicitacaoLgpd,
    Subsede,
)
from app.permissoes import ACESSO, CATALOGO, CODIGOS, MENU
from app.services.lgpd import aplicar_opt_out
from app.services.whatsapp import numero_whatsapp
from app.services.brevo import enviar_lotes
from app.services.mensagens import montar_comunicados
from app.services.storage import enviar_midia
from app.services.whatsapp import link_wa_me
from app.utils import formatar_data_hora_br, normalizar_email

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.app_template_global("formatar_data_hora_br")
def _quando(momento, dia_inteiro=False):
    return formatar_data_hora_br(momento, dia_inteiro)
_FUSO = ZoneInfo("America/Sao_Paulo")
_TIPOS_INFORMATIVO = ("banner", "foto", "video", "aviso")
_STATUS_EVENTO = ("ativo", "encerrado", "cancelado")
_STATUS_CAMPANHA = ("ativa", "encerrada")
_TIPOS_FERIADO = ("estadual", "municipal", "ponto_facultativo")


def _admin_atual():
    if "admin_resolvido" in g:
        return g.admin_resolvido
    ident = session.get("admin_id")
    admin = db.session.get(Administrador, ident) if ident else None
    if admin is None or not admin.ativo:
        if ident:
            session.clear()
        admin = None
    g.admin_resolvido = admin
    return admin


def _so_fotos() -> bool:
    admin = _admin_atual()
    return bool(admin and not admin.eh_super_admin and not admin.pode("criar_informativos"))


def _so_empreendedores() -> bool:
    admin = _admin_atual()
    return bool(admin and not admin.eh_super_admin and not admin.pode("gerenciar_eventos"))


def _ultimo_super(admin: Administrador) -> bool:
    if not admin.eh_super_admin or not admin.ativo:
        return False
    outros = Administrador.query.filter(
        Administrador.eh_super_admin.is_(True),
        Administrador.ativo.is_(True),
        Administrador.id != admin.id,
    ).count()
    return outros == 0


@bp.app_context_processor
def injetar_acesso():
    admin = _admin_atual()

    def pode(*codigos):
        return bool(admin and admin.pode(*codigos))

    itens = []
    if admin is not None:
        for endpoint, rotulo, codigos, ativos in MENU:
            if codigos is None:
                if admin.eh_super_admin:
                    itens.append({"endpoint": endpoint, "rotulo": rotulo, "ativos": ativos})
            elif admin.pode(*codigos):
                itens.append({"endpoint": endpoint, "rotulo": rotulo, "ativos": ativos})
    return {"admin_atual": admin, "pode": pode, "itens_menu": itens}


@bp.before_request
def exigir_login():
    # g vive no contexto da aplicação. Nos testes ele atravessa pedidos;
    # cada pedido precisa resolver o acesso de novo.
    g.pop("admin_resolvido", None)
    if request.endpoint == "admin.entrar":
        return None
    admin = _admin_atual()
    if admin is None:
        return redirect(url_for("admin.entrar"))
    if request.endpoint in {"admin.equipe", "admin.equipe_item", "admin.excluir_equipe"}:
        if not admin.eh_super_admin:
            flash("Só o administrador master altera a equipe.")
            return redirect(url_for("admin.painel"))
        return None
    codigos = ACESSO.get(request.endpoint)
    if codigos and not admin.pode(*codigos):
        flash("Seu acesso não inclui esta área.")
        return redirect(url_for("admin.painel"))
    return None


def _texto(nome: str) -> str:
    return (request.form.get(nome) or "").strip()


def _marcado(nome: str) -> bool:
    return nome in request.form


def _dia_existe(dia: int, mes: int, ano: int | None) -> bool:
    try:
        date(ano or 2024, mes, dia)
    except (TypeError, ValueError):
        return False
    return True


def _inteiro(nome: str, padrao=None):
    bruto = _texto(nome)
    if not bruto:
        return padrao
    sinal = 1
    if bruto.startswith("-"):
        sinal = -1
        bruto = bruto[1:]
    if not bruto.isdigit():
        return None
    return sinal * int(bruto)


def _decimal(nome: str):
    bruto = _texto(nome) or "0"
    if "," in bruto:
        bruto = bruto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(bruto)
    except InvalidOperation:
        return None
    if valor < 0:
        return None
    return valor.quantize(Decimal("0.01"))


def _data_hora(nome: str):
    bruto = _texto(nome)
    if not bruto:
        return None
    try:
        momento = datetime.fromisoformat(bruto)
    except ValueError:
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=_FUSO)
    return momento.astimezone(timezone.utc)


def _data(nome: str):
    bruto = _texto(nome)
    if not bruto:
        return None
    try:
        return date.fromisoformat(bruto[:10])
    except ValueError:
        return None


def _valor_data_hora(momento) -> str:
    if momento is None:
        return ""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(_FUSO).strftime("%Y-%m-%dT%H:%M")


def _subsedes():
    return Subsede.query.order_by(Subsede.eh_sede.desc(), Subsede.ordem.asc(), Subsede.nome.asc()).all()


def _url_da_midia(campo: str) -> tuple[str, str]:
    arquivo = request.files.get("arquivo")
    if arquivo and arquivo.filename:
        conteudo = arquivo.read()
        resultado = enviar_midia(
            supabase_url=current_app.config.get("SUPABASE_URL", ""),
            service_key=current_app.config.get("SUPABASE_SERVICE_KEY", ""),
            nome_arquivo=arquivo.filename,
            conteudo=conteudo,
            cliente=current_app.config.get("CLIENTE_STORAGE"),
        )
        if not resultado.ok:
            return "", resultado.erro
        return resultado.url, ""
    return _texto(campo), ""


def _gravar():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return False
    return True


@bp.route("/entrar", methods=["GET", "POST"])
def entrar():
    if request.method == "GET" and _admin_atual() is not None:
        return redirect(url_for("admin.painel"))
    erro = ""
    if request.method == "POST":
        email = normalizar_email(_texto("email"))
        senha = request.form.get("senha") or ""
        if not email or not senha:
            erro = "Informe e-mail e senha."
        else:
            admin = Administrador.query.filter(func.lower(Administrador.email) == email).one_or_none()
            confere = senha_confere(senha, admin.senha_hash if admin else "")
            if admin is None or not confere:
                erro = "E-mail ou senha não conferem."
            elif not admin.ativo:
                erro = "Este acesso está desativado."
            else:
                session.clear()
                g.pop("admin_resolvido", None)
                session["admin_id"] = admin.id
                session.permanent = True
                return redirect(url_for("admin.painel"))
    return render_template(
        "admin/entrar.html",
        erro=erro,
        sem_administrador=Administrador.query.count() == 0,
    )


@bp.post("/sair")
def sair():
    session.clear()
    g.pop("admin_resolvido", None)
    return redirect(url_for("admin.entrar"))


@bp.get("/")
def painel():
    return render_template(
        "admin/painel.html",
        totais={
            "subsedes": Subsede.query.count(),
            "congregados": Congregado.query.filter_by(recebe_noticias=True).count(),
            "campanhas": Campanha.query.filter_by(status="ativa").count(),
            "eventos": Evento.query.filter_by(status="ativo").count(),
            "informativos": Informativo.query.filter_by(ativo=True).count(),
        },
        comunicados=Comunicado.query.order_by(Comunicado.enviado_em.desc()).limit(5).all(),
    )


@bp.route("/subsedes", methods=["GET", "POST"])
@bp.route("/subsedes/<int:item_id>", methods=["GET", "POST"])
def subsedes(item_id=None):
    item = db.session.get(Subsede, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if request.method == "POST":
        nome = _texto("nome")
        cidade = _texto("cidade")
        uf = _texto("uf").upper()
        if len(nome) < 2 or not cidade or len(uf) != 2:
            flash("Informe nome, cidade e UF.")
        else:
            imagem, erro = _url_da_midia("imagem_url")
            if erro:
                flash(erro)
            else:
                if _marcado("eh_sede"):
                    consulta = Subsede.query
                    if item is not None:
                        consulta = consulta.filter(Subsede.id != item.id)
                    consulta.update({Subsede.eh_sede: False}, synchronize_session=False)
                if item is None:
                    item = Subsede(nome=nome, cidade=cidade, uf=uf)
                    db.session.add(item)
                item.nome = nome
                item.cidade = cidade
                item.uf = uf
                item.endereco = _texto("endereco")
                item.bairro = _texto("bairro")
                item.cep = _texto("cep")
                item.telefone = _texto("telefone")
                item.whatsapp = _texto("whatsapp")
                item.email = _texto("email")
                item.instagram_url = _texto("instagram_url")
                item.pastor_responsavel = _texto("pastor_responsavel")
                item.horarios_culto = _texto("horarios_culto")
                item.mapa_url = _texto("mapa_url")
                item.imagem_url = imagem
                item.eh_sede = _marcado("eh_sede")
                item.ativa = _marcado("ativa") if request.method == "POST" else True
                item.ordem = _inteiro("ordem", 0) or 0
                if _gravar():
                    flash("Subsede salva.")
                    return redirect(url_for("admin.subsedes"))
                flash("Não foi possível salvar. Só uma subsede pode ser a sede.")
    return render_template("admin/subsedes.html", itens=_subsedes(), item=item)


@bp.post("/subsedes/<int:item_id>/excluir")
def excluir_subsede(item_id):
    item = db.session.get(Subsede, item_id)
    if item is None:
        abort(404)
    db.session.delete(item)
    if _gravar():
        flash("Subsede excluída.")
    else:
        flash("Não foi possível excluir a subsede.")
    return redirect(url_for("admin.subsedes"))


@bp.route("/informativos", methods=["GET", "POST"])
@bp.route("/informativos/<int:item_id>", methods=["GET", "POST"])
def informativos(item_id=None):
    item = db.session.get(Informativo, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if item is not None and _so_fotos() and item.tipo != "foto":
        abort(404)
    tipos = ["foto"] if _so_fotos() else list(_TIPOS_INFORMATIVO)
    consulta = Informativo.query
    if _so_fotos():
        consulta = consulta.filter_by(tipo="foto")
    if request.method == "POST":
        titulo = _texto("titulo")
        tipo = _texto("tipo")
        if _so_fotos() and tipo != "foto":
            flash("Seu acesso só altera fotos.")
        elif len(titulo) < 2 or tipo not in tipos:
            flash("Informe o título e o tipo.")
        else:
            url, erro = _url_da_midia("conteudo_url")
            if erro:
                flash(erro)
            elif tipo != "aviso" and not url:
                flash("Este tipo precisa de um arquivo ou de um endereço.")
            else:
                if item is None:
                    item = Informativo(titulo=titulo, tipo=tipo)
                    db.session.add(item)
                item.titulo = titulo
                item.tipo = tipo
                item.conteudo_url = url
                item.texto = _texto("texto")
                item.link_url = _texto("link_url")
                item.destaque = _marcado("destaque")
                item.ativo = _marcado("ativo")
                item.ordem = _inteiro("ordem", 0) or 0
                if _gravar():
                    flash("Informativo salvo.")
                    return redirect(url_for("admin.informativos"))
                flash("Não foi possível salvar o informativo.")
    return render_template(
        "admin/informativos.html",
        itens=consulta.order_by(Informativo.ordem, Informativo.id).all(),
        item=item,
        tipos=tipos,
    )


@bp.post("/informativos/<int:item_id>/excluir")
def excluir_informativo(item_id):
    item = db.session.get(Informativo, item_id)
    if item is None or (_so_fotos() and item.tipo != "foto"):
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Informativo excluído.")
    return redirect(url_for("admin.informativos"))


@bp.route("/eventos", methods=["GET", "POST"])
@bp.route("/eventos/<int:item_id>", methods=["GET", "POST"])
def eventos(item_id=None):
    item = db.session.get(Evento, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if item is not None and _so_empreendedores() and item.categoria != "empreendedores":
        abort(404)
    consulta = Evento.query
    if _so_empreendedores():
        consulta = consulta.filter_by(categoria="empreendedores")
    if request.method == "POST":
        titulo = _texto("titulo")
        momento = _data_hora("data_evento")
        status = _texto("status") or "ativo"
        if len(titulo) < 2 or momento is None or status not in _STATUS_EVENTO:
            flash("Informe título, data e um status válido.")
        else:
            imagem, erro = _url_da_midia("imagem_url")
            if erro:
                flash(erro)
            else:
                if item is None:
                    item = Evento(titulo=titulo, data_evento=momento)
                    db.session.add(item)
                item.titulo = titulo
                item.descricao = _texto("descricao")
                item.data_evento = momento
                item.data_fim = _data_hora("data_fim")
                item.dia_inteiro = _marcado("dia_inteiro")
                item.local = _texto("local")
                item.subsede_id = _inteiro("subsede_id")
                item.imagem_url = imagem
                item.status = status
                if _so_empreendedores():
                    item.categoria = "empreendedores"
                else:
                    categoria = _texto("categoria")
                    item.categoria = categoria if categoria in {"geral", "empreendedores"} else "geral"
                if _gravar():
                    flash("Evento salvo.")
                    return redirect(url_for("admin.eventos"))
                flash("Não foi possível salvar o evento.")
    return render_template(
        "admin/eventos.html",
        itens=consulta.order_by(Evento.data_evento.desc()).all(),
        item=item,
        subsedes=_subsedes(),
        valor_data_hora=_valor_data_hora,
        so_empreendedores=_so_empreendedores(),
    )


@bp.post("/eventos/<int:item_id>/excluir")
def excluir_evento(item_id):
    item = db.session.get(Evento, item_id)
    if item is None or (_so_empreendedores() and item.categoria != "empreendedores"):
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Evento excluído.")
    return redirect(url_for("admin.eventos"))


@bp.route("/campanhas", methods=["GET", "POST"])
@bp.route("/campanhas/<int:item_id>", methods=["GET", "POST"])
def campanhas(item_id=None):
    item = db.session.get(Campanha, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if request.method == "POST":
        titulo = _texto("titulo")
        meta = _decimal("meta")
        arrecadado = _decimal("arrecadado")
        status = _texto("status") or "ativa"
        if len(titulo) < 2 or meta is None or arrecadado is None or status not in _STATUS_CAMPANHA:
            flash("Informe título, meta e valor arrecadado válidos.")
        else:
            imagem, erro = _url_da_midia("imagem_url")
            if erro:
                flash(erro)
            else:
                if item is None:
                    item = Campanha(titulo=titulo)
                    db.session.add(item)
                item.titulo = titulo
                item.descricao = _texto("descricao")
                item.meta = meta
                item.arrecadado = arrecadado
                item.unidade = _texto("unidade") or "R$"
                item.status = status
                item.imagem_url = imagem
                item.data_inicio = _data("data_inicio")
                item.data_fim = _data("data_fim")
                item.subsede_id = _inteiro("subsede_id")
                item.atualizado_em = datetime.now(timezone.utc)
                if _gravar():
                    flash("Campanha salva.")
                    return redirect(url_for("admin.campanhas"))
                flash("Não foi possível salvar a campanha.")
    return render_template(
        "admin/campanhas.html",
        itens=Campanha.query.order_by(Campanha.criado_em.desc()).all(),
        item=item,
        subsedes=_subsedes(),
    )


@bp.post("/campanhas/<int:item_id>/excluir")
def excluir_campanha(item_id):
    item = db.session.get(Campanha, item_id)
    if item is None:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Campanha excluída.")
    return redirect(url_for("admin.campanhas"))


@bp.route("/feriados", methods=["GET", "POST"])
@bp.route("/feriados/<int:item_id>", methods=["GET", "POST"])
def feriados(item_id=None):
    item = db.session.get(FeriadoLocal, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if request.method == "POST":
        nome = _texto("nome")
        dia = _inteiro("dia")
        mes = _inteiro("mes")
        ano = _inteiro("ano")
        tipo = _texto("tipo")
        if len(nome) < 2 or dia is None or mes is None or tipo not in _TIPOS_FERIADO:
            flash("Informe nome, dia, mês e tipo.")
        elif not _dia_existe(dia, mes, ano):
            flash("Dia ou mês inválido.")
        elif ano is not None and ano < 1900:
            flash("Ano inválido.")
        else:
            if item is None:
                item = FeriadoLocal(nome=nome, dia=dia, mes=mes, tipo=tipo)
                db.session.add(item)
            item.nome = nome
            item.dia = dia
            item.mes = mes
            item.ano = ano
            item.tipo = tipo
            if _gravar():
                flash("Feriado salvo.")
                return redirect(url_for("admin.feriados"))
            flash("Não foi possível salvar o feriado.")
    return render_template(
        "admin/feriados.html",
        itens=FeriadoLocal.query.order_by(FeriadoLocal.mes, FeriadoLocal.dia).all(),
        item=item,
    )


@bp.post("/feriados/<int:item_id>/excluir")
def excluir_feriado(item_id):
    item = db.session.get(FeriadoLocal, item_id)
    if item is None:
        abort(404)
    db.session.delete(item)
    db.session.commit()
    flash("Feriado excluído.")
    return redirect(url_for("admin.feriados"))


def _salvar_congregado(item: Congregado | None):
    editando = item is not None
    nome = _texto("nome")
    email = normalizar_email(_texto("email"))
    whatsapp = _texto("whatsapp")
    erros = [erro for erro in (erro_nome(nome), erro_email(email), erro_whatsapp(whatsapp)) if erro]
    if erros:
        flash(erros[0])
        return None
    if item is None:
        item = Congregado(nome=nome, email=email, whatsapp=whatsapp)
        db.session.add(item)
    item.nome = nome
    item.email = email
    item.whatsapp = whatsapp
    item.whatsapp_e164 = numero_whatsapp(whatsapp) or ""
    item.subsede_id = _inteiro("subsede_id")
    item.recebe_noticias = _marcado("recebe_noticias")
    if item.recebe_noticias:
        if item.opt_in_status != "confirmado":
            item.opt_in_status = "confirmado"
            item.opt_in_origem = item.opt_in_origem or "painel"
            item.consentimento_em = item.consentimento_em or datetime.now(timezone.utc)
        if item.status_envio == "opt_out":
            item.status_envio = "nunca_enviado"
    else:
        aplicar_opt_out(item)
    if editando:
        SolicitacaoLgpd.query.filter_by(
            congregado_id=item.id,
            tipo="alteracao",
            resultado="pendente",
        ).update({"resultado": "concluida"}, synchronize_session=False)
    if not _gravar():
        flash("Já existe um congregado com este e-mail.")
        return None
    return item


def _dados_congregados(item):
    return {
        "itens": Congregado.query.filter_by(anonimizado=False).order_by(Congregado.nome.asc()).all(),
        "removidos": Congregado.query.filter_by(anonimizado=True)
        .order_by(Congregado.excluido_em.desc(), Congregado.id.desc())
        .all(),
        "subsedes": _subsedes(),
        "item": item,
        "pedidos": SolicitacaoLgpd.query.order_by(SolicitacaoLgpd.criado_em.desc()).limit(30).all(),
    }


@bp.route("/congregados", methods=["GET", "POST"])
def congregados():
    if request.method == "POST" and _salvar_congregado(None):
        flash("Congregado salvo.")
        return redirect(url_for("admin.congregados"))
    return render_template("admin/congregados.html", **_dados_congregados(None))


@bp.route("/congregados/<int:item_id>", methods=["GET", "POST"])
def congregado(item_id):
    item = db.session.get(Congregado, item_id)
    if item is None or item.anonimizado:
        abort(404)
    if request.method == "POST" and _salvar_congregado(item):
        flash("Congregado salvo.")
        return redirect(url_for("admin.congregados"))
    return render_template("admin/congregados.html", **_dados_congregados(item))


@bp.get("/congregados.csv")
def congregados_csv():
    buffer = io.StringIO()
    escritor = csv.writer(buffer)
    escritor.writerow(
        [
            "nome",
            "email",
            "whatsapp",
            "whatsapp_e164",
            "subsede",
            "recebe_noticias",
            "opt_in_status",
            "consentimento_em",
            "status_envio",
            "anonimizado",
            "data_cadastro",
        ]
    )
    for pessoa in Congregado.query.order_by(Congregado.nome.asc()).all():
        escritor.writerow(
            [
                pessoa.nome,
                pessoa.email,
                pessoa.whatsapp,
                pessoa.numero_internacional,
                pessoa.subsede.nome if pessoa.subsede else "",
                "sim" if pessoa.recebe_noticias else "não",
                pessoa.opt_in_status,
                formatar_data_hora_br(pessoa.consentimento_em) if pessoa.consentimento_em else "",
                pessoa.status_envio,
                "sim" if pessoa.anonimizado else "não",
                formatar_data_hora_br(pessoa.data_cadastro),
            ]
        )
    return Response(
        "\ufeff" + buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=congregados.csv"},
    )


@bp.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    item = db.session.get(Configuracao, 1)
    if request.method == "POST":
        nome = _texto("nome_igreja")
        if len(nome) < 2:
            flash("Informe o nome da igreja.")
        else:
            if item is None:
                item = Configuracao(id=1, nome_igreja=nome)
                db.session.add(item)
            item.nome_igreja = nome
            item.slogan = _texto("slogan")
            item.instagram_url = _texto("instagram_url")
            item.instagram_usuario = _texto("instagram_usuario")
            item.youtube_url = _texto("youtube_url")
            item.facebook_url = _texto("facebook_url")
            item.whatsapp = _texto("whatsapp")
            item.email_contato = _texto("email_contato")
            item.endereco = _texto("endereco")
            item.sobre = _texto("sobre")
            if _gravar():
                flash("Configurações salvas.")
                return redirect(url_for("admin.configuracoes"))
            flash("Não foi possível salvar as configurações.")
    return render_template("admin/configuracoes.html", item=item)


def _destinatarios():
    consulta = Congregado.query.filter_by(recebe_noticias=True, anonimizado=False)
    subsede_id = _inteiro("subsede_id") if request.method == "POST" else _inteiro_query("subsede_id")
    if subsede_id:
        consulta = consulta.filter_by(subsede_id=subsede_id)
    return consulta.order_by(Congregado.nome.asc()).all(), subsede_id


def _inteiro_query(nome: str):
    bruto = (request.args.get(nome) or "").strip()
    return int(bruto) if bruto.isdigit() else None


@bp.route("/comunicados", methods=["GET", "POST"])
def comunicados():
    pessoas, subsede_id = _destinatarios() if request.method == "POST" else (
        Congregado.query.filter_by(recebe_noticias=True, anonimizado=False).order_by(Congregado.nome.asc()).all(),
        None,
    )
    if request.method == "POST":
        if not _admin_atual().pode("enviar_comunicados"):
            flash("Seu acesso prepara a divulgação, mas não envia o e-mail geral.")
            return redirect(url_for("admin.comunicados"))
        assunto = _texto("assunto")
        mensagem = _texto("mensagem")
        if len(assunto) < 2 or len(mensagem) < 2:
            flash("Informe assunto e mensagem.")
        elif not pessoas:
            flash("Ninguém com notícias ativas para este envio.")
        else:
            versoes = montar_comunicados(pessoas, current_app.config.get("URL_PUBLICA", ""), mensagem)
            resultado = enviar_lotes(
                api_key=current_app.config.get("BREVO_API_KEY", ""),
                remetente=current_app.config.get("EMAIL_REMETENTE", ""),
                nome_remetente=current_app.config.get("NOME_REMETENTE", ""),
                assunto=assunto,
                destinatarios=versoes,
                cliente=current_app.config.get("CLIENTE_BREVO"),
            )
            admin = _admin_atual()
            registro = Comunicado(
                canal="email",
                assunto=assunto,
                mensagem=mensagem,
                subsede_id=subsede_id,
                total_destinatarios=len(pessoas),
                total_enviados=len(pessoas) if resultado.ok else 0,
                erro=None if resultado.ok else resultado.erro,
                enviado_por=admin.email if admin else "",
            )
            db.session.add(registro)
            db.session.commit()
            if resultado.ok:
                flash(f"E-mail enviado para {len(pessoas)} pessoa(s).")
            else:
                flash(resultado.erro)
            return redirect(url_for("admin.comunicados"))
    links = []
    for pessoa in pessoas:
        link = link_wa_me(pessoa.whatsapp, request.args.get("mensagem") or "Olá, {nome}. Paz!", pessoa.nome)
        if link:
            links.append({"nome": pessoa.nome, "link": link})
    return render_template(
        "admin/comunicados.html",
        pessoas=pessoas,
        links=links,
        subsedes=_subsedes(),
        historico=Comunicado.query.order_by(Comunicado.enviado_em.desc()).limit(20).all(),
        elegiveis_meta=[
            pessoa
            for pessoa in Congregado.query.filter_by(
                recebe_noticias=True,
                anonimizado=False,
                opt_in_status="confirmado",
            ).order_by(Congregado.nome.asc())
            if pessoa.numero_internacional
        ],
        meta_configurada=bool(
            current_app.config.get("WHATSAPP_TOKEN") and current_app.config.get("WHATSAPP_PHONE_NUMBER_ID")
        ),
    )


@bp.post("/comunicados/whatsapp")
def preparar_whatsapp():
    mensagem = _texto("mensagem")
    if len(mensagem) < 2:
        flash("Escreva a mensagem do WhatsApp.")
        return redirect(url_for("admin.comunicados"))
    pessoas = Congregado.query.filter_by(recebe_noticias=True, anonimizado=False).order_by(Congregado.nome.asc()).all()
    links = [pessoa for pessoa in pessoas if link_wa_me(pessoa.whatsapp, mensagem, pessoa.nome)]
    admin = _admin_atual()
    db.session.add(
        Comunicado(
            canal="whatsapp",
            assunto="WhatsApp",
            mensagem=mensagem,
            total_destinatarios=len(links),
            total_enviados=0,
            enviado_por=admin.email if admin else "",
        )
    )
    db.session.commit()
    flash("Lista pronta. O site não envia o WhatsApp sozinho: abra cada conversa.")
    return redirect(url_for("admin.comunicados", mensagem=mensagem))


def _codigos_marcados() -> list[str]:
    return [codigo for codigo in request.form.getlist("permissao") if codigo in CODIGOS]


def _gravar_permissoes(item: Administrador, codigos: list[str]) -> None:
    item.permissoes.clear()
    for codigo in codigos:
        item.permissoes.append(AdministradorPermissao(codigo=codigo))


@bp.route("/equipe", methods=["GET", "POST"])
@bp.route("/equipe/<int:item_id>", methods=["GET", "POST"])
def equipe(item_id=None):
    item = db.session.get(Administrador, item_id) if item_id else None
    if item_id and item is None:
        abort(404)
    if request.method == "POST":
        nome = _texto("nome")
        email = normalizar_email(_texto("email"))
        ministerio = _texto("ministerio")
        senha = request.form.get("senha") or ""
        quer_super = _marcado("eh_super_admin")
        quer_ativo = _marcado("ativo")
        if erro_nome(nome) or erro_email(email):
            flash(erro_nome(nome) or erro_email(email))
        elif item is not None and _ultimo_super(item) and (not quer_super or not quer_ativo):
            flash("O último administrador master precisa continuar ativo.")
        else:
            if item is None or senha:
                erro_senha = validar_senha_nova(senha)
            else:
                erro_senha = ""
            if erro_senha:
                flash(erro_senha)
            else:
                if item is None:
                    item = Administrador(nome=nome, email=email)
                    db.session.add(item)
                item.nome = nome
                item.email = email
                item.ministerio = ministerio
                item.eh_super_admin = quer_super
                item.ativo = quer_ativo if item.id != _admin_atual().id else True
                if senha:
                    item.senha_hash = hash_senha(senha)
                db.session.flush()
                _gravar_permissoes(item, _codigos_marcados())
                if _gravar():
                    flash("Acesso salvo.")
                    return redirect(url_for("admin.equipe"))
                flash("Já existe um acesso com este e-mail.")
    return render_template(
        "admin/equipe.html",
        itens=Administrador.query.order_by(Administrador.nome.asc()).all(),
        item=item,
        catalogo=CATALOGO,
        marcadas=set(_codigos_marcados()) if request.method == "POST" else (set() if item is None else item.codigos()),
    )


@bp.post("/equipe/<int:item_id>/excluir")
def excluir_equipe(item_id):
    item = db.session.get(Administrador, item_id)
    if item is None:
        abort(404)
    if _ultimo_super(item):
        flash("O último administrador master não pode ser excluído.")
        return redirect(url_for("admin.equipe"))
    era_eu = _admin_atual().id == item.id
    db.session.delete(item)
    db.session.commit()
    flash("Acesso excluído.")
    if era_eu:
        session.clear()
        return redirect(url_for("admin.entrar"))
    return redirect(url_for("admin.equipe"))
