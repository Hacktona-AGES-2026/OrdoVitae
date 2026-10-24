"""Etapa 2: compara a classe aprovada com a proposta e gera sugestão para o regulador.

O decisor não escolhe posição: a posição sai de `fila.ordenar` a partir das
classes aprovadas. O humano aprova mudança de CLASSE.
"""
from .avaliacao import mais_urgente
from .modelos import Avaliacao, CodigoAchado as C, Sugestao, TipoSugestao

ALERTAS_SEM_MUDANCA = {C.PERDA_CONTATO, C.OTIMIZAR_CLINICAMENTE, C.DADOS_INSUFICIENTES}


def decidir(av: Avaliacao, classe_aprovada: str | None) -> list[Sugestao]:
    sugestoes: list[Sugestao] = []
    motivos = [c.achado for c in av.contribuicoes[:4]]

    saida = [a for a in av.alertas if a.codigo == C.SAIU_DA_FILA]
    if saida:
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.REMOVER, classe_aprovada, None, saida,
            justificativa=f"Indício de saída da fila: {_citar(saida)}.",
        ))

    if classe_aprovada is None:
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.CLASSIFICACAO_INICIAL, None, av.classe, motivos,
            justificativa=_justificar(av, None, motivos),
            urgente=av.classe in ("A1", "A2"),
        ))
    elif av.classe != classe_aprovada:
        subir = mais_urgente(av.classe, classe_aprovada) == av.classe
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.SUBIR if subir else TipoSugestao.DESCER,
            classe_aprovada, av.classe, motivos,
            justificativa=_justificar(av, classe_aprovada, motivos),
            urgente=subir and av.classe in ("A1", "A2"),
        ))

    outros = [a for a in av.alertas if a.codigo in ALERTAS_SEM_MUDANCA]
    if outros:
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.ALERTA, classe_aprovada, classe_aprovada, outros,
            justificativa=f"Verificar: {_citar(outros)}.",
        ))
    return sugestoes


def _citar(achados) -> str:
    partes = []
    for a in achados:
        data = a.data_fato.strftime("%d/%m/%Y") if a.data_fato else "s/ data"
        trecho = f' "{a.evidencia.trecho}"' if a.evidencia.trecho else ""
        partes.append(f"{a.codigo.value} em {data} ({a.evidencia.ref}){trecho}")
    return "; ".join(partes)


def _justificar(av: Avaliacao, de: str | None, motivos) -> str:
    # TODO: versão com LLM só para redação — pode citar apenas os achados de `motivos`.
    mudanca = f"{de} → {av.classe}" if de else f"classe inicial {av.classe}"
    return (f"{mudanca} ({av.motivo_classe}; gravidade {av.gravidade}, "
            f"deterioração {av.deterioracao}). Principais achados: {_citar(motivos)}.")
