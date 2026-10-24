"""Motor Secundário: Decisão Compartilhada, Adesão e Gestão Manual do Paciente.

Módulo 100% isolado do `backend/motor` principal para não interferir na ordenação
SWALIS nem quebrar contratos existentes. Consome os dados da solicitação, eventos
clínicos e achados extraídos pela LLM (`achados_llm`) para identificar fatores
decisivos na relação médico-paciente (adesão medicamentosa, resposta ao tratamento
conservador, preferências de janela cirúrgica e barreiras sociais/logísticas).
"""
from .modelos import (
    AvaliacaoDecisaoCompartilhada,
    CategoriaDecisao,
    CodigoDecisao,
    ItemDecisaoCompartilhada,
    NivelAtencaoMedica,
    StatusAdesao,
)
from .heuristica import avaliar_decisao_compartilhada, avaliar_lote_sqlite

__all__ = [
    "AvaliacaoDecisaoCompartilhada",
    "CategoriaDecisao",
    "CodigoDecisao",
    "ItemDecisaoCompartilhada",
    "NivelAtencaoMedica",
    "StatusAdesao",
    "avaliar_decisao_compartilhada",
    "avaliar_lote_sqlite",
]
