"""Pedido público de exclusão e o opt-in pensado para a API da Meta.

O cadastro some como dado pessoal: nome, e-mail e telefone são trocados.
O pedido guarda só o hash desses identificadores e o motivo informado.
"""

import hashlib

from sqlalchemy import func

from app.extensions import db
from app.models import Congregado, SolicitacaoLgpd
from app.services.whatsapp import numero_whatsapp
from app.utils import agora_utc, gerar_token_descadastro, normalizar_email


def hash_identificador(valor: str) -> str:
    return hashlib.sha256((valor or "").encode("utf-8")).hexdigest()


def aplicar_opt_in(pessoa: Congregado, whatsapp: str, origem: str = "formulario_site") -> None:
    """Grava o consentimento e o número no formato 55 + DDD + número."""
    pessoa.whatsapp = (whatsapp or "").strip()
    pessoa.whatsapp_e164 = numero_whatsapp(whatsapp) or ""
    pessoa.recebe_noticias = True
    pessoa.opt_in_status = "confirmado"
    pessoa.opt_in_origem = origem
    pessoa.consentimento_em = agora_utc()
    if pessoa.status_envio in ("", "opt_out"):
        pessoa.status_envio = "nunca_enviado"
    pessoa.excluido_em = None
    pessoa.anonimizado = False
    pessoa.motivo_exclusao = ""


def aplicar_opt_out(pessoa: Congregado) -> None:
    """Interrompe os envios e mantém o cadastro, para o link do e-mail."""
    pessoa.recebe_noticias = False
    pessoa.opt_in_status = "revogado"
    pessoa.status_envio = "opt_out"


def anonimizar(pessoa: Congregado, motivo: str) -> None:
    """Apaga o dado pessoal e invalida o link antigo de descadastro."""
    aplicar_opt_out(pessoa)
    pessoa.anonimizado = True
    pessoa.nome = "Cadastro removido"
    pessoa.whatsapp = ""
    pessoa.whatsapp_e164 = ""
    pessoa.excluido_em = agora_utc()
    pessoa.motivo_exclusao = (motivo or "").strip()[:500]
    pessoa.token_descadastro = gerar_token_descadastro()
    pessoa.email = f"removido-{pessoa.id}@anonimo.invalid"


def processar_pedido(email: str, whatsapp: str, motivo: str, tipo: str = "remocao") -> str:
    """Localiza pelo e-mail e pelo WhatsApp juntos.

    Remoção apaga o dado pessoal. Alteração só registra o pedido para o painel editar.
    Devolve removido, pendente ou nao_encontrado.
    """
    if tipo not in ("remocao", "alteracao"):
        tipo = "remocao"
    email_norm = normalizar_email(email)
    numero = numero_whatsapp(whatsapp) or ""
    pessoa = Congregado.query.filter(
        func.lower(Congregado.email) == email_norm,
        Congregado.anonimizado.is_(False),
    ).one_or_none()
    gravado = ""
    if pessoa is not None:
        gravado = pessoa.whatsapp_e164 or numero_whatsapp(pessoa.whatsapp) or ""
    if pessoa is not None and numero and gravado == numero:
        if tipo == "alteracao":
            resultado = "pendente"
        else:
            anonimizar(pessoa, motivo)
            resultado = "removido"
        congregado_id = pessoa.id
    else:
        resultado = "nao_encontrado"
        congregado_id = None
    db.session.add(
        SolicitacaoLgpd(
            tipo=tipo,
            congregado_id=congregado_id,
            email_hash=hash_identificador(email_norm),
            whatsapp_hash=hash_identificador(numero),
            motivo=(motivo or "").strip()[:500],
            resultado=resultado,
        )
    )
    db.session.commit()
    return resultado


def processar_exclusao(email: str, whatsapp: str, motivo: str) -> str:
    """Atalho do pedido de remoção."""
    return processar_pedido(email, whatsapp, motivo, "remocao")
