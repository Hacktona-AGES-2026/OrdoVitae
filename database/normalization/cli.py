"""Fluxo de CLI para gerar CSV normalizado alternativo e auditoria."""

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

from .contracts import load_contract, read_entries
from .entry_validation import prepare_entries
from .gemini_review import review_entries


def _write_artifacts(output_path, audit_path, entries, contract):
    """Grava o CSV e a auditoria por linha, sem sobrescrever arquivos."""
    if output_path.exists():
        raise FileExistsError(f"Arquivo de saída já existe: {output_path}")
    if audit_path.exists():
        raise FileExistsError(f"Arquivo de auditoria já existe: {audit_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_paths = []
    try:
        output_descriptor, output_name = tempfile.mkstemp(
            prefix=f".{output_path.stem}.", suffix=".tmp", dir=output_path.parent
        )
        os.close(output_descriptor)
        temporary_output = Path(output_name)
        temporary_paths.append(temporary_output)

        audit_descriptor, audit_name = tempfile.mkstemp(
            prefix=f".{audit_path.stem}.", suffix=".tmp", dir=audit_path.parent
        )
        os.close(audit_descriptor)
        temporary_audit = Path(audit_name)
        temporary_paths.append(temporary_audit)

        field_names = [field["name"] for field in contract["fields"]]
        with temporary_output.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(
                output_file, fieldnames=field_names, lineterminator="\n"
            )
            writer.writeheader()
            for entry in entries:
                writer.writerow(entry["normalized"])

        with temporary_audit.open("w", encoding="utf-8", newline="\n") as audit_file:
            for entry in entries:
                audit_record = {
                    "row_index": entry["row_index"],
                    "source_line": entry["source_line"],
                    "status": entry["status"],
                    "issues": entry["issues"],
                    "empty_optional_fields": entry["empty_optional_fields"],
                    "gemini_assessment": entry["gemini_assessment"],
                    "source_headers": entry["source_headers"],
                    "raw_cells": entry["raw_cells"],
                    "original": entry["original"],
                    "normalized": entry["normalized"],
                }
                audit_file.write(
                    json.dumps(audit_record, ensure_ascii=False) + "\n"
                )

        if output_path.exists() or audit_path.exists():
            raise FileExistsError("Um arquivo de saída foi criado durante o processamento.")
        os.rename(temporary_audit, audit_path)
        os.rename(temporary_output, output_path)
    finally:
        for temporary_path in temporary_paths:
            if temporary_path.exists():
                temporary_path.unlink()


def parse_args():
    """Interpreta as opções de uma execução de normalização."""
    parser = argparse.ArgumentParser(
        description=(
            "Normaliza um CSV sem descartar linhas e gera um arquivo de auditoria."
        )
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Não carrega credenciais nem envia dados ao Gemini.",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size deve ser maior que zero.")
    return args


def main(parse_args_fn=parse_args):
    """Valida caminhos, normaliza entradas, revisa alertas e grava os resultados."""
    args = parse_args_fn()
    contract_path = args.contract.resolve()
    input_path = args.input.resolve()
    output_path = (
        args.output.resolve()
        if args.output
        else input_path.with_name(f"{input_path.stem}_normalizado.csv")
    )
    audit_path = output_path.with_suffix(output_path.suffix + ".audit.jsonl")

    if input_path == output_path or input_path == audit_path:
        raise ValueError("Saídas não podem sobrescrever o CSV de entrada.")
    if output_path == audit_path:
        raise ValueError("CSV e auditoria precisam ter caminhos diferentes.")
    if not input_path.is_file():
        raise FileNotFoundError(f"CSV de entrada não encontrado: {input_path}")
    if not contract_path.is_file():
        raise FileNotFoundError(f"Contrato JSON não encontrado: {contract_path}")
    if output_path.exists() or audit_path.exists():
        raise FileExistsError(
            "Saída ou auditoria já existe; informe outro --output para preservar "
            "o resultado anterior."
        )

    contract = load_contract(contract_path)
    entries = prepare_entries(read_entries(input_path, contract), contract)
    gemini_failed = review_entries(
        entries, contract, args.batch_size, offline=getattr(args, "offline", False)
    )

    _write_artifacts(output_path, audit_path, entries, contract)
    counts = {}
    for entry in entries:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
    print(
        f"CSV preservado/normalizado: {output_path} "
        f"({len(entries)} registros; tabela {contract['table']})."
    )
    print(f"Auditoria por linha: {audit_path}")
    print(f"Resumo: {counts}")
    if gemini_failed:
        print(
            "AVISO: todas as linhas foram preservadas; consulte a auditoria, "
            "pois algumas ainda precisam de revisão humana.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    main()
