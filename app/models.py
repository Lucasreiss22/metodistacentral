"""Tabelas do site. O banco em produção nasce do supabase/schema.sql.

Os tipos ficam compatíveis com SQLite para os testes não precisarem do Supabase.
"""

from sqlalchemy import CheckConstraint, Index, text

from app.extensions import db
from app.utils import agora_utc, gerar_token_descadastro


class Subsede(db.Model):
    """Sede ou igreja filiada. Só uma linha pode ter eh_sede verdadeiro."""

    __tablename__ = "subsedes"
    __table_args__ = (
        Index(
            "idx_subsedes_uma_sede",
            "eh_sede",
            unique=True,
            postgresql_where=text("eh_sede IS TRUE"),
            sqlite_where=text("eh_sede = 1"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    endereco = db.Column(db.Text, nullable=False, default="")
    bairro = db.Column(db.Text, nullable=False, default="")
    cidade = db.Column(db.Text, nullable=False)
    uf = db.Column(db.Text, nullable=False)
    cep = db.Column(db.Text, nullable=False, default="")
    telefone = db.Column(db.Text, nullable=False, default="")
    whatsapp = db.Column(db.Text, nullable=False, default="")
    email = db.Column(db.Text, nullable=False, default="")
    instagram_url = db.Column(db.Text, nullable=False, default="")
    pastor_responsavel = db.Column(db.Text, nullable=False, default="")
    horarios_culto = db.Column(db.Text, nullable=False, default="")
    mapa_url = db.Column(db.Text, nullable=False, default="")
    imagem_url = db.Column(db.Text, nullable=False, default="")
    eh_sede = db.Column(db.Boolean, nullable=False, default=False)
    ativa = db.Column(db.Boolean, nullable=False, default=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    congregados = db.relationship("Congregado", back_populates="subsede")
    campanhas = db.relationship("Campanha", back_populates="subsede")
    eventos = db.relationship("Evento", back_populates="subsede")

    def __repr__(self) -> str:
        return f"<Subsede {self.id}>"


class Congregado(db.Model):
    """Pessoa cadastrada em "Seja um congregado".

    O e-mail é gravado em minúsculas. O índice único usa lower(email)
    para o banco também recusar duplicata com maiúsculas.
    """

    __tablename__ = "congregados"
    __table_args__ = (
        Index("idx_congregados_email_lower", text("lower(email)"), unique=True),
        Index("idx_congregados_subsede_id", "subsede_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    email = db.Column(db.Text, nullable=False)
    whatsapp = db.Column(db.Text, nullable=False)
    subsede_id = db.Column(
        db.Integer,
        db.ForeignKey("subsedes.id", ondelete="SET NULL"),
        nullable=True,
    )
    recebe_noticias = db.Column(db.Boolean, nullable=False, default=True)
    token_descadastro = db.Column(
        db.Text,
        nullable=False,
        unique=True,
        default=gerar_token_descadastro,
    )
    data_cadastro = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    subsede = db.relationship("Subsede", back_populates="congregados")

    def __repr__(self) -> str:
        return f"<Congregado {self.id}>"


class Campanha(db.Model):
    """Campanha de arrecadação. A meta pode ser em reais ou em unidades."""

    __tablename__ = "campanhas"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ativa', 'encerrada')",
            name="ck_campanhas_status",
        ),
        CheckConstraint("meta >= 0 AND arrecadado >= 0", name="ck_campanhas_valores"),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.Text, nullable=False, default="")
    meta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    arrecadado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    unidade = db.Column(db.Text, nullable=False, default="R$")
    status = db.Column(db.Text, nullable=False, default="ativa")
    imagem_url = db.Column(db.Text, nullable=False, default="")
    data_inicio = db.Column(db.Date, nullable=True)
    data_fim = db.Column(db.Date, nullable=True)
    subsede_id = db.Column(
        db.Integer,
        db.ForeignKey("subsedes.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)
    atualizado_em = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=agora_utc,
        onupdate=agora_utc,
    )

    subsede = db.relationship("Subsede", back_populates="campanhas")

    def __repr__(self) -> str:
        return f"<Campanha {self.id}>"


class Evento(db.Model):
    """Culto, reunião ou atividade que aparece no calendário."""

    __tablename__ = "eventos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ativo', 'encerrado', 'cancelado')",
            name="ck_eventos_status",
        ),
        Index("idx_eventos_data_evento", "data_evento"),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text, nullable=False)
    descricao = db.Column(db.Text, nullable=False, default="")
    data_evento = db.Column(db.DateTime(timezone=True), nullable=False)
    data_fim = db.Column(db.DateTime(timezone=True), nullable=True)
    dia_inteiro = db.Column(db.Boolean, nullable=False, default=False)
    local = db.Column(db.Text, nullable=False, default="")
    subsede_id = db.Column(
        db.Integer,
        db.ForeignKey("subsedes.id", ondelete="SET NULL"),
        nullable=True,
    )
    imagem_url = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.Text, nullable=False, default="ativo")
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    subsede = db.relationship("Subsede", back_populates="eventos")

    def __repr__(self) -> str:
        return f"<Evento {self.id}>"


class Informativo(db.Model):
    """Banner, foto, vídeo ou aviso editável da página inicial."""

    __tablename__ = "informativos"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('banner', 'foto', 'video', 'aviso')",
            name="ck_informativos_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.Text, nullable=False)
    tipo = db.Column(db.Text, nullable=False)
    conteudo_url = db.Column(db.Text, nullable=False, default="")
    texto = db.Column(db.Text, nullable=False, default="")
    link_url = db.Column(db.Text, nullable=False, default="")
    destaque = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    ordem = db.Column(db.Integer, nullable=False, default=0)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    def __repr__(self) -> str:
        return f"<Informativo {self.id}>"


class FeriadoLocal(db.Model):
    """Feriado estadual, municipal ou ponto facultativo editável pelo admin.

    ano vazio significa que a data vale todo ano. Os feriados nacionais
    não ficam nesta tabela: são calculados no código.
    """

    __tablename__ = "feriados_locais"
    __table_args__ = (
        CheckConstraint("dia >= 1 AND dia <= 31", name="ck_feriados_locais_dia"),
        CheckConstraint("mes >= 1 AND mes <= 12", name="ck_feriados_locais_mes"),
        CheckConstraint("ano IS NULL OR ano >= 1900", name="ck_feriados_locais_ano"),
        CheckConstraint(
            "tipo IN ('estadual', 'municipal', 'ponto_facultativo')",
            name="ck_feriados_locais_tipo",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.Text, nullable=False)
    dia = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)
    ano = db.Column(db.Integer, nullable=True)
    tipo = db.Column(db.Text, nullable=False)

    def __repr__(self) -> str:
        return f"<FeriadoLocal {self.id}>"


class Configuracao(db.Model):
    """Textos e links públicos do site. Existe uma linha só, com id = 1."""

    __tablename__ = "configuracoes"
    __table_args__ = (CheckConstraint("id = 1", name="ck_configuracoes_id"),)

    id = db.Column(db.Integer, primary_key=True)
    nome_igreja = db.Column(db.Text, nullable=False)
    slogan = db.Column(db.Text, nullable=False, default="")
    instagram_url = db.Column(db.Text, nullable=False, default="")
    instagram_usuario = db.Column(db.Text, nullable=False, default="")
    youtube_url = db.Column(db.Text, nullable=False, default="")
    facebook_url = db.Column(db.Text, nullable=False, default="")
    whatsapp = db.Column(db.Text, nullable=False, default="")
    email_contato = db.Column(db.Text, nullable=False, default="")
    endereco = db.Column(db.Text, nullable=False, default="")
    sobre = db.Column(db.Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<Configuracao {self.id}>"


class Administrador(db.Model):
    """Quem pode entrar no painel. A senha fica no Supabase Auth, não aqui."""

    __tablename__ = "administradores"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    nome = db.Column(db.Text, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    def __repr__(self) -> str:
        return f"<Administrador {self.id}>"


class Comunicado(db.Model):
    """Histórico de um disparo de e-mail ou do preparo de WhatsApp."""

    __tablename__ = "comunicados"
    __table_args__ = (
        CheckConstraint(
            "canal IN ('email', 'whatsapp')",
            name="ck_comunicados_canal",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    canal = db.Column(db.Text, nullable=False)
    assunto = db.Column(db.Text, nullable=False, default="")
    mensagem = db.Column(db.Text, nullable=False, default="")
    evento_id = db.Column(
        db.Integer,
        db.ForeignKey("eventos.id", ondelete="SET NULL"),
        nullable=True,
    )
    campanha_id = db.Column(
        db.Integer,
        db.ForeignKey("campanhas.id", ondelete="SET NULL"),
        nullable=True,
    )
    subsede_id = db.Column(
        db.Integer,
        db.ForeignKey("subsedes.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_destinatarios = db.Column(db.Integer, nullable=False, default=0)
    total_enviados = db.Column(db.Integer, nullable=False, default=0)
    erro = db.Column(db.Text, nullable=True)
    enviado_por = db.Column(db.Text, nullable=False, default="")
    enviado_em = db.Column(db.DateTime(timezone=True), nullable=False, default=agora_utc)

    def __repr__(self) -> str:
        return f"<Comunicado {self.id}>"
