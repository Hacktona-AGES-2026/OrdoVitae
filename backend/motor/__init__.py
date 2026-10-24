"""Motor de priorização: achados → avaliação (classe SWALIS, estado clínico) + risco → sugestões → fila."""
from .avaliacao import avaliar
from .decisor import EstadoAprovado, decidir
from .fila import ItemFila, critico, ordenar, prazos_estourados, prever_posicoes
from .risco import AvaliacaoRisco, avaliar_risco

__all__ = ["avaliar", "decidir", "ordenar", "prever_posicoes", "prazos_estourados", "critico", "EstadoAprovado", "ItemFila",
           "avaliar_risco", "AvaliacaoRisco"]
