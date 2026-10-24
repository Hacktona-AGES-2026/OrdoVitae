"""Etapa 2: compara o estado aprovado com a avaliação nova e gera sugestões para o regulador.

Só um achado NOVO gera sugestão de mudança: o tempo passando (decaimento, prazo)
não gera sugestão sozinho. O humano aprova classe + parte clínica do OrdoScore; a posição sai de
`fila.ordenar`, e `fila.prever_posicoes` preenche a prévia.
"""
from dataclasses import dataclass

from .avaliacao import mais_urgente
from .modelos import Achado, Avaliacao, CodigoAchado as C, Dimensao, Sugestao, TipoSugestao

ALERTAS_SEM_MUDANCA = {C.PERDA_CONTATO, C.OTIMIZAR_CLINICAMENTE, C.DADOS_INSUFICIENTES}


@dataclass
class EstadoAprovado:
    classe: str
    ordo_clinico: float


def decidir(av: Avaliacao, aprovado: EstadoAprovado | None, novos: list[Achado]) -> list[Sugestao]:
    """`novos`: achados trazidos pelo gatilho (solicitação nova ou evento novo)."""
    sugestoes: list[Sugestao] = []
    novos_ids = {a.id for a in novos}
    novos_alertas = [a for a in av.alertas if a.id in novos_ids]
    novos_clinicos = [a for a in novos if a.dimensao != Dimensao.ALERTA]
    classe_de = aprovado.classe if aprovado else None
    ordo_de = aprovado.ordo_clinico if aprovado else None

    saida = [a for a in novos_alertas if a.codigo == C.SAIU_DA_FILA]
    if saida:
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.REMOVER, classe_de, None, saida,
            justificativa=f"Indício de saída da fila: {_citar(saida)}.",
        ))

    if aprovado is None:
        motivos = [c.achado for c in av.contribuicoes[:4]]
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.CLASSIFICACAO_INICIAL, None, av.classe, motivos,
            justificativa=_justificar(av, None, None, motivos),
            urgente=av.classe in ("A1", "A2"),
            ordo_clinico_para=av.ordo_clinico,
        ))
    elif novos_clinicos and (av.classe != aprovado.classe or av.ordo_clinico != aprovado.ordo_clinico):
        if av.classe != aprovado.classe:
            subir = mais_urgente(av.classe, aprovado.classe) == av.classe
        else:
            subir = av.ordo_clinico > aprovado.ordo_clinico
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.SUBIR if subir else TipoSugestao.DESCER,
            aprovado.classe, av.classe, novos_clinicos,
            justificativa=_justificar(av, aprovado.classe, ordo_de, novos_clinicos),
            urgente=subir and av.classe in ("A1", "A2"),
            ordo_clinico_de=ordo_de, ordo_clinico_para=av.ordo_clinico,
        ))

    outros = [a for a in novos_alertas if a.codigo in ALERTAS_SEM_MUDANCA]
    if outros:
        sugestoes.append(Sugestao(
            av.solicitacao_id, TipoSugestao.ALERTA, classe_de, classe_de, outros,
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


def _justificar(av: Avaliacao, classe_de: str | None, ordo_de: float | None, motivos) -> str:
    # TODO: versão com LLM só para redação — pode citar apenas os achados de `motivos`.
    if classe_de is None:
        mudanca = f"Classe inicial {av.classe}, OrdoScore clínico {av.ordo_clinico}"
    else:
        mudanca = f"Classe {classe_de} → {av.classe}, OrdoScore clínico {ordo_de} → {av.ordo_clinico}"
    return (f"{mudanca} ({av.motivo_classe}; gravidade {av.gravidade}, deterioração {av.deterioracao}, "
            f"chance de piora em 90 dias {av.p_piora:.0%}). Achados: {_citar(motivos)}.")
