"""Regras pequenas e puras que o serviço usa para montar os dados do motor.

`sem_urgencia` reproduz EXATAMENTE o critério do verificador oficial (verificar_fila_priorizada.py),
porque é ele que julga a regra de ouro. Usa só dados brutos da solicitação e eventos tipados: achados
de LLM ou de observação não contam (senão um paciente deixaria de ser "sem urgência" para nós e
continuaria sendo para o verificador, e a trava não protegeria o oncológico).
"""
import re
from datetime import date

from motor.modelos import Achado, CodigoAchado as C, Origem, Sugestao

from .modelos import MotivoSaida

# Copiados do verificador oficial.
KW_ALARME = re.compile(
    r"encarcer|estrangul|colangite|icter|pancreatite|enterorragia|melena|hematemese|suboclus|perda ponderal|disfagia|sepse|"
    r"hidronefrose|perda de funcao|transfund|hemoptise|rouquidao|linfonodo.*(?:fixo|palpavel)|sangramento espontaneo|acamad|"
    r"ulcera de pressao|quedas de repeticao|glaucoma facomorfico|retencao de co2|dano neurologico|psa em elevacao|dessaturacao|"
    r"angina em repouso|sincope|crescimento rapido|retencao urinaria aguda|massa anexial|ca-125")
CID_URGENTE = {"I200", "K403", "K400", "K420", "K430", "K800", "N132", "I832"}
EVENTOS_DE_PIORA = {C.PRONTO_SOCORRO, C.INTERNACAO, C.BIOPSIA_POSITIVA, C.PROGRESSAO_IMAGEM, C.REAVALIACAO_PIORA}

RISCO_PROCEDIMENTO_PADRAO = 3   # procedimento fora do catálogo conta como risco médio


def sem_urgencia(dados: dict, achados: list[Achado]) -> bool:
    """Definição conservadora de "sem urgência clínica" do verificador oficial."""
    dor = str(dados.get("intensidade_dor_eva") or "").strip()
    lim = str(dados.get("limitacao_funcional") or "").strip().lower() or "nenhuma"
    piora = any(a.codigo in EVENTOS_DE_PIORA and a.evidencia.fonte == "evento" and a.origem == Origem.REGRA
                for a in achados)
    return (not oncologico(dados)
            and (float(dor) if dor else 0) <= 3
            and lim in ("nenhuma", "leve")
            and cid(dados) not in CID_URGENTE
            and not piora
            and not KW_ALARME.search(str(dados.get("justificativa_clinica") or "").lower()))


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
