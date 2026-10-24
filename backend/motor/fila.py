"""Ordenação da fila oficial (a partir das classes APROVADAS) + trava da regra de ouro."""
from dataclasses import dataclass
from datetime import date

from . import config


@dataclass
class ItemFila:
    solicitacao_id: str
    classe: str                 # classe aprovada (ou provisória, para quem acabou de entrar)
    data_entrada: date
    oncologico: bool            # pelo CID C* (não pela flag)
    sem_urgencia: bool          # definição do verificador oficial
    posicao: int = 0

    def razao_prazo(self, data_ref: date) -> float:
        """Quanto do prazo da classe já foi consumido (>1 = estourado)."""
        return (data_ref - self.data_entrada).days / config.PRAZO_DIAS[self.classe]


def ordenar(itens: list[ItemFila], data_ref: date) -> list[ItemFila]:
    """Classe → quem está mais perto de estourar o prazo → mais dias → id (desempate fixo)."""
    fila = sorted(itens, key=lambda i: (
        config.CLASSES.index(i.classe),
        -i.razao_prazo(data_ref),
        i.data_entrada,
        i.solicitacao_id,
    ))
    fila = aplicar_regra_de_ouro(fila)
    for pos, item in enumerate(fila, start=1):
        item.posicao = pos
    return fila


def aplicar_regra_de_ouro(fila: list[ItemFila]) -> list[ItemFila]:
    """Nenhum oncológico abaixo do primeiro paciente sem urgência.

    Com o piso A2 para oncológicos isso já não deveria acontecer; a trava existe
    para garantir mesmo se um regulador aprovar algo errado ou os pesos mudarem.
    """
    primeiro_calmo = next((i for i, x in enumerate(fila) if x.sem_urgencia), None)
    if primeiro_calmo is None:
        return fila
    acima, abaixo = fila[:primeiro_calmo], fila[primeiro_calmo:]
    onco_abaixo = [x for x in abaixo if x.oncologico]
    resto = [x for x in abaixo if not x.oncologico]
    return acima + onco_abaixo + resto
