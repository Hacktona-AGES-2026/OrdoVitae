"""Fonte do simulador: lê o dataset (database/ordovitae.sqlite3) e entrega as chegadas de cada dia.

Só existe para a simulação (SIMULADOR=1). Em produção, os dados chegam pelas rotas /integracao/*.
Regras das chegadas (as mesmas de scripts/replay_servico.py):
  - solicitação chega em data_entrada_fila, SEM observacoes (não vaza informação futura);
  - evento anterior à entrada fica segurado e chega no dia da entrada;
  - observação vira evento tipo_evento="observacao", junto do último evento do paciente
    (sem eventos: no último dia);
  - dentro do dia: solicitações → eventos → observações;
  - resposta_llm vem da tabela extracoes_llm, quando existir.
"""
import collections
import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CAMINHO_DATASET = Path(__file__).resolve().parents[2] / "database" / "ordovitae.sqlite3"
REF = date(2026, 10, 23)   # data de referência do dataset


@dataclass(frozen=True)
class Chegada:
    tipo: str                         # "solicitacao" | "evento"
    dados: dict
    resposta_llm: list[dict] | None


class FonteDataset:
    def __init__(self, caminho: str | Path = CAMINHO_DATASET, ref: date = REF):
        self.ref = ref
        with sqlite3.connect(caminho) as con:
            con.row_factory = sqlite3.Row
            fila = [_como_texto(r) for r in con.execute("SELECT * FROM fila_cirurgica")]
            eventos = [_como_texto(r) for r in con.execute("SELECT * FROM eventos_clinicos")]
            llm = _respostas_llm(con)
        self._por_dia = _montar_chegadas(fila, eventos, llm, ref)

    def chegadas(self, dia: date) -> list[Chegada]:
        return self._por_dia.get(dia, [])

    def primeira_data(self) -> date:
        return min(self._por_dia)

    def dias_com_chegada(self) -> list[date]:
        return sorted(self._por_dia)


def _como_texto(linha: sqlite3.Row) -> dict:
    """Mesmo formato do CSV: tudo string, vazio no lugar de NULL."""
    return {k: "" if linha[k] is None else str(linha[k]) for k in linha.keys()}


def _respostas_llm(con: sqlite3.Connection) -> dict[str, list[dict]]:
    existe = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='extracoes_llm'").fetchone()
    if not existe:
        return {}
    respostas = {}
    for ref, resposta in con.execute("SELECT ref, resposta_json FROM extracoes_llm"):
        try:
            itens = json.loads(resposta or "[]")
        except json.JSONDecodeError:
            continue
        if itens:
            respostas[ref] = itens
    return respostas


def _montar_chegadas(fila: list[dict], eventos: list[dict], llm: dict[str, list[dict]], ref: date) -> dict[date, list[Chegada]]:
    entrada = {s["solicitacao_id"]: date.fromisoformat(s["data_entrada_fila"]) for s in fila}
    ultimo_evento: dict[str, date] = {}
    for e in eventos:
        d = date.fromisoformat(e["data_evento"])
        ultimo_evento[e["solicitacao_id"]] = max(ultimo_evento.get(e["solicitacao_id"], d), d)

    sols, evs, obs = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    for s in fila:
        sid = s["solicitacao_id"]
        texto_obs = s["observacoes"].strip()
        dados = dict(s, observacoes="")
        sols[entrada[sid]].append(Chegada("solicitacao", dados, llm.get(f"{sid}:justificativa_clinica")))
        if texto_obs:
            dia = max(ultimo_evento.get(sid, ref), entrada[sid])
            evento = {"evento_id": f"OBS-{sid}", "solicitacao_id": sid, "paciente_id": s["paciente_id"],
                      "data_evento": dia.isoformat(), "tipo_evento": "observacao", "resultado": "",
                      "valor_numerico": "", "descricao": texto_obs, "origem": "observacoes"}
            obs[dia].append(Chegada("evento", evento, llm.get(f"{sid}:observacoes")))
    for e in eventos:
        d = date.fromisoformat(e["data_evento"])
        dia = max(d, entrada.get(e["solicitacao_id"], d))
        evs[dia].append(Chegada("evento", e, llm.get(e["evento_id"])))

    dias = set(sols) | set(evs) | set(obs)
    return {d: sols[d] + evs[d] + obs[d] for d in dias}
