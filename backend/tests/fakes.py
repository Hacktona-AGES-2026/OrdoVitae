"""Implementações em memória das portas do serviço, para testar os casos de uso sem banco.

`BancoMemoria` faz o papel do banco; cada `UnidadeDeTrabalhoMemoria` abre uma "transação":
copia o estado ao entrar e o restaura se houver erro ou se `commit()` não for chamado,
como uma sessão SQLAlchemy fechada sem commit.
"""
import copy
from dataclasses import dataclass, field
from datetime import date, timedelta

from motor import AvaliacaoRisco, EstadoAprovado, ItemFila
from motor.modelos import Achado, Sugestao
from servico.modelos import StatusSugestao, SugestaoRegistrada


@dataclass
class BancoMemoria:
    solicitacoes: dict[str, dict] = field(default_factory=dict)
    eventos: dict[str, dict] = field(default_factory=dict)
    achados: dict[str, list[Achado]] = field(default_factory=dict)
    estados: dict[str, tuple[EstadoAprovado, AvaliacaoRisco, bool]] = field(default_factory=dict)
    sugestoes: dict[int, SugestaoRegistrada] = field(default_factory=dict)
    saidas: dict[str, dict] = field(default_factory=dict)
    fotos: dict[date, list[dict]] = field(default_factory=dict)
    auditoria: list[dict] = field(default_factory=list)
    simulacao: dict = field(default_factory=lambda: {"hoje": None, "auto_aprovar": False})


class RepoSolicitacoesMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def salvar(self, dados: dict) -> None:
        self.b.solicitacoes[dados["solicitacao_id"]] = dict(dados)

    def obter(self, sid: str) -> dict | None:
        return self.b.solicitacoes.get(sid)

    def ativas(self) -> list[dict]:
        return [s for sid, s in self.b.solicitacoes.items() if sid not in self.b.saidas]

    def esta_ativa(self, sid: str) -> bool:
        return sid in self.b.solicitacoes and sid not in self.b.saidas

    def ativa_do_paciente(self, pid: str, proc_id: str) -> dict | None:
        return next((s for s in self.ativas()
                     if s.get("paciente_id") == pid and s.get("procedimento_id") == proc_id), None)

    def datas_entrada(self, sids: list[str]) -> dict[str, date]:
        return {sid: date.fromisoformat(str(self.b.solicitacoes[sid]["data_entrada_fila"])[:10])
                for sid in sids if sid in self.b.solicitacoes}


class RepoEventosMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def salvar(self, dados: dict) -> None:
        self.b.eventos[dados["evento_id"]] = dict(dados)

    def existe(self, evento_id: str) -> bool:
        return evento_id in self.b.eventos

    def da_solicitacao(self, sid: str) -> list[dict]:
        evs = [dict(e) for e in self.b.eventos.values() if e.get("solicitacao_id") == sid]
        return sorted(evs, key=lambda e: (e.get("data_evento") or "", e["evento_id"]))


class RepoAchadosMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def adicionar(self, achados: list[Achado]) -> None:
        """Ignora achado repetido (mesma `Achado.id` na solicitação), como o UNIQUE da tabela."""
        for a in achados:
            lista = self.b.achados.setdefault(a.solicitacao_id, [])
            if all(x.id != a.id for x in lista):
                lista.append(a)

    def da_solicitacao(self, sid: str) -> list[Achado]:
        return list(self.b.achados.get(sid, []))

    def de_varias(self, sids: list[str]) -> dict[str, list[Achado]]:
        return {sid: self.da_solicitacao(sid) for sid in sids}


class RepoEstadosMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def obter(self, sid: str) -> tuple[EstadoAprovado, AvaliacaoRisco] | None:
        e = self.b.estados.get(sid)
        return (e[0], e[1]) if e else None

    def salvar(self, sid: str, estado: EstadoAprovado, risco: AvaliacaoRisco, provisorio: bool) -> None:
        self.b.estados[sid] = (estado, risco, provisorio)

    def todos(self) -> dict[str, tuple[EstadoAprovado, AvaliacaoRisco]]:
        return {sid: (e[0], e[1]) for sid, e in self.b.estados.items()}

    def provisorio(self, sid: str) -> bool:          # só para os testes
        return self.b.estados[sid][2]


class RepoSugestoesMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def criar(self, s: Sugestao, criada_em: date) -> int:
        novo_id = max(self.b.sugestoes, default=0) + 1
        self.b.sugestoes[novo_id] = SugestaoRegistrada(novo_id, s, StatusSugestao.PENDENTE, criada_em)
        return novo_id

    def obter(self, id: int) -> SugestaoRegistrada | None:
        return self.b.sugestoes.get(id)

    def pendentes_de(self, sid: str) -> list[SugestaoRegistrada]:
        return [r for r in self.b.sugestoes.values()
                if r.solicitacao_id == sid and r.status == StatusSugestao.PENDENTE]

    def listar(self, status: str | None = None) -> list[SugestaoRegistrada]:
        return [r for r in self.b.sugestoes.values() if status is None or r.status == StatusSugestao(status)]

    def mudar_status(self, id: int, status: str, por: str, em: date, comentario: str = "") -> None:
        r = self.b.sugestoes[id]
        r.status, r.decidida_por, r.decidida_em, r.comentario = StatusSugestao(status), por, em, comentario


class RepoSaidasMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def registrar(self, sid: str, motivo: str, justificativa: str, em: date) -> None:
        self.b.saidas[sid] = {"motivo": motivo, "justificativa": justificativa, "em": em}


class RepoHistoricoMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def salvar_foto(self, data: date, itens: list[ItemFila]) -> None:
        self.b.fotos[data] = [{"solicitacao_id": i.solicitacao_id, "posicao": i.posicao,
                               "score": i.score(data), "classe": i.classe} for i in itens]

    def foto(self, data: date) -> list[dict]:
        return list(self.b.fotos.get(data, []))

    def posicoes(self, sid: str) -> list[tuple[date, int, float]]:
        return [(d, x["posicao"], x["score"]) for d, itens in sorted(self.b.fotos.items())
                for x in itens if x["solicitacao_id"] == sid]

    def datas(self) -> list[date]:
        return sorted(self.b.fotos)


class RepoAuditoriaMemoria:
    def __init__(self, banco: BancoMemoria):
        self.b = banco

    def registrar(self, acao: str, sid: str, detalhe: str, por: str, em: date) -> None:
        self.b.auditoria.append({"acao": acao, "sid": sid, "detalhe": detalhe, "por": por, "em": em})


class UnidadeDeTrabalhoMemoria:
    def __init__(self, banco: BancoMemoria):
        self.banco = banco
        self.solicitacoes = RepoSolicitacoesMemoria(banco)
        self.eventos = RepoEventosMemoria(banco)
        self.achados = RepoAchadosMemoria(banco)
        self.estados = RepoEstadosMemoria(banco)
        self.sugestoes = RepoSugestoesMemoria(banco)
        self.saidas = RepoSaidasMemoria(banco)
        self.historico = RepoHistoricoMemoria(banco)
        self.auditoria = RepoAuditoriaMemoria(banco)

    def __enter__(self) -> "UnidadeDeTrabalhoMemoria":
        self._copia = copy.deepcopy(self.banco.__dict__)
        self._commitado = False
        return self

    def __exit__(self, *exc) -> None:
        if exc[0] is not None or not self._commitado:   # rollback
            self.banco.__dict__.update(self._copia)

    def commit(self) -> None:
        self._commitado = True


class RelogioMemoria:
    """Mesma regra do RelogioSQL: sem data definida, o dia zero é a entrada mais antiga recebida;
    sem nenhuma solicitação ainda, devolve `date.min` (o serviço usa max(hoje, data do fato))."""

    def __init__(self, banco: BancoMemoria):
        self.b = banco

    @property
    def sim(self) -> dict:                  # persiste no "banco", como a tabela `simulacao`; lido a cada acesso
        return self.b.simulacao             # porque o rollback da UoW troca os dicts do banco por cópias

    def hoje(self) -> date:
        if self.sim["hoje"] is None and self.b.solicitacoes:
            self.sim["hoje"] = min(date.fromisoformat(s["data_entrada_fila"]) for s in self.b.solicitacoes.values())
        return self.sim["hoje"] or date.min

    def avancar(self, dias: int = 1) -> date:
        self.sim["hoje"] = self.hoje() + timedelta(days=dias)
        return self.sim["hoje"]

    @property
    def auto_aprovar(self) -> bool:
        return self.sim["auto_aprovar"]

    @auto_aprovar.setter
    def auto_aprovar(self, valor: bool) -> None:
        self.sim["auto_aprovar"] = bool(valor)


class RedatorFake:
    def justificar(self, s: Sugestao, av) -> str:
        return s.justificativa

    def explicar(self, s: Sugestao) -> str:
        return s.justificativa

    def explicar_sem_llm(self, s: Sugestao) -> str:
        return s.justificativa
