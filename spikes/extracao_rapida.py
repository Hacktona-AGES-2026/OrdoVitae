"""Extração por regras mínima (só para a spike; a versão real é do Rodrigo)."""
import csv
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from motor.modelos import Achado, CodigoAchado as C, Dimensao as D, Evidencia  # noqa: E402

DATASET = Path(__file__).resolve().parents[2] / "dataset"
REF = date(2026, 10, 23)
CID_URG = {"I200", "K403", "K400", "K420", "K430", "K800", "N132", "I832"}
ALARME = re.compile(r"encarcer|estrangul|colangite|icter|pancreatite|enterorragia|melena|hematemese|suboclus|perda ponderal|"
                    r"disfagia|sepse|hidronefrose|perda de funcao|transfund|hemoptise|rouquidao|linfonodo.*(?:fixo|palpavel)|"
                    r"sangramento espontaneo|acamad|ulcera de pressao|quedas de repeticao|glaucoma facomorfico|retencao de co2|"
                    r"dano neurologico|psa em elevacao|dessaturacao|angina em repouso|sincope|crescimento rapido|"
                    r"retencao urinaria aguda|massa anexial|ca-125", re.I)
EV = {
    ("biopsia", "positivo"): (C.BIOPSIA_POSITIVA, D.GRAVIDADE),
    ("exame_imagem", "progressao"): (C.PROGRESSAO_IMAGEM, D.DETERIORACAO),
    ("consulta_reavaliacao", "piora"): (C.REAVALIACAO_PIORA, D.DETERIORACAO),
    ("consulta_reavaliacao", "melhora"): (C.MELHORA, D.DETERIORACAO),
    ("contato_telefonico", "relata_piora"): (C.PIORA_RELATADA, D.DETERIORACAO),
    ("contato_telefonico", "relata_melhora"): (C.MELHORA, D.DETERIORACAO),
    ("contato_telefonico", "nao_atendeu"): (C.PERDA_CONTATO, D.ALERTA),
    ("contato_telefonico", "desistiu"): (C.SAIU_DA_FILA, D.ALERTA),
    ("contato_telefonico", "informou_cirurgia_outro_servico"): (C.SAIU_DA_FILA, D.ALERTA),
}
NAO_CALMO = {C.CID_MALIGNO, C.CID_URGENTE, C.SINAL_ALARME, C.DOR_INTENSA, C.DOR_MODERADA, C.LIMITACAO_GRAVE,
             C.LIMITACAO_MODERADA, C.PRONTO_SOCORRO, C.INTERNACAO, C.BIOPSIA_POSITIVA, C.PROGRESSAO_IMAGEM,
             C.REAVALIACAO_PIORA}
DETERIORA = {C.PRONTO_SOCORRO, C.INTERNACAO, C.PROGRESSAO_IMAGEM, C.REAVALIACAO_PIORA, C.PIORA_RELATADA, C.HBA1C_DESCONTROLADA}


def ler(nome):
    with open(DATASET / nome, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def cid(s):
    return s["cid_principal"].upper().replace(".", "").strip()


def extrair_solicitacao(s):
    sid, d0 = s["solicitacao_id"], date.fromisoformat(s["data_entrada_fila"])
    out = []
    def add(c, dim, campo, trecho=""):
        out.append(Achado(c, dim, sid, d0, Evidencia("solicitacao", f"{sid}:{campo}", trecho)))
    c = cid(s)
    if c.startswith("C"): add(C.CID_MALIGNO, D.GRAVIDADE, "cid_principal")
    if re.match(r"D(3[7-9]|4[0-8])|R91", c): add(C.CID_SUSPEITO, D.GRAVIDADE, "cid_principal")
    if c in CID_URG: add(C.CID_URGENTE, D.GRAVIDADE, "cid_principal")
    eva = int(s["intensidade_dor_eva"]) if s["intensidade_dor_eva"].strip() else None
    if eva is not None and eva >= 7: add(C.DOR_INTENSA, D.GRAVIDADE, "intensidade_dor_eva")
    elif eva is not None and eva >= 4: add(C.DOR_MODERADA, D.GRAVIDADE, "intensidade_dor_eva")
    lim = s["limitacao_funcional"].strip().lower()
    if lim == "grave": add(C.LIMITACAO_GRAVE, D.GRAVIDADE, "limitacao_funcional")
    if lim == "moderada": add(C.LIMITACAO_MODERADA, D.GRAVIDADE, "limitacao_funcional")
    j = s["justificativa_clinica"]
    if len(j.strip()) < 30: add(C.DADOS_INSUFICIENTES, D.ALERTA, "justificativa_clinica")
    m = ALARME.search(j)
    if m: add(C.SINAL_ALARME, D.GRAVIDADE, "justificativa_clinica", m.group(0))
    return out


def extrair_evento(e):
    t, r, sid = e["tipo_evento"], e["resultado"], e["solicitacao_id"]
    d = date.fromisoformat(e["data_evento"])
    ev = Evidencia("evento", e["evento_id"], e["descricao"])
    mk = lambda c, dim: Achado(c, dim, sid, d, ev)
    if t == "pronto_socorro": return [mk(C.PRONTO_SOCORRO, D.DETERIORACAO)]
    if t == "internacao": return [mk(C.INTERNACAO, D.DETERIORACAO)]
    if t == "falta": return [mk(C.PERDA_CONTATO, D.ALERTA)]
    if t == "hba1c" and e["valor_numerico"] and float(e["valor_numerico"]) > 8.5:
        return [mk(C.HBA1C_DESCONTROLADA, D.DETERIORACAO), mk(C.OTIMIZAR_CLINICAMENTE, D.ALERTA)]
    if (t, r) in EV: return [mk(*EV[(t, r)])]
    return []


def carregar():
    fila = ler("fila_cirurgica.csv")
    eventos = ler("eventos_clinicos.csv")
    ids = {s["solicitacao_id"] for s in fila}
    achados = {s["solicitacao_id"]: extrair_solicitacao(s) for s in fila}
    for e in eventos:
        if e["solicitacao_id"] in ids:
            achados[e["solicitacao_id"]] += extrair_evento(e)
    return fila, eventos, achados
