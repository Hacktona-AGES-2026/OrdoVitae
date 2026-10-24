"""Repositórios SQLAlchemy: um por porta de servico/portas.py, todos recebendo a Session da unidade de trabalho."""
from datetime import date

from sqlalchemy import delete, exists, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from motor import AvaliacaoRisco, EstadoAprovado, ItemFila
from motor.modelos import Achado, Sugestao
from servico.modelos import StatusSugestao, SugestaoRegistrada

from . import conversores as cv
from .orm import (AchadoORM, AuditoriaORM, EstadoORM, EventoORM, HistoricoFilaORM, SaidaORM, SolicitacaoORM,
                  SugestaoORM)


def _data(valor) -> date | None:
    return date.fromisoformat(str(valor)[:10]) if valor else None


class RepoSolicitacoesSQL:
    def __init__(self, s: Session):
        self.s = s

    def salvar(self, dados: dict) -> None:
        self.s.merge(SolicitacaoORM(solicitacao_id=dados["solicitacao_id"], paciente_id=dados.get("paciente_id"),
                                    procedimento_id=dados.get("procedimento_id"),
                                    data_entrada=_data(dados["data_entrada_fila"]), dados=dict(dados)))

    def obter(self, sid: str) -> dict | None:
        linha = self.s.get(SolicitacaoORM, sid)
        return dict(linha.dados) if linha else None

    def _ativas(self):
        sem_saida = ~exists().where(SaidaORM.solicitacao_id == SolicitacaoORM.solicitacao_id)
        return select(SolicitacaoORM).where(sem_saida).order_by(SolicitacaoORM.data_entrada, SolicitacaoORM.solicitacao_id)

    def ativas(self) -> list[dict]:
        return [dict(l.dados) for l in self.s.scalars(self._ativas())]

    def esta_ativa(self, sid: str) -> bool:
        return self.s.get(SolicitacaoORM, sid) is not None and self.s.get(SaidaORM, sid) is None

    def ativa_do_paciente(self, pid: str, proc_id: str) -> dict | None:
        linha = self.s.scalars(self._ativas().where(SolicitacaoORM.paciente_id == pid,
                                                    SolicitacaoORM.procedimento_id == proc_id)).first()
        return dict(linha.dados) if linha else None

    def datas_entrada(self, sids: list[str]) -> dict[str, date]:
        q = select(SolicitacaoORM.solicitacao_id, SolicitacaoORM.data_entrada).where(SolicitacaoORM.solicitacao_id.in_(sids))
        return {sid: entrada for sid, entrada in self.s.execute(q)}


class RepoEventosSQL:
    def __init__(self, s: Session):
        self.s = s

    def salvar(self, dados: dict) -> None:
        self.s.merge(EventoORM(evento_id=dados["evento_id"], solicitacao_id=dados.get("solicitacao_id"),
                               tipo_evento=dados.get("tipo_evento"), data_evento=_data(dados.get("data_evento")),
                               dados=dict(dados)))

    def existe(self, evento_id: str) -> bool:
        self.s.flush()
        return self.s.get(EventoORM, evento_id) is not None

    def da_solicitacao(self, sid: str) -> list[dict]:
        linhas = self.s.scalars(select(EventoORM).where(EventoORM.solicitacao_id == sid)
                                .order_by(EventoORM.data_evento, EventoORM.evento_id))
        return [dict(l.dados) for l in linhas]


class RepoAchadosSQL:
    def __init__(self, s: Session):
        self.s = s

    def adicionar(self, achados: list[Achado]) -> None:
        """Achado repetido (mesma solicitação + chave) é ignorado pelo UNIQUE, sem erro."""
        if not achados:
            return
        linhas = [{c.name: getattr(cv.achado_para_linha(a), c.name) for c in AchadoORM.__table__.columns if c.name != "id"}
                  for a in achados]
        self.s.execute(insert(AchadoORM).values(linhas).on_conflict_do_nothing(index_elements=["solicitacao_id", "chave"]))

    def da_solicitacao(self, sid: str) -> list[Achado]:
        return [cv.achado_de_linha(l) for l in
                self.s.scalars(select(AchadoORM).where(AchadoORM.solicitacao_id == sid).order_by(AchadoORM.id))]

    def de_varias(self, sids: list[str]) -> dict[str, list[Achado]]:
        saida: dict[str, list[Achado]] = {sid: [] for sid in sids}
        for l in self.s.scalars(select(AchadoORM).where(AchadoORM.solicitacao_id.in_(sids)).order_by(AchadoORM.id)):
            saida[l.solicitacao_id].append(cv.achado_de_linha(l))
        return saida


class RepoEstadosSQL:
    def __init__(self, s: Session):
        self.s = s

    def obter(self, sid: str) -> tuple[EstadoAprovado, AvaliacaoRisco] | None:
        linha = self.s.get(EstadoORM, sid)
        return cv.estado_de_linha(linha) if linha else None

    def salvar(self, sid: str, estado: EstadoAprovado, risco: AvaliacaoRisco, provisorio: bool) -> None:
        linha = self.s.get(EstadoORM, sid)
        novo = cv.estado_para_linha(sid, estado, risco, provisorio, linha)
        if linha is None:
            self.s.add(novo)

    def todos(self) -> dict[str, tuple[EstadoAprovado, AvaliacaoRisco]]:
        return {l.solicitacao_id: cv.estado_de_linha(l) for l in self.s.scalars(select(EstadoORM))}


class RepoSugestoesSQL:
    def __init__(self, s: Session):
        self.s = s

    def criar(self, sug: Sugestao, criada_em: date) -> int:
        linha = cv.sugestao_para_linha(sug, criada_em)
        self.s.add(linha)
        self.s.flush()                                   # gera o id
        return linha.id

    def obter(self, id: int) -> SugestaoRegistrada | None:
        linha = self.s.get(SugestaoORM, id)
        return cv.sugestao_de_linha(linha) if linha else None

    def pendentes_de(self, sid: str) -> list[SugestaoRegistrada]:
        q = select(SugestaoORM).where(SugestaoORM.solicitacao_id == sid,
                                      SugestaoORM.status == StatusSugestao.PENDENTE.value).order_by(SugestaoORM.id)
        return [cv.sugestao_de_linha(l) for l in self.s.scalars(q)]

    def listar(self, status: str | None = None) -> list[SugestaoRegistrada]:
        q = select(SugestaoORM).order_by(SugestaoORM.id)
        if status is not None:
            q = q.where(SugestaoORM.status == StatusSugestao(status).value)
        return [cv.sugestao_de_linha(l) for l in self.s.scalars(q)]

    def mudar_status(self, id: int, status: str, por: str, em: date, comentario: str = "") -> None:
        linha = self.s.get(SugestaoORM, id)
        linha.status, linha.decidida_por, linha.decidida_em, linha.comentario = (
            StatusSugestao(status).value, por, em, comentario)


class RepoSaidasSQL:
    def __init__(self, s: Session):
        self.s = s

    def registrar(self, sid: str, motivo: str, justificativa: str, em: date) -> None:
        self.s.add(SaidaORM(solicitacao_id=sid, motivo=motivo, justificativa=justificativa, em=em))


class RepoHistoricoSQL:
    def __init__(self, s: Session):
        self.s = s

    def salvar_foto(self, data: date, itens: list[ItemFila]) -> None:
        """Uma foto por dia: refazer a foto do mesmo dia substitui a anterior."""
        self.s.execute(delete(HistoricoFilaORM).where(HistoricoFilaORM.data == data))
        self.s.add_all(HistoricoFilaORM(data=data, solicitacao_id=i.solicitacao_id, posicao=i.posicao,
                                        score=i.score(data), classe=i.classe) for i in itens)

    def foto(self, data: date) -> list[dict]:
        q = select(HistoricoFilaORM).where(HistoricoFilaORM.data == data).order_by(HistoricoFilaORM.posicao)
        return [{"solicitacao_id": l.solicitacao_id, "posicao": l.posicao, "score": l.score, "classe": l.classe}
                for l in self.s.scalars(q)]

    def posicoes(self, sid: str) -> list[tuple[date, int, float]]:
        q = select(HistoricoFilaORM).where(HistoricoFilaORM.solicitacao_id == sid).order_by(HistoricoFilaORM.data)
        return [(l.data, l.posicao, l.score) for l in self.s.scalars(q)]

    def datas(self) -> list[date]:
        return list(self.s.scalars(select(HistoricoFilaORM.data).distinct().order_by(HistoricoFilaORM.data)))


class RepoAuditoriaSQL:
    def __init__(self, s: Session):
        self.s = s

    def registrar(self, acao: str, sid: str, detalhe: str, por: str, em: date) -> None:
        self.s.add(AuditoriaORM(acao=acao, solicitacao_id=sid, detalhe=detalhe, por=por, em=em))
