#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de demonstração e teste interativo do módulo de extração.
Executa tanto com dados simulados em memória quanto com pacientes reais do banco SQLite.
"""
import sqlite3
from datetime import date
from pathlib import Path

from extracao import extrair_solicitacao, extrair_evento
from motor import avaliar, decidir


def demo_em_memoria():
    print("=" * 60)
    print("1. TESTE ISOLADO COM DADOS SIMULADOS EM MEMÓRIA")
    print("=" * 60)

    # Simula uma solicitação cirúrgica
    solicitacao_simulada = {
        "solicitacao_id": "SOL-TESTE-999",
        "nome_paciente": "Paciente Exemplo Silva",
        "cid_principal": "C50.4",  # Câncer de mama (dimensão gravidade)
        "intensidade_dor_eva": 8,   # Dor intensa >= 7
        "limitacao_funcional": "grave",
        "justificativa_clinica": "Nódulo suspeito em quadrante superior externo com perda ponderal e crescimento rápido.",
        "data_entrada_fila": "2026-06-01",
    }

    # Simula dois eventos clínicos ao longo da espera
    evento_biopsia = {
        "evento_id": "EVT-TESTE-01",
        "solicitacao_id": "SOL-TESTE-999",
        "tipo_evento": "biopsia",
        "resultado": "positivo",
        "data_evento": "2026-07-15",
        "descricao": "Biópsia confirma carcinoma invasor grau 3.",
    }

    evento_ps = {
        "evento_id": "EVT-TESTE-02",
        "solicitacao_id": "SOL-TESTE-999",
        "tipo_evento": "pronto_socorro",
        "resultado": "observacao",
        "data_evento": "2026-09-10",
        "descricao": "Atendimento de urgência por dor aguda intratável.",
    }

    print(f"Paciente: {solicitacao_simulada['nome_paciente']} ({solicitacao_simulada['solicitacao_id']})")
    print(f"CID: {solicitacao_simulada['cid_principal']} | Dor: {solicitacao_simulada['intensidade_dor_eva']} | Limitação: {solicitacao_simulada['limitacao_funcional']}")
    print(f"Texto: \"{solicitacao_simulada['justificativa_clinica']}\"\n")

    # Extrai achados
    achados = extrair_solicitacao(solicitacao_simulada)
    achados.extend(extrair_evento(evento_biopsia))
    achados.extend(extrair_evento(evento_ps))

    print(f"Total de achados identificados pelo extrator: {len(achados)}")
    for i, a in enumerate(achados, 1):
        print(f"  {i}. [{a.dimensao.value.upper()}] Código: {a.codigo.value} | Evidência: '{a.evidencia.trecho}' (ref: {a.evidencia.ref})")

    # Passa pelo motor de decisão
    d_ref = date(2026, 10, 23)
    d_ent = date.fromisoformat(solicitacao_simulada["data_entrada_fila"])
    av = avaliar(solicitacao_simulada["solicitacao_id"], achados, data_ref=d_ref, data_entrada=d_ent)

    print("\n--- AVALIAÇÃO DO MOTOR ---")
    print(f"Classe proposta: {av.classe} | Motivo: {av.motivo_classe}")
    print(f"Score gravidade: {av.gravidade} | Score deterioração: {av.deterioracao}")

    sugestoes = decidir(av, classe_aprovada=None)
    print("\n--- SUGESTÕES GERADAS PELO DECISOR ---")
    for s in sugestoes:
        print(f"• [{s.tipo.value}] Classe Proposta: {s.classe_para} (Urgente: {s.urgente})")
        print(f"  Justificativa: {s.justificativa}")


def demo_banco_real():
    print("\n" + "=" * 60)
    print("2. TESTE COM CASO REAL DO BANCO SQLITE (ordovitae.sqlite3)")
    print("=" * 60)

    candidatos_db = [
        Path(__file__).resolve().parent.parent / "database" / "ordovitae.sqlite3",
        Path(__file__).resolve().parent / "database" / "ordovitae.sqlite3",
    ]
    db_path = next((p for p in candidatos_db if p.exists()), None)
    if not db_path:
        print("Banco SQLite não encontrado para demonstração em lote.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Busca um paciente oncológico com eventos no banco
    sol = conn.execute("""
        SELECT f.* FROM fila_cirurgica f
        WHERE f.flag_oncologico = 'sim'
        LIMIT 1
    """).fetchone()

    if not sol:
        print("Nenhuma solicitação encontrada no banco.")
        return

    sol_dict = dict(sol)
    achados = extrair_solicitacao(sol_dict)

    evts = conn.execute("""
        SELECT * FROM eventos_clinicos
        WHERE solicitacao_id = ?
        ORDER BY data_evento
    """, (sol_dict["solicitacao_id"],)).fetchall()

    for e in evts:
        achados.extend(extrair_evento(dict(e)))

    print(f"Paciente: {sol_dict['nome_paciente']} ({sol_dict['solicitacao_id']})")
    print(f"Procedimento: {sol_dict['procedimento']} | Especialidade: {sol_dict['especialidade']}")
    print(f"CID: {sol_dict['cid_principal']} - {sol_dict['cid_descricao']}")
    print(f"Justificativa: \"{sol_dict['justificativa_clinica']}\"\n")

    print(f"Achados clínicos extraídos ({len(achados)}):")
    for a in achados:
        print(f"  • [{a.dimensao.value.upper()}] {a.codigo.value} -> '{a.evidencia.trecho}'")

    d_ref = date(2026, 10, 23)
    d_ent = date.fromisoformat(sol_dict["data_entrada_fila"])
    av = avaliar(sol_dict["solicitacao_id"], achados, data_ref=d_ref, data_entrada=d_ent)

    print("\nClassificação do Motor:")
    print(f"  Classe: {av.classe} ({av.motivo_classe})")
    print(f"  Gravidade: {av.gravidade} | Deterioração: {av.deterioracao}")

    sugestoes = decidir(av, classe_aprovada=None)
    for s in sugestoes:
        print(f"  • [{s.tipo.value}] Classe Proposta: {s.classe_para} (Urgente: {s.urgente})")
        print(f"    Justificativa: {s.justificativa}")

    conn.close()


if __name__ == "__main__":
    demo_em_memoria()
    demo_banco_real()
