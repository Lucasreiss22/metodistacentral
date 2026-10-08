"""Regras puras da Parte 2: feriados, valores, WhatsApp, Bíblia e Brevo."""

import json
from datetime import date

from app.services.biblia import (
    LIVROS,
    buscar_capitulo,
    capitulo_vizinho,
    interpretar_resposta,
    limpar_cache,
)
from app.services.brevo import corpo_do_email, enviar_lotes, fatiar_lotes, montar_versoes
from app.services.brevo import ResultadoEnvio
from app.services.feriados import calendario_do_ano, data_da_pascoa, feriados_nacionais
from app.services.mensagens import link_de_descadastro, texto_boas_vindas
from app.services.whatsapp import link_wa_me, numero_whatsapp
from app.utils import formatar_quantidade, id_do_youtube, percentual_meta


def test_pascoa_em_anos_conhecidos():
    assert data_da_pascoa(2024) == date(2024, 3, 31)
    assert data_da_pascoa(2025) == date(2025, 4, 20)
    assert data_da_pascoa(2026) == date(2026, 4, 5)


def test_sexta_carnaval_e_corpus_christi_2024():
    por_nome = {item.nome: item for item in feriados_nacionais(2024)}
    assert por_nome["Sexta-feira Santa"].dia == date(2024, 3, 29)
    assert por_nome["Sexta-feira Santa"].tipo == "feriado_nacional"
    assert por_nome["Terça-feira de Carnaval"].dia == date(2024, 2, 13)
    assert por_nome["Terça-feira de Carnaval"].tipo == "ponto_facultativo"
    assert por_nome["Corpus Christi"].dia == date(2024, 5, 30)
    assert por_nome["Corpus Christi"].tipo == "ponto_facultativo"


def test_consciencia_negra_comeca_em_2024():
    nomes_2023 = {item.nome for item in feriados_nacionais(2023)}
    nomes_2024 = {item.nome for item in feriados_nacionais(2024)}
    assert "Consciência Negra" not in nomes_2023
    assert "Consciência Negra" in nomes_2024


def test_feriado_local_entra_no_ano_e_respeita_ano_fixo():
    class Registro:
        def __init__(self, nome, dia, mes, ano, tipo):
            self.nome = nome
            self.dia = dia
            self.mes = mes
            self.ano = ano
            self.tipo = tipo

    itens = calendario_do_ano(
        2026,
        [
            Registro("São Jorge", 23, 4, None, "estadual"),
            Registro("Festa única", 1, 6, 2020, "municipal"),
        ],
    )
    jorge = next(item for item in itens if item.nome == "São Jorge")
    assert jorge.dia == date(2026, 4, 23)
    assert jorge.tipo == "estadual"
    assert all(item.nome != "Festa única" for item in itens)


def test_valores_em_reais_e_em_unidades():
    assert formatar_quantidade("1234.56", "R$") == "R$ 1.234,56"
    assert formatar_quantidade(200, "cestas") == "200 cestas"
    assert percentual_meta(50, 200) == 25
    assert percentual_meta(10, 0) == 0
    assert percentual_meta(300, 100) == 100


def test_link_de_whatsapp_troca_o_primeiro_nome():
    assert numero_whatsapp("(21) 99999-8888") == "5521999998888"
    assert numero_whatsapp("021999998888") == "5521999998888"
    link = link_wa_me("21999998888", "Olá, {nome}", "Maria Silva")
    assert link.startswith("https://wa.me/5521999998888?text=")
    assert "Maria" in link
    assert "{nome}" not in link
    assert link_wa_me("123", "oi") is None


def test_sao_66_livros_e_a_navegacao_muda_de_livro():
    assert len(LIVROS) == 66
    assert capitulo_vizinho("genesis", 1, -1) is None
    assert capitulo_vizinho("genesis", 50, 1) == ("exodo", 1)
    assert capitulo_vizinho("apocalipse", 22, 1) is None


def test_biblia_usa_cache_e_nao_chama_a_rede_de_novo():
    limpar_cache()
    chamadas = []

    def cliente(url):
        chamadas.append(url)
        return json.dumps({"verses": [{"verse": 1, "text": "No princípio"}]})

    primeiro = buscar_capitulo("genesis", 1, cliente=cliente)
    segundo = buscar_capitulo("genesis", 1, cliente=cliente)
    assert primeiro.ok and segundo.ok
    assert primeiro.versiculos[0] == (1, "No princípio")
    assert len(chamadas) == 1
    assert "almeida" in chamadas[0]
    limpar_cache()


def test_biblia_avisa_quando_a_api_falha():
    limpar_cache()

    def cliente(url):
        raise TimeoutError("sem rede")

    resultado = buscar_capitulo("joao", 3, cliente=cliente)
    assert not resultado.ok
    assert resultado.link_externo.startswith("https://www.bibliaonline.com.br")
    assert interpretar_resposta('{"text": "só o bloco"}') == ((1, "só o bloco"),)


def test_id_do_youtube():
    assert id_do_youtube("https://www.youtube.com/watch?v=abc123XYZ_-") == "abc123XYZ_-"
    assert id_do_youtube("https://youtu.be/abc123XYZ_-") == "abc123XYZ_-"


def test_lote_do_brevo_separa_o_html_de_cada_pessoa():
    pessoas = [
        {"email": f"p{i}@igreja.com", "nome": f"Pessoa {i}", "html": f"<p>link-{i}</p>", "texto": "t"}
        for i in range(51)
    ]
    versoes = montar_versoes(pessoas)
    assert versoes[0]["to"][0]["email"] == "p0@igreja.com"
    assert "link-0" in versoes[0]["htmlContent"]
    assert "link-1" not in versoes[0]["htmlContent"]
    assert len(fatiar_lotes(versoes, 50)) == 2

    chamadas = []

    def cliente(corpo):
        chamadas.append(corpo)
        assert "to" not in corpo or corpo.get("messageVersions")
        return ResultadoEnvio(True)

    resultado = enviar_lotes(
        api_key="teste",
        remetente="igreja@exemplo.com",
        nome_remetente="Igreja",
        assunto="Aviso",
        destinatarios=pessoas,
        cliente=cliente,
    )
    assert resultado.ok
    assert len(chamadas) == 2
    assert "api-key" not in json.dumps(chamadas[0])


def test_link_de_descadastro_e_absoluto():
    link = link_de_descadastro("https://metodistacentral.onrender.com", "abc")
    assert link == "https://metodistacentral.onrender.com/descadastrar/abc"
    assert "abc" in texto_boas_vindas("Ana Silva", "Igreja", link)


def test_corpo_de_um_email_nao_leva_a_chave():
    corpo = corpo_do_email(
        remetente="igreja@exemplo.com",
        nome_remetente="Igreja",
        assunto="Olá",
        destinatario="ana@igreja.com",
        nome="Ana",
        html="<p>oi</p>",
        texto="oi",
    )
    assert corpo["to"][0]["email"] == "ana@igreja.com"
    assert "api-key" not in corpo
