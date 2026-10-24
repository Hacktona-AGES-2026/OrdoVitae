"""Replay dia a dia: solicitações e eventos chegam na ordem do tempo, sugestões auto-aprovadas.
Mede: regra de ouro em todo dia, sugestões/dia, trajetória do paciente da demo e o 'envelhecimento'
do estado aprovado (aprovado × reavaliado do zero em 23/10/2026)."""
import collections as Cn
import statistics as st
import sys
from datetime import date

from extracao_rapida import NAO_CALMO, REF, carregar, cid, extrair_evento, extrair_solicitacao

sys.path.insert(0, "../backend")
from motor import EstadoAprovado, ItemFila, avaliar, decidir, ordenar, prazos_estourados  # noqa: E402
from motor.fila import aplicar_regra_de_ouro  # noqa: E402
from motor.modelos import CodigoAchado as C, TipoSugestao as T  # noqa: E402

DEMO = sys.argv[1] if len(sys.argv) > 1 else "SOL-2025-00146"
fila, eventos, _ = carregar()
F = {s["solicitacao_id"]: s for s in fila}
entrada = {k: date.fromisoformat(s["data_entrada_fila"]) for k, s in F.items()}

# linha do tempo: (data, tipo, id) — evento anterior à entrada é segurado até a entrada
chegadas = Cn.defaultdict(list)
for k, d in entrada.items():
    chegadas[d].append(("sol", k, extrair_solicitacao(F[k])))
for e in eventos:
    k = e["solicitacao_id"]
    if k not in F:
        continue
    d = max(date.fromisoformat(e["data_evento"]), entrada[k])
    chegadas[d].append(("ev", k, extrair_evento(e)))

achados = Cn.defaultdict(list)
aprovado: dict[str, EstadoAprovado] = {}
aprovado_alguma_vez: set[str] = set()
itens: dict[str, ItemFila] = {}
sug_por_dia = Cn.Counter()
tipos = Cn.Counter()
trava_agiu = 0
traj = []
pior = (0, None, [])

for d in sorted(chegadas):
    novos_por_sol = Cn.defaultdict(list)
    for tipo, k, achs in sorted(chegadas[d], key=lambda x: x[0] != "sol"):  # solicitação antes dos eventos
        achados[k] += achs
        novos_por_sol[k] += achs
    for k, novos in novos_por_sol.items():
        if k not in itens and k in aprovado_alguma_vez:
            continue  # evento de quem já saiu da fila
        av = avaliar(k, achados[k], d, entrada[k])
        for s in decidir(av, aprovado.get(k), novos):
            tipos[s.tipo] += 1
            sug_por_dia[d] += 1
            if s.tipo == T.REMOVER:
                itens.pop(k, None)
                aprovado.pop(k, None)
            elif s.tipo in (T.CLASSIFICACAO_INICIAL, T.SUBIR, T.DESCER):
                aprovado[k] = EstadoAprovado(s.classe_para, s.ordo_clinico_para)
                aprovado_alguma_vez.add(k)
                codigos = {a.codigo for a in achados[k]}
                itens[k] = ItemFila(k, s.classe_para, s.ordo_clinico_para, entrada[k], cid(F[k]).startswith("C"),
                                    not (codigos & NAO_CALMO))
            # (sem_urgencia é atualizado só quando há sugestão — suficiente p/ medir a trava)
    # regra de ouro: a ordenação SEM a trava já respeita?
    sem_trava = sorted(itens.values(), key=lambda i: (["A1", "A2", "B", "C", "D"].index(i.classe), -i.ordo_score(d), i.data_entrada, i.solicitacao_id))
    if aplicar_regra_de_ouro(list(sem_trava)) != sem_trava:
        trava_agiu += 1
    if DEMO in itens:
        pos = next(i.posicao for i in ordenar(list(itens.values()), d) if i.solicitacao_id == DEMO)
        it = itens[DEMO]
        if pos > pior[0]:
            fila_d = ordenar(list(itens.values()), d)
            pior = (pos, d, [(i.ordo_clinico, (d - i.data_entrada).days, i.ordo_score(d)) for i in fila_d[:pos - 1]])
        if not traj or traj[-1][2:4] != (it.classe, it.ordo_clinico) or abs(traj[-1][1] - pos) >= 10:
            traj.append((d.isoformat(), pos, it.classe, it.ordo_clinico, it.ordo_score(d), len(itens)))

print(f"dias com chegada: {len(chegadas)} | fila final: {len(itens)}")
print("sugestões por tipo:", {t.value: n for t, n in tipos.items()})
ult = [n for d, n in sug_por_dia.items() if (REF - d).days <= 180]
print(f"últimos 180 dias: {sum(ult)} sugestões; por dia com chegada: mediana {st.median(ult)}, máx {max(ult)}")
print(f"dias em que a ordenação sem trava violaria a regra de ouro: {trava_agiu}")

print(f"\ntrajetória {DEMO} (data, posição, classe, Ordo clínico, OrdoScore final, tamanho da fila):")
for t in traj:
    print("  ", t)

pos, d, frente = pior
print(f"\npior posição do demo: {pos} em {d}; os {len(frente)} à frente: "
      f"ordo clínico mediano {st.median(f[0] for f in frente):.1f} (demo 44.9), "
      f"dias na fila mediano {st.median(f[1] for f in frente)}, com ordo clínico > 44.9: {sum(f[0] > 44.9 for f in frente)}")
est = prazos_estourados(list(itens.values()), REF)
print(f"\nprazo estourado em 23/10/2026: {len(est)} de {len(itens)}; por classe:", dict(Cn.Counter(i.classe for i in est)))
print("\n== envelhecimento: aprovado × reavaliado do zero em 23/10/2026 ==")
dif_ordo, dif_classe = [], 0
for k, ap in aprovado.items():
    av = avaliar(k, achados[k], REF, entrada[k])
    dif_ordo.append(ap.ordo_clinico - av.ordo_clinico)
    dif_classe += ap.classe != av.classe
print(f"classe diferente: {dif_classe} de {len(aprovado)}")
print(f"OrdoScore aprovado - atual: mediana {st.median(dif_ordo):.1f}, >10 pts acima: {sum(x > 10 for x in dif_ordo)}, >30: {sum(x > 30 for x in dif_ordo)}")
pos_aprov = {i.solicitacao_id: i.posicao for i in ordenar(list(itens.values()), REF)}
fresh = [ItemFila(k, (av := avaliar(k, achados[k], REF, entrada[k])).classe, av.ordo_clinico, entrada[k], it.oncologico, it.sem_urgencia) for k, it in itens.items()]
pos_fresh = {i.solicitacao_id: i.posicao for i in ordenar(fresh, REF)}
desloc = [abs(pos_aprov[k] - pos_fresh[k]) for k in pos_aprov]
print(f"posição aprovada × reavaliada: mediana {st.median(desloc)}, >50 posições: {sum(x > 50 for x in desloc)}, >200: {sum(x > 200 for x in desloc)}")
