"""Heurística de Decisão Compartilhada, Adesão Terapêutica e Gestão Manual da Fila.

Combina os achados extraídos pela LLM (`achados_llm`) com sinais estruturados e
contextuais da solicitação e dos eventos clínicos para responder a duas perguntas
para o médico regulador:
1. Existe algum fator de decisão compartilhada, adesão ao tratamento (remédio/dieta/preparo)
   ou preferência/barreira do paciente?
2. Essa conduta/escolha do paciente é clinicamente VÁLIDA (segura para pactuar adiamento
   ou tratamento conservador) ou existe um CONFLITO CLÍNICO (quadro oncológico/urgente
   onde a não-adesão ou adiamento coloca a vida/órgão em risco)?
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .modelos import (
    AvaliacaoDecisaoCompartilhada,
    CategoriaDecisao,
    CodigoDecisao,
    ItemDecisaoCompartilhada,
    NivelAtencaoMedica,
    StatusAdesao,
)

# ---------------------------------------------------------------------------
# Padrões clínicos e comportamentais para Decisão Compartilhada
# ---------------------------------------------------------------------------
RE_SEM_INSULINA_OU_REMEDIO = re.compile(
    r"(?:ficou\s+sem\s+insulina|sem\s+medica[cç][aã]o|suspendeu\s+por\s+conta|"
    r"interrompeu\s+(?:o\s+)?tratamento|uso\s+irregular|n[aã]o\s+toma\s+direito)",
    re.IGNORECASE,
)

RE_ORIENTADO_DIETA_GLICEMIA = re.compile(
    r"(?:orientad[oa]\s+ajuste\s+de\s+dieta|solicita\s+controle\s+glic[eê]mico\s+antes\s+de\s+liberar|"
    r"glicemia\s+de\s+jejum\s+\d+.*orientad|encaminhad[oa]\s+para\s+endocrinologia|"
    r"diabetes\s+mal\s+controlado)",
    re.IGNORECASE,
)

RE_TABAGISMO_ORIENTADO = re.compile(
    r"tabagista\s+ativ[oa],\s*orientad[oa]\s+a\s+cessar",
    re.IGNORECASE,
)

RE_ANTICOAGULANTE = re.compile(
    r"anticoagula(?:nte|[cç][aã]o)\s+oral|orientar\s+suspens[aã]o\s+pr[eé]-?op",
    re.IGNORECASE,
)

RE_MELHORA_REMEDIO_OBS = re.compile(
    r"n[aã]o\s+deseja\s+mais\s+operar\s+no\s+momento.*melhorou\s+com\s+rem[eé]dio|"
    r"melhorou\s+com\s+rem[eé]dio|melhora\s+dos\s+sintomas\s+com\s+tratamento\s+cl[ií]nico",
    re.IGNORECASE,
)

RE_ADESAO_POSITIVA = re.compile(
    r"aderiu\s+ao\s+tratamento,\s*glicemias?\s+controladas?|"
    r"hba1c\s+em\s+queda\s+ap[oó]s\s+ajuste\s+de\s+medica[cç][aã]o.*liberou\s+para\s+cirurgia|"
    r"acompanhamento\s+multidisciplinar\s+completo",
    re.IGNORECASE,
)

RE_PEDIDO_FERIAS = re.compile(
    r"pede\s+cirurgia\s+no\s+per[ií]odo\s+de\s+f[eé]rias",
    re.IGNORECASE,
)

RE_DESEJO_ELETIVO = re.compile(
    r"ex[eé]rese\s+por\s+desejo\s+d[ao]\s+paciente|"
    r"assintom[aá]tic[oa],\s*achado\s+de\s+(?:exame|us\s+de\s+rotina)\.\s*pct\s+(?:deseja\s+corre[cç][aã]o\s+eletiva|solicita\s+cirurgia)",
    re.IGNORECASE,
)

RE_BARREIRA_TRANSPORTE = re.compile(
    r"falta\s+de\s+transporte|dificuldade\s+de\s+transporte|necessita\s+tfd|"
    r"n[aã]o\s+tem\s+condi[cç][oõ]es\s+de\s+se\s+deslocar\s+com\s+frequ[eê]ncia|"
    r"solicita\s+agendar\s+exames\s+no\s+mesmo\s+dia\s+da\s+consulta",
    re.IGNORECASE,
)

RE_REDE_APOIO_VULNERAVEL = re.compile(
    r"dependente\s+de\s+familiares|depende\s+de\s+familiar\s+para\s+vir\s+ao\s+hospital|"
    r"mora\s+sozinh[oa],\s*j[aá]\s+teve\s+\d+\s+queda|dificuldade\s+auditiva,\s*contato\s+via\s+familiar|"
    r"mora\s+em\s+zona\s+rural,\s*sem\s+telefone\s+pr[oó]prio|n[aã]o\s+possui\s+telefone\s+fixo\.\s*contato\s+via\s+acs",
    re.IGNORECASE,
)

CIDS_URGENTES = {"I200", "K400", "K403", "K420", "K430", "K800", "N132", "I832"}


def _normalizar_cid(cid: str | None) -> str:
    if not cid:
        return ""
    return cid.strip().upper().replace(".", "").replace(" ", "")


def _verificar_gravidade_critica(
    solicitacao: dict[str, Any],
    eventos: list[dict[str, Any]],
    achados_llm: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Identifica se o paciente possui quadro oncológico, suspeito de alto risco ou urgência.

    Usado pela heurística para validar se uma preferência do paciente (ex: operar só nas férias)
    ou uma percepção subjetiva (ex: "melhorou com remédio") é clinicamente segura ou se gera
    um conflito que exige intervenção ativa do médico.
    """
    motivos: list[str] = []
    cid_norm = _normalizar_cid(solicitacao.get("cid_principal"))

    if cid_norm.startswith("C"):
        motivos.append(f"CID oncológico maligno ({solicitacao.get('cid_principal')})")
    elif cid_norm == "D051" or (len(cid_norm) >= 3 and "D37" <= cid_norm[:3] <= "D48") or cid_norm.startswith("R91"):
        motivos.append(f"Lesão de comportamento incerto/suspeita ({solicitacao.get('cid_principal')})")

    if cid_norm in CIDS_URGENTES:
        motivos.append(f"Patologia com risco agudo/obstrutivo ({solicitacao.get('cid_principal')})")

    codigos_llm = {a.get("codigo") for a in achados_llm}
    if "BIOPSIA_POSITIVA" in codigos_llm or any(
        e.get("tipo_evento") == "biopsia" and e.get("resultado") == "positivo" for e in eventos
    ):
        motivos.append("Biópsia positiva para malignidade")

    if "SINAL_ALARME" in codigos_llm:
        motivos.append("Sinal de alarme clínico identificado pela LLM")

    if "INTERNACAO" in codigos_llm or any(e.get("tipo_evento") == "internacao" for e in eventos):
        motivos.append("Histórico de internação hospitalar/UPA")

    if "PROGRESSAO_IMAGEM" in codigos_llm or any(
        e.get("tipo_evento") == "exame_imagem" and e.get("resultado") == "progressao" for e in eventos
    ):
        motivos.append("Progressão documentada em exame de imagem")

    return (len(motivos) > 0, motivos)


def avaliar_decisao_compartilhada(
    solicitacao: dict[str, Any],
    eventos: list[dict[str, Any]] | None = None,
    achados_llm: list[dict[str, Any]] | None = None,
) -> AvaliacaoDecisaoCompartilhada:
    """Avalia uma solicitação cirúrgica e retorna os itens de Decisão Compartilhada e Adesão."""
    eventos = eventos or []
    achados_llm = achados_llm or []

    sid = str(solicitacao.get("solicitacao_id") or "")
    pid = str(solicitacao.get("paciente_id") or "")
    justificativa = str(solicitacao.get("justificativa_clinica") or "")
    observacoes = str(solicitacao.get("observacoes") or "")
    comorbidades = str(solicitacao.get("comorbidades") or "")

    tem_gravidade, motivos_gravidade = _verificar_gravidade_critica(solicitacao, eventos, achados_llm)
    resumo_gravidade = "; ".join(motivos_gravidade)

    itens: list[ItemDecisaoCompartilhada] = []

    # -----------------------------------------------------------------------
    # 1. INTERRUPÇÃO DE MEDICAÇÃO (ex.: ficou sem insulina na UBS por 1 mês)
    # -----------------------------------------------------------------------
    for fonte, texto in [("observacoes", observacoes), ("justificativa_clinica", justificativa)]:
        m = RE_SEM_INSULINA_OU_REMEDIO.search(texto)
        if m:
            itens.append(
                ItemDecisaoCompartilhada(
                    codigo=CodigoDecisao.INTERRUPCAO_MEDICACAO,
                    categoria=CategoriaDecisao.QUEBRA_ADESAO,
                    nivel_atencao=NivelAtencaoMedica.CRITICO,
                    titulo="Interrupção de Medicação Crítica (Insulina / Uso Contínuo)",
                    descricao_medica=(
                        "Paciente ficou sem utilizar medicação essencial prescrita (insulina/controle basal), "
                        "elevando o risco de descompensação metabólica e infecção cirúrgica."
                    ),
                    recomendacao_conduta=(
                        "Decisão compartilhada urgente: restabelecer fornecimento/adesão medicamentosa junto à UBS "
                        "e revalidar glicemia antes de confirmar data cirúrgica."
                    ),
                    trecho_evidencia=texto.strip(),
                    fonte=fonte,
                    valido_para_decisao=True,
                )
            )
            break

    # -----------------------------------------------------------------------
    # 2. DESCONTROLE METABÓLICO / ORIENTAÇÃO DE DIETA E MEDICAÇÃO (LLM + Texto)
    # -----------------------------------------------------------------------
    achados_hba1c_llm = [a for a in achados_llm if a.get("codigo") == "HBA1C_DESCONTROLADA"]
    m_dieta_obs = RE_ORIENTADO_DIETA_GLICEMIA.search(observacoes)
    m_dieta_just = RE_ORIENTADO_DIETA_GLICEMIA.search(justificativa)

    # Verifica se já não registrou adesão positiva posterior ("HbA1c em queda... liberou")
    ja_compensou = bool(RE_ADESAO_POSITIVA.search(observacoes) or RE_ADESAO_POSITIVA.search(justificativa))

    if (m_dieta_obs or m_dieta_just or achados_hba1c_llm) and not ja_compensou:
        if m_dieta_obs:
            trecho = observacoes.strip()
            fonte = "observacoes"
        elif m_dieta_just:
            trecho = m_dieta_just.group(0)
            fonte = "justificativa_clinica"
        else:
            trecho = str(achados_hba1c_llm[0].get("trecho_literal") or "HbA1c > 8,5% detectada pela LLM")
            fonte = "achados_llm"

        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.DESCONTROLE_METABOLICO_DIETA,
                categoria=CategoriaDecisao.MANEJO_MEDICACAO,
                nivel_atencao=NivelAtencaoMedica.CRITICO if tem_gravidade else NivelAtencaoMedica.MODERADO,
                titulo="Meta Glicêmica / Dieta Pendente de Adesão Pré-Operatória",
                descricao_medica=(
                    "Identificada hiperglicemia ou HbA1c descompensada com orientação médica de ajuste dietético "
                    "ou endocrinológico pendente de estabilização pelo paciente."
                ),
                recomendacao_conduta=(
                    "Pactuar meta de controle glicêmico e adesão à dieta/medicação com o paciente. "
                    + (
                        f"Como há quadro grave ({resumo_gravidade}), otimizar em regime acelerado sem perder janela cirúrgica."
                        if tem_gravidade
                        else "Liberar agendamento eletivo após confirmação de queda da glicemia/HbA1c."
                    )
                ),
                trecho_evidencia=trecho,
                fonte=fonte,
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # 3. TABAGISMO ATIVO APÓS ORIENTAÇÃO DE CESSAÇÃO
    # -----------------------------------------------------------------------
    m_tab = RE_TABAGISMO_ORIENTADO.search(justificativa) or RE_TABAGISMO_ORIENTADO.search(observacoes)
    if m_tab:
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.TABAGISMO_ATIVO_ORIENTADO,
                categoria=CategoriaDecisao.QUEBRA_ADESAO,
                nivel_atencao=NivelAtencaoMedica.MODERADO,
                titulo="Tabagismo Mantido Apesar de Orientação Médica de Cessação",
                descricao_medica=(
                    "Médico assistente orientou cessação do tabagismo para reduzir risco cardiopulmonar e de "
                    "deiscência/infecção de ferida operatória, mas paciente mantém hábito ativo."
                ),
                recomendacao_conduta=(
                    "Abordar em decisão compartilhada os riscos de complicação pulmonar/cicatricial e oferecer "
                    "apoio farmacológico para abstinência pré-operatória (ideal >= 4 semanas)."
                ),
                trecho_evidencia=m_tab.group(0),
                fonte="justificativa_clinica",
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # 4. MANEJO DE ANTICOAGULAÇÃO ORAL PRÉ-OPERATÓRIA
    # -----------------------------------------------------------------------
    m_aco_txt = RE_ANTICOAGULANTE.search(justificativa) or RE_ANTICOAGULANTE.search(observacoes)
    tem_aco_comorb = "anticoagulacao oral" in comorbidades.lower()
    if m_aco_txt or tem_aco_comorb:
        trecho_aco = (
            m_aco_txt.group(0)
            if m_aco_txt
            else f"Comorbidades: {comorbidades} (em uso de anticoagulação oral)"
        )
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.SUSPENSAO_ANTICOAGULANTE,
                categoria=CategoriaDecisao.MANEJO_MEDICACAO,
                nivel_atencao=NivelAtencaoMedica.MODERADO,
                titulo="Pactuação Obrigatória de Suspensão de Anticoagulante Oral",
                descricao_medica=(
                    "Paciente em uso contínuo de anticoagulante oral. Não pode ser convocado de última hora "
                    "sem janela programada de suspensão medicamentosa (ou ponte de heparina)."
                ),
                recomendacao_conduta=(
                    "Alinhar diretamente com paciente e cardiologista/clínico a data exata de parada do "
                    "anticoagulante (geralmente 5 a 7 dias antes do procedimento) e checar INR/coagulograma."
                ),
                trecho_evidencia=trecho_aco,
                fonte="justificativa_clinica" if m_aco_txt else "comorbidades",
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # 5. MELHORA COM TRATAMENTO CLÍNICO / REMÉDIO (LLM + Eventos + Observações)
    # -----------------------------------------------------------------------
    m_melhora_obs = RE_MELHORA_REMEDIO_OBS.search(observacoes) or RE_MELHORA_REMEDIO_OBS.search(justificativa)
    achados_melhora_llm = [a for a in achados_llm if a.get("codigo") == "MELHORA"]
    eventos_melhora = [
        e for e in eventos if e.get("resultado") == "relata_melhora" or "melhora" in str(e.get("descricao") or "").lower()
    ]

    # Verifica se houve evento de piora MAIS RECENTE do que a melhora
    datas_melhora = [str(e.get("data_evento") or "") for e in eventos_melhora if e.get("data_evento")]
    datas_piora = [
        str(e.get("data_evento") or "")
        for e in eventos
        if e.get("tipo_evento") in ("pronto_socorro", "internacao")
        or e.get("resultado") in ("piora", "relata_piora", "progressao")
    ]
    piorou_depois = bool(datas_melhora and datas_piora and max(datas_piora) > max(datas_melhora) and not m_melhora_obs)

    if (m_melhora_obs or achados_melhora_llm or eventos_melhora) and not piorou_depois:
        if m_melhora_obs:
            trecho_mel = observacoes.strip() if RE_MELHORA_REMEDIO_OBS.search(observacoes) else justificativa.strip()
            fonte_mel = "observacoes"
        elif achados_melhora_llm:
            trecho_mel = str(achados_melhora_llm[0].get("trecho_literal") or "Pct refere melhora com tratamento clínico.")
            fonte_mel = "achados_llm"
        else:
            trecho_mel = str(eventos_melhora[-1].get("descricao") or "Pct refere melhora dos sintomas com tratamento clínico.")
            fonte_mel = "eventos_clinicos"

        # HEURÍSTICA DE VALIDAÇÃO CLÍNICA:
        # Se o paciente tem câncer/biópsia positiva/urgência, "melhorar com remédio" (ex: analgésico)
        # NÃO torna seguro cancelar a cirurgia -> gera CONFLITO CLÍNICO!
        if tem_gravidade:
            itens.append(
                ItemDecisaoCompartilhada(
                    codigo=CodigoDecisao.MELHORA_COM_REMEDIO,
                    categoria=CategoriaDecisao.MELHORA_CONSERVADORA,
                    nivel_atencao=NivelAtencaoMedica.CRITICO,
                    titulo="Alerta de Falsa Segurança: Relato de Melhora em Quadro Grave/Oncológico",
                    descricao_medica=(
                        f"Paciente relatou melhora sintomática com medicação, porém apresenta quadro de alta gravidade "
                        f"({resumo_gravidade}). O alívio sintomático não resolve a patologia de base."
                    ),
                    recomendacao_conduta=(
                        "NÃO remover da fila nem adiar cirurgia. Realizar contato médico ativo para esclarecer ao "
                        "paciente os riscos de abandonar o tratamento cirúrgico."
                    ),
                    trecho_evidencia=trecho_mel,
                    fonte=fonte_mel,
                    valido_para_decisao=False,
                    conflito_clinico=(
                        f"Incompatível com suspensão cirúrgica devido a: {resumo_gravidade}."
                    ),
                )
            )
        else:
            itens.append(
                ItemDecisaoCompartilhada(
                    codigo=CodigoDecisao.MELHORA_COM_REMEDIO,
                    categoria=CategoriaDecisao.MELHORA_CONSERVADORA,
                    nivel_atencao=NivelAtencaoMedica.MODERADO,
                    titulo="Boa Resposta ao Tratamento Medicamentoso — Reavaliar Necessidade Cirúrgica",
                    descricao_medica=(
                        "Paciente com patologia benigna/eletiva relata controle dos sintomas com uso de medicação "
                        "ou tratamento conservador, questionando a necessidade de operar no momento."
                    ),
                    recomendacao_conduta=(
                        "Caso VÁLIDO para Decisão Compartilhada: agendar teleconsulta ou revisão ambulatorial para "
                        "decidir em conjunto pela manutenção do tratamento clínico e alta/suspensão segura da fila."
                    ),
                    trecho_evidencia=trecho_mel,
                    fonte=fonte_mel,
                    valido_para_decisao=True,
                )
            )

    # -----------------------------------------------------------------------
    # 6. ADESÃO POSITIVA COMPROVADA AO TRATAMENTO PROPOSTO
    # -----------------------------------------------------------------------
    m_adesao = RE_ADESAO_POSITIVA.search(observacoes) or RE_ADESAO_POSITIVA.search(justificativa)
    if m_adesao:
        fonte_ad = "observacoes" if RE_ADESAO_POSITIVA.search(observacoes) else "justificativa_clinica"
        trecho_ad = observacoes.strip() if fonte_ad == "observacoes" else m_adesao.group(0)
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.ADESAO_COMPROVADA,
                categoria=CategoriaDecisao.ADESAO_POSITIVA,
                nivel_atencao=NivelAtencaoMedica.INFORMATIVO,
                titulo="Adesão Terapêutica Comprovada — Paciente Otimizado",
                descricao_medica=(
                    "Paciente seguiu rigorosamente as orientações médicas (ajuste medicamentoso, controle "
                    "glicêmico ou preparo multidisciplinar), atingindo as metas pré-operatórias."
                ),
                recomendacao_conduta=(
                    "Sinal verde clínico: priorizar encaixe de agenda cirúrgica para aproveitar a janela "
                    "de compensação clínica conquistada pelo paciente."
                ),
                trecho_evidencia=trecho_ad,
                fonte=fonte_ad,
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # 7. PREFERÊNCIA DE JANELA CIRÚRGICA (FÉRIAS) E DESEJO ELETIVO DO PACIENTE
    # -----------------------------------------------------------------------
    if RE_PEDIDO_FERIAS.search(observacoes) or RE_PEDIDO_FERIAS.search(justificativa):
        if tem_gravidade:
            itens.append(
                ItemDecisaoCompartilhada(
                    codigo=CodigoDecisao.PEDIDO_JANELA_FERIAS,
                    categoria=CategoriaDecisao.PREFERENCIA_PACIENTE,
                    nivel_atencao=NivelAtencaoMedica.CRITICO,
                    titulo="Conflito de Decisão: Pedido de Adiamento para Férias em Caso de Risco",
                    descricao_medica=(
                        f"Paciente solicitou operar apenas no período de férias, mas possui condição clínica "
                        f"sensível ao tempo ({resumo_gravidade})."
                    ),
                    recomendacao_conduta=(
                        "Contatar paciente para decisão compartilhada informada: explicar que aguardar o período "
                        "de férias acarreta risco de progressão/descompensação e oferecer atestado/afastamento legal."
                    ),
                    trecho_evidencia=observacoes.strip() or justificativa.strip(),
                    fonte="observacoes",
                    valido_para_decisao=False,
                    conflito_clinico=f"Adiamento para férias contraindicado por: {resumo_gravidade}.",
                )
            )
        else:
            itens.append(
                ItemDecisaoCompartilhada(
                    codigo=CodigoDecisao.PEDIDO_JANELA_FERIAS,
                    categoria=CategoriaDecisao.PREFERENCIA_PACIENTE,
                    nivel_atencao=NivelAtencaoMedica.INFORMATIVO,
                    titulo="Preferência de Janela Cirúrgica (Período de Férias) — Válida",
                    descricao_medica=(
                        "Paciente com quadro eletivo estável solicita programação cirúrgica no período de férias "
                        "para conciliar recuperação pós-operatória com atividade laboral."
                    ),
                    recomendacao_conduta=(
                        "Preferência clinicamente VÁLIDA: quadro estável permite alinhar o agendamento cirúrgico "
                        "com a janela de férias do paciente sem prejuízo clínico."
                    ),
                    trecho_evidencia=observacoes.strip() or justificativa.strip(),
                    fonte="observacoes",
                    valido_para_decisao=True,
                )
            )

    m_desejo = RE_DESEJO_ELETIVO.search(justificativa)
    if m_desejo and not tem_gravidade:
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.CIRURGIA_POR_DESEJO_PACIENTE,
                categoria=CategoriaDecisao.PREFERENCIA_PACIENTE,
                nivel_atencao=NivelAtencaoMedica.INFORMATIVO,
                titulo="Indicação Eletiva por Preferência / Desejo do Paciente",
                descricao_medica=(
                    "Condição benigna ou oligossintomática na qual a indicação cirúrgica decorre "
                    "primariamente da preferência informada do paciente."
                ),
                recomendacao_conduta=(
                    "Caso apto para revisão de expectativa risco-benefício em consulta pré-operatória, "
                    "podendo aguardar janela eletiva padrão (Classes C/D)."
                ),
                trecho_evidencia=m_desejo.group(0),
                fonte="justificativa_clinica",
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # 8. FALTAS PRÉ-OPERATÓRIAS vs. BARREIRAS DE TRANSPORTE (TFD) E REDE DE APOIO
    # -----------------------------------------------------------------------
    eventos_falta = [e for e in eventos if e.get("tipo_evento") == "falta"]
    falta_obs = "faltou a consulta" in observacoes.lower()
    falta_transporte_evt = any("falta de transporte" in str(e.get("descricao") or "").lower() for e in eventos_falta)
    m_transp_obs = RE_BARREIRA_TRANSPORTE.search(observacoes)

    if falta_transporte_evt or m_transp_obs:
        trecho_tr = (
            observacoes.strip()
            if m_transp_obs
            else "Paciente não compareceu - informou falta de transporte (eventos_clinicos)."
        )
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.BARREIRA_TRANSPORTE_TFD,
                categoria=CategoriaDecisao.BARREIRA_LOGISTICA,
                nivel_atencao=NivelAtencaoMedica.CRITICO if tem_gravidade else NivelAtencaoMedica.MODERADO,
                titulo="Barreira Logística / Necessidade de TFD (Tratamento Fora de Domicílio)",
                descricao_medica=(
                    "Dificuldade comprovada de deslocamento até o hospital ou necessidade de TFD municipal, "
                    "impactando o comparecimento a consultas e exames pré-operatórios."
                ),
                recomendacao_conduta=(
                    "Não penalizar paciente por faltas. Acionar Serviço Social / TFD da Secretaria Municipal "
                    "e concentrar exames pré-operatórios e avaliação anestésica no mesmo turno."
                ),
                trecho_evidencia=trecho_tr,
                fonte="observacoes" if m_transp_obs else "eventos_clinicos",
                valido_para_decisao=True,
            )
        )
    elif len(eventos_falta) >= 2 or falta_obs or any(
        e.get("resultado") == "avaliacao_pre_anestesica" for e in eventos_falta
    ):
        tipos_falta = ", ".join(sorted({str(e.get("resultado") or "consulta") for e in eventos_falta}))
        trecho_flt = (
            observacoes.strip()
            if falta_obs
            else f"{len(eventos_falta)} falta(s) registrada(s) em ambulatorio ({tipos_falta})."
        )
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.FALTA_NAO_JUSTIFICADA,
                categoria=CategoriaDecisao.QUEBRA_ADESAO,
                nivel_atencao=NivelAtencaoMedica.CRITICO if tem_gravidade else NivelAtencaoMedica.MODERADO,
                titulo="Absenteísmo no Preparo Pré-Operatório (Sem Barreira TFD Registrada)",
                descricao_medica=(
                    "Paciente faltou a etapas críticas do preparo cirúrgico (avaliação pré-anestésica, "
                    "exames ou reavaliação) sem registro de barreira de transporte."
                ),
                recomendacao_conduta=(
                    "Busca ativa para verificar se houve desistência tácita, barreira social oculta ou "
                    "falha de comunicação. "
                    + (
                        f"ATENÇÃO: Paciente possui quadro grave ({resumo_gravidade}) — não excluir da fila!"
                        if tem_gravidade
                        else "Confirmar interesse antes de alocar sala cirúrgica."
                    )
                ),
                trecho_evidencia=trecho_flt,
                fonte="observacoes" if falta_obs else "eventos_clinicos",
                valido_para_decisao=not tem_gravidade,
                conflito_clinico=(
                    f"Risco elevado de desfecho adverso por absenteísmo em quadro grave ({resumo_gravidade})."
                    if tem_gravidade
                    else ""
                ),
            )
        )

    # 9. VULNERABILIDADE DE REDE DE APOIO / CUIDADOR
    m_rede = RE_REDE_APOIO_VULNERAVEL.search(observacoes) or RE_REDE_APOIO_VULNERAVEL.search(justificativa)
    if m_rede:
        fonte_rd = "observacoes" if RE_REDE_APOIO_VULNERAVEL.search(observacoes) else "justificativa_clinica"
        itens.append(
            ItemDecisaoCompartilhada(
                codigo=CodigoDecisao.VULNERABILIDADE_REDE_APOIO,
                categoria=CategoriaDecisao.BARREIRA_LOGISTICA,
                nivel_atencao=NivelAtencaoMedica.MODERADO,
                titulo="Dependência de Rede de Apoio / Cuidador ou Busca via ACS",
                descricao_medica=(
                    "Paciente idoso/vulnerável que mora sozinho, depende de familiares para cuidados "
                    "pós-operatórios ou depende de Agente Comunitário de Saúde (ACS) para comunicação."
                ),
                recomendacao_conduta=(
                    "Incluir familiar/cuidador ou ACS no processo de decisão compartilhada e no planejamento "
                    "da alta hospitalar segura."
                ),
                trecho_evidencia=m_rede.group(0),
                fonte=fonte_rd,
                valido_para_decisao=True,
            )
        )

    # -----------------------------------------------------------------------
    # Consolidação do Status Geral e Resumo Executivo para o Médico
    # -----------------------------------------------------------------------
    if not itens:
        return AvaliacaoDecisaoCompartilhada(
            solicitacao_id=sid,
            paciente_id=pid,
            elegivel_decisao_compartilhada=False,
            status_adesao=StatusAdesao.PADRAO,
            nivel_atencao_maximo=NivelAtencaoMedica.NENHUM,
            tem_conflito_clinico=False,
            resumo_medico="Fluxo padrão: sem alertas específicos de adesão medicamentosa ou conflitos de decisão compartilhada.",
            itens=[],
        )

    tem_conflito = any(not i.valido_para_decisao for i in itens)
    ordem_nivel = {
        NivelAtencaoMedica.CRITICO: 3,
        NivelAtencaoMedica.MODERADO: 2,
        NivelAtencaoMedica.INFORMATIVO: 1,
        NivelAtencaoMedica.NENHUM: 0,
    }
    nivel_max = max((i.nivel_atencao for i in itens), key=lambda n: ordem_nivel[n])

    codigos = {i.codigo for i in itens}
    if tem_conflito:
        status = StatusAdesao.CONFLITO_DECISAO
    elif CodigoDecisao.INTERRUPCAO_MEDICACAO in codigos or CodigoDecisao.TABAGISMO_ATIVO_ORIENTADO in codigos or CodigoDecisao.FALTA_NAO_JUSTIFICADA in codigos:
        status = StatusAdesao.QUEBRA_ADESAO
    elif CodigoDecisao.MELHORA_COM_REMEDIO in codigos:
        status = StatusAdesao.REAVALIAR_INDICACAO
    elif CodigoDecisao.DESCONTROLE_METABOLICO_DIETA in codigos or CodigoDecisao.SUSPENSAO_ANTICOAGULANTE in codigos:
        status = StatusAdesao.ALERTA_MANEJO
    elif CodigoDecisao.BARREIRA_TRANSPORTE_TFD in codigos or CodigoDecisao.VULNERABILIDADE_REDE_APOIO in codigos:
        status = StatusAdesao.BARREIRA_SOCIAL
    elif CodigoDecisao.ADESAO_COMPROVADA in codigos:
        status = StatusAdesao.ADESAO_POSITIVA
    else:
        status = StatusAdesao.PREFERENCIA_VALIDA

    resumo = " | ".join(f"{i.titulo}: {i.recomendacao_conduta}" for i in itens[:2])

    return AvaliacaoDecisaoCompartilhada(
        solicitacao_id=sid,
        paciente_id=pid,
        elegivel_decisao_compartilhada=True,
        status_adesao=status,
        nivel_atencao_maximo=nivel_max,
        tem_conflito_clinico=tem_conflito,
        resumo_medico=resumo,
        itens=itens,
    )


def avaliar_lote_sqlite(
    db_path: str | Path,
    salvar_tabela: bool = True,
    exportar_json_path: str | Path | None = None,
) -> dict[str, AvaliacaoDecisaoCompartilhada]:
    """Processa todas as solicitações do banco SQLite usando os dados + achados_llm.

    Opcionalmente persiste a tabela `decisao_compartilhada` no SQLite e exporta
    um arquivo JSON compacto para consumo direto pelo Frontend.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    solicitacoes = [dict(r) for r in cur.execute("SELECT * FROM fila_cirurgica").fetchall()]

    eventos_por_sol: dict[str, list[dict[str, Any]]] = {}
    for r in cur.execute("SELECT * FROM eventos_clinicos ORDER BY data_evento ASC").fetchall():
        d = dict(r)
        eventos_por_sol.setdefault(str(d.get("solicitacao_id") or ""), []).append(d)

    achados_por_sol: dict[str, list[dict[str, Any]]] = {}
    tabelas = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "achados_llm" in tabelas:
        for r in cur.execute("SELECT * FROM achados_llm").fetchall():
            d = dict(r)
            achados_por_sol.setdefault(str(d.get("solicitacao_id") or ""), []).append(d)

    resultados: dict[str, AvaliacaoDecisaoCompartilhada] = {}
    for sol in solicitacoes:
        sid = str(sol["solicitacao_id"])
        av = avaliar_decisao_compartilhada(
            solicitacao=sol,
            eventos=eventos_por_sol.get(sid, []),
            achados_llm=achados_por_sol.get(sid, []),
        )
        resultados[sid] = av

    if salvar_tabela:
        cur.execute("DROP TABLE IF EXISTS decisao_compartilhada")
        cur.execute(
            """
            CREATE TABLE decisao_compartilhada (
                solicitacao_id TEXT PRIMARY KEY,
                paciente_id TEXT NOT NULL,
                elegivel_decisao_compartilhada INTEGER NOT NULL,
                status_adesao TEXT NOT NULL,
                nivel_atencao_maximo TEXT NOT NULL,
                tem_conflito_clinico INTEGER NOT NULL,
                total_itens INTEGER NOT NULL,
                resumo_medico TEXT NOT NULL,
                itens_json TEXT NOT NULL
            )
            """
        )
        cur.executemany(
            """
            INSERT INTO decisao_compartilhada (
                solicitacao_id, paciente_id, elegivel_decisao_compartilhada,
                status_adesao, nivel_atencao_maximo, tem_conflito_clinico,
                total_itens, resumo_medico, itens_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    av.solicitacao_id,
                    av.paciente_id,
                    1 if av.elegivel_decisao_compartilhada else 0,
                    av.status_adesao.value,
                    av.nivel_atencao_maximo.value,
                    1 if av.tem_conflito_clinico else 0,
                    len(av.itens),
                    av.resumo_medico,
                    json.dumps([i.to_dict() for i in av.itens], ensure_ascii=False),
                )
                for av in resultados.values()
            ],
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dc_status ON decisao_compartilhada(status_adesao)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dc_elegivel ON decisao_compartilhada(elegivel_decisao_compartilhada)")
        conn.commit()

    conn.close()

    if exportar_json_path:
        export_map = {
            sid: av.to_dict()
            for sid, av in resultados.items()
            if av.elegivel_decisao_compartilhada
        }
        Path(exportar_json_path).write_text(
            json.dumps(export_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return resultados
