"""Utilitários das spikes: carrega o dataset da raiz do repo e roda o extrator real (backend/extracao)."""
import csv
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from extracao import extrair_evento, extrair_solicitacao  # noqa: E402,F401
from motor import avaliar_risco  # noqa: E402
from motor.modelos import CodigoAchado as C  # noqa: E402

DATASET = Path(__file__).resolve().parents[1]
REF = date(2026, 10, 23)
NAO_CALMO = {C.CID_MALIGNO, C.CID_URGENTE, C.SINAL_ALARME, C.DOR_INTENSA, C.DOR_MODERADA, C.LIMITACAO_GRAVE,
             C.LIMITACAO_MODERADA, C.PRONTO_SOCORRO, C.INTERNACAO, C.BIOPSIA_POSITIVA, C.PROGRESSAO_IMAGEM,
             C.REAVALIACAO_PIORA}
DETERIORA = {C.PRONTO_SOCORRO, C.INTERNACAO, C.PROGRESSAO_IMAGEM, C.REAVALIACAO_PIORA, C.PIORA_RELATADA}


def ler(nome):
    with open(DATASET / nome, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cid(s):
    return s["cid_principal"].upper().replace(".", "").strip()


def carregar():
    fila = ler("fila_cirurgica.csv")
    eventos = ler("eventos_clinicos.csv")
    ids = {s["solicitacao_id"] for s in fila}
    achados = {s["solicitacao_id"]: extrair_solicitacao(s) for s in fila}
    for e in eventos:
        if e["solicitacao_id"] in ids:
            achados[e["solicitacao_id"]] += extrair_evento(e)
    return fila, eventos, achados


_RISCO_PROC: dict[str, int] = {}


def risco(s):
    """AvaliacaoRisco da solicitação (ASA × risco do procedimento)."""
    if not _RISCO_PROC:
        _RISCO_PROC.update({p["procedimento_id"]: int(p["risco_cirurgico"]) for p in ler("procedimentos.csv")})
    c = s["comorbidades"].strip().lower()
    n = 0 if c in ("", "nenhuma") else len(c.split(";"))
    asa = int(s["asa"]) if s["asa"].strip() else None
    return avaliar_risco(asa, n, _RISCO_PROC[s["procedimento_id"]])
