"""Login do painel via Supabase Auth.

A senha não fica no banco do site e não existe senha mestra no código.
Quem autentica ainda precisa ter o e-mail na tabela administradores.
"""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ResultadoLogin:
    ok: bool
    email: str = ""
    erro: str = ""


def autenticar(email: str, senha: str, url: str, anon_key: str, cliente=None) -> ResultadoLogin:
    """Confere e-mail e senha no Supabase Auth. cliente substitui a rede nos testes."""
    endereco = (email or "").strip()
    if not endereco or not senha:
        return ResultadoLogin(False, erro="Informe e-mail e senha.")
    if cliente is not None:
        return cliente(endereco, senha)
    if not url or not anon_key:
        return ResultadoLogin(False, erro="O login do painel ainda não está configurado.")

    pedido = Request(
        f"{url.rstrip('/')}/auth/v1/token?grant_type=password",
        data=json.dumps({"email": endereco, "password": senha}).encode("utf-8"),
        headers={
            "apikey": anon_key,
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(pedido, timeout=20) as resposta:
            dados = json.loads(resposta.read().decode("utf-8"))
    except HTTPError:
        return ResultadoLogin(False, erro="E-mail ou senha não conferem.")
    except (URLError, json.JSONDecodeError, TimeoutError):
        return ResultadoLogin(False, erro="Não foi possível falar com o Supabase Auth.")

    usuario = dados.get("user") or {}
    confirmado = (usuario.get("email") or "").strip()
    if not dados.get("access_token") or not confirmado:
        return ResultadoLogin(False, erro="E-mail ou senha não conferem.")
    return ResultadoLogin(True, email=confirmado)
