"""Modelos próprios do serviço: o ciclo de vida de uma sugestão do motor."""
from dataclasses import dataclass
from datetime import date
from enum import Enum

from motor.modelos import Achado, Sugestao


class StatusSugestao(str, Enum):
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    SUBSTITUIDA = "substituida"   # chegou evento novo do mesmo paciente antes da decisão


@dataclass
class SugestaoRegistrada:
    """`Sugestao` do motor + o que acontece com ela no serviço (composição, não herança)."""
    id: int
    sugestao: Sugestao
    status: StatusSugestao
    criada_em: date
    decidida_em: date | None = None
    decidida_por: str = ""
    comentario: str = ""

    @property
    def solicitacao_id(self) -> str:
        return self.sugestao.solicitacao_id


class MotivoSaida(str, Enum):
    DESISTENCIA = "desistencia"
    OUTRO_SERVICO = "outro_servico"
    DUPLICATA = "duplicata"


@dataclass
class LinhaFila:
    """Uma posição da fila. Na fila do dia todos os campos vêm; numa foto antiga, só os da foto."""
    solicitacao_id: str
    posicao: int
    posicao_anterior: int | None
    classe: str
    score: float
    dias_em_fila: int
    score_clinico: float | None = None
    ordo_clinico: float | None = None
    risco: float | None = None
    risco_motivo: str | None = None
    asa_estimado: bool | None = None
    oncologico: bool | None = None
    provisorio: bool | None = None
    critico: bool | None = None


@dataclass
class FichaPaciente:
    solicitacao_id: str
    dados: dict
    ativa: bool
    classe: str
    ordo_clinico: float
    provisorio: bool
    risco: float
    risco_motivo: str
    posicao: int | None
    achados: list[Achado]
    historico: list[tuple[date, int, float]]
    sugestoes: list[SugestaoRegistrada]


@dataclass
class Alerta:
    tipo: str               # hba1c_descontrolada | perda_contato | dados_insuficientes | sem_asa | critico | prazo_estourado
    solicitacao_id: str
    detalhe: str
    sugestao_id: int | None = None


@dataclass
class Simulacao:
    hoje: date
    auto_aprovar: bool
