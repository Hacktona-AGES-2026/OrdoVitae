"""Injeção de dependências: o ÚNICO lugar que liga o serviço à infra.

Variáveis de ambiente:
  ORDO_DB_URL           banco do sistema (padrão: database/sistema.sqlite3)
  ORDO_PROCEDIMENTOS    catálogo de procedimentos (padrão: procedimentos.csv na raiz do repo)
  ORDO_REDATOR=llm      liga o RedatorLLM (DeepSeek; precisa de DEEPSEEK_API_KEY); padrão: template
Lidas também de backend/.env (copie backend/.env.example).
  SIMULADOR=1           liga as rotas de simulação que injetam o dataset (não é produção)
  ORDO_DATASET          banco do dataset para o simulador (padrão: database/ordovitae.sqlite3)
"""
import csv
import os
import threading
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends

from infra.db import URL_SISTEMA, fabrica_para
from infra.redator import RedatorLLM, RedatorTemplate
from infra.relogio import RelogioSQL
from infra.unidade_de_trabalho import UnidadeDeTrabalhoSQL
from servico.casos_uso import ServicoFila

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / "backend" / ".env")


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
def obter_fonte():
    from infra.fonte_dataset import CAMINHO_DATASET, FonteDataset
    return FonteDataset(os.environ.get("ORDO_DATASET") or CAMINHO_DATASET)


_trava_servico = threading.Lock()


@lru_cache
def _servico_unico() -> ServicoFila:
    return criar_servico()


def obter_servico() -> ServicoFila:
    """Dependência do FastAPI. Os testes trocam por `app.dependency_overrides[obter_servico]`.

    Com trava: as primeiras requisições chegam juntas (threadpool) e criariam o banco em paralelo."""
    with _trava_servico:
        return _servico_unico()


def obter_simulador(svc: Annotated[ServicoFila, Depends(obter_servico)]):
    """Dependência do FastAPI (só com SIMULADOR=1): simulador sobre o MESMO serviço da API."""
    from servico.simulador import Simulador
    return Simulador(svc, obter_fonte())
