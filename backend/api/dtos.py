"""DTOs da API (Pydantic), separados das dataclasses do motor/serviço.

JSON em camelCase para casar com o front (`priorizacao.ts`: posicaoAnterior, diasEmFila, alemDoPrazo…).
"""
from datetime import date
from typing import Generic, TypeVar, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from motor import config
from motor.modelos import Achado
from servico.modelos import Alerta, FichaPaciente, LinhaFila, Simulacao, SugestaoRegistrada


class DTO(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _data(d: date | None) -> date | None:
    return None if d in (None, date.min) else d   # date.min = relógio ainda sem dia zero


# --- entrada ---------------------------------------------------------------------------

class EntradaIntegracao(DTO):
    dados: dict[str, Any]
    resposta_llm: list[dict[str, Any]] | None = None


class EntradaPularAte(DTO):
    data: date


class EntradaAvancarDia(DTO):
    dias: int = Field(1, ge=1, le=3650)


class EntradaSimulacao(DTO):
    auto_aprovar: bool


class EntradaRejeitar(DTO):
    comentario: str = ""


class EntradaDecisao(DTO):
    """PATCH /sugestoes/{id}: o regulador decide. Rejeitar exige comentário."""
    status: Literal["aprovada", "rejeitada"]
    comentario: str = ""


class EntradaPatchSimulacao(DTO):
    """PATCH /simulacao: muda o estado da simulação (campos ausentes ficam como estão)."""
    auto_aprovar: bool | None = None
    hoje: date | None = None                       # avança o relógio até esta data
    modo: Literal["passo", "rapido"] = "passo"     # passo: dia a dia com foto; rapido: aprovação automática, sem fotos


# --- saída -----------------------------------------------------------------------------

class AchadoDTO(DTO):
    codigo: str
    dimensao: str
    data_fato: date | None
    fonte: str
    ref: str
    trecho: str
    origem: str
    confianca: float

    @classmethod
    def de(cls, a: Achado) -> "AchadoDTO":
        return cls(codigo=a.codigo.value, dimensao=a.dimensao.value, data_fato=a.data_fato, fonte=a.evidencia.fonte,
                   ref=a.evidencia.ref, trecho=a.evidencia.trecho, origem=a.origem.value, confianca=a.confianca)


class PreviaDTO(DTO):
    posicao_de: int | None
    posicao_para: int | None
    score_de: float | None
    score_para: float | None


class SugestaoDTO(DTO):
    id: int
    solicitacao_id: str
    tipo: str
    status: str
    classe_de: str | None
    classe_para: str | None
    ordo_clinico_de: float | None
    ordo_clinico_para: float | None
    urgente: bool
    justificativa: str
    motivos: list[AchadoDTO]
    criada_em: date
    decidida_em: date | None
    decidida_por: str
    comentario: str
    previa: PreviaDTO | None = None
    ultrapassados: int = 0
    comparacao: list[dict] = []
    justificativa_comparativa: str = ""

    @classmethod
    def de(cls, r: SugestaoRegistrada) -> "SugestaoDTO":
        s = r.sugestao
        tem_previa = any(v is not None for v in (s.posicao_de, s.posicao_para, s.ordo_de, s.ordo_para))
        return cls(id=r.id, solicitacao_id=s.solicitacao_id, tipo=s.tipo.value, status=r.status.value,
                   classe_de=s.classe_de, classe_para=s.classe_para, ordo_clinico_de=s.ordo_clinico_de,
                   ordo_clinico_para=s.ordo_clinico_para, urgente=s.urgente, justificativa=s.justificativa,
                   motivos=[AchadoDTO.de(a) for a in s.motivos], criada_em=r.criada_em, decidida_em=r.decidida_em,
                   decidida_por=r.decidida_por, comentario=r.comentario,
                   previa=PreviaDTO(posicao_de=s.posicao_de, posicao_para=s.posicao_para,
                                    score_de=s.ordo_de, score_para=s.ordo_para) if tem_previa else None,
                   ultrapassados=s.ultrapassados, justificativa_comparativa=s.justificativa_comparativa,
                   comparacao=[{"solicitacaoId": c.solicitacao_id, "classe": c.classe, "score": c.score,
                                "componentes": c.componentes} for c in s.comparacao])


class RecebimentoDTO(DTO):
    sugestoes: list[SugestaoDTO]


class ItemFilaDTO(DTO):
    solicitacao_id: str
    posicao: int
    posicao_anterior: int | None
    classe: str
    score: float
    dias_em_fila: int
    prazo: int
    alem_do_prazo: int
    score_clinico: float | None = None
    ordo_clinico: float | None = None
    risco: float | None = None
    risco_motivo: str | None = None
    asa_estimado: bool | None = None
    oncologico: bool | None = None
    provisorio: bool | None = None
    critico: bool | None = None

    @classmethod
    def de(cls, l: LinhaFila) -> "ItemFilaDTO":
        prazo = config.PRAZO_DIAS[l.classe]
        return cls(**vars(l), prazo=prazo, alem_do_prazo=max(0, l.dias_em_fila - prazo))


T = TypeVar("T")


class PaginaDTO(DTO, Generic[T]):
    """Envelope de coleção: itens da página + total da coleção (com os filtros), limite e offset."""
    itens: list[T]
    total: int
    limite: int
    offset: int

    @classmethod
    def de(cls, pagina, conv) -> "PaginaDTO":
        return cls(itens=[conv(x) for x in pagina], total=pagina.total, limite=pagina.limite, offset=pagina.offset)


class DiaFilaDTO(DTO):
    """Fila de um dia, paginada. `ordem` mantém o nome que o front já usa."""
    data: date | None
    ordem: list[ItemFilaDTO]
    total: int
    limite: int
    offset: int


class PosicaoHistoricoDTO(DTO):
    data: date
    posicao: int
    score: float


class FichaDTO(DTO):
    solicitacao_id: str
    dados: dict[str, Any]
    ativa: bool
    classe: str
    ordo_clinico: float
    provisorio: bool
    risco: float
    risco_motivo: str
    posicao: int | None
    achados: list[AchadoDTO]
    historico: list[PosicaoHistoricoDTO]
    sugestoes: list[SugestaoDTO]

    @classmethod
    def de(cls, f: FichaPaciente) -> "FichaDTO":
        return cls(solicitacao_id=f.solicitacao_id, dados=f.dados, ativa=f.ativa, classe=f.classe,
                   ordo_clinico=f.ordo_clinico, provisorio=f.provisorio, risco=f.risco, risco_motivo=f.risco_motivo,
                   posicao=f.posicao, achados=[AchadoDTO.de(a) for a in f.achados],
                   historico=[PosicaoHistoricoDTO(data=d, posicao=p, score=s) for d, p, s in f.historico],
                   sugestoes=[SugestaoDTO.de(r) for r in f.sugestoes])


class AlertaDTO(DTO):
    tipo: str
    solicitacao_id: str
    detalhe: str
    sugestao_id: int | None

    @classmethod
    def de(cls, a: Alerta) -> "AlertaDTO":
        return cls(**vars(a))


class ItemDecisaoDTO(DTO):
    codigo: str
    categoria: str
    nivel_atencao: str
    titulo: str
    descricao_medica: str
    recomendacao_conduta: str
    trecho_evidencia: str
    fonte: str
    valido_para_decisao: bool
    conflito_clinico: str


class DecisaoCompartilhadaDTO(DTO):
    """Motor secundário (decisão compartilhada médico–paciente), calculado com os dados recebidos até hoje."""
    solicitacao_id: str
    data_referencia: date | None
    elegivel_decisao_compartilhada: bool
    status_adesao: str
    nivel_atencao_maximo: str
    tem_conflito_clinico: bool
    resumo_medico: str
    usou_llm: bool
    itens: list[ItemDecisaoDTO]

    @classmethod
    def de(cls, av, usou_llm: bool, hoje: date | None) -> "DecisaoCompartilhadaDTO":
        d = av.to_dict()
        return cls(solicitacao_id=d["solicitacao_id"], data_referencia=_data(hoje),
                   elegivel_decisao_compartilhada=d["elegivel_decisao_compartilhada"], status_adesao=d["status_adesao"],
                   nivel_atencao_maximo=d["nivel_atencao_maximo"], tem_conflito_clinico=d["tem_conflito_clinico"],
                   resumo_medico=d["resumo_medico"], usou_llm=usou_llm, itens=[ItemDecisaoDTO(**i) for i in d["itens"]])


class SimulacaoDTO(DTO):
    hoje: date | None
    auto_aprovar: bool

    @classmethod
    def de(cls, s: Simulacao) -> "SimulacaoDTO":
        return cls(hoje=_data(s.hoje), auto_aprovar=s.auto_aprovar)


class ErroDTO(DTO):
    erro: str
    detalhe: str
