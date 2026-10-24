"""Módulo de extração de achados clínicos a partir de solicitações e eventos.

Contratos consumidos de backend.motor.modelos:
- Achado, CodigoAchado, Dimensao, Evidencia, Origem
"""
import re
from datetime import date, datetime
from typing import Any

from motor.modelos import (
    Achado,
    CodigoAchado as C,
    Dimensao as D,
    Evidencia,
    Origem,
)

KW_ALARME = re.compile(
    r"encarcer|estrangul|colangite|icter|pancreatite|enterorragia|melena|hematemese|"
    r"suboclus|perda ponderal|disfagia|sepse|hidronefrose|perda de funcao|transfund|"
    r"hemoptise|rouquidao|linfonodo.*?(?:fixo|palpavel)|sangramento espontaneo|acamad|"
    r"ulcera de pressao|quedas de repeticao|glaucoma facomorfico|retencao de co2|"
    r"dano neurologico|psa em elevacao|dessaturacao|angina em repouso|sincope|"
    r"crescimento rapido|retencao urinaria aguda|massa anexial|ca-125",
    re.IGNORECASE,
)

CID_URGENTE = {"I200", "K403", "K400", "K420", "K430", "K800", "N132", "I832"}

CODIGO_DIMENSAO = {
    # Gravidade
    C.CID_MALIGNO: D.GRAVIDADE,
    C.CID_SUSPEITO: D.GRAVIDADE,
    C.CID_URGENTE: D.GRAVIDADE,
    C.BIOPSIA_POSITIVA: D.GRAVIDADE,
    C.SINAL_ALARME: D.GRAVIDADE,
    C.DOR_INTENSA: D.GRAVIDADE,
    C.DOR_MODERADA: D.GRAVIDADE,
    C.LIMITACAO_GRAVE: D.GRAVIDADE,
    C.LIMITACAO_MODERADA: D.GRAVIDADE,
    # Deterioração
    C.INTERNACAO: D.DETERIORACAO,
    C.PRONTO_SOCORRO: D.DETERIORACAO,
    C.PROGRESSAO_IMAGEM: D.DETERIORACAO,
    C.REAVALIACAO_PIORA: D.DETERIORACAO,
    C.PIORA_RELATADA: D.DETERIORACAO,
    C.HBA1C_DESCONTROLADA: D.DETERIORACAO,
    C.MELHORA: D.DETERIORACAO,
    # Alerta
    C.PERDA_CONTATO: D.ALERTA,
    C.SAIU_DA_FILA: D.ALERTA,
    C.OTIMIZAR_CLINICAMENTE: D.ALERTA,
    C.DADOS_INSUFICIENTES: D.ALERTA,
}


def _parse_date(val: Any) -> date | None:
    if isinstance(val, date):
        return val
    if not val:
        return None
    val_str = str(val).strip()
    try:
        return date.fromisoformat(val_str[:10])
    except (ValueError, TypeError):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(val_str[:10], fmt).date()
            except (ValueError, TypeError):
                continue
    return None


def _is_cid_suspeito(cid: str) -> bool:
    if not cid:
        return False
    cid_upper = cid.upper().replace(".", "").strip()
    if cid_upper.startswith("R91"):
        return True
    m = re.match(r"^D(\d{2})", cid_upper)
    if m:
        num = int(m.group(1))
        return 37 <= num <= 48
    return False


def extrair_solicitacao(
    sol: dict, resposta_llm: list[dict] | None = None
) -> list[Achado]:
    """Extrai achados clínicos de uma solicitação cirúrgica."""
    achados: list[Achado] = []
    sol_id = str(sol.get("solicitacao_id") or "").strip()
    data_fato = _parse_date(sol.get("data_entrada_fila"))

    # 1. CID Principal
    cid = str(sol.get("cid_principal") or "").upper().replace(".", "").strip()
    if cid:
        if cid.startswith("C"):
            achados.append(
                Achado(
                    codigo=C.CID_MALIGNO,
                    dimensao=D.GRAVIDADE,
                    solicitacao_id=sol_id,
                    data_fato=data_fato,
                    evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:cid_principal", trecho=cid),
                )
            )
        elif _is_cid_suspeito(cid):
            achados.append(
                Achado(
                    codigo=C.CID_SUSPEITO,
                    dimensao=D.GRAVIDADE,
                    solicitacao_id=sol_id,
                    data_fato=data_fato,
                    evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:cid_principal", trecho=cid),
                )
            )

        if cid in CID_URGENTE:
            achados.append(
                Achado(
                    codigo=C.CID_URGENTE,
                    dimensao=D.GRAVIDADE,
                    solicitacao_id=sol_id,
                    data_fato=data_fato,
                    evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:cid_principal", trecho=cid),
                )
            )

    # 2. Dor (EVA)
    dor_raw = sol.get("intensidade_dor_eva")
    if dor_raw is not None and str(dor_raw).strip() != "":
        try:
            dor = int(dor_raw)
            if dor >= 7:
                achados.append(
                    Achado(
                        codigo=C.DOR_INTENSA,
                        dimensao=D.GRAVIDADE,
                        solicitacao_id=sol_id,
                        data_fato=data_fato,
                        evidencia=Evidencia(
                            fonte="solicitacao",
                            ref=f"{sol_id}:intensidade_dor_eva",
                            trecho=str(dor),
                        ),
                    )
                )
            elif 4 <= dor <= 6:
                achados.append(
                    Achado(
                        codigo=C.DOR_MODERADA,
                        dimensao=D.GRAVIDADE,
                        solicitacao_id=sol_id,
                        data_fato=data_fato,
                        evidencia=Evidencia(
                            fonte="solicitacao",
                            ref=f"{sol_id}:intensidade_dor_eva",
                            trecho=str(dor),
                        ),
                    )
                )
        except (ValueError, TypeError):
            pass

    # 3. Limitação Funcional
    lim = str(sol.get("limitacao_funcional") or "").lower().strip()
    if lim == "grave":
        achados.append(
            Achado(
                codigo=C.LIMITACAO_GRAVE,
                dimensao=D.GRAVIDADE,
                solicitacao_id=sol_id,
                data_fato=data_fato,
                evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:limitacao_funcional", trecho=lim),
            )
        )
    elif lim == "moderada":
        achados.append(
            Achado(
                codigo=C.LIMITACAO_MODERADA,
                dimensao=D.GRAVIDADE,
                solicitacao_id=sol_id,
                data_fato=data_fato,
                evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:limitacao_funcional", trecho=lim),
            )
        )

    # 4. Justificativa Clínica (tamanho e regex de alarme)
    just = str(sol.get("justificativa_clinica") or "").strip()
    if len(just) < 30:
        achados.append(
            Achado(
                codigo=C.DADOS_INSUFICIENTES,
                dimensao=D.ALERTA,
                solicitacao_id=sol_id,
                data_fato=data_fato,
                evidencia=Evidencia(fonte="solicitacao", ref=f"{sol_id}:justificativa_clinica", trecho=just),
            )
        )

    if just:
        matches = list(KW_ALARME.finditer(just))
        if matches:
            trechos = "; ".join(dict.fromkeys(m.group(0) for m in matches))
            achados.append(
                Achado(
                    codigo=C.SINAL_ALARME,
                    dimensao=D.GRAVIDADE,
                    solicitacao_id=sol_id,
                    data_fato=data_fato,
                    evidencia=Evidencia(
                        fonte="solicitacao",
                        ref=f"{sol_id}:justificativa_clinica",
                        trecho=trechos,
                    ),
                )
            )

    # 5. Achados de LLM pré-computados (se houver)
    if resposta_llm:
        _anexar_achados_llm(achados, sol_id, just, resposta_llm)

    return achados


def extrair_evento(
    ev: dict, resposta_llm: list[dict] | None = None
) -> list[Achado]:
    """Extrai achados clínicos de um evento de acompanhamento."""
    achados: list[Achado] = []
    sol_id = str(ev.get("solicitacao_id") or "").strip()
    evt_id = str(ev.get("evento_id") or "").strip()
    tipo = str(ev.get("tipo_evento") or "").lower().strip()
    resultado = str(ev.get("resultado") or "").lower().strip()
    desc = str(ev.get("descricao") or "").strip()
    data_fato = _parse_date(ev.get("data_evento"))
    evidencia = Evidencia(fonte="evento", ref=evt_id, trecho=desc)

    if tipo == "biopsia":
        if resultado == "positivo":
            achados.append(
                Achado(codigo=C.BIOPSIA_POSITIVA, dimensao=D.GRAVIDADE, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
    elif tipo == "pronto_socorro":
        achados.append(
            Achado(codigo=C.PRONTO_SOCORRO, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
        )
    elif tipo == "internacao":
        achados.append(
            Achado(codigo=C.INTERNACAO, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
        )
    elif tipo == "exame_imagem":
        if resultado == "progressao":
            achados.append(
                Achado(codigo=C.PROGRESSAO_IMAGEM, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
    elif tipo == "consulta_reavaliacao":
        if resultado == "piora":
            achados.append(
                Achado(codigo=C.REAVALIACAO_PIORA, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
        elif resultado == "melhora":
            achados.append(
                Achado(codigo=C.MELHORA, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
    elif tipo == "contato_telefonico":
        if resultado == "relata_piora":
            achados.append(
                Achado(codigo=C.PIORA_RELATADA, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
        elif resultado == "relata_melhora":
            achados.append(
                Achado(codigo=C.MELHORA, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
        elif resultado == "nao_atendeu":
            achados.append(
                Achado(codigo=C.PERDA_CONTATO, dimensao=D.ALERTA, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
        elif resultado in ("desistiu", "informou_cirurgia_outro_servico"):
            achados.append(
                Achado(codigo=C.SAIU_DA_FILA, dimensao=D.ALERTA, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
            )
    elif tipo == "falta":
        achados.append(
            Achado(codigo=C.PERDA_CONTATO, dimensao=D.ALERTA, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
        )
    elif tipo == "hba1c":
        val_raw = ev.get("valor_numerico")
        if val_raw is not None and str(val_raw).strip() != "":
            try:
                val_num = float(str(val_raw).replace(",", "."))
                if val_num > 8.5:
                    achados.append(
                        Achado(codigo=C.HBA1C_DESCONTROLADA, dimensao=D.DETERIORACAO, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
                    )
                    achados.append(
                        Achado(codigo=C.OTIMIZAR_CLINICAMENTE, dimensao=D.ALERTA, solicitacao_id=sol_id, data_fato=data_fato, evidencia=evidencia)
                    )
            except (ValueError, TypeError):
                pass

    if resposta_llm:
        _anexar_achados_llm(achados, sol_id, desc, resposta_llm, fonte="evento", ref=evt_id)

    return achados


def _anexar_achados_llm(
    achados: list[Achado],
    sol_id: str,
    texto_original: str,
    resposta_llm: list[dict],
    fonte: str = "solicitacao",
    ref: str = "",
) -> None:
    """Valida e anexa achados produzidos por LLM."""
    texto_lower = texto_original.lower()
    for item in resposta_llm:
        cod_str = item.get("codigo")
        try:
            codigo = C(cod_str)
        except (ValueError, KeyError):
            continue

        trecho = str(item.get("trecho") or "").strip()
        # Trecho literal deve existir no texto original (anti-alucinação)
        if not trecho or trecho.lower() not in texto_lower:
            continue

        dt_fato = _parse_date(item.get("data_fato"))
        dimensao = CODIGO_DIMENSAO.get(codigo, D.ALERTA)
        ref_final = ref or f"{sol_id}:justificativa_clinica"

        achados.append(
            Achado(
                codigo=codigo,
                dimensao=dimensao,
                solicitacao_id=sol_id,
                data_fato=dt_fato,
                evidencia=Evidencia(fonte=fonte, ref=ref_final, trecho=trecho),
                origem=Origem.LLM,
            )
        )
