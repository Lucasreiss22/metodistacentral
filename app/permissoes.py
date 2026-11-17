"""Catálogo de permissões do painel.

O administrador master ignora esta lista e pode tudo.
Os demais acessos só entram na rota se tiverem um dos códigos exigidos.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Permissao:
    codigo: str
    rotulo: str
    descricao: str


CATALOGO: tuple[Permissao, ...] = (
    Permissao(
        "gerenciar_fotos",
        "Gerenciar fotos",
        "Enviar, editar e excluir fotos e mídia dos informativos.",
    ),
    Permissao(
        "criar_informativos",
        "Criar informativos",
        "Criar banners, fotos, vídeos e avisos da página inicial.",
    ),
    Permissao(
        "gerenciar_eventos",
        "Gerenciar eventos",
        "Criar e editar qualquer evento do calendário.",
    ),
    Permissao(
        "gerenciar_eventos_empreendedores",
        "Gerenciar eventos de empreendedores",
        "Criar e editar só os eventos do Ministério de Empreendedores.",
    ),
    Permissao(
        "divulgar_empreendedores",
        "Divulgar empreendedores",
        "Preparar a divulgação no WhatsApp. Não envia o e-mail geral.",
    ),
    Permissao(
        "enviar_comunicados",
        "Enviar informativos",
        "Enviar e-mail e preparar WhatsApp para os congregados.",
    ),
    Permissao(
        "gerenciar_congregados",
        "Gerenciar congregados",
        "Ver, editar e exportar quem recebe os informativos.",
    ),
    Permissao(
        "gerenciar_campanhas",
        "Gerenciar campanhas",
        "Criar e editar campanhas de arrecadação.",
    ),
    Permissao(
        "gerenciar_subsedes",
        "Gerenciar subsedes",
        "Editar a sede e as subsedes.",
    ),
    Permissao(
        "gerenciar_feriados",
        "Gerenciar feriados",
        "Editar os feriados locais do calendário.",
    ),
    Permissao(
        "gerenciar_configuracoes",
        "Configurações do site",
        "Alterar nome, redes e textos públicos.",
    ),
)

CODIGOS = {item.codigo for item in CATALOGO}

# None libera qualquer pessoa logada. Conjunto vazio não é usado.
ACESSO: dict[str, set[str] | None] = {
    "admin.painel": None,
    "admin.sair": None,
    "admin.subsedes": {"gerenciar_subsedes"},
    "admin.excluir_subsede": {"gerenciar_subsedes"},
    "admin.informativos": {"criar_informativos", "gerenciar_fotos"},
    "admin.excluir_informativo": {"criar_informativos", "gerenciar_fotos"},
    "admin.eventos": {"gerenciar_eventos", "gerenciar_eventos_empreendedores"},
    "admin.excluir_evento": {"gerenciar_eventos", "gerenciar_eventos_empreendedores"},
    "admin.campanhas": {"gerenciar_campanhas"},
    "admin.excluir_campanha": {"gerenciar_campanhas"},
    "admin.feriados": {"gerenciar_feriados"},
    "admin.excluir_feriado": {"gerenciar_feriados"},
    "admin.congregados": {"gerenciar_congregados"},
    "admin.congregado": {"gerenciar_congregados"},
    "admin.congregados_csv": {"gerenciar_congregados"},
    "admin.comunicados": {"enviar_comunicados", "divulgar_empreendedores"},
    "admin.preparar_whatsapp": {"enviar_comunicados", "divulgar_empreendedores"},
    "admin.configuracoes": {"gerenciar_configuracoes"},
    "admin.equipe": None,
    "admin.equipe_item": None,
    "admin.excluir_equipe": None,
}

MENU = (
    ("admin.subsedes", "Subsedes", {"gerenciar_subsedes"}, ("admin.subsedes", "admin.excluir_subsede")),
    (
        "admin.informativos",
        "Informativos",
        {"criar_informativos", "gerenciar_fotos"},
        ("admin.informativos", "admin.excluir_informativo"),
    ),
    (
        "admin.eventos",
        "Eventos",
        {"gerenciar_eventos", "gerenciar_eventos_empreendedores"},
        ("admin.eventos", "admin.excluir_evento"),
    ),
    ("admin.campanhas", "Campanhas", {"gerenciar_campanhas"}, ("admin.campanhas", "admin.excluir_campanha")),
    ("admin.feriados", "Feriados", {"gerenciar_feriados"}, ("admin.feriados", "admin.excluir_feriado")),
    (
        "admin.congregados",
        "Congregados",
        {"gerenciar_congregados"},
        ("admin.congregados", "admin.congregado", "admin.congregados_csv"),
    ),
    (
        "admin.comunicados",
        "Comunicados",
        {"enviar_comunicados", "divulgar_empreendedores"},
        ("admin.comunicados", "admin.preparar_whatsapp"),
    ),
    ("admin.configuracoes", "Configurações", {"gerenciar_configuracoes"}, ("admin.configuracoes",)),
    ("admin.equipe", "Equipe", None, ("admin.equipe", "admin.equipe_item", "admin.excluir_equipe")),
)
