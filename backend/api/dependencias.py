"""Injeção de dependências: o ÚNICO lugar que liga o serviço à infra.

Variáveis de ambiente:
  ORDO_DB_URL           banco do sistema (padrão: database/sistema.sqlite3)
  ORDO_PROCEDIMENTOS    catálogo de procedimentos (padrão: procedimentos.csv na raiz do repo)
  ORDO_REDATOR=llm      liga o RedatorLLM (precisa de GEMINI_KEY); padrão: template
"""
import csv
import os
from functools import lru_cache
from pathlib import Path

from infra.db import URL_SISTEMA, fabrica_para
from infra.redator import RedatorLLM, RedatorTemplate
from infra.relogio import RelogioSQL
from infra.unidade_de_trabalho import UnidadeDeTrabalhoSQL
from servico.casos_uso import ServicoFila

RAIZ = Path(__file__).resolve().parents[2]


def carregar_catalogo(caminho: str | Path | None = None) -> dict[str, int]:
    """procedimento_id → risco_cirurgico (1–5)."""
    caminho = Path(caminho or os.environ.get("ORDO_PROCEDIMENTOS") or RAIZ / "procedimentos.csv")
    with open(caminho, encoding="utf-8") as f:
        return {p["procedimento_id"]: int(p["risco_cirurgico"]) for p in csv.DictReader(f)}


def criar_servico(url: str | None = None, catalogo: dict[str, int] | None = None) -> ServicoFila:
    fabrica = fabrica_para(url or os.environ.get("ORDO_DB_URL") or URL_SISTEMA)
    redator = RedatorLLM() if os.environ.get("ORDO_REDATOR") == "llm" else RedatorTemplate()
    return ServicoFila(lambda: UnidadeDeTrabalhoSQL(fabrica), RelogioSQL(fabrica), redator,
                       catalogo if catalogo is not None else carregar_catalogo())


@lru_cache
def obter_servico() -> ServicoFila:
    """Dependência do FastAPI. Os testes trocam por `app.dependency_overrides[obter_servico]`."""
    return criar_servico()
