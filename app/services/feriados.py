"""Feriados nacionais calculados e feriados locais vindos do banco.

Carnaval e Corpus Christi entram como ponto facultativo.
Sexta-feira Santa entra como feriado nacional.
Consciência Negra (20/11) vale a partir de 2024.
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class DataComemorativa:
    nome: str
    dia: date
    tipo: str


CORES = {
    "evento": "#1d4e89",
    "feriado_nacional": "#b91c1c",
    "estadual": "#c2410c",
    "municipal": "#a16207",
    "ponto_facultativo": "#6d28d9",
}

LEGENDA = (
    ("evento", "Evento da igreja"),
    ("feriado_nacional", "Feriado nacional"),
    ("estadual", "Feriado estadual"),
    ("municipal", "Feriado municipal"),
    ("ponto_facultativo", "Ponto facultativo"),
)

_FIXOS = (
    (1, 1, "Confraternização Universal"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do Trabalho"),
    (9, 7, "Independência do Brasil"),
    (10, 12, "Nossa Senhora Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (12, 25, "Natal"),
)


def data_da_pascoa(ano: int) -> date:
    """Domingo de Páscoa no calendário gregoriano (algoritmo de Meeus)."""
    a = ano % 19
    b = ano // 100
    c = ano % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    mes = (h + ell - 7 * m + 114) // 31
    dia = ((h + ell - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano: int) -> list[DataComemorativa]:
    """Feriados nacionais e pontos facultativos federais daquele ano."""
    pascoa = data_da_pascoa(ano)
    itens = [
        DataComemorativa(nome, date(ano, mes, dia), "feriado_nacional")
        for mes, dia, nome in _FIXOS
    ]
    itens.extend(
        [
            DataComemorativa(
                "Segunda-feira de Carnaval",
                pascoa - timedelta(days=48),
                "ponto_facultativo",
            ),
            DataComemorativa(
                "Terça-feira de Carnaval",
                pascoa - timedelta(days=47),
                "ponto_facultativo",
            ),
            DataComemorativa(
                "Sexta-feira Santa",
                pascoa - timedelta(days=2),
                "feriado_nacional",
            ),
            DataComemorativa(
                "Corpus Christi",
                pascoa + timedelta(days=60),
                "ponto_facultativo",
            ),
        ]
    )
    if ano >= 2024:
        itens.append(
            DataComemorativa(
                "Consciência Negra",
                date(ano, 11, 20),
                "feriado_nacional",
            )
        )
    return sorted(itens, key=lambda item: item.dia)


def ocorre_no_ano(dia: int, mes: int, ano_fixo: int | None, ano: int) -> date | None:
    """Data local naquele ano. ano_fixo vazio significa que vale todo ano."""
    if ano_fixo is not None and ano_fixo != ano:
        return None
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None


def feriados_locais_no_ano(registros, ano: int) -> list[DataComemorativa]:
    """Expande as linhas editáveis pelo admin para um ano."""
    itens: list[DataComemorativa] = []
    for registro in registros:
        quando = ocorre_no_ano(registro.dia, registro.mes, registro.ano, ano)
        if quando is None:
            continue
        itens.append(DataComemorativa(registro.nome, quando, registro.tipo))
    return itens


def calendario_do_ano(ano: int, registros_locais) -> list[DataComemorativa]:
    """Nacionais calculados mais os locais cadastrados."""
    juntos = feriados_nacionais(ano) + feriados_locais_no_ano(registros_locais, ano)
    return sorted(juntos, key=lambda item: (item.dia, item.nome))
