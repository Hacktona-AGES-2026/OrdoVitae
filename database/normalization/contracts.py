"""Validação dos contratos e leitura de CSV com preservação das entradas."""

import csv
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _issue(code, severity, field, message, action):
    return {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
        "action": action,
    }


def _canonical_token(value):
    decomposed = unicodedata.normalize("NFKD", value)
    unaccented = "".join(
        character for character in decomposed
        if not unicodedata.combining(character)
    )
    return re.sub(r"[\s-]+", "_", unaccented.casefold().strip())


def _normalise_enum(value, allowed):
    by_token = {_canonical_token(item): item for item in allowed}
    return by_token.get(_canonical_token(value))


def _read_date(value):
    try:
        return date.fromisoformat(value), None
    except ValueError:
        pass

    for pattern in ("%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, pattern).date(), pattern
        except ValueError:
            continue
    return None, None


def load_contract(path):
    with path.open("r", encoding="utf-8") as contract_file:
        contract = json.load(contract_file)

    if not isinstance(contract, dict):
        raise ValueError("O contrato JSON deve conter um objeto.")
    fields = contract.get("fields")
    if not isinstance(fields, list) or not fields:
        raise ValueError("O contrato deve definir uma lista não vazia em 'fields'.")

    names = []
    for field in fields:
        if not isinstance(field, dict):
            raise ValueError("Cada campo do contrato deve ser um objeto.")
        name = field.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("Todo campo do contrato precisa ter um nome.")
        if field.get("type") not in {"string", "integer", "number", "date"}:
            raise ValueError(f"Tipo inválido no contrato para {name!r}.")
        if not isinstance(field.get("nullable"), bool):
            raise ValueError(f"O campo {name!r} precisa definir nullable como boolean.")
        enum = field.get("enum")
        if enum is not None and (
            not isinstance(enum, list)
            or not enum
            or not all(isinstance(value, str) for value in enum)
            or len(enum) != len(set(enum))
            or len({_canonical_token(value) for value in enum}) != len(enum)
        ):
            raise ValueError(f"O domínio enum do campo {name!r} é inválido.")
        limits = {}
        for bound in ("minimum", "maximum"):
            value = field.get(bound)
            if value is not None:
                try:
                    limits[bound] = Decimal(str(value))
                except InvalidOperation as error:
                    raise ValueError(
                        f"Limite {bound} inválido para o campo {name!r}."
                    ) from error
                if not limits[bound].is_finite():
                    raise ValueError(
                        f"Limite {bound} inválido para o campo {name!r}."
                    )
        minimum = field.get("minimum")
        maximum = field.get("maximum")
        if (
            minimum is not None
            and maximum is not None
            and limits["minimum"] > limits["maximum"]
        ):
            raise ValueError(f"Intervalo inválido para o campo {name!r}.")
        names.append(name)

    if len(names) != len(set(names)):
        raise ValueError("O contrato contém nomes de campo duplicados.")
    table = contract.get("table")
    if not isinstance(table, str) or not table:
        raise ValueError("O contrato precisa identificar a tabela em 'table'.")

    required = contract.get("required", [])
    immutable = contract.get("immutable_fields", [])
    if (
        not isinstance(required, list)
        or not all(isinstance(name, str) for name in required)
        or not set(required).issubset(names)
    ):
        raise ValueError("'required' deve listar somente campos do contrato.")
    if (
        not isinstance(immutable, list)
        or not all(isinstance(name, str) for name in immutable)
        or not set(immutable).issubset(names)
    ):
        raise ValueError("'immutable_fields' deve listar somente campos do contrato.")
    return contract


def read_entries(path, contract):
    expected_fields = [field["name"] for field in contract["fields"]]
    entries = []

    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.reader(csv_file, strict=True)
        try:
            headers = next(reader)
        except StopIteration as error:
            raise ValueError(f"O CSV está vazio: {path}") from error

        if not headers or any(not header.strip() for header in headers):
            raise ValueError("O cabeçalho CSV contém nome de coluna vazio.")
        if len(headers) != len(set(headers)):
            raise ValueError("O cabeçalho CSV contém nomes de coluna duplicados.")

        missing_headers = sorted(set(expected_fields) - set(headers))
        extra_headers = sorted(set(headers) - set(expected_fields))
        row_index = 0
        for raw_cells in reader:
            row_index += 1
            source_line = reader.line_num
            original = {
                name: raw_cells[headers.index(name)]
                if name in headers and headers.index(name) < len(raw_cells)
                else ""
                for name in expected_fields
            }
            issues = []
            if missing_headers:
                issues.append(
                    _issue(
                        "missing_columns",
                        "error",
                        None,
                        f"Colunas esperadas ausentes no cabeçalho: {missing_headers}.",
                        "keep_original_for_review",
                    )
                )
            if extra_headers:
                issues.append(
                    _issue(
                        "unexpected_columns",
                        "warning",
                        None,
                        f"Colunas extras serão mantidas no arquivo de auditoria: {extra_headers}.",
                        "keep_original_for_review",
                    )
                )
            if len(raw_cells) < len(headers):
                issues.append(
                    _issue(
                        "short_row",
                        "error",
                        None,
                        f"Linha CSV tem {len(raw_cells)} valores para {len(headers)} colunas.",
                        "keep_original_for_review",
                    )
                )
            elif len(raw_cells) > len(headers):
                issues.append(
                    _issue(
                        "extra_values",
                        "error",
                        None,
                        f"Linha CSV tem {len(raw_cells) - len(headers)} valores extras.",
                        "keep_original_for_review",
                    )
                )
            entries.append(
                {
                    "row_index": row_index - 1,
                    "source_line": source_line,
                    "raw_cells": raw_cells,
                    "source_headers": headers,
                    "original": original,
                    "issues": issues,
                    "empty_optional_fields": [],
                    "normalized": dict(original),
                    "gemini_assessment": None,
                }
            )

    return entries
