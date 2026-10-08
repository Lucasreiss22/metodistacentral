"""Envio de fotos, GIF e vídeos para o bucket público midia.

O arquivo segue com a SUPABASE_SERVICE_KEY. O visitante só lê o endereço público.
"""

from dataclasses import dataclass
from secrets import token_hex
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

EXTENSOES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".apng": "image/png",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}
LIMITE_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class ResultadoMidia:
    ok: bool
    url: str = ""
    erro: str = ""


def _extensao(nome_arquivo: str) -> str:
    nome = (nome_arquivo or "").strip().lower()
    if "." not in nome:
        return ""
    return "." + nome.rsplit(".", 1)[-1]


def enviar_midia(
    *,
    supabase_url: str,
    service_key: str,
    nome_arquivo: str,
    conteudo: bytes,
    cliente=None,
) -> ResultadoMidia:
    """Grava o arquivo e devolve o endereço público. cliente substitui a rede nos testes."""
    extensao = _extensao(nome_arquivo)
    if extensao not in EXTENSOES:
        return ResultadoMidia(
            False,
            erro="Envie JPG, PNG, GIF, WebP, APNG, MP4 ou WebM.",
        )
    if not conteudo:
        return ResultadoMidia(False, erro="O arquivo está vazio.")
    if len(conteudo) > LIMITE_BYTES:
        return ResultadoMidia(False, erro="O arquivo passa de 16 MB.")

    caminho = f"{token_hex(16)}{extensao}"
    mime = EXTENSOES[extensao]
    if cliente is not None:
        erro = cliente(caminho, conteudo, mime)
    else:
        erro = _enviar_http(supabase_url, service_key, caminho, conteudo, mime)
    if erro:
        return ResultadoMidia(False, erro=erro)
    base = (supabase_url or "").rstrip("/")
    if not base:
        return ResultadoMidia(False, erro="SUPABASE_URL não configurada.")
    return ResultadoMidia(True, url=f"{base}/storage/v1/object/public/midia/{caminho}")


def _enviar_http(supabase_url: str, service_key: str, caminho: str, conteudo: bytes, mime: str) -> str:
    if not supabase_url or not service_key:
        return "O envio de arquivos ainda não está configurado. Você pode colar o endereço."
    destino = f"{supabase_url.rstrip('/')}/storage/v1/object/midia/{caminho}"
    pedido = Request(
        destino,
        data=conteudo,
        headers={
            "Authorization": f"Bearer {service_key}",
            "apikey": service_key,
            "Content-Type": mime,
            "x-upsert": "true",
        },
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=30) as resposta:
            resposta.read()
    except HTTPError as erro:
        return f"O Supabase recusou o arquivo ({erro.code})."
    except (URLError, TimeoutError):
        return "Não foi possível enviar o arquivo."
    return ""
