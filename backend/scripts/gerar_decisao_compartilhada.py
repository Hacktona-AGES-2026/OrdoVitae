"""Script de execução do Motor Secundário de Decisão Compartilhada e Adesão.

Lê o banco `database/ordovitae.sqlite3` (incluindo `achados_llm`), aplica a heurística
de decisão compartilhada a todas as 941 solicitações, salva a tabela `decisao_compartilhada`
no SQLite e exporta `frontend/src/data/decisao-compartilhada.json` para exibição no modal
do paciente no Frontend.
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT_BACKEND = Path(__file__).resolve().parent.parent
if str(ROOT_BACKEND) not in sys.path:
    sys.path.insert(0, str(ROOT_BACKEND))

from motor_secundario import avaliar_lote_sqlite


def main() -> None:
    repo_root = ROOT_BACKEND.parent
    db_path = repo_root / "database" / "ordovitae.sqlite3"
    json_out = repo_root / "frontend" / "src" / "data" / "decisao-compartilhada.json"

    if not db_path.exists():
        print(f"[ERRO] Banco SQLite nao encontrado em: {db_path}")
        sys.exit(1)

    json_out.parent.mkdir(parents=True, exist_ok=True)
    resultados = avaliar_lote_sqlite(
        db_path=db_path,
        salvar_tabela=True,
        exportar_json_path=json_out,
    )

    elegiveis = [r for r in resultados.values() if r.elegivel_decisao_compartilhada]
    conflitos = [r for r in elegiveis if r.tem_conflito_clinico]

    contagem_status = collections.Counter(r.status_adesao.value for r in elegiveis)
    contagem_codigos = collections.Counter(
        item.codigo.value for r in elegiveis for item in r.itens
    )

    print("=" * 80)
    print("MOTOR SECUNDARIO: DECISAO COMPARTILHADA E ADESAO TERAPEUTICA")
    print("=" * 80)
    print(f"* Total de solicitacoes analisadas:             {len(resultados)}")
    print(f"* Solicitacoes com Decisao Compartilhada:       {len(elegiveis)} ({len(elegiveis)*100/len(resultados):.1f}%)")
    print(f"* Casos Validados sem Conflito Clinico:         {len(elegiveis) - len(conflitos)}")
    print(f"* Casos com Conflito Clinico (Alerta Medico):   {len(conflitos)}")
    print("-" * 80)
    print("DISTRIBUICAO POR STATUS DE ADESAO / DECISAO:")
    for st, qtd in contagem_status.most_common():
        print(f"  - {st:<25}: {qtd:>4} paciente(s)")
    print("-" * 80)
    print("DISTRIBUICAO POR CODIGO DE FATOR IDENTIFICADO:")
    for cod, qtd in contagem_codigos.most_common():
        print(f"  - {cod:<32}: {qtd:>4} ocorrencia(s)")
    print("-" * 80)
    print(f"[OK] Tabela `decisao_compartilhada` gravada em: {db_path}")
    print(f"[OK] JSON para o Frontend exportado em:         {json_out}")
    print("=" * 80)


if __name__ == "__main__":
    main()
