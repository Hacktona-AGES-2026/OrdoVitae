"""Simulador (só com SIMULADOR=1): faz o papel do sistema externo, alimentando o serviço dia a dia.

Usa exatamente os mesmos casos de uso da integração real; só a ORIGEM dos dados é simulada.
"""
from datetime import date, timedelta
from typing import Protocol

from .casos_uso import ServicoFila
from .erros import TransicaoInvalida


class Chegada(Protocol):
    tipo: str
    dados: dict
    resposta_llm: list[dict] | None


class Fonte(Protocol):
    def chegadas(self, dia: date) -> list[Chegada]: ...
    def primeira_data(self) -> date: ...


class Simulador:
    def __init__(self, servico: ServicoFila, fonte: Fonte):
        self.svc = servico
        self.fonte = fonte

    def avancar(self, dias: int = 1, foto: bool = True) -> date:
        """Para cada dia: anda o relógio, injeta as chegadas do dia e (opcionalmente) fotografa a fila."""
        if dias < 1:
            raise TransicaoInvalida("dias deve ser >= 1")
        for _ in range(dias):
            hoje = self.svc.relogio.hoje()
            if hoje == date.min:                     # sistema vazio: o primeiro passo é o dia zero
                dia = self.fonte.primeira_data()
            else:
                dia = self.svc.relogio.avancar(1)
            self._injetar(dia)
            if foto:
                self.svc.fotografar_fila()
        return self.svc.relogio.hoje()

    def pular_ate(self, alvo: date) -> date:
        """Avanço rápido até `alvo`, com aprovação automática ligada e sem fotos (só a do último dia)."""
        hoje = self.svc.relogio.hoje()
        if hoje != date.min and alvo <= hoje:
            raise TransicaoInvalida(f"a simulação já está em {hoje}")
        anterior = self.svc.relogio.auto_aprovar
        self.svc.configurar_simulacao(auto_aprovar=True)
        try:
            if hoje == date.min:
                self.avancar(1, foto=False)
            dias = (alvo - self.svc.relogio.hoje()).days
            if dias > 0:
                self.avancar(dias, foto=False)
            self.svc.fotografar_fila()
        finally:
            self.svc.configurar_simulacao(auto_aprovar=anterior)
        return self.svc.relogio.hoje()

    def _injetar(self, dia: date) -> None:
        for c in self.fonte.chegadas(dia):
            receber = self.svc.receber_solicitacao if c.tipo == "solicitacao" else self.svc.receber_evento
            receber(c.dados, c.resposta_llm)


def dias_entre(de: date, ate: date) -> list[date]:
    return [de + timedelta(days=i) for i in range((ate - de).days + 1)]
