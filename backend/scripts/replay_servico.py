"""Replay do dataset inteiro PELO SERVIÇO (o papel do simulador, em processo), com aprovação automática.

Solicitações chegam na data de entrada; eventos na própria data (ou na entrada, se forem anteriores).
Observações seguem a regra 11 (mesma decisão de spikes/carga.py): saem da solicitação e chegam como
evento `tipo_evento = "observacao"` junto do último evento do paciente (sem eventos: no último dia),
para não vazar informação do futuro. O relógio pula direto pelos anos de histórico e só usa
`avancar_dia` (que tira foto diária) nos últimos `dias_com_foto` dias.

Uso (de dentro de backend/):
  python -m scripts.replay_servico [saida.csv] [--db sqlite:///caminho.sqlite3]
"""
import collections
import csv
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
REF = date(2026, 10, 23)


def ler(nome: str) -> list[dict]:
    with open(RAIZ / nome, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def observacoes_como_eventos(fila: list[dict], eventos: list[dict], ref: date = REF) -> list[dict]:
    """Regra 11: tira `observacoes` da solicitação e devolve cada uma como evento "observacao"."""
    ultimo: dict[str, str] = {}
    for e in eventos:
        ultimo[e["solicitacao_id"]] = max(ultimo.get(e["solicitacao_id"], ""), e["data_evento"])
    obs = []
    for s in fila:
        texto = (s.get("observacoes") or "").strip()
        if texto:
            obs.append({"evento_id": f"OBS-{s['solicitacao_id']}", "solicitacao_id": s["solicitacao_id"],
                        "paciente_id": s["paciente_id"], "tipo_evento": "observacao", "resultado": "",
                        "valor_numerico": "", "descricao": texto, "origem": "observacoes",
                        "data_evento": max(ultimo.get(s["solicitacao_id"], ref.isoformat()), s["data_entrada_fila"])})
        s["observacoes"] = ""
    return obs


def replay(svc, dias_com_foto: int = 30, ref: date = REF) -> dict:
    fila, eventos = ler("fila_cirurgica.csv"), ler("eventos_clinicos.csv")
    eventos += observacoes_como_eventos(fila, eventos, ref)
    entrada = {s["solicitacao_id"]: date.fromisoformat(s["data_entrada_fila"]) for s in fila}
    chegadas = collections.defaultdict(list)
    for s in fila:
        chegadas[entrada[s["solicitacao_id"]]].append(("sol", s))
    for e in eventos:
        d = date.fromisoformat(e["data_evento"])
        chegadas[max(d, entrada.get(e["solicitacao_id"], d))].append(("ev", e))

    svc.configurar_simulacao(auto_aprovar=True)
    inicio_fotos = ref - timedelta(days=dias_com_foto)
    tipos = collections.Counter()
    for d in sorted(chegadas):
        _ir_para(svc, min(d, ref), inicio_fotos)
        for tipo, dados in sorted(chegadas[d], key=lambda x: x[0] != "sol"):   # solicitação antes dos eventos
            receber = svc.receber_solicitacao if tipo == "sol" else svc.receber_evento
            for r in receber(dados):
                tipos[r.sugestao.tipo.value] += 1
    _ir_para(svc, ref, inicio_fotos)
    return {"sugestoes": dict(tipos), "fila": len(svc.consultar_fila()), "hoje": svc.consultar_simulacao().hoje}


def _ir_para(svc, alvo: date, inicio_fotos: date) -> None:
    hoje = svc.consultar_simulacao().hoje
    if hoje == date.min or alvo <= hoje:
        return
    if alvo > inicio_fotos and hoje < inicio_fotos:
        svc.relogio.avancar((inicio_fotos - hoje).days)          # histórico: pula sem foto
        hoje = inicio_fotos
    if alvo <= inicio_fotos:
        svc.relogio.avancar((alvo - hoje).days)
    else:
        svc.avancar_dia((alvo - hoje).days)                     # janela final: foto por dia


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ / "backend"))
    from api.dependencias import criar_servico

    args = sys.argv[1:]
    url = args[args.index("--db") + 1] if "--db" in args else "sqlite://"
    saida = Path(next((a for a in args if a.endswith(".csv")), RAIZ / "fila_priorizada.csv"))
    svc = criar_servico(url)
    print(replay(svc))
    saida.write_text(svc.exportar_fila_priorizada(), encoding="utf-8")
    print(f"CSV: {saida}  →  python verificar_fila_priorizada.py {saida}")
