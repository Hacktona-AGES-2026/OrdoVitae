"""Spike: parâmetro extra para o SWALIS no score clínico (sem agrupar por classe), risco multiplicando a 20%."""
import statistics as st
import sys

sys.argv = sys.argv[:2] if len(sys.argv) > 1 else [sys.argv[0], "."]
exec(open("spike_risco.py").read().split("configs = {")[0])  # reaproveita pac, ordenar, verificar

W = dict(pts=W_PONTOS, piora=W_PIORA, urg=W_CLASSE, esp=W_ESPERA)
FATOR = {"A1": 1.3, "A2": 1.25, "B": 1.1, "C": 1.0, "D": 0.9}


def clin_base(c, mult_urg=1.0, esp_por_classe=False):
    esp = c["esp"] * (0.3 + 0.7 * c["urg"]) if esp_por_classe else c["esp"]
    return 100 * (W["pts"] * c["pts"] + W["piora"] * c["piora"] + W["urg"] * c["urg"] * mult_urg + W["esp"] * esp)


variantes = {
    "atual (sem parâmetro)": lambda p: clin_base(p["comp"]),
    "1) classe ×1,5": lambda p: clin_base(p["comp"], 1.5),
    "1) classe ×2": lambda p: clin_base(p["comp"], 2.0),
    "2) fator por classe": lambda p: clin_base(p["comp"]) * FATOR[p["classe"]],
    "3) espera × classe": lambda p: clin_base(p["comp"], esp_por_classe=True),
    "1+3) classe ×1,5 + espera × classe": lambda p: clin_base(p["comp"], 1.5, True),
}
CLASSES = ["A1", "A2", "B", "C", "D"]
print(f"{'variante':36s} {'resgates':>8s} {'demo':>5s} {'mistura':>8s} {'calmos últ.terço':>16s} {'onco mediana':>12s}")
for nome, clin in variantes.items():
    pos, (resg, _), itens = ordenar(lambda p: clin(p) * (1 - 0.2 * p["risco"]))
    # "mistura": % de pares vizinhos com classes diferentes fora de ordem (0% = agrupado por classe)
    ordem = sorted(pac, key=lambda p: pos[p["id"]])
    inv = sum(CLASSES.index(a["classe"]) > CLASSES.index(b["classe"]) for a, b in zip(ordem, ordem[1:]))
    ind, res = verificar("var", pos)
    print(f"{nome:36s} {resg:8d} {pos[DEMO]:5d} {inv / (len(ordem) - 1):8.0%} {ind[3].split(' ')[0]:>16s} {ind[0].split(' de ')[0]:>12s}  {res}")
