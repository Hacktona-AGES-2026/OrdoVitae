"""Motor de priorização: achados → avaliação (classe SWALIS) → sugestões → fila."""
from .avaliacao import avaliar
from .decisor import decidir
from .fila import ItemFila, ordenar

__all__ = ["avaliar", "decidir", "ordenar", "ItemFila"]
