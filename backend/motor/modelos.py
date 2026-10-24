"""Contratos do motor.

`Achado` é a fronteira com o módulo de extração: a extração produz achados,
o motor só consome achados (nunca lê texto livre nem chama LLM).
"""
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Dimensao(str, Enum):
    GRAVIDADE = "gravidade"        # como o paciente está (base, não decai com o tempo)
    DETERIORACAO = "deterioracao"  # para onde está indo (decai com o tempo)
    ALERTA = "alerta"              # não pontua; vira aviso para o regulador


class CodigoAchado(str, Enum):
    # gravidade
    CID_MALIGNO = "CID_MALIGNO"              # CID C*
    CID_SUSPEITO = "CID_SUSPEITO"            # D37–D48, R91
    CID_URGENTE = "CID_URGENTE"              # obstrução/estrangulamento/angina instável…
    BIOPSIA_POSITIVA = "BIOPSIA_POSITIVA"
    SINAL_ALARME = "SINAL_ALARME"            # icterícia, perda ponderal, sangramento… (texto)
    DOR_INTENSA = "DOR_INTENSA"              # EVA >= 7
    DOR_MODERADA = "DOR_MODERADA"            # EVA 4–6
    LIMITACAO_GRAVE = "LIMITACAO_GRAVE"
    LIMITACAO_MODERADA = "LIMITACAO_MODERADA"
    # deterioração
    INTERNACAO = "INTERNACAO"
    PRONTO_SOCORRO = "PRONTO_SOCORRO"
    PROGRESSAO_IMAGEM = "PROGRESSAO_IMAGEM"
    REAVALIACAO_PIORA = "REAVALIACAO_PIORA"
    PIORA_RELATADA = "PIORA_RELATADA"        # telefone, observação, texto
    HBA1C_DESCONTROLADA = "HBA1C_DESCONTROLADA"  # HbA1c > 8,5
    MELHORA = "MELHORA"                      # reavaliação com melhora, relata melhora
    # alertas (0 pontos)
    PERDA_CONTATO = "PERDA_CONTATO"          # não atendeu, faltas
    SAIU_DA_FILA = "SAIU_DA_FILA"            # desistiu, operou em outro serviço
    OTIMIZAR_CLINICAMENTE = "OTIMIZAR_CLINICAMENTE"  # ex.: HbA1c alta antes de cirurgia
    DADOS_INSUFICIENTES = "DADOS_INSUFICIENTES"      # justificativa pobre


class Origem(str, Enum):
    REGRA = "regra"
    LLM = "llm"


@dataclass(frozen=True)
class Evidencia:
    fonte: str             # "evento" | "solicitacao" | "observacao"
    ref: str               # evento_id ou "SOL-…:justificativa_clinica"
    trecho: str = ""       # texto que sustenta o achado (obrigatório quando origem = LLM)


@dataclass(frozen=True)
class Achado:
    codigo: CodigoAchado
    dimensao: Dimensao
    solicitacao_id: str
    data_fato: date | None     # quando aconteceu; None se o texto não diz
    evidencia: Evidencia
    origem: Origem = Origem.REGRA
    confianca: float = 1.0

    @property
    def id(self) -> str:
        return f"{self.codigo.value}:{self.evidencia.ref}:{self.data_fato or '-'}"


@dataclass
class Contribuicao:
    achado: Achado
    pontos: float              # já com decaimento aplicado


@dataclass
class Avaliacao:
    """Estado clínico de uma solicitação numa data. Saída da etapa 1."""
    solicitacao_id: str
    data_ref: date
    gravidade: float
    deterioracao: float
    classe: str                         # A1, A2, B, C, D
    motivo_classe: str                  # "piso: oncológico", "limiar: total 7.0 >= 6"…
    p_piora: float                      # P(piora em 90 dias), tabela empírica
    ordo_clinico: float                 # 0–100, parte clínica do OrdoScore (sem prazo)
    contribuicoes: list[Contribuicao] = field(default_factory=list)
    alertas: list[Achado] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.gravidade + self.deterioracao


class TipoSugestao(str, Enum):
    CLASSIFICACAO_INICIAL = "classificacao_inicial"
    SUBIR = "subir"
    DESCER = "descer"
    REMOVER = "remover"
    ALERTA = "alerta"


@dataclass
class Sugestao:
    """Saída da etapa 2. O regulador aprova/rejeita; aprovar = aplicar `classe_para`."""
    solicitacao_id: str
    tipo: TipoSugestao
    classe_de: str | None
    classe_para: str | None
    motivos: list[Achado]
    justificativa: str
    urgente: bool = False
    ordo_clinico_de: float | None = None
    ordo_clinico_para: float | None = None
    # preenchidas por fila.prever_posicoes (OrdoScore final, com prazo, na data de referência)
    ordo_de: float | None = None
    ordo_para: float | None = None
    posicao_de: int | None = None
    posicao_para: int | None = None
