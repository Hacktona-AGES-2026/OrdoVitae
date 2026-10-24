"""Score de risco: risco do paciente (ASA) × risco do procedimento. Desce o paciente na fila.

Função pura sobre dados estruturados da solicitação (não usa achados nem LLM).
"""
from dataclasses import dataclass

from . import config


@dataclass(frozen=True)
class AvaliacaoRisco:
    asa: int
    asa_estimado: bool          # True → gerar alerta "sem ASA, solicitar avaliação"
    nivel_paciente: str         # baixo | medio | alto
    nivel_procedimento: str
    valor: float                # 0–1

    @property
    def motivo(self) -> str:
        asa = f"ASA {self.asa}{' (estimado pelas comorbidades)' if self.asa_estimado else ''}"
        return f"paciente {self.nivel_paciente} ({asa}), procedimento {self.nivel_procedimento}"


def avaliar_risco(asa: int | None, n_comorbidades: int, risco_procedimento: int) -> AvaliacaoRisco:
    estimado = asa is None
    if estimado:
        asa = config.ASA_ESTIMADO_POR_COMORBIDADES.get(n_comorbidades, 3)
    nivel_pac = config.ASA_NIVEL[min(max(asa, 1), 4)]
    nivel_proc = config.PROCEDIMENTO_NIVEL[min(max(risco_procedimento, 1), 5)]
    valor = (config.NIVEL_RISCO[nivel_pac] + config.NIVEL_RISCO[nivel_proc]) / 2
    return AvaliacaoRisco(asa, estimado, nivel_pac, nivel_proc, valor)
