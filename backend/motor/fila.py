"""Ordenação da fila oficial (a partir do estado APROVADO) + trava da regra de ouro."""
from dataclasses import dataclass, replace
from datetime import date

from . import config
from .modelos import Comparacao, Sugestao, TipoSugestao


@dataclass
class ItemFila:
    solicitacao_id: str
    classe: str                 # classe aprovada (ou provisória, para quem acabou de entrar)
    ordo_clinico: float         # estado clínico aprovado (0–100)
    data_entrada: date
    oncologico: bool            # pelo CID C* (não pela flag)
    sem_urgencia: bool          # definição do verificador oficial
    risco: float = 0.0          # score de risco (0–1), de motor.risco
    posicao: int = 0

    def razao_prazo(self, data_ref: date) -> float:
        """Quanto do prazo da classe já foi consumido (>1 = estourado)."""
        return (data_ref - self.data_entrada).days / config.PRAZO_DIAS[self.classe]

    def componentes(self, data_ref: date) -> dict[str, float]:
        """Pontos de cada parte no score final (somam o score): estado, classe, espera e o desconto do risco."""
        urg = config.URGENCIA_CLASSE[self.classe]
        espera = min((data_ref - self.data_entrada).days / config.TETO_ESPERA_DIAS, 1)
        espera *= config.ESPERA_PISO + (1 - config.ESPERA_PISO) * urg
        maximo = config.W_PONTOS + config.W_PIORA + config.W_CLASSE * config.MULT_CLASSE + config.W_ESPERA
        partes = {"estado": (config.W_PONTOS + config.W_PIORA) * self.ordo_clinico / 100,
                  "classe": config.W_CLASSE * config.MULT_CLASSE * urg,
                  "espera": config.W_ESPERA * espera}
        partes = {k: 100 * v / maximo for k, v in partes.items()}
        partes["risco"] = -sum(partes.values()) * config.PESO_RISCO * self.risco
        return {k: round(v, 1) for k, v in partes.items()}

    def score_clinico(self, data_ref: date) -> float:
        """0–100: estado clínico aprovado + urgência da classe + espera ponderada pela classe."""
        c = self.componentes(data_ref)
        return round(c["estado"] + c["classe"] + c["espera"], 1)

    def score(self, data_ref: date) -> float:
        """Score final que ordena a fila: clínico, descontado pelo risco."""
        return round(sum(self.componentes(data_ref).values()), 1)


def critico(item: ItemFila, data_ref: date) -> bool:
    """Flag de destaque para o front. Não altera posição."""
    return (item.classe in config.CRITICO_CLASSES
            and item.razao_prazo(data_ref) >= config.CRITICO_RAZAO_PRAZO
            and item.score(data_ref) >= config.CRITICO_SCORE_MIN)


def ordenar(itens: list[ItemFila], data_ref: date) -> list[ItemFila]:
    """Score final → mais antigo na fila → id (desempate fixo), depois a regra de ouro.

    Não agrupa por classe: a classe já está dentro do score clínico.
    """
    fila = sorted(itens, key=lambda i: (-i.score(data_ref), i.data_entrada, i.solicitacao_id))
    fila = aplicar_regra_de_ouro(fila)
    for pos, item in enumerate(fila, start=1):
        item.posicao = pos
    return fila


def aplicar_regra_de_ouro(fila: list[ItemFila]) -> list[ItemFila]:
    """Nenhum oncológico abaixo do primeiro paciente sem urgência.

    O multiplicador da classe e a espera ponderada já deixam quase todos os oncológicos acima
    (spike: 4 de 177 ainda dependem da trava); a trava garante o resto e protege contra
    pesos mal calibrados ou aprovações erradas.
    """
    primeiro_calmo = next((i for i, x in enumerate(fila) if x.sem_urgencia), None)
    if primeiro_calmo is None:
        return fila
    acima, abaixo = fila[:primeiro_calmo], fila[primeiro_calmo:]
    onco_abaixo = [x for x in abaixo if x.oncologico]
    resto = [x for x in abaixo if not x.oncologico]
    return acima + onco_abaixo + resto


def prazos_estourados(fila: list[ItemFila], data_ref: date) -> list[ItemFila]:
    """Alerta para o regulador: quem já passou do prazo da classe, do mais estourado ao menos."""
    return sorted((i for i in fila if i.razao_prazo(data_ref) > 1), key=lambda i: -i.razao_prazo(data_ref))


def prever_posicoes(fila_oficial: list[ItemFila], sugestoes: list[Sugestao], data_ref: date,
                    novos: dict[str, ItemFila] | None = None) -> None:
    """Preenche score final e posição (de/para) de cada sugestão, como se SÓ ela fosse aprovada.

    A fila final não depende da ordem de aprovação (é função do estado aprovado);
    só as prévias mudam — recalcule depois de cada aprovação.
    `novos`: ItemFila de pacientes que ainda não estão na fila oficial (classificação inicial).
    """
    novos = novos or {}
    por_id = {i.solicitacao_id: i for i in fila_oficial}
    for s in sugestoes:
        atual = por_id.get(s.solicitacao_id)
        if atual:
            s.posicao_de, s.ordo_de = atual.posicao, atual.score(data_ref)
        if s.tipo == TipoSugestao.REMOVER:
            continue
        if s.tipo == TipoSugestao.ALERTA:
            s.posicao_para, s.ordo_para = s.posicao_de, s.ordo_de
            continue
        base = atual or novos.get(s.solicitacao_id)
        if base is None:
            continue
        proposto = replace(base, classe=s.classe_para, ordo_clinico=s.ordo_clinico_para)
        simulada = ordenar([replace(i) for i in fila_oficial if i.solicitacao_id != s.solicitacao_id] + [proposto], data_ref)
        s.posicao_para = next(i.posicao for i in simulada if i.solicitacao_id == s.solicitacao_id)
        s.ordo_para = proposto.score(data_ref)
        s.componentes_para = proposto.componentes(data_ref)
        _comparar(s, simulada, atual.posicao if atual else None, data_ref)


def _comparar(s: Sugestao, simulada: list[ItemFila], pos_antes: int | None, data_ref: date, n: int = 3) -> None:
    """Quem a sugestão ultrapassa (subindo) ou quem passa à frente dela (descendo), e por quê."""
    antes = pos_antes or len(simulada) + 1
    if s.posicao_para < antes:      # subiu: estava acima dele e agora fica abaixo
        afetados = [i for i in simulada if s.posicao_para < i.posicao <= antes]
        perto = afetados[:n]
        verbo = "Passa à frente de"
    elif s.posicao_para > antes:    # desceu: estava abaixo dele e agora fica acima
        afetados = [i for i in simulada if antes <= i.posicao < s.posicao_para]
        perto = afetados[-n:]
        verbo = "Fica atrás de"
    else:
        return
    s.ultrapassados = len(afetados)
    s.comparacao = [Comparacao(i.solicitacao_id, i.classe, i.score(data_ref), i.componentes(data_ref)) for i in perto]
    if not perto:
        return
    nomes = {"estado": "estado clínico", "classe": "classe SWALIS", "espera": "tempo de espera", "risco": "risco"}
    viz = s.comparacao[0]
    dif = {k: round(s.componentes_para[k] - viz.componentes[k], 1) for k in viz.componentes}
    subiu = s.posicao_para < antes
    decisivo = max(dif, key=lambda k: dif[k]) if subiu else min(dif, key=lambda k: dif[k])
    num = lambda x: f"{x:+.1f}".replace(".", ",")
    s.justificativa_comparativa = (
        f"{'Passa à frente de' if subiu else 'Fica atrás de'} {len(afetados)} paciente(s). "
        f"{'Logo abaixo' if subiu else 'Logo acima'} fica {viz.solicitacao_id} "
        f"(classe {viz.classe}, score {str(viz.score).replace('.', ',')}): "
        f"a diferença está no {nomes[decisivo]} ({num(dif[decisivo])} pontos).")
