#!/usr/bin/env python3
"""Create normalized CSV copies and load them into a separate SQLite database."""

import argparse
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = PROJECT_ROOT / "dataset"
DEFAULT_NORMALIZED_DATASET = DATABASE_DIR / "dataset_normalizado"
DEFAULT_DATABASE = DATABASE_DIR / "ordovitae_normalizado.sqlite3"
NORMALIZER = DATABASE_DIR / "normalize_csv_review.py"
IMPORTER = DATABASE_DIR / "import_database.py"
JOBS = (
    ("procedimentos.csv", "procedimentos.json"),
    ("fila_cirurgica.csv", "fila_cirurgica.json"),
    ("eventos_clinicos.csv", "eventos_clinicos.json"),
    (
        str(Path("referencias") / "swalis.csv"),
        "referencias_swalis.json",
    ),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Gera cópias normalizadas dos CSVs e alimenta um banco SQLite separado. "
            "Não envia dados ao Gemini."
        )
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Pasta dos CSVs originais.",
    )
    parser.add_argument(
        "--normalized-dataset",
        type=Path,
        default=DEFAULT_NORMALIZED_DATASET,
        help="Pasta nova para os CSVs normalizados e suas auditorias.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="Novo arquivo SQLite a criar.",
    )
    return parser.parse_args()


def run():
    args = parse_args()
    source_dir = args.dataset.resolve()
    normalized_dir = args.normalized_dataset.resolve()
    database_path = args.database.resolve()

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Pasta dos CSVs originais não encontrada: {source_dir}")
    if source_dir == normalized_dir:
        raise ValueError("A pasta normalizada deve ser diferente da pasta original.")
    if normalized_dir.exists():
        raise FileExistsError(
            f"A pasta de saída já existe; escolha outra para preservar resultados: "
            f"{normalized_dir}"
        )
    if database_path.exists():
        raise FileExistsError(
            f"O banco de saída já existe; escolha outro caminho: {database_path}"
        )
    source_paths = [(source_dir / relative_csv).resolve() for relative_csv, _ in JOBS]
    if database_path in source_paths:
        raise ValueError("O banco SQLite não pode substituir um CSV de origem.")

    for relative_csv, contract_name in JOBS:
        source_path = source_dir / relative_csv
        contract_path = DATABASE_DIR / "contracts" / contract_name
        if not source_path.is_file():
            raise FileNotFoundError(f"CSV de origem não encontrado: {source_path}")
        if not contract_path.is_file():
            raise FileNotFoundError(f"Contrato não encontrado: {contract_path}")

    normalized_dir.mkdir(parents=True)
    environment = os.environ.copy()
    environment["GEMINI_KEY"] = ""
    review_required = False

    print("Gemini desabilitado: nenhum dado será enviado a um serviço externo.")
    for relative_csv, contract_name in JOBS:
        source_path = source_dir / relative_csv
        output_path = normalized_dir / relative_csv
        output_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path = DATABASE_DIR / "contracts" / contract_name
        command = [
            sys.executable,
            str(NORMALIZER),
            "--contract",
            str(contract_path),
            "--input",
            str(source_path),
            "--output",
            str(output_path),
            "--offline",
        ]
        result = subprocess.run(command, env=environment, check=False)
        audit_path = output_path.with_suffix(
            output_path.suffix + ".audit.jsonl"
        )
        if result.returncode not in (0, 2):
            raise RuntimeError(
                f"Normalização falhou para {source_path} "
                f"(código {result.returncode})."
            )
        if not output_path.is_file() or not audit_path.is_file():
            raise RuntimeError(
                f"Saída ou auditoria não foi gerada para {source_path}."
            )
        review_required = review_required or result.returncode == 2

    database_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(IMPORTER),
        "--dataset",
        str(normalized_dir),
        "--output",
        str(database_path),
    ]
    subprocess.run(command, env=environment, check=True)

    if review_required:
        print(
            "Atenção: algumas linhas precisam de revisão. Consulte as auditorias "
            "JSONL antes de usar os dados em decisões clínicas."
        )
    print(f"CSV originais preservados em: {source_dir}")
    print(f"CSV normalizados e auditorias: {normalized_dir}")
    print(f"Banco SQLite criado: {database_path}")


if __name__ == "__main__":
    run()
