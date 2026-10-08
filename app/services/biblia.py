"""Leitor da Bíblia. A página chama este módulo; o navegador não fala com a API.

A tradução padrão é a Almeida, na bible-api.com, sem chave.
O resultado de cada capítulo fica em memória até o processo reiniciar.
"""

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

LINK_EXTERNO = "https://www.bibliaonline.com.br/"
TRADUCAO = "almeida"

# id interno, nome em português, nome na URL da API, quantidade de capítulos.
LIVROS = (
    ("genesis", "Gênesis", "genesis", 50),
    ("exodo", "Êxodo", "exodus", 40),
    ("levitico", "Levítico", "leviticus", 27),
    ("numeros", "Números", "numbers", 36),
    ("deuteronomio", "Deuteronômio", "deuteronomy", 34),
    ("josue", "Josué", "joshua", 24),
    ("juizes", "Juízes", "judges", 21),
    ("rute", "Rute", "ruth", 4),
    ("1samuel", "1 Samuel", "1 samuel", 31),
    ("2samuel", "2 Samuel", "2 samuel", 24),
    ("1reis", "1 Reis", "1 kings", 22),
    ("2reis", "2 Reis", "2 kings", 25),
    ("1cronicas", "1 Crônicas", "1 chronicles", 29),
    ("2cronicas", "2 Crônicas", "2 chronicles", 36),
    ("esdras", "Esdras", "ezra", 10),
    ("neemias", "Neemias", "nehemiah", 13),
    ("ester", "Ester", "esther", 10),
    ("jo", "Jó", "job", 42),
    ("salmos", "Salmos", "psalms", 150),
    ("proverbios", "Provérbios", "proverbs", 31),
    ("eclesiastes", "Eclesiastes", "ecclesiastes", 12),
    ("canticos", "Cânticos", "song of solomon", 8),
    ("isaias", "Isaías", "isaiah", 66),
    ("jeremias", "Jeremias", "jeremiah", 52),
    ("lamentacoes", "Lamentações", "lamentations", 5),
    ("ezequiel", "Ezequiel", "ezekiel", 48),
    ("daniel", "Daniel", "daniel", 12),
    ("oseias", "Oseias", "hosea", 14),
    ("joel", "Joel", "joel", 3),
    ("amos", "Amós", "amos", 9),
    ("obadias", "Obadias", "obadiah", 1),
    ("jonas", "Jonas", "jonah", 4),
    ("miqueias", "Miqueias", "micah", 7),
    ("naum", "Naum", "nahum", 3),
    ("habacuque", "Habacuque", "habakkuk", 3),
    ("sofonias", "Sofonias", "zephaniah", 3),
    ("ageu", "Ageu", "haggai", 2),
    ("zacarias", "Zacarias", "zechariah", 14),
    ("malaquias", "Malaquias", "malachi", 4),
    ("mateus", "Mateus", "matthew", 28),
    ("marcos", "Marcos", "mark", 16),
    ("lucas", "Lucas", "luke", 24),
    ("joao", "João", "john", 21),
    ("atos", "Atos", "acts", 28),
    ("romanos", "Romanos", "romans", 16),
    ("1corintios", "1 Coríntios", "1 corinthians", 16),
    ("2corintios", "2 Coríntios", "2 corinthians", 13),
    ("galatas", "Gálatas", "galatians", 6),
    ("efesios", "Efésios", "ephesians", 6),
    ("filipenses", "Filipenses", "philippians", 4),
    ("colossenses", "Colossenses", "colossians", 4),
    ("1tessalonicenses", "1 Tessalonicenses", "1 thessalonians", 5),
    ("2tessalonicenses", "2 Tessalonicenses", "2 thessalonians", 3),
    ("1timoteo", "1 Timóteo", "1 timothy", 6),
    ("2timoteo", "2 Timóteo", "2 timothy", 4),
    ("tito", "Tito", "titus", 3),
    ("filemom", "Filemom", "philemon", 1),
    ("hebreus", "Hebreus", "hebrews", 13),
    ("tiago", "Tiago", "james", 5),
    ("1pedro", "1 Pedro", "1 peter", 5),
    ("2pedro", "2 Pedro", "2 peter", 3),
    ("1joao", "1 João", "1 john", 5),
    ("2joao", "2 João", "2 john", 1),
    ("3joao", "3 João", "3 john", 1),
    ("judas", "Judas", "jude", 1),
    ("apocalipse", "Apocalipse", "revelation", 22),
)

_POR_ID = {livro[0]: livro for livro in LIVROS}
_cache: dict[tuple[str, int], "Capitulo"] = {}


@dataclass(frozen=True)
class Capitulo:
    ok: bool
    livro_id: str
    nome: str
    capitulo: int
    versiculos: tuple[tuple[int, str], ...] = ()
    erro: str = ""
    link_externo: str = LINK_EXTERNO
    anterior: tuple[str, int] | None = None
    proximo: tuple[str, int] | None = None


def listar_livros() -> tuple:
    """Os 66 livros, na ordem do cânon protestante."""
    return LIVROS


def buscar_livro(livro_id: str | None):
    if not livro_id:
        return None
    return _POR_ID.get(livro_id.strip().lower())


def capitulo_vizinho(livro_id: str, capitulo: int, passo: int) -> tuple[str, int] | None:
    """Capítulo anterior ou próximo, mudando de livro na ponta."""
    if passo not in (-1, 1) or livro_id not in _POR_ID:
        return None
    indice = next(i for i, livro in enumerate(LIVROS) if livro[0] == livro_id)
    _, _, _, quantidade = LIVROS[indice]
    destino = capitulo + passo
    if 1 <= destino <= quantidade:
        return (livro_id, destino)
    if passo == 1:
        if indice + 1 >= len(LIVROS):
            return None
        return (LIVROS[indice + 1][0], 1)
    if indice == 0:
        return None
    return (LIVROS[indice - 1][0], LIVROS[indice - 1][3])


def url_do_capitulo(nome_api: str, capitulo: int) -> str:
    return f"https://bible-api.com/{quote(nome_api)}+{capitulo}?translation={TRADUCAO}"


def limpar_cache() -> None:
    _cache.clear()


def _baixar(url: str) -> str:
    pedido = Request(url, headers={"User-Agent": "IgrejaMetodistaCentral/1.0"})
    with urlopen(pedido, timeout=8) as resposta:
        return resposta.read().decode("utf-8")


def _falha(livro_id: str, nome: str, capitulo: int, erro: str) -> Capitulo:
    return Capitulo(
        ok=False,
        livro_id=livro_id,
        nome=nome,
        capitulo=capitulo,
        erro=erro,
        anterior=capitulo_vizinho(livro_id, capitulo, -1) if livro_id in _POR_ID else None,
        proximo=capitulo_vizinho(livro_id, capitulo, 1) if livro_id in _POR_ID else None,
    )


def interpretar_resposta(bruto: str) -> tuple[tuple[int, str], ...]:
    """Extrai (número, texto) do JSON da bible-api.com."""
    dados = json.loads(bruto)
    versos = dados.get("verses") or []
    itens = []
    for verso in versos:
        numero = int(verso.get("verse") or 0)
        texto = (verso.get("text") or "").strip()
        if numero and texto:
            itens.append((numero, texto))
    if itens:
        return tuple(itens)
    texto = (dados.get("text") or "").strip()
    if texto:
        return ((1, texto),)
    return ()


def buscar_capitulo(livro_id: str, capitulo: int, cliente=None) -> Capitulo:
    """Busca o capítulo. cliente substitui a rede nos testes."""
    livro = buscar_livro(livro_id)
    if livro is None:
        return _falha(livro_id or "", "", capitulo or 0, "Esse livro não faz parte da lista.")
    ident, nome, nome_api, quantidade = livro
    if capitulo < 1 or capitulo > quantidade:
        return _falha(ident, nome, capitulo, "Esse capítulo não existe neste livro.")

    chave = (ident, capitulo)
    if chave in _cache:
        return _cache[chave]

    try:
        bruto = (cliente or _baixar)(url_do_capitulo(nome_api, capitulo))
        versiculos = interpretar_resposta(bruto)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return _falha(
            ident,
            nome,
            capitulo,
            "Não foi possível carregar este capítulo agora.",
        )
    if not versiculos:
        return _falha(ident, nome, capitulo, "A resposta da Bíblia veio vazia.")

    resultado = Capitulo(
        ok=True,
        livro_id=ident,
        nome=nome,
        capitulo=capitulo,
        versiculos=versiculos,
        anterior=capitulo_vizinho(ident, capitulo, -1),
        proximo=capitulo_vizinho(ident, capitulo, 1),
    )
    _cache[chave] = resultado
    return resultado
