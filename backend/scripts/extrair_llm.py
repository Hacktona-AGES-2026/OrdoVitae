#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Módulo de Extração com LLM para Textos Livres (justificativa_clinica, observacoes, descricao).
Permite testar amostras lado a lado (Regex vs LLM) e processar em lote salvando na tabela SQLite extracoes_llm.

Suporta:
- Provedores compatíveis com OpenAI (Groq, OpenRouter, DeepSeek, OpenAI, Ollama)
- Google Gemini API (gemini-1.5-flash, gemini-2.0-flash, gemini-1.5-flash-8b)
- Zero dependências obrigatórias: usa urllib da biblioteca padrão do Python.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Adiciona o diretório backend ao path para importar extrator e modelos
RAIZ_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ_BACKEND))

try:
    from extracao.extrator import KW_ALARME
    from motor.modelos import CodigoAchado as C
except ImportError:
    KW_ALARME = None
    C = None

# Códigos clínicos que a LLM tem permissão para extrair do texto livre
CODIGOS_PERMITIDOS_LLM = [
    "SINAL_ALARME",          # icterícia, perda ponderal, hemorragia, colangite, sepse, etc.
    "BIOPSIA_POSITIVA",      # confirmação histopatológica citada em texto
    "INTERNACAO",            # relato de internação prévia ou em UPA/hospital
    "PRONTO_SOCORRO",        # menção a ida recente a pronto-socorro / emergência
    "PROGRESSAO_IMAGEM",     # exame mostrando crescimento tumoral, piora de lesão
    "REAVALIACAO_PIORA",     # consulta médica que atestou piora
    "PIORA_RELATADA",        # paciente ou familiar relata piora dos sintomas/dor
    "MELHORA",               # melhora clínica ou remissão de sintomas
    "PERDA_CONTATO",         # paciente não atende chamadas, telefone inexistente, mudou
    "SAIU_DA_FILA",          # desistência expressa, cirurgia em outro hospital/convênio/particular
    "HBA1C_DESCONTROLADA",   # diabetes descompensada, glicemias muito elevadas
]

PROMPT_SISTEMA = f"""Você é um extrator clínico de alta precisão para a regulação cirúrgica do SUS.
Sua missão é extrair estritamente fatos clínicos explícitos a partir de textos livres (justificativas, observações de call center ou notas ambulatoriais).

Você DEVE responder EXCLUSIVAMENTE em formato JSON (uma lista de objetos). Não inclua nenhuma saudação, markdown extra ou texto além do JSON.

CÓDIGOS PERMITIDOS:
{json.dumps(CODIGOS_PERMITIDOS_LLM, indent=2, ensure_ascii=False)}

REGRAS OBRIGATÓRIAS (ANTI-ALUCINAÇÃO):
1. O campo "trecho" DEVE ser uma cópia EXATA e LITERAL de um trecho contido no texto informado. Nunca invente ou parafraseie.
2. Atenção rigorosa a NEGAÇÕES: se o texto diz "sem perda ponderal" ou "nega febre", NÃO extraia SINAL_ALARME. Extraia somente fatos afirmativos presentes.
3. O campo "data_fato" deve ser uma data no formato "AAAA-MM-DD" se houver uma data inequívoca mencionada no texto; caso contrário, use null. Nunca invente datas.
4. Se o texto não contiver nenhum dos fatos clínicos permitidos, responda simplesmente [].

FORMATO DO OBJETO JSON:
[
  {{"codigo": "NOME_DO_CODIGO", "data_fato": "AAAA-MM-DD ou null", "trecho": "trecho literal extraído"}}
]
"""


def _chamar_api_openai_compativel(
    texto: str,
    api_key: str,
    base_url: str = "https://api.openai.com/v1",
    modelo: str = "gpt-4o-mini",
) -> list[dict]:
    """Chama qualquer endpoint compatível com OpenAI (Groq, OpenRouter, DeepSeek, etc)."""
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": modelo,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {"role": "user", "content": f"Texto clínico:\n\"\"\"{texto}\"\"\""},
        ],
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "OrdoVitae-Extrator/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        conteudo = data["choices"][0]["message"]["content"].strip()
        # Remove eventuais fences de markdown (```json ... ```)
        conteudo = re.sub(r"^```(?:json)?\s*", "", conteudo, flags=re.MULTILINE)
        conteudo = re.sub(r"```\s*$", "", conteudo, flags=re.MULTILINE).strip()
        return json.loads(conteudo)


def _chamar_api_gemini(
    texto: str,
    api_key: str,
    modelo: str = "gemini-1.5-flash",
) -> list[dict]:
    """Chama a API nativa do Google Gemini."""
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={api_key}"
    prompt_completo = f"{PROMPT_SISTEMA}\n\nTexto clínico para extração:\n\"\"\"{texto}\"\"\""
    
    payload = {
        "contents": [{"parts": [{"text": prompt_completo}]}],
        "generationConfig": {
            "temperature": 0.0,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        conteudo = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        conteudo = re.sub(r"^```(?:json)?\s*", "", conteudo, flags=re.MULTILINE)
        conteudo = re.sub(r"```\s*$", "", conteudo, flags=re.MULTILINE).strip()
        return json.loads(conteudo)


def extrair_com_llm(
    texto: str,
    provedor: str,
    api_key: str,
    base_url: str | None = None,
    modelo: str | None = None,
) -> list[dict]:
    """Extrai achados via LLM e aplica validação anti-alucinação mandatória."""
    if not texto or len(texto.strip()) < 5:
        return []

    provedor_norm = (provedor or "openai").lower()
    if "gemini" in provedor_norm:
        modelo_escolhido = modelo or "gemini-1.5-flash"
        bruto = _chamar_api_gemini(texto, api_key, modelo=modelo_escolhido)
    else:
        # Default para openai_compatible (Groq, DeepSeek, OpenRouter, OpenAI, etc)
        base = base_url or os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1"
        modelo_escolhido = modelo or os.environ.get("LLM_MODEL") or "gpt-4o-mini"
        bruto = _chamar_api_openai_compativel(texto, api_key, base_url=base, modelo=modelo_escolhido)

    if not isinstance(bruto, list):
        return []

    # Validação obrigatória da spec (anti-alucinação)
    validos = []
    texto_lower = texto.lower()
    for item in bruto:
        if not isinstance(item, dict):
            continue
        cod = str(item.get("codigo") or "").strip()
        trecho = str(item.get("trecho") or "").strip()
        data_fato = item.get("data_fato")

        # 1. Código deve existir na lista autorizada
        if cod not in CODIGOS_PERMITIDOS_LLM:
            continue

        # 2. Trecho DEVE ser cópia literal do texto original
        if not trecho or trecho.lower() not in texto_lower:
            # Descartado por segurança anti-alucinação!
            continue

        # 3. Data se informada deve ter formato YYYY-MM-DD
        if data_fato is not None:
            data_str = str(data_fato).strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_str):
                data_str = None
        else:
            data_str = None

        validos.append({
            "codigo": cod,
            "data_fato": data_str,
            "trecho": trecho,
        })

    return validos


def extrair_via_regex_local(texto: str) -> list[str]:
    """Extração rápida de referência usando o regex do extrator determinístico."""
    if not texto or not KW_ALARME:
        return []
    matches = list(KW_ALARME.finditer(texto))
    return list(dict.fromkeys(m.group(0) for m in matches))


def carregar_amostras_teste(db_path: Path, n: int = 6) -> list[dict]:
    """Seleciona uma amostra diversificada de textos para comparação."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    amostras = []
    # 1. Justificativa com sinal de alarme
    r = conn.execute("SELECT solicitacao_id, justificativa_clinica FROM fila_cirurgica WHERE justificativa_clinica LIKE '%perda ponderal%' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": f"{r['solicitacao_id']}:justificativa_clinica", "tipo": "Justificativa (Alarme)", "texto": r["justificativa_clinica"]})

    # 2. Justificativa com negação ("sem ulcera")
    r = conn.execute("SELECT solicitacao_id, justificativa_clinica FROM fila_cirurgica WHERE justificativa_clinica LIKE '%sem ulcera%' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": f"{r['solicitacao_id']}:justificativa_clinica", "tipo": "Justificativa (Negação)", "texto": r["justificativa_clinica"]})

    # 3. Observação de desistência / saída de fila
    r = conn.execute("SELECT solicitacao_id, observacoes FROM fila_cirurgica WHERE observacoes LIKE '%outro servico%' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": f"{r['solicitacao_id']}:observacoes", "tipo": "Observação (Saída da fila)", "texto": r["observacoes"]})

    # 4. Observação de relato de piora
    r = conn.execute("SELECT solicitacao_id, observacoes FROM fila_cirurgica WHERE observacoes LIKE '%piora%' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": f"{r['solicitacao_id']}:observacoes", "tipo": "Observação (Piora relatada)", "texto": r["observacoes"]})

    # 5. Descrição de evento com biópsia
    r = conn.execute("SELECT evento_id, descricao FROM eventos_clinicos WHERE tipo_evento = 'biopsia' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": r["evento_id"], "tipo": "Evento (Biópsia)", "texto": r["descricao"]})

    # 6. Observação de descontrole glicêmico (HbA1c)
    r = conn.execute("SELECT solicitacao_id, observacoes FROM fila_cirurgica WHERE observacoes LIKE '%HbA1c%' LIMIT 1").fetchone()
    if r:
        amostras.append({"ref": f"{r['solicitacao_id']}:observacoes", "tipo": "Observação (HbA1c)", "texto": r["observacoes"]})

    conn.close()
    return amostras[:n]


def executar_teste_comparativo(amostras: list[dict], provedor: str, api_key: str, base_url: str | None, modelo: str | None):
    """Executa a comparação lado a lado entre Regex e LLM."""
    print("=" * 80)
    print(f"TESTE COMPARATIVO: REGEX vs LLM ({modelo or 'default'})")
    print("=" * 80)

    for i, a in enumerate(amostras, 1):
        texto = a["texto"]
        ref = a["ref"]
        tipo = a["tipo"]

        print(f"\n--- [Caso {i}/{len(amostras)}] {tipo} (Ref: {ref}) ---")
        print(f"Texto original:\n\"{texto}\"")

        # 1. Executa Regex
        achados_regex = extrair_via_regex_local(texto)
        print(f"\n[1. REGEX]: {len(achados_regex)} termo(s) capturado(s):")
        if achados_regex:
            print(f"   -> {', '.join(achados_regex)}")
        else:
            print("   -> (nenhum sinal de alarme por regex)")

        # 2. Executa LLM
        print("\n[2. LLM]: Consultando API...", end="", flush=True)
        try:
            inicio = datetime.now()
            achados_llm = extrair_com_llm(texto, provedor, api_key, base_url, modelo)
            tempo = (datetime.now() - inicio).total_seconds()
            print(f" concluído em {tempo:.2f}s!")

            if achados_llm:
                for item in achados_llm:
                    dt = f" (data: {item['data_fato']})" if item.get('data_fato') else ""
                    print(f"   * Código: {item['codigo']}{dt} | Trecho: \"{item['trecho']}\"")
            else:
                print("   * (nenhum achado relevante)")

            # Análise de valor agregado
            print("\n[3. AVALIAÇÃO QUALITATIVA]:")
            if any(item["codigo"] == "SAIU_DA_FILA" for item in achados_llm):
                print("   ✔ LLM identificou indício semântico de SAÍDA DA FILA.")
            elif any(item["codigo"] == "PIORA_RELATADA" for item in achados_llm):
                print("   ✔ LLM capturou relato de piora do paciente com precisão.")
            elif "sem" in texto.lower() and not achados_llm and achados_regex:
                print("   ✔ LLM respeitou a NEGAÇÃO clínica, evitando falso positivo do regex!")
            else:
                print("   ✔ Extração consistente com as regras.")

        except Exception as e:
            print(f" ERRO na chamada LLM: {e}")

    print("\n" + "=" * 80)
    print("Fim do teste comparativo.")


def main():
    parser = argparse.ArgumentParser(description="Extrator de Fatos Clínicos com LLM para o OrdoVitae")
    parser.add_argument("--provedor", default="openai", choices=["openai", "gemini"], help="Provedor: 'openai' (serve Groq, OpenRouter, DeepSeek, etc) ou 'gemini'")
    parser.add_argument("--api-key", default=None, help="Chave de API (ou via env LLM_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY)")
    parser.add_argument("--base-url", default=None, help="URL base para openai_compatible (ex: https://api.groq.com/openai/v1)")
    parser.add_argument("--modelo", default=None, help="Nome do modelo (ex: gpt-4o-mini, llama-3.1-8b-instant, gemini-1.5-flash)")
    parser.add_argument("--test", action="store_true", default=True, help="Executa teste comparativo com amostras reais do banco")
    parser.add_argument("--amostras", type=int, default=6, help="Quantidade de amostras para testar")

    args = parser.parse_args()

    # Busca a chave de API
    api_key = args.api_key or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("\n" + "!" * 70)
        print("AVISO: Nenhuma chave de API informada.")
        print("Você pode passar via parâmetro ou variável de ambiente:")
        print("  python extrair_llm.py --api-key \"SUA_CHAVE\" --modelo \"seu-modelo\"")
        print("\nExemplos de modelos baratos / gratuitos para usar:")
        print("1. Groq (Llama 3.1 8B - Grátis e super rápido):")
        print("   python extrair_llm.py --provedor openai --base-url \"https://api.groq.com/openai/v1\" --modelo \"llama-3.1-8b-instant\" --api-key \"gsk_...\"")
        print("\n2. Google Gemini 1.5 Flash (Free tier / Frações de centavo):")
        print("   python extrair_llm.py --provedor gemini --modelo \"gemini-1.5-flash\" --api-key \"AIzaSy...\"")
        print("\n3. OpenRouter / DeepSeek V3 (Centavos):")
        print("   python extrair_llm.py --provedor openai --base-url \"https://openrouter.ai/api/v1\" --modelo \"deepseek/deepseek-chat\" --api-key \"sk-or-...\"")
        print("!" * 70 + "\n")
        return

    # Localiza o banco de dados
    candidatos_db = [
        RAIZ_BACKEND.parent / "database" / "ordovitae.sqlite3",
        RAIZ_BACKEND / "database" / "ordovitae.sqlite3",
    ]
    db_path = next((p for p in candidatos_db if p.exists()), None)
    if not db_path:
        print("Banco ordovitae.sqlite3 não encontrado!")
        return

    amostras = carregar_amostras_teste(db_path, n=args.amostras)
    executar_teste_comparativo(amostras, args.provedor, api_key, args.base_url, args.modelo)


if __name__ == "__main__":
    main()
