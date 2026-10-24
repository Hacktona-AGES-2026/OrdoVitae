"""Gera a tabela P_PIORA do motor/config.py: P(evento de piora nos próximos 90 dias)
dado o nº de pioras nos últimos 90 dias (0, 1, 2+).
Oncológico ficou de fora: células com n < 10, e o CID já pesa nos pontos clínicos. Amostra cada solicitação a cada 30 dias."""
import collections as Cn
from datetime import timedelta

from carga import DETERIORA, REF, carregar, date

fila, _, achados = carregar()
g = Cn.defaultdict(lambda: [0, 0])
for s in fila:
    k = s["solicitacao_id"]
    datas = sorted(a.data_fato for a in achados[k] if a.codigo in DETERIORA and a.data_fato)
    t = date.fromisoformat(s["data_entrada_fila"])
    while t <= REF - timedelta(days=90):
        n = min(sum(t - timedelta(days=90) < d <= t for d in datas), 2)
        g[n][0] += any(t < d <= t + timedelta(days=90) for d in datas)
        g[n][1] += 1
        t += timedelta(days=30)
print("P_PIORA = {")
for chave in sorted(g):
    sim, n = g[chave]
    print(f"    {chave}: {sim / n:.3f},  # n={n}")
print("}")
