"""Gera fila_priorizada.csv em 23/10/2026 com todas as sugestões auto-aprovadas (baseline p/ validar o motor)."""
import csv
import sys
from datetime import date

from extracao_rapida import NAO_CALMO, REF, carregar, cid

sys.path.insert(0, "../backend")
from motor import ItemFila, avaliar, ordenar  # noqa: E402
from motor.modelos import CodigoAchado as C, TipoSugestao  # noqa: E402
from motor.decisor import decidir  # noqa: E402


fila, _, achados = carregar()
itens, justificativas, removidos = [], {}, []
for s in fila:
    k = s["solicitacao_id"]
    av = avaliar(k, achados[k], REF, date.fromisoformat(s["data_entrada_fila"]))
    sugs = decidir(av, None, achados[k])
    if any(x.tipo == TipoSugestao.REMOVER for x in sugs):
        removidos.append(k)
        continue
    codigos = {a.codigo for a in achados[k]}
    itens.append(ItemFila(k, av.classe, av.ordo_clinico, date.fromisoformat(s["data_entrada_fila"]),
                          cid(s).startswith("C"), not (codigos & NAO_CALMO)))
    justificativas[k] = next(x.justificativa for x in sugs if x.tipo == TipoSugestao.CLASSIFICACAO_INICIAL)

saida = sys.argv[1] if len(sys.argv) > 1 else "fila_priorizada.csv"
with open(saida, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["solicitacao_id", "posicao", "justificativa"])
    for i in ordenar(itens, REF):
        w.writerow([i.solicitacao_id, i.posicao, justificativas[i.solicitacao_id]])
print(f"{len(itens)} na fila, {len(removidos)} removidos (saíram da fila) → {saida}")
