"""Spike: ordem SEM classe na frente. Score clínico (pontos, piora, classe SWALIS, espera) ponderado
contra score de risco (ASA × risco do procedimento), por subtração ou multiplicação.
Uso: python3 spike_risco.py [pasta_saida_csv]"""
import csv
import statistics as st
import subprocess
import sys
from datetime import date
from pathlib import Path

from carga import DATASET, NAO_CALMO, REF, carregar, cid, ler

sys.path.insert(0, "../backend")
from motor import ItemFila, avaliar  # noqa: E402
from motor.fila import aplicar_regra_de_ouro  # noqa: E402
from motor.modelos import TipoSugestao  # noqa: E402
from motor.decisor import decidir  # noqa: E402

SAIDA = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
DEMO = "SOL-2025-00146"

# --- score clínico (0–100) -----------------------------------------------------
URGENCIA_CLASSE = {"A1": 1.0, "A2": 0.8, "B": 0.55, "C": 0.3, "D": 0.0}
W_PONTOS, W_PIORA, W_CLASSE, W_ESPERA = 0.35, 0.20, 0.25, 0.20
TETO_PONTOS, P_MAX, TETO_ESPERA = 15, 0.385, 730

# --- score de risco (0–1) ------------------------------------------------------
NIVEL = {"baixo": 0.0, "medio": 0.5, "alto": 1.0}
ASA_POR_N_COMORB = {0: 1, 1: 2, 2: 2, 3: 3}


def nivel_asa(r):
    if r["asa"].strip():
        a, estimado = int(r["asa"]), False
    else:
        c = r["comorbidades"].strip().lower()
        n = 0 if c in ("", "nenhuma") else len(c.split(";"))
        a, estimado = ASA_POR_N_COMORB.get(n, 3), True
    return ("baixo" if a <= 2 else "medio" if a == 3 else "alto"), estimado


def nivel_proc(risco):
    return "baixo" if risco <= 2 else "medio" if risco == 3 else "alto"


fila, _, achados = carregar()
proc = {p["procedimento_id"]: int(p["risco_cirurgico"]) for p in ler("procedimentos.csv")}
pac = []
for s in fila:
    k = s["solicitacao_id"]
    ent = date.fromisoformat(s["data_entrada_fila"])
    av = avaliar(k, achados[k], REF, ent)
    if any(x.tipo == TipoSugestao.REMOVER for x in decidir(av, None, achados[k])):
        continue
    clin = 100 * (W_PONTOS * min(av.total / TETO_PONTOS, 1) + W_PIORA * av.p_piora / P_MAX
                  + W_CLASSE * URGENCIA_CLASSE[av.classe] + W_ESPERA * min((REF - ent).days / TETO_ESPERA, 1))
    np_, est = nivel_asa(s)
    nq = nivel_proc(proc[s["procedimento_id"]])
    risco = (NIVEL[np_] + NIVEL[nq]) / 2
    codigos = {a.codigo for a in achados[k]}
    comp = dict(pts=min(av.total / TETO_PONTOS, 1), piora=av.p_piora / P_MAX, urg=URGENCIA_CLASSE[av.classe],
                esp=min((REF - ent).days / TETO_ESPERA, 1))
    pac.append(dict(id=k, ent=ent, classe=av.classe, clin=clin, comp=comp, risco=risco, np=np_, nq=nq, asa_est=est,
                    onco=cid(s).startswith("C"), calmo=not (codigos & NAO_CALMO)))


def ordenar(final):
    itens = sorted(pac, key=lambda p: (-final(p), p["ent"], p["id"]))
    # trava da regra de ouro (reaproveita a do motor com ItemFila "fantasma")
    fake = [ItemFila(p["id"], "D", 0, p["ent"], p["onco"], p["calmo"]) for p in itens]
    travada = aplicar_regra_de_ouro(fake)
    primeiro_calmo = next(i for i, p in enumerate(itens, 1) if p["calmo"])
    resgatados = sum(1 for i, p in enumerate(itens, 1) if p["onco"] and i > primeiro_calmo)
    agiu = (resgatados, primeiro_calmo)
    pos = {x.solicitacao_id: i for i, x in enumerate(travada, 1)}
    return pos, agiu, itens


def verificar(nome, pos):
    arq = SAIDA / f"fila_{nome}.csv"
    with open(arq, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["solicitacao_id", "posicao", "justificativa"])
        for k, p in sorted(pos.items(), key=lambda x: x[1]):
            w.writerow([k, p, nome])
    out = subprocess.run(["uv", "run", "-q", "--no-project", "--with", "pandas", "python",
                          str(DATASET / "verificar_fila_priorizada.py"), str(arq), "--dataset", str(DATASET)],
                         capture_output=True, text=True).stdout
    linhas = [l.split(": ", 1)[1] for l in out.splitlines() if l.startswith("- ")]
    return linhas, "OK" if "RESULTADO: OK" in out else "FALHOU"


configs = {"sem_risco": lambda p: p["clin"]}
for w in (0.1, 0.2, 0.3):
    configs[f"sub_{int(w*100)}"] = (lambda w: lambda p: p["clin"] - w * 100 * p["risco"])(w)
    configs[f"mul_{int(w*100)}"] = (lambda w: lambda p: p["clin"] * (1 - w * p["risco"]))(w)

base, _, _ = ordenar(configs["sem_risco"])
print(f"{len(pac)} pacientes | risco: " + ", ".join(f"{n}={sum(p['risco']==v for p in pac)}" for n, v in [("0", 0), ("0.25", .25), ("0.5", .5), ("0.75", .75), ("1", 1)]))
print(f"{'config':10s} {'trava (onco resgatados / 1º calmo)':>34s} {'demo':>5s} {'desloc med':>10s} {'risco≥.75 Δpos':>14s} {'onco proc alto Δ':>16s} | verificador (onco mediana | onco 1º terço | PS 1ª metade | calmos último terço)")
for nome, fn in configs.items():
    pos, agiu, _ = ordenar(fn)
    d = [pos[p["id"]] - base[p["id"]] for p in pac]
    alto = [pos[p["id"]] - base[p["id"]] for p in pac if p["risco"] >= 0.75]
    onco_alto = [pos[p["id"]] - base[p["id"]] for p in pac if p["onco"] and p["nq"] == "alto"]
    ind, res = verificar(nome, pos)
    print(f"{nome:10s} {f'{agiu[0]} / pos {agiu[1]}':>34s} {pos[DEMO]:5d} {st.median(abs(x) for x in d):10.0f} {st.mean(alto) if alto else 0:+14.0f} {st.mean(onco_alto):+16.0f} | {res} " + " | ".join(i.split(' de ')[0] for i in ind))
