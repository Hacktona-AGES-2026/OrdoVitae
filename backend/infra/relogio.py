"""Relógio da simulação persistido na tabela `simulacao` (linha única). Cada chamada usa sua própria sessão."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from .orm import SimulacaoORM, SolicitacaoORM


class RelogioSQL:
    def __init__(self, fabrica: sessionmaker):
        self.fabrica = fabrica

    def _linha(self, s) -> SimulacaoORM:
        linha = s.get(SimulacaoORM, 1)
        if linha is None:
            linha = SimulacaoORM(id=1, hoje=None, auto_aprovar=False)
            s.add(linha)
        return linha

    def hoje(self) -> date:
        """Sem data definida, o dia zero é a entrada mais antiga recebida; sem solicitações, `date.min`."""
        with self.fabrica() as s:
            linha = self._linha(s)
            if linha.hoje is None:
                linha.hoje = s.scalar(select(func.min(SolicitacaoORM.data_entrada)))
                if linha.hoje is not None:
                    s.commit()
            return linha.hoje or date.min

    def avancar(self, dias: int = 1) -> date:
        base = self.hoje()
        with self.fabrica() as s:
            linha = self._linha(s)
            linha.hoje = base + timedelta(days=dias)
            s.commit()
            return linha.hoje

    @property
    def auto_aprovar(self) -> bool:
        with self.fabrica() as s:
            return self._linha(s).auto_aprovar

    @auto_aprovar.setter
    def auto_aprovar(self, valor: bool) -> None:
        with self.fabrica() as s:
            self._linha(s).auto_aprovar = bool(valor)
            s.commit()
