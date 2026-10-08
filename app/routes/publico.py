"""Páginas públicas. O visual em Tailwind entra na Parte 3."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from zoneinfo import ZoneInfo

from app.extensions import db
from app.formularios import FormularioCongregado
from app.models import Campanha, Congregado, Configuracao, Evento, FeriadoLocal, Informativo, Subsede
from app.services.biblia import buscar_capitulo, buscar_livro, listar_livros
from app.services.brevo import enviar_email
from app.services.feriados import CORES, LEGENDA, calendario_do_ano
from app.services.mensagens import assunto_boas_vindas, link_de_descadastro, texto_boas_vindas
from app.services.whatsapp import link_wa_me
from app.utils import (
    formatar_data_hora_br,
    formatar_quantidade,
    normalizar_email,
    percentual_meta,
    url_embed_youtube,
)

bp = Blueprint("publico", __name__)
_FUSO = ZoneInfo("America/Sao_Paulo")


def _configuracao_vazia():
    return SimpleNamespace(
        nome_igreja="Igreja Metodista Central",
        slogan="",
        instagram_url="",
        instagram_usuario="",
        youtube_url="",
        facebook_url="",
        whatsapp="",
        email_contato="",
        endereco="Teresópolis - RJ",
        sobre="",
    )


def obter_configuracao():
    linha = db.session.get(Configuracao, 1)
    return linha or _configuracao_vazia()


@bp.app_context_processor
def injetar_configuracao():
    return {"configuracao": obter_configuracao()}


@bp.app_template_global("url_embed_youtube")
def _embed(url):
    return url_embed_youtube(url)


@bp.app_template_global("formatar_quantidade")
def _quantidade(valor, unidade):
    return formatar_quantidade(valor, unidade)


@bp.app_template_global("percentual_meta")
def _percentual(arrecadado, meta):
    return percentual_meta(arrecadado, meta)


@bp.app_template_global("formatar_data_hora_br")
def _quando(momento, dia_inteiro=False):
    return formatar_data_hora_br(momento, dia_inteiro)


@bp.app_template_global("link_wa_me")
def _whatsapp(telefone, mensagem="", nome=""):
    return link_wa_me(telefone, mensagem, nome)


def subsedes_ativas():
    return (
        Subsede.query.filter_by(ativa=True)
        .order_by(Subsede.eh_sede.desc(), Subsede.ordem.asc(), Subsede.nome.asc())
        .all()
    )


def _dia_local(momento: datetime) -> date:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(_FUSO).date()


def _ler_data(valor: str | None) -> date | None:
    if not valor:
        return None
    texto = valor.strip()
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        return None


@bp.get("/")
def inicio():
    informativos = (
        Informativo.query.filter_by(ativo=True)
        .order_by(Informativo.destaque.desc(), Informativo.ordem.asc(), Informativo.id.asc())
        .all()
    )
    agora = datetime.now(timezone.utc)
    eventos = (
        Evento.query.filter(Evento.status == "ativo", Evento.data_evento >= agora - timedelta(days=1))
        .order_by(Evento.data_evento.asc())
        .limit(6)
        .all()
    )
    campanhas = (
        Campanha.query.filter_by(status="ativa").order_by(Campanha.criado_em.desc()).all()
    )
    return render_template(
        "publico/inicio.html",
        informativos=informativos,
        eventos=eventos,
        campanhas=campanhas,
        subsedes=subsedes_ativas(),
    )


@bp.get("/subsedes")
def subsedes():
    return render_template("publico/subsedes.html", subsedes=subsedes_ativas())


@bp.get("/campanhas")
def campanhas():
    lista = Campanha.query.filter_by(status="ativa").order_by(Campanha.criado_em.desc()).all()
    return render_template("publico/campanhas.html", campanhas=lista)


@bp.get("/campanhas/<int:campanha_id>")
def campanha(campanha_id: int):
    item = db.session.get(Campanha, campanha_id)
    if item is None:
        abort(404)
    return render_template("publico/campanha.html", campanha=item)


@bp.get("/calendario")
def calendario():
    hoje = datetime.now(_FUSO).date()
    dados = calendario_do_ano(hoje.year, FeriadoLocal.query.all())
    eventos = (
        Evento.query.filter_by(status="ativo").order_by(Evento.data_evento.asc()).all()
    )
    return render_template(
        "publico/calendario.html",
        feriados=dados,
        eventos=eventos,
        legenda=LEGENDA,
        cores=CORES,
        ano=hoje.year,
    )


@bp.get("/calendario/eventos.json")
def calendario_dados():
    inicio = _ler_data(request.args.get("start"))
    fim = _ler_data(request.args.get("end"))
    hoje = datetime.now(_FUSO).date()
    if inicio is None:
        inicio = date(hoje.year, 1, 1)
    if fim is None:
        fim = date(hoje.year, 12, 31)
    if fim < inicio:
        inicio, fim = fim, inicio

    itens = []
    for ano in range(inicio.year, fim.year + 1):
        for feriado in calendario_do_ano(ano, FeriadoLocal.query.all()):
            if inicio <= feriado.dia <= fim:
                itens.append(
                    {
                        "title": feriado.nome,
                        "start": feriado.dia.isoformat(),
                        "allDay": True,
                        "backgroundColor": CORES.get(feriado.tipo, CORES["feriado_nacional"]),
                        "extendedProps": {"tipo": feriado.tipo},
                    }
                )

    eventos = Evento.query.filter_by(status="ativo").all()
    for evento in eventos:
        dia = _dia_local(evento.data_evento)
        if not (inicio <= dia <= fim):
            continue
        subsede = evento.subsede.nome if evento.subsede else ""
        fim_evento = evento.data_fim.isoformat() if evento.data_fim else None
        itens.append(
            {
                "title": evento.titulo,
                "start": evento.data_evento.isoformat(),
                "end": fim_evento,
                "allDay": bool(evento.dia_inteiro),
                "backgroundColor": CORES["evento"],
                "extendedProps": {
                    "tipo": "evento",
                    "local": evento.local,
                    "subsede": subsede,
                    "descricao": evento.descricao,
                },
            }
        )
    return jsonify(itens)


@bp.get("/biblia")
@bp.get("/biblia/<livro_id>/<int:capitulo>")
def biblia(livro_id: str = "genesis", capitulo: int = 1):
    if request.args.get("livro"):
        livro_id = request.args.get("livro")
    if request.args.get("capitulo", "").isdigit():
        capitulo = int(request.args["capitulo"])
    cliente = current_app.config.get("CLIENTE_BIBLIA")
    resultado = buscar_capitulo(livro_id, capitulo, cliente=cliente)
    return render_template(
        "publico/biblia.html",
        livros=listar_livros(),
        resultado=resultado,
        livro_atual=buscar_livro(livro_id),
    )


@bp.route("/congregado", methods=["GET", "POST"])
def congregado():
    ativas = subsedes_ativas()
    formulario = FormularioCongregado(ativas)
    if formulario.validate_on_submit():
        if (formulario.empresa.data or "").strip():
            flash("Cadastro recebido. Obrigado.")
            return redirect(url_for("publico.congregado"))
        pessoa = _gravar_congregado(formulario)
        _enviar_boas_vindas(pessoa)
        return redirect(url_for("publico.congregado"))
    return render_template("publico/congregado.html", formulario=formulario, subsedes=ativas)


def _gravar_congregado(formulario: FormularioCongregado) -> Congregado:
    email = normalizar_email(formulario.email.data)
    existente = Congregado.query.filter(func.lower(Congregado.email) == email).one_or_none()
    if existente:
        existente.nome = formulario.nome.data.strip()
        existente.whatsapp = formulario.whatsapp.data.strip()
        existente.subsede_id = formulario.subsede_id.data
        existente.recebe_noticias = True
        db.session.commit()
        return existente

    pessoa = Congregado(
        nome=formulario.nome.data.strip(),
        email=email,
        whatsapp=formulario.whatsapp.data.strip(),
        subsede_id=formulario.subsede_id.data,
        recebe_noticias=True,
    )
    db.session.add(pessoa)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        de_novo = Congregado.query.filter(func.lower(Congregado.email) == email).one_or_none()
        if de_novo is None:
            raise
        de_novo.nome = formulario.nome.data.strip()
        de_novo.whatsapp = formulario.whatsapp.data.strip()
        de_novo.subsede_id = formulario.subsede_id.data
        de_novo.recebe_noticias = True
        db.session.commit()
        return de_novo
    return pessoa


def _enviar_boas_vindas(pessoa: Congregado) -> None:
    configuracao = obter_configuracao()
    base = current_app.config.get("URL_PUBLICA") or request.host_url.rstrip("/")
    link = link_de_descadastro(base, pessoa.token_descadastro)
    igreja = configuracao.nome_igreja
    html = render_template(
        "emails/boas_vindas.html",
        nome=pessoa.nome,
        nome_igreja=igreja,
        link=link,
    )
    resultado = enviar_email(
        api_key=current_app.config.get("BREVO_API_KEY", ""),
        remetente=current_app.config.get("EMAIL_REMETENTE", ""),
        nome_remetente=current_app.config.get("NOME_REMETENTE", "") or igreja,
        assunto=assunto_boas_vindas(igreja),
        destinatario=pessoa.email,
        nome=pessoa.nome,
        html=html,
        texto=texto_boas_vindas(pessoa.nome, igreja, link),
        cliente=current_app.config.get("CLIENTE_BREVO"),
    )
    if resultado.ok:
        flash("Cadastro salvo. Enviamos um e-mail de boas-vindas.")
    else:
        flash("Cadastro salvo. O e-mail de boas-vindas não pôde ser enviado.")


@bp.get("/descadastrar/<token>")
def descadastrar(token: str):
    pessoa = Congregado.query.filter_by(token_descadastro=token).one_or_none()
    if pessoa is None:
        return render_template("publico/descadastrar.html", encontrado=False), 404
    pessoa.recebe_noticias = False
    db.session.commit()
    return render_template("publico/descadastrar.html", encontrado=True)
