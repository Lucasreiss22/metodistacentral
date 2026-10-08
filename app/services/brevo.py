"""Envio pela API HTTP do Brevo. Não usa SMTP.

O cliente HTTP entra por parâmetro para os testes não acessarem a internet.
"""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

URL_API = "https://api.brevo.com/v3/smtp/email"
TAMANHO_DO_LOTE = 50


@dataclass(frozen=True)
class ResultadoEnvio:
    ok: bool
    erro: str = ""


def montar_versoes(destinatarios: list[dict]) -> list[dict]:
    """Uma versão por pessoa, com o HTML e o texto dela."""
    versoes = []
    for pessoa in destinatarios:
        versoes.append(
            {
                "to": [{"email": pessoa["email"], "name": pessoa.get("nome") or ""}],
                "htmlContent": pessoa.get("html") or "",
                "textContent": pessoa.get("texto") or "",
            }
        )
    return versoes


def fatiar_lotes(versoes: list[dict], tamanho: int = TAMANHO_DO_LOTE) -> list[list[dict]]:
    """A API aceita um número limitado de messageVersions por chamada."""
    if tamanho < 1:
        tamanho = TAMANHO_DO_LOTE
    return [versoes[inicio : inicio + tamanho] for inicio in range(0, len(versoes), tamanho)]


def corpo_do_email(
    *,
    remetente: str,
    nome_remetente: str,
    assunto: str,
    destinatario: str = "",
    nome: str = "",
    html: str = "",
    texto: str = "",
    versoes: list[dict] | None = None,
) -> dict:
    """JSON da API. Com versões, cada pessoa recebe o próprio HTML."""
    corpo = {
        "sender": {"email": remetente, "name": nome_remetente or remetente},
        "subject": assunto,
    }
    if versoes:
        # Com messageVersions o Brevo não usa um destinatário geral.
        corpo["htmlContent"] = html or " "
        corpo["textContent"] = texto or " "
        corpo["messageVersions"] = versoes
    else:
        corpo["to"] = [{"email": destinatario, "name": nome or destinatario}]
        corpo["htmlContent"] = html
        corpo["textContent"] = texto
    return corpo


def _enviar_json(api_key: str, corpo: dict) -> ResultadoEnvio:
    pedido = Request(
        URL_API,
        data=json.dumps(corpo).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=20) as resposta:
            resposta.read()
    except HTTPError as erro:
        detalhe = erro.read().decode("utf-8", errors="replace")[:300]
        return ResultadoEnvio(False, f"Brevo recusou o envio ({erro.code}). {detalhe}")
    except URLError as erro:
        return ResultadoEnvio(False, f"Não foi possível falar com o Brevo. {erro.reason}")
    return ResultadoEnvio(True)


def enviar_email(
    *,
    api_key: str,
    remetente: str,
    nome_remetente: str,
    assunto: str,
    destinatario: str = "",
    nome: str = "",
    html: str = "",
    texto: str = "",
    versoes: list[dict] | None = None,
    cliente=None,
) -> ResultadoEnvio:
    """Envia um e-mail ou um lote. cliente substitui a rede nos testes."""
    if not api_key:
        return ResultadoEnvio(False, "BREVO_API_KEY não configurada.")
    if not remetente:
        return ResultadoEnvio(False, "EMAIL_REMETENTE não configurado.")
    if not versoes and not destinatario:
        return ResultadoEnvio(False, "Nenhum destinatário.")
    corpo = corpo_do_email(
        remetente=remetente,
        nome_remetente=nome_remetente,
        assunto=assunto,
        destinatario=destinatario,
        nome=nome,
        html=html,
        texto=texto,
        versoes=versoes,
    )
    if cliente is not None:
        return cliente(corpo)
    return _enviar_json(api_key, corpo)


def enviar_lotes(
    *,
    api_key: str,
    remetente: str,
    nome_remetente: str,
    assunto: str,
    destinatarios: list[dict],
    cliente=None,
) -> ResultadoEnvio:
    """Envia em lotes. Para no primeiro erro e informa quantos já saíram."""
    versoes = montar_versoes(destinatarios)
    enviados = 0
    for lote in fatiar_lotes(versoes):
        resultado = enviar_email(
            api_key=api_key,
            remetente=remetente,
            nome_remetente=nome_remetente,
            assunto=assunto,
            versoes=lote,
            cliente=cliente,
        )
        if not resultado.ok:
            return ResultadoEnvio(False, f"{enviados} já enviados. {resultado.erro}")
        enviados += len(lote)
    return ResultadoEnvio(True)
