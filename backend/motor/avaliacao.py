"""Etapa 1: achados de UMA solicitação → scores + classe SWALIS proposta.

Função pura: não conhece os outros pacientes, não acessa banco, não chama LLM.
"""
from datetime import date

from . import config
from .modelos import Achado, Avaliacao, CodigoAchado as C, Contribuicao, Dimensao, Origem


def mais_urgente(a: str, b: str) -> str:
    return a if config.CLASSES.index(a) <= config.CLASSES.index(b) else b


def deduplicar(achados: list[Achado]) -> list[Achado]:
    """Remove repetições: mesmo código na mesma data. Regra vence LLM.

    Achado de LLM sem data cujo código já veio de regra é descartado
    (ex.: texto diz "foi ao PS" e o evento de PS já está registrado).
    """
    ordenados = sorted(achados, key=lambda a: a.origem != Origem.REGRA)
    vistos: set[tuple] = set()
    codigos_de_regra = {a.codigo for a in achados if a.origem == Origem.REGRA}
    saida = []
    for a in ordenados:
        if a.origem == Origem.LLM and a.data_fato is None and a.codigo in codigos_de_regra:
            continue
        chave = (a.codigo, a.data_fato)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(a)
    return saida


def _decaimento(data_fato: date, data_ref: date) -> float:
    dias = max((data_ref - data_fato).days, 0)
    return 0.5 ** (dias / config.MEIA_VIDA_DIAS)


def avaliar(solicitacao_id: str, achados: list[Achado], data_ref: date, data_entrada: date) -> Avaliacao:
    validos = [a for a in achados if a.data_fato is None or a.data_fato <= data_ref]
    validos = deduplicar(validos)

    contribuicoes: list[Contribuicao] = []
    alertas: list[Achado] = []
    gravidade = 0.0
    deterioracao = 0.0
    codigos_gravidade: set[C] = set()

    for a in validos:
        if a.dimensao == Dimensao.ALERTA:
            alertas.append(a)
        elif a.dimensao == Dimensao.GRAVIDADE:
            if a.codigo in codigos_gravidade:  # gravidade conta uma vez por código
                continue
            codigos_gravidade.add(a.codigo)
            pts = config.PONTOS.get(a.codigo, 0)
            gravidade += pts
            contribuicoes.append(Contribuicao(a, pts))
        else:
            pts = config.PONTOS.get(a.codigo, 0) * _decaimento(a.data_fato or data_entrada, data_ref)
            deterioracao += pts
            contribuicoes.append(Contribuicao(a, round(pts, 2)))

    deterioracao = max(deterioracao, 0.0)
    classe, motivo = _classificar(gravidade + deterioracao, validos, data_ref)

    return Avaliacao(
        solicitacao_id=solicitacao_id,
        data_ref=data_ref,
        gravidade=round(gravidade, 2),
        deterioracao=round(deterioracao, 2),
        classe=classe,
        motivo_classe=motivo,
        contribuicoes=sorted(contribuicoes, key=lambda c: -abs(c.pontos)),
        alertas=alertas,
    )


def _classificar(total: float, achados: list[Achado], data_ref: date) -> tuple[str, str]:
    classe, motivo = "D", f"total {total:.1f} < {config.LIMIARES[-1][1]}"
    for c, limiar in config.LIMIARES:
        if total >= limiar:
            classe, motivo = c, f"total {total:.1f} >= {limiar}"
            break

    codigos = {a.codigo for a in achados}
    oncologico = C.CID_MALIGNO in codigos or C.BIOPSIA_POSITIVA in codigos
    progressao_recente = any(
        a.codigo == C.PROGRESSAO_IMAGEM and a.data_fato
        and (data_ref - a.data_fato).days <= config.JANELA_PROGRESSAO_DIAS
        for a in achados
    )

    pisos = []
    if oncologico:
        pisos.append((config.PISO_ONCOLOGICO, "piso: oncológico"))
    if oncologico and progressao_recente:
        pisos.append((config.ONCOLOGICO_EM_PROGRESSAO, "piso: oncológico em progressão"))
    if C.CID_URGENTE in codigos:
        pisos.append((config.PISO_CID_URGENTE, "piso: CID de urgência"))

    for piso, motivo_piso in pisos:
        if mais_urgente(piso, classe) == piso and piso != classe:
            classe, motivo = piso, motivo_piso
    return classe, motivo
