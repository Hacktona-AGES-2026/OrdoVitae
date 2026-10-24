#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script único de Normalização Sintática e Carga SQLite (Padrão definido pelo Líder):
- Padroniza caixa (maiúsculas/minúsculas), remove acentos em categorias e pontos no CID.
- Preserva textos livres (justificativa_clinica, observacoes, descricao) intactos.
- Não faz imputação nem conversão/inferência de números.
- Remove apenas registros 100% duplicados (nos dados) e eventos órfãos inválidos,
  mantendo solicitações que possuem qualquer campo diferente.
"""
import csv
import re
import sqlite3
import unicodedata
from pathlib import Path

PREPOSICOES = {"de", "da", "do", "das", "dos", "e"}


def _espacos(txt: str) -> str:
    """Remove espaços nas pontas e colapsa espaços múltiplos internos."""
    return re.sub(r"\s+", " ", (txt or "").strip())


def _sem_acentos_minusculo(txt: str) -> str:
    """Converte para minúsculas e remove acentos ('Média' -> 'media')."""
    txt = _espacos(txt).lower()
    if not txt:
        return ""
    nfkd = unicodedata.normalize("NFKD", txt)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _padronizar_prioridade(txt: str) -> str:
    """Garante 'alta', 'media', 'baixa' ou vazio mesmo se houver caractere corrompido ('Mdia')."""
    p = _sem_acentos_minusculo(txt)
    if not p:
        return ""
    if p in ("alta", "media", "baixa"):
        return p
    if p.startswith("m") and p.endswith("dia"):
        return "media"
    return p


def _padronizar_titulo(txt: str) -> str:
    """Padroniza nomes e municípios ('PORTO ALEGRE' / 'porto alegre' -> 'Porto Alegre')."""
    txt = _espacos(txt)
    if not txt:
        return ""
    palavras = txt.lower().split(" ")
    return " ".join(
        p if (i > 0 and p in PREPOSICOES) else p.capitalize()
        for i, p in enumerate(palavras)
    )


def _padronizar_cid(txt: str) -> str:
    """Maiúsculas, sem ponto e sem espaços ('k40.9' -> 'K409')."""
    return re.sub(r"[.\s]", "", (txt or "").strip().upper())


def _padronizar_comorbidades(txt: str) -> str:
    """Padroniza separador '; ' mantendo os termos originais."""
    txt = _espacos(txt)
    if not txt:
        return ""
    if txt.lower() == "nenhuma":
        return "nenhuma"
    itens = [_espacos(x) for x in txt.split(";") if _espacos(x)]
    return "; ".join(itens)


def normalizar_fila_row(r: dict) -> dict:
    return {
        "solicitacao_id": _espacos(r["solicitacao_id"]),
        "paciente_id": _espacos(r["paciente_id"]),
        "nome_paciente": _padronizar_titulo(r["nome_paciente"]),
        "sexo": _espacos(r["sexo"]).upper(),
        "idade": _espacos(r["idade"]),
        "municipio": _padronizar_titulo(_sem_acentos_minusculo(r["municipio"])),
        "uf": _espacos(r["uf"]).upper(),
        "distancia_hospital_km": _espacos(r["distancia_hospital_km"]),
        "procedimento_id": _espacos(r["procedimento_id"]),
        "procedimento": _espacos(r["procedimento"]),
        "especialidade": _espacos(r["especialidade"]),
        "cid_principal": _padronizar_cid(r["cid_principal"]),
        "cid_descricao": _espacos(r["cid_descricao"]),
        "cid_secundario": _padronizar_cid(r["cid_secundario"]),
        "asa": _espacos(r["asa"]),
        "comorbidades": _padronizar_comorbidades(r["comorbidades"]),
        "intensidade_dor_eva": _espacos(r["intensidade_dor_eva"]),
        "limitacao_funcional": _sem_acentos_minusculo(r["limitacao_funcional"]),
        # Textos livres enviados de uma vez (apenas trim nas pontas) para o backend tratar:
        "justificativa_clinica": (r["justificativa_clinica"] or "").strip(),
        "observacoes": (r["observacoes"] or "").strip(),
        "data_entrada_fila": _espacos(r["data_entrada_fila"]),
        "dias_em_fila": _espacos(r["dias_em_fila"]),
        "prioridade_regulacao": _padronizar_prioridade(r["prioridade_regulacao"]),
        "data_ultima_revisao_prioridade": _espacos(r["data_ultima_revisao_prioridade"]),
        "flag_oncologico": _sem_acentos_minusculo(r["flag_oncologico"]),
        "flag_diabetico": _sem_acentos_minusculo(r["flag_diabetico"]),
        "flag_piora_clinica": _sem_acentos_minusculo(r["flag_piora_clinica"]),
        "hba1c_ultima": _espacos(r["hba1c_ultima"]).replace(",", "."),
        "data_hba1c_ultima": _espacos(r["data_hba1c_ultima"]),
        "avaliacao_pre_anestesica": _sem_acentos_minusculo(r["avaliacao_pre_anestesica"]),
        "exames_pre_op_validos": _sem_acentos_minusculo(r["exames_pre_op_validos"]),
    }


def normalizar_evento_row(r: dict) -> dict:
    return {
        "evento_id": _espacos(r["evento_id"]),
        "solicitacao_id": _espacos(r["solicitacao_id"]),
        "paciente_id": _espacos(r["paciente_id"]),
        "data_evento": _espacos(r["data_evento"]),
        "tipo_evento": _sem_acentos_minusculo(r["tipo_evento"]),
        "resultado": _sem_acentos_minusculo(r["resultado"]),
        "valor_numerico": _espacos(r["valor_numerico"]).replace(",", "."),
        "descricao": (r["descricao"] or "").strip(),
        "origem": _espacos(r["origem"]),
    }


def normalizar_procedimento_row(r: dict) -> dict:
    return {
        "procedimento_id": _espacos(r["procedimento_id"]),
        "procedimento": _espacos(r["procedimento"]),
        "especialidade": _espacos(r["especialidade"]),
        "porte": _sem_acentos_minusculo(r["porte"]),
        "risco_cirurgico": _espacos(r["risco_cirurgico"]),
        "duracao_media_min": _espacos(r["duracao_media_min"]),
        "necessita_uti": _sem_acentos_minusculo(r["necessita_uti"]),
    }


def normalizar_swalis_row(r: dict) -> dict:
    return {
        "classe": _espacos(r["classe"]).upper(),
        "descricao": _espacos(r["descricao"]),
        "prazo_maximo_dias": _espacos(r["prazo_maximo_dias"]),
        "exemplos": _espacos(r["exemplos"]),
    }


def executar_pipeline(pasta_dataset: Path, arquivo_sqlite: Path, schema_sql_path: Path):
    # 1. Lê e normaliza procedimentos e swalis
    with (pasta_dataset / "procedimentos.csv").open("r", encoding="utf-8-sig") as f:
        procs = [normalizar_procedimento_row(r) for r in csv.DictReader(f)]

    with (pasta_dataset / "referencias" / "swalis.csv").open("r", encoding="utf-8-sig") as f:
        swalis = [normalizar_swalis_row(r) for r in csv.DictReader(f)]

    # 2. Lê, normaliza e remove apenas duplicatas 100% idênticas na fila_cirurgica
    fila = []
    fila_assinaturas = set()
    ids_solicitacoes_validas = set()
    with (pasta_dataset / "fila_cirurgica.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            norm = normalizar_fila_row(r)
            # Assinatura de todos os campos (exceto solicitacao_id) para checar se é 100% igual
            assinatura = tuple(v for k, v in norm.items() if k != "solicitacao_id")
            if assinatura in fila_assinaturas:
                continue
            fila_assinaturas.add(assinatura)
            ids_solicitacoes_validas.add(norm["solicitacao_id"])
            fila.append(norm)

    # 3. Lê, normaliza e limpa eventos 100% duplicados e eventos órfãos (fora da fila)
    eventos = []
    eventos_assinaturas = set()
    with (pasta_dataset / "eventos_clinicos.csv").open("r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            norm = normalizar_evento_row(r)
            # Remove os 9 eventos órfãos de solicitações já removidas da fila
            if norm["solicitacao_id"] not in ids_solicitacoes_validas:
                continue
            # Remove os 7 eventos 100% duplicados (mesmo conteúdo em todas as colunas de dados)
            assinatura = tuple(v for k, v in norm.items() if k != "evento_id")
            if assinatura in eventos_assinaturas:
                continue
            eventos_assinaturas.add(assinatura)
            eventos.append(norm)

    # 4. Grava no SQLite usando o schema.sql da equipe
    if arquivo_sqlite.exists():
        arquivo_sqlite.unlink()

    conn = sqlite3.connect(arquivo_sqlite)
    with conn:
        conn.executescript(schema_sql_path.read_text(encoding="utf-8"))
        for nome_tabela, registros in (
            ("procedimentos", procs),
            ("fila_cirurgica", fila),
            ("eventos_clinicos", eventos),
            ("referencias_swalis", swalis),
        ):
            colunas = list(registros[0].keys())
            placeholders = ", ".join("?" for _ in colunas)
            sql = f"INSERT INTO {nome_tabela} ({', '.join(colunas)}) VALUES ({placeholders})"
            valores = [
                [None if row[c] == "" else row[c] for c in colunas]
                for row in registros
            ]
            conn.executemany(sql, valores)
    conn.close()
    print(f"SQLite pronto: {len(procs)} procs | {len(fila)} fila | {len(eventos)} eventos | {len(swalis)} swalis")