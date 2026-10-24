"""Portas: o contrato entre o serviço e a infra (SQLAlchemy, do Francisco).

O serviço só conhece estes Protocols. Os testes usam implementações em memória
(`tests/fakes.py`). Mudar uma porta = combinar com o Francisco antes.
"""
from datetime import date
from typing import Protocol

from motor import AvaliacaoRisco, EstadoAprovado, ItemFila
from motor.modelos import Achado, Avaliacao, Sugestao

from .modelos import SugestaoRegistrada


class RepoSolicitacoes(Protocol):
    def salvar(self, dados: dict) -> None: ...
    def obter(self, sid: str) -> dict | None: ...
    def ativas(self) -> list[dict]: ...                       # sem saída registrada
    def esta_ativa(self, sid: str) -> bool: ...               # recebida e sem saída
    def ativa_do_paciente(self, pid: str, proc_id: str) -> dict | None: ...


class RepoEventos(Protocol):
    def salvar(self, dados: dict) -> None: ...
    def existe(self, evento_id: str) -> bool: ...
    def da_solicitacao(self, sid: str) -> list[dict]: ...    # em ordem de data do evento


class RepoAchados(Protocol):
    def adicionar(self, achados: list[Achado]) -> None: ...
    def da_solicitacao(self, sid: str) -> list[Achado]: ...
    def de_varias(self, sids: list[str]) -> dict[str, list[Achado]]: ...   # uma consulta para a fila inteira


class RepoEstados(Protocol):                                  # estado aprovado + risco
    def obter(self, sid: str) -> tuple[EstadoAprovado, AvaliacaoRisco] | None: ...
    def salvar(self, sid: str, estado: EstadoAprovado, risco: AvaliacaoRisco, provisorio: bool) -> None: ...
    def todos(self) -> dict[str, tuple[EstadoAprovado, AvaliacaoRisco]]: ...


class RepoSugestoes(Protocol):
    def criar(self, s: Sugestao, criada_em: date) -> int: ...
    def obter(self, id: int) -> SugestaoRegistrada | None: ...
    def pendentes_de(self, sid: str) -> list[SugestaoRegistrada]: ...
    def listar(self, status: str | None = None) -> list[SugestaoRegistrada]: ...
    def mudar_status(self, id: int, status: str, por: str, em: date, comentario: str = "") -> None: ...


class RepoSaidas(Protocol):
    def registrar(self, sid: str, motivo: str, justificativa: str, em: date) -> None: ...


class RepoHistorico(Protocol):
    def salvar_foto(self, data: date, itens: list[ItemFila]) -> None: ...
    def foto(self, data: date) -> list[dict]: ...
    def posicoes(self, sid: str) -> list[tuple[date, int, float]]: ...
    def datas(self) -> list[date]: ...                         # dias com foto, em ordem


class RepoAuditoria(Protocol):
    def registrar(self, acao: str, sid: str, detalhe: str, por: str, em: date) -> None: ...


class UnidadeDeTrabalho(Protocol):          # uma por caso de uso; commit no fim, rollback em erro
    solicitacoes: RepoSolicitacoes
    eventos: RepoEventos
    achados: RepoAchados
    estados: RepoEstados
    sugestoes: RepoSugestoes
    saidas: RepoSaidas
    historico: RepoHistorico
    auditoria: RepoAuditoria

    def __enter__(self) -> "UnidadeDeTrabalho": ...
    def __exit__(self, *exc) -> None: ...
    def commit(self) -> None: ...


class Relogio(Protocol):                                      # data simulada, persistida
    auto_aprovar: bool

    def hoje(self) -> date: ...
    def avancar(self, dias: int = 1) -> date: ...


class Redator(Protocol):                                      # justificativa por LLM, com template de fallback
    def justificar(self, s: Sugestao, av: Avaliacao) -> str: ...
    def explicar(self, s: Sugestao) -> str: ...                # texto exibido com a prévia (por que mudou + por que ali)
