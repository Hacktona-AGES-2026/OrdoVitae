#!/usr/bin/env python3
"""Build the OrdoVitae SQLite database from the source CSV files."""

import argparse
import csv
import os
import sqlite3
import tempfile
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "dataset"
DEFAULT_OUTPUT = Path(__file__).resolve().parent / "ordovitae.sqlite3"
SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

TABLES = {
    "procedimentos": {
        "file": "procedimentos.csv",
        "columns": (
            "procedimento_id",
            "procedimento",
            "especialidade",
            "porte",
            "risco_cirurgico",
            "duracao_media_min",
            "necessita_uti",
        ),
        "required": {"procedimento_id"},
        "integers": {"risco_cirurgico", "duracao_media_min"},
        "reals": set(),
        "dates": set(),
    },
    "fila_cirurgica": {
        "file": "fila_cirurgica.csv",
        "columns": (
            "solicitacao_id",
            "paciente_id",
            "nome_paciente",
            "sexo",
            "idade",
            "municipio",
            "uf",
            "distancia_hospital_km",
            "procedimento_id",
            "procedimento",
            "especialidade",
            "cid_principal",
            "cid_descricao",
            "cid_secundario",
            "asa",
            "comorbidades",
            "intensidade_dor_eva",
            "limitacao_funcional",
            "justificativa_clinica",
            "observacoes",
            "data_entrada_fila",
            "dias_em_fila",
            "prioridade_regulacao",
            "data_ultima_revisao_prioridade",
            "flag_oncologico",
            "flag_diabetico",
            "flag_piora_clinica",
            "hba1c_ultima",
            "data_hba1c_ultima",
            "avaliacao_pre_anestesica",
            "exames_pre_op_validos",
        ),
        "required": {"solicitacao_id", "procedimento_id"},
        "integers": {
            "idade",
            "distancia_hospital_km",
            "asa",
            "intensidade_dor_eva",
            "dias_em_fila",
        },
        "reals": {"hba1c_ultima"},
        "dates": {
            "data_entrada_fila",
            "data_ultima_revisao_prioridade",
            "data_hba1c_ultima",
        },
    },
    "eventos_clinicos": {
        "file": "eventos_clinicos.csv",
        "columns": (
            "evento_id",
            "solicitacao_id",
            "paciente_id",
            "data_evento",
            "tipo_evento",
            "resultado",
            "valor_numerico",
            "descricao",
            "origem",
        ),
        "required": {"evento_id"},
        "integers": set(),
        "reals": {"valor_numerico"},
        "dates": {"data_evento"},
    },
    "referencias_swalis": {
        "file": Path("referencias") / "swalis.csv",
        "columns": ("classe", "descricao", "prazo_maximo_dias", "exemplos"),
        "required": {"classe"},
        "integers": {"prazo_maximo_dias"},
        "reals": set(),
        "dates": set(),
    },
}


def convert_value(value, column, integers, reals, dates, source, line_number):
    if value is None or not value.strip():
        return None

    value = value.strip()
    try:
        if column in integers:
            return int(value)
        if column in reals:
            return float(value)
        if column in dates:
            date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(
            f"{source}:{line_number}: valor inválido para {column}: {value!r}"
        ) from error
    return value


def load_csv(connection, dataset, table, config):
    source = dataset / config["file"]
    expected_columns = config["columns"]
    inserted = 0

    with source.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise ValueError(
                f"{source}: cabeçalho diferente do esperado. "
                f"Esperado: {', '.join(expected_columns)}"
            )

        placeholders = ", ".join("?" for _ in expected_columns)
        column_list = ", ".join(expected_columns)
        insert_sql = (
            f"INSERT INTO {table} ({column_list}) "
            f"VALUES ({placeholders})"
        )

        for row in reader:
            line_number = reader.line_num
            if None in row or any(row[column] is None for column in expected_columns):
                raise ValueError(f"{source}:{line_number}: quantidade de campos inválida")
            for column in config["required"]:
                if not row[column].strip():
                    raise ValueError(
                        f"{source}:{line_number}: campo obrigatório {column} vazio"
                    )

            values = [
                convert_value(
                    row[column],
                    column,
                    config["integers"],
                    config["reals"],
                    config["dates"],
                    source,
                    line_number,
                )
                for column in expected_columns
            ]
            try:
                connection.execute(insert_sql, values)
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    f"{source}:{line_number}: registro inválido em {table}: {error}"
                ) from error
            inserted += 1

    return inserted


def build_database(dataset, output):
    if not SCHEMA_FILE.is_file():
        raise FileNotFoundError(f"Esquema SQLite não encontrado: {SCHEMA_FILE}")
    if not dataset.is_dir():
        raise FileNotFoundError(f"Diretório do dataset não encontrado: {dataset}")

    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}.", suffix=".tmp", dir=output.parent
    )
    os.close(descriptor)
    temporary_output = Path(temporary_name)

    try:
        counts = {}
        connection = sqlite3.connect(temporary_output)
        try:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))

                for table in (
                    "procedimentos",
                    "fila_cirurgica",
                    "eventos_clinicos",
                    "referencias_swalis",
                ):
                    counts[table] = load_csv(
                        connection, dataset, table, TABLES[table]
                    )

                foreign_key_errors = connection.execute(
                    "PRAGMA foreign_key_check"
                ).fetchall()
                if foreign_key_errors:
                    raise sqlite3.IntegrityError(
                        f"Falha de integridade referencial: {foreign_key_errors}"
                    )

                integrity = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]
                if integrity != "ok":
                    raise sqlite3.DatabaseError(
                        f"Falha na verificação de integridade SQLite: {integrity}"
                    )
        finally:
            connection.close()

        os.replace(temporary_output, output)
    finally:
        if temporary_output.exists():
            temporary_output.unlink()

    return counts


def main():
    parser = argparse.ArgumentParser(
        description="Cria/recria o banco SQLite do dataset OrdoVitae."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Pasta com os CSVs (padrão: ../dataset).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Arquivo SQLite de saída (padrão: ordovitae.sqlite3 nesta pasta).",
    )
    args = parser.parse_args()

    counts = build_database(args.dataset.resolve(), args.output.resolve())
    print(f"Banco SQLite criado: {args.output.resolve()}")
    for table, count in counts.items():
        print(f"  {table}: {count} registros")


if __name__ == "__main__":
    main()
