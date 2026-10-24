"""Tabelas do banco do sistema (database/sistema.sqlite3). Enums como texto (`.value`), datas como Date."""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SolicitacaoORM(Base):
    __tablename__ = "solicitacoes"
    solicitacao_id: Mapped[str] = mapped_column(String, primary_key=True)
    paciente_id: Mapped[str | None] = mapped_column(String, index=True)
    procedimento_id: Mapped[str | None] = mapped_column(String)
    data_entrada: Mapped[date] = mapped_column(Date)
    dados: Mapped[dict] = mapped_column(JSON)                 # registro bruto, como chegou
    recebida_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class EventoORM(Base):
    __tablename__ = "eventos"
    evento_id: Mapped[str] = mapped_column(String, primary_key=True)
    solicitacao_id: Mapped[str | None] = mapped_column(String, index=True)
    tipo_evento: Mapped[str | None] = mapped_column(String)
    data_evento: Mapped[date | None] = mapped_column(Date)
    dados: Mapped[dict] = mapped_column(JSON)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class AchadoORM(Base):
    __tablename__ = "achados"
    __table_args__ = (UniqueConstraint("solicitacao_id", "chave", name="uq_achado_chave"),)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solicitacao_id: Mapped[str] = mapped_column(String, index=True)
    chave: Mapped[str] = mapped_column(String)                 # = Achado.id
    codigo: Mapped[str] = mapped_column(String)
    dimensao: Mapped[str] = mapped_column(String)
    data_fato: Mapped[date | None] = mapped_column(Date)
    fonte: Mapped[str] = mapped_column(String)
    ref: Mapped[str] = mapped_column(String)
    trecho: Mapped[str] = mapped_column(Text, default="")
    origem: Mapped[str] = mapped_column(String)
    confianca: Mapped[float] = mapped_column(Float, default=1.0)


class EstadoORM(Base):
    __tablename__ = "estados"
    solicitacao_id: Mapped[str] = mapped_column(String, primary_key=True)
    classe: Mapped[str] = mapped_column(String)
    ordo_clinico: Mapped[float] = mapped_column(Float)
    provisorio: Mapped[bool]
    risco_valor: Mapped[float] = mapped_column(Float)
    asa: Mapped[int]
    asa_estimado: Mapped[bool]
    nivel_paciente: Mapped[str] = mapped_column(String)
    nivel_procedimento: Mapped[str] = mapped_column(String)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    atualizado_por: Mapped[str | None] = mapped_column(String)


class SugestaoORM(Base):
    __tablename__ = "sugestoes"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    solicitacao_id: Mapped[str] = mapped_column(String, index=True)
    tipo: Mapped[str] = mapped_column(String)
    classe_de: Mapped[str | None] = mapped_column(String)
    classe_para: Mapped[str | None] = mapped_column(String)
    ordo_clinico_de: Mapped[float | None] = mapped_column(Float)
    ordo_clinico_para: Mapped[float | None] = mapped_column(Float)
    urgente: Mapped[bool] = mapped_column(default=False)
    justificativa: Mapped[str] = mapped_column(Text)
    motivos: Mapped[list] = mapped_column(JSON)               # achados serializados por inteiro
    status: Mapped[str] = mapped_column(String, index=True)
    criada_em: Mapped[date] = mapped_column(Date)
    decidida_em: Mapped[date | None] = mapped_column(Date)
    decidida_por: Mapped[str] = mapped_column(String, default="")
    comentario: Mapped[str] = mapped_column(Text, default="")


class SaidaORM(Base):
    __tablename__ = "saidas"
    solicitacao_id: Mapped[str] = mapped_column(String, primary_key=True)
    motivo: Mapped[str] = mapped_column(String)
    justificativa: Mapped[str] = mapped_column(Text)
    em: Mapped[date] = mapped_column(Date)
    sugestao_id: Mapped[int | None] = mapped_column(ForeignKey("sugestoes.id"))


class HistoricoFilaORM(Base):
    __tablename__ = "historico_fila"
    __table_args__ = (Index("ix_historico_sid", "solicitacao_id"),)
    data: Mapped[date] = mapped_column(Date, primary_key=True)
    solicitacao_id: Mapped[str] = mapped_column(String, primary_key=True)
    posicao: Mapped[int]
    score: Mapped[float] = mapped_column(Float)
    classe: Mapped[str] = mapped_column(String)


class AuditoriaORM(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    em: Mapped[date] = mapped_column(Date)
    acao: Mapped[str] = mapped_column(String)
    solicitacao_id: Mapped[str] = mapped_column(String, index=True)
    detalhe: Mapped[str] = mapped_column(Text)
    por: Mapped[str] = mapped_column(String)


class SimulacaoORM(Base):
    __tablename__ = "simulacao"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)   # linha única
    hoje: Mapped[date | None] = mapped_column(Date)
    auto_aprovar: Mapped[bool] = mapped_column(default=False)
