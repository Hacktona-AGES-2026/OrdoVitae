"""Regras pequenas e puras que o serviço usa para montar os dados do motor.

`sem_urgencia` repete o critério `NAO_CALMO` de spikes/carga.py; o lugar final dele é o motor.
"""
import re
from datetime import date

from motor.modelos import Achado, CodigoAchado as C, Sugestao

from .modelos import MotivoSaida

NAO_CALMO = {C.CID_MALIGNO, C.CID_URGENTE, C.SINAL_ALARME, C.DOR_INTENSA, C.DOR_MODERADA, C.LIMITACAO_GRAVE,
             C.LIMITACAO_MODERADA, C.PRONTO_SOCORRO, C.INTERNACAO, C.BIOPSIA_POSITIVA, C.PROGRESSAO_IMAGEM,
             C.REAVALIACAO_PIORA}

RISCO_PROCEDIMENTO_PADRAO = 3   # procedimento fora do catálogo conta como risco médio


def sem_urgencia(achados: list[Achado]) -> bool:
    """Definição conservadora de "sem urgência clínica" (a do verificador oficial)."""
    return not ({a.codigo for a in achados} & NAO_CALMO)


def oncologico(dados: dict) -> bool:
    """Pelo CID (C*), nunca pela flag do cadastro."""
    return cid(dados).startswith("C")


def cid(dados: dict) -> str:
    return str(dados.get("cid_principal") or "").upper().replace(".", "").strip()


def n_comorbidades(dados: dict) -> int:
    c = str(dados.get("comorbidades") or "").strip().lower()
    return 0 if c in ("", "nenhuma") else len([x for x in c.split(";") if x.strip()])


def asa(dados: dict) -> int | None:
    valor = str(dados.get("asa") or "").strip()
    return int(float(valor)) if valor else None


def data(valor) -> date:
    return valor if isinstance(valor, date) else date.fromisoformat(str(valor)[:10])


OPEROU_FORA = re.compile(r"outro servi|conv[eê]nio|particular|\boperou\b|realizou o procedimento")


def motivo_saida(s: Sugestao) -> MotivoSaida:
    """Duplicata é a única REMOVER criada pelo serviço (sem achados); as do motor vêm de SAIU_DA_FILA.

    No dataset: "ja realizou o procedimento em outro servico", "operou pelo convenio" → outro serviço;
    "nao deseja mais operar", "DESISTIU DO PROCEDIMENTO" → desistência.
    """
    if not s.motivos:
        return MotivoSaida.DUPLICATA
    texto = " ".join(a.evidencia.trecho.lower() for a in s.motivos)
    return MotivoSaida.OUTRO_SERVICO if OPEROU_FORA.search(texto) else MotivoSaida.DESISTENCIA
