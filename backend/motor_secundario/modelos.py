"""Contratos de dados do Motor Secundário de Decisão Compartilhada.

Projetado para envio direto ao Frontend (JSON/API) e persistência em SQLite,
sem acoplamento com `backend/motor/modelos.py`.
"""
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class CategoriaDecisao(str, Enum):
    QUEBRA_ADESAO = "quebra_adesao"                  # Parou remédio, sem insulina, tabagismo mantido, faltas sem justificativa
    MANEJO_MEDICACAO = "manejo_medicacao"            # Anticoagulante oral, ajuste glicêmico pré-op obrigatório
    MELHORA_CONSERVADORA = "melhora_conservadora"    # Melhorou com remédio / tratamento clínico
    ADESAO_POSITIVA = "adesao_positiva"              # Aderiu à dieta/medicação, HbA1c em queda, liberado pela endócrino
    PREFERENCIA_PACIENTE = "preferencia_paciente"    # Pede cirurgia nas férias, desejo eletivo em quadro assintomático
    BARREIRA_LOGISTICA = "barreira_logistica"        # Falta de transporte, TFD, mora sozinho/dependente de familiar


class CodigoDecisao(str, Enum):
    INTERRUPCAO_MEDICACAO = "INTERRUPCAO_MEDICACAO"            # Ex: ficou sem insulina na UBS por 1 mês
    DESCONTROLE_METABOLICO_DIETA = "DESCONTROLE_METABOLICO_DIETA"  # Ex: Glicemia 248 / HbA1c > 8.5% exigindo adesão
    TABAGISMO_ATIVO_ORIENTADO = "TABAGISMO_ATIVO_ORIENTADO"    # Ex: Tabagista ativo, orientado a cessar
    SUSPENSAO_ANTICOAGULANTE = "SUSPENSAO_ANTICOAGULANTE"      # Ex: Em uso de anticoagulante oral, orientar suspensão pré-op
    FALTA_NAO_JUSTIFICADA = "FALTA_NAO_JUSTIFICADA"            # Ex: Faltou à consulta/exame/pré-anestésico sem barreira TFD
    MELHORA_COM_REMEDIO = "MELHORA_COM_REMEDIO"                # Ex: Refere melhora com remédio / não deseja operar agora
    ADESAO_COMPROVADA = "ADESAO_COMPROVADA"                    # Ex: Aderiu ao tratamento, glicemias controladas / HbA1c em queda
    PEDIDO_JANELA_FERIAS = "PEDIDO_JANELA_FERIAS"              # Ex: Paciente pede cirurgia no período de férias
    CIRURGIA_POR_DESEJO_PACIENTE = "CIRURGIA_POR_DESEJO_PACIENTE"  # Ex: Lesão benigna/assintomática, exérese por desejo
    BARREIRA_TRANSPORTE_TFD = "BARREIRA_TRANSPORTE_TFD"        # Ex: Falta de transporte / necessita TFD / exames no mesmo dia
    VULNERABILIDADE_REDE_APOIO = "VULNERABILIDADE_REDE_APOIO"  # Ex: Mora sozinha, dependente de familiares, contato via ACS


class NivelAtencaoMedica(str, Enum):
    CRITICO = "critico"          # Exige intervenção médica imediata (quebra de adesão grave ou conflito oncológico)
    MODERADO = "moderado"        # Exige alinhamento pré-operatório (suspender anticoagulante, agendar TFD, reavaliar melhora)
    INFORMATIVO = "informativo"  # Preferência válida ou adesão positiva (sinal verde)
    NENHUM = "nenhum"


class StatusAdesao(str, Enum):
    QUEBRA_ADESAO = "quebra_adesao"
    ALERTA_MANEJO = "alerta_manejo"
    REAVALIAR_INDICACAO = "reavaliar_indicacao"
    CONFLITO_DECISAO = "conflito_decisao"
    BARREIRA_SOCIAL = "barreira_social"
    ADESAO_POSITIVA = "adesao_positiva"
    PREFERENCIA_VALIDA = "preferencia_valida"
    PADRAO = "padrao"


@dataclass
class ItemDecisaoCompartilhada:
    codigo: CodigoDecisao
    categoria: CategoriaDecisao
    nivel_atencao: NivelAtencaoMedica
    titulo: str
    descricao_medica: str
    recomendacao_conduta: str
    trecho_evidencia: str
    fonte: str                   # "observacoes" | "justificativa_clinica" | "eventos_clinicos" | "achados_llm" | "comorbidades"
    valido_para_decisao: bool    # True se a preferência/conduta é clinicamente segura; False se há conflito com gravidade
    conflito_clinico: str = ""   # Explica por que não é seguro adiar/suspender (ex.: paciente oncológico pedindo férias)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["codigo"] = self.codigo.value
        d["categoria"] = self.categoria.value
        d["nivel_atencao"] = self.nivel_atencao.value
        return d


@dataclass
class AvaliacaoDecisaoCompartilhada:
    solicitacao_id: str
    paciente_id: str
    elegivel_decisao_compartilhada: bool
    status_adesao: StatusAdesao
    nivel_atencao_maximo: NivelAtencaoMedica
    tem_conflito_clinico: bool
    resumo_medico: str
    itens: list[ItemDecisaoCompartilhada] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "solicitacao_id": self.solicitacao_id,
            "paciente_id": self.paciente_id,
            "elegivel_decisao_compartilhada": self.elegivel_decisao_compartilhada,
            "status_adesao": self.status_adesao.value,
            "nivel_atencao_maximo": self.nivel_atencao_maximo.value,
            "tem_conflito_clinico": self.tem_conflito_clinico,
            "total_itens": len(self.itens),
            "resumo_medico": self.resumo_medico,
            "itens": [item.to_dict() for item in self.itens],
        }
