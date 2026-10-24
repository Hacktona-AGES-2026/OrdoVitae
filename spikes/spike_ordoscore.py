"""Spike: o que move pacientes na fila, quanta sugestão gera, e dá pra estimar 'probabilidade de piora'?"""
import collections as Cn
import statistics as st
import sys
from datetime import date, timedelta

from carga import DETERIORA, REF, carregar, cid

sys.path.insert(0, "../backend")
from motor import avaliar  # noqa: E402

fila, eventos, achados = carregar()
F = {s["solicitacao_id"]: s for s in fila}
entrada = {k: date.fromisoformat(s["data_entrada_fila"]) for k, s in F.items()}

print("== 1. Foto em 23/10/2026 ==")
avs = {k: avaliar(k, achados[k], REF, entrada[k]) for k in F}
por_classe = Cn.defaultdict(list)
for av in avs.values():
    por_classe[av.classe].append(av)
for c in ["A1", "A2", "B", "C", "D"]:
    l = por_classe[c]
    tot = [a.total for a in l]
    onco = sum(cid(F[a.solicitacao_id]).startswith("C") for a in l)
    print(f"{c}: {len(l):4d} pacientes | onco {onco:3d} | pontos min {min(tot):.1f} mediana {st.median(tot):.1f} max {max(tot):.1f}"
          f" | distintos {len(set(round(t, 1) for t in tot))}")

print("\n== 2. Replay: o que cada evento novo provoca (eventos após a entrada) ==")
evs_por_data = Cn.defaultdict(list)
for e in eventos:
    sid = e["solicitacao_id"]
    if sid in F and date.fromisoformat(e["data_evento"]) > entrada[sid]:
        evs_por_data[date.fromisoformat(e["data_evento"])].append(sid)
muda_classe, muda_pontos, nada = 0, Cn.Counter(), 0
por_semana = Cn.Counter()
for d, sids in sorted(evs_por_data.items()):
    for sid in set(sids):
        antes = avaliar(sid, achados[sid], d - timedelta(days=1), entrada[sid])
        depois = avaliar(sid, achados[sid], d, entrada[sid])
        delta = depois.total - antes.total
        if depois.classe != antes.classe:
            muda_classe += 1
            por_semana[d.isocalendar()[:2]] += 1
        elif abs(delta) >= 0.5:
            muda_pontos[round(delta)] += 1
            por_semana[d.isocalendar()[:2]] += 1
        else:
            nada += 1
print(f"dias com evento: {len(evs_por_data)}; mudam classe: {muda_classe}; mudam só pontos: {sum(muda_pontos.values())} {dict(sorted(muda_pontos.items()))}; sem efeito: {nada}")
ultimas = sorted(por_semana.items())[-12:]
print("sugestões por semana (últimas 12):", [n for _, n in ultimas])
entradas_sem = Cn.Counter(entrada[k].isocalendar()[:2] for k in F)
print("entradas novas por semana (últimas 12):", [entradas_sem[w] for w, _ in ultimas])
dias_evento = [(date.fromisoformat(e["data_evento"]) - entrada[e["solicitacao_id"]]).days for e in eventos if e["solicitacao_id"] in F]
print("eventos antes da entrada:", sum(d < 0 for d in dias_evento), "| depois:", sum(d >= 0 for d in dias_evento))
print("eventos nos últimos 180 dias antes de REF:", sum(1 for e in eventos if (REF - date.fromisoformat(e['data_evento'])).days <= 180))

print("\n== 3. Probabilidade empírica de piorar nos próximos 90 dias ==")
deter = Cn.defaultdict(list)
for k, l in achados.items():
    deter[k] = sorted(a.data_fato for a in l if a.codigo in DETERIORA and a.data_fato)
grupos = Cn.defaultdict(lambda: [0, 0])
for k in F:
    # amostra a cada 30 dias desde a entrada até REF-90 (pra ter janela futura completa)
    t = entrada[k]
    while t <= REF - timedelta(days=90):
        passado = [d for d in deter[k] if t - timedelta(days=90) < d <= t]
        futuro = any(t < d <= t + timedelta(days=90) for d in deter[k])
        av = avaliar(k, achados[k], t, entrada[k])
        onco = "onco" if cid(F[k]).startswith("C") else "nao_onco"
        for chave in [("piorou_90d", len(passado) > 0), ("n_pioras_90d", min(len(passado), 2)), ("classe", av.classe), ("onco", onco)]:
            g = grupos[chave]
            g[0] += futuro
            g[1] += 1
        t += timedelta(days=30)
for chave, (sim, n) in sorted(grupos.items(), key=lambda x: str(x[0])):
    print(f"{str(chave):32s} P(piora em 90d) = {sim / n:5.1%}  (n={n})")
