"""Unidade de trabalho SQLAlchemy: `with uow:` abre a Session; `uow.commit()` explícito; sem commit ou com erro → rollback."""
from sqlalchemy.orm import Session, sessionmaker

from .db import fabrica_para
from .repositorios import (RepoAchadosSQL, RepoAuditoriaSQL, RepoEstadosSQL, RepoEventosSQL, RepoHistoricoSQL,
                           RepoSaidasSQL, RepoSolicitacoesSQL, RepoSugestoesSQL)


class UnidadeDeTrabalhoSQL:
    def __init__(self, fabrica: sessionmaker | str):
        """`fabrica`: sessionmaker (uso normal) ou URL (atalho para testes: `UnidadeDeTrabalhoSQL("sqlite://")`)."""
        self.fabrica = fabrica_para(fabrica) if isinstance(fabrica, str) else fabrica
        self.sessao: Session | None = None

    def __enter__(self) -> "UnidadeDeTrabalhoSQL":
        self.sessao = self.fabrica()
        self.solicitacoes = RepoSolicitacoesSQL(self.sessao)
        self.eventos = RepoEventosSQL(self.sessao)
        self.achados = RepoAchadosSQL(self.sessao)
        self.estados = RepoEstadosSQL(self.sessao)
        self.sugestoes = RepoSugestoesSQL(self.sessao)
        self.saidas = RepoSaidasSQL(self.sessao)
        self.historico = RepoHistoricoSQL(self.sessao)
        self.auditoria = RepoAuditoriaSQL(self.sessao)
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.sessao.rollback()          # no-op depois de commit; desfaz o resto (erro ou commit esquecido)
        finally:
            self.sessao.close()
            self.sessao = None

    def commit(self) -> None:
        self.sessao.commit()
