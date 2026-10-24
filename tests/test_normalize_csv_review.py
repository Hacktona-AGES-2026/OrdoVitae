import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "database"))

import normalize_csv_review as normalizer
from normalization import gemini_review


class FakeModels:
    def __init__(self, action="keep_original_for_review"):
        self.calls = []
        self.action = action

    def generate_content(self, *, model, contents, config):
        self.calls.append(
            {"model": model, "contents": contents, "config": config}
        )
        prompt = contents.split("REGISTROS COM PROBLEMAS:\n", 1)[1]
        payload = json.loads(prompt)
        reviews = [
            {
                "row_index": entry["row_index"],
                "assessment": "Manter a origem e encaminhar o problema para revisão.",
                "recommended_action": self.action,
            }
            for entry in payload
        ]
        return type(
            "FakeResponse",
            (),
            {"text": json.dumps({"reviews": reviews}, ensure_ascii=False)},
        )()


class FakeClient:
    def __init__(self):
        self.models = FakeModels()


def load_contract(table):
    return normalizer.load_contract(
        PROJECT_ROOT / "database" / "contracts" / f"{table}.json"
    )


def make_valid_row(contract):
    row = {}
    for field in contract["fields"]:
        if field["nullable"]:
            row[field["name"]] = ""
        elif field.get("enum"):
            row[field["name"]] = field["enum"][0]
        elif field["type"] == "integer":
            row[field["name"]] = str(field.get("minimum", 1))
        elif field["type"] == "number":
            row[field["name"]] = str(field.get("minimum", 1))
        elif field["type"] == "date":
            row[field["name"]] = "2026-10-23"
        else:
            row[field["name"]] = f"{field['name']}_teste"
    return row


def write_csv(path, headers, rows):
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)
        writer.writerows(rows)


class NormalizeCsvReviewTests(unittest.TestCase):
    def test_accented_enum_and_cid_are_canonicalized_deterministically(self):
        contract = load_contract("fila_cirurgica")
        row = make_valid_row(contract)
        row["prioridade_regulacao"] = "Média"
        row["cid_principal"] = " c50.9 "
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fila.csv"
            write_csv(source, headers, [list(row.values())])
            entries = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )

        entry = entries[0]
        self.assertEqual(entry["normalized"]["prioridade_regulacao"], "media")
        self.assertEqual(entry["normalized"]["cid_principal"], "C509")
        self.assertIn(
            "category_canonicalized",
            {issue["code"] for issue in entry["issues"]},
        )
        self.assertIn("cid_canonicalized", {issue["code"] for issue in entry["issues"]})

    def test_missing_required_value_is_retained_and_never_inferred(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        row["procedimento_id"] = ""
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            write_csv(source, headers, [list(row.values())])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["procedimento_id"], "")
        self.assertIn(
            "missing_required_value",
            {issue["code"] for issue in entry["issues"]},
        )
        self.assertEqual(entry["status"], "review_required")

    def test_invalid_numeric_is_preserved_for_manual_review(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        row["risco_cirurgico"] = "desconhecido"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            write_csv(source, headers, [list(row.values())])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["risco_cirurgico"], "desconhecido")
        self.assertIn(
            "invalid_integer",
            {issue["code"] for issue in entry["issues"]},
        )

    def test_missing_header_column_is_reported_and_row_is_retained(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        headers = [field["name"] for field in contract["fields"]][:-1]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["necessita_uti"], "")
        self.assertIn(
            "missing_columns",
            {issue["code"] for issue in entry["issues"]},
        )
        self.assertEqual(entry["raw_cells"], [row[name] for name in headers])

    def test_unambiguous_decimal_comma_is_canonicalized(self):
        contract = load_contract("fila_cirurgica")
        row = make_valid_row(contract)
        row["hba1c_ultima"] = "7,4"
        row["data_hba1c_ultima"] = "2026-02-01"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fila.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["hba1c_ultima"], "7.4")
        self.assertIn(
            "decimal_separator_canonicalized",
            {issue["code"] for issue in entry["issues"]},
        )

    def test_ambiguous_decimal_comma_is_preserved_for_review(self):
        contract = load_contract("fila_cirurgica")
        row = make_valid_row(contract)
        row["hba1c_ultima"] = "1,234"
        row["data_hba1c_ultima"] = "2026-02-01"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fila.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["hba1c_ultima"], "1,234")
        self.assertIn(
            "ambiguous_number_format",
            {issue["code"] for issue in entry["issues"]},
        )

    def test_row_width_mismatch_is_archived_and_all_expected_fields_are_retained(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        headers = [field["name"] for field in contract["fields"]]
        cells = [row[name] for name in headers] + ["campo extra"]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            write_csv(source, headers, [cells])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]
            output = Path(folder) / "normalized.csv"
            audit = Path(folder) / "normalized.csv.audit.jsonl"
            normalizer._write_artifacts(output, audit, [entry], contract)
            archived = json.loads(audit.read_text(encoding="utf-8").strip())
            with output.open("r", encoding="utf-8", newline="") as result_file:
                output_rows = list(csv.DictReader(result_file))

        self.assertEqual(len(output_rows), 1)
        self.assertEqual(archived["raw_cells"], cells)
        self.assertIn(
            "extra_values",
            {issue["code"] for issue in archived["issues"]},
        )
        self.assertEqual(output_rows[0], row)

    def test_duplicate_primary_keys_keep_every_historical_row(self):
        contract = load_contract("eventos_clinicos")
        first = make_valid_row(contract)
        second = dict(first)
        second["data_evento"] = "2026-10-22"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "eventos.csv"
            write_csv(source, headers, [[first[name] for name in headers], [second[name] for name in headers]])
            entries = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )

        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertIn(
                "duplicate_primary_key",
                {issue["code"] for issue in entry["issues"]},
            )
            self.assertEqual(entry["status"], "review_required")

    def test_event_result_is_checked_against_event_type(self):
        contract = load_contract("eventos_clinicos")
        row = make_valid_row(contract)
        row["tipo_evento"] = "biopsia"
        row["resultado"] = "alta"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "eventos.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertIn(
            "event_result_mismatch",
            {issue["code"] for issue in entry["issues"]},
        )
        self.assertEqual(entry["normalized"]["resultado"], "alta")

    def test_optional_missing_values_stay_empty_without_being_inferred(self):
        contract = load_contract("fila_cirurgica")
        row = make_valid_row(contract)
        row["hba1c_ultima"] = ""
        row["data_hba1c_ultima"] = ""
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "fila.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["hba1c_ultima"], "")
        self.assertEqual(entry["normalized"]["data_hba1c_ultima"], "")
        self.assertIn("hba1c_ultima", entry["empty_optional_fields"])
        self.assertNotIn(
            "missing_required_value",
            {issue["code"] for issue in entry["issues"]},
        )

    def test_gemini_receives_problem_codes_and_only_returns_review(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        row["risco_cirurgico"] = "incerto"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entries = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )
        client = FakeClient()

        reviews = normalizer.request_gemini_reviews(
            client, contract, entries, batch_size=5
        )

        self.assertIn("invalid_integer", client.models.calls[0]["contents"])
        self.assertEqual(set(reviews), {0})
        self.assertEqual(
            reviews[0]["recommended_action"], "keep_original_for_review"
        )
        self.assertEqual(entries[0]["normalized"]["risco_cirurgico"], "incerto")

    def test_event_duplicates_with_distinct_ids_are_flagged_not_deleted(self):
        contract = load_contract("eventos_clinicos")
        first = make_valid_row(contract)
        second = dict(first)
        second["evento_id"] = "EVT-OTHER"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "eventos.csv"
            write_csv(source, headers, [[first[name] for name in headers], [second[name] for name in headers]])
            entries = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )

        self.assertEqual(len(entries), 2)
        for entry in entries:
            self.assertIn(
                "possible_duplicate_event",
                {issue["code"] for issue in entry["issues"]},
            )

    def test_formula_like_text_is_flagged_but_original_is_retained(self):
        contract = load_contract("eventos_clinicos")
        row = make_valid_row(contract)
        row["descricao"] = "=HYPERLINK(\"https://invalid.example\")"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "eventos.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            entry = normalizer.prepare_entries(
                normalizer.read_entries(source, contract), contract
            )[0]

        self.assertEqual(entry["normalized"]["descricao"], row["descricao"])
        self.assertIn(
            "spreadsheet_formula_risk",
            {issue["code"] for issue in entry["issues"]},
        )

    def test_api_failure_keeps_all_rows_and_writes_review_audit(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        row["risco_cirurgico"] = "incerto"
        headers = [field["name"] for field in contract["fields"]]

        class FailingModels:
            def generate_content(self, **kwargs):
                raise httpx.ConnectError("synthetic connection failure")

        class FailingClient:
            models = FailingModels()

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            output = Path(folder) / "normalized.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            with (
                mock.patch.object(normalizer, "parse_args") as parse_args,
                mock.patch.object(gemini_review, "load_dotenv"),
                mock.patch.object(
                    gemini_review.genai, "Client", return_value=FailingClient()
                ),
                mock.patch.dict(os.environ, {"GEMINI_KEY": "synthetic-test-key"}),
            ):
                parse_args.return_value = type(
                    "Args",
                    (),
                    {
                        "contract": PROJECT_ROOT / "database" / "contracts" / "procedimentos.json",
                        "input": source,
                        "output": output,
                        "batch_size": 5,
                    },
                )()
                result = normalizer.main()

            audit_path = output.with_suffix(output.suffix + ".audit.jsonl")
            with output.open("r", encoding="utf-8", newline="") as csv_file:
                output_rows = list(csv.DictReader(csv_file))
            audit_rows = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(result, 2)
        self.assertEqual(len(output_rows), 1)
        self.assertEqual(output_rows[0]["risco_cirurgico"], "incerto")
        self.assertEqual(len(audit_rows), 1)
        self.assertEqual(
            audit_rows[0]["gemini_assessment"]["status"],
            "review_request_failed",
        )

    def test_offline_mode_does_not_load_credentials_or_call_gemini(self):
        contract = load_contract("procedimentos")
        row = make_valid_row(contract)
        row["risco_cirurgico"] = "incerto"
        headers = [field["name"] for field in contract["fields"]]

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "procedimentos.csv"
            output = Path(folder) / "normalized.csv"
            write_csv(source, headers, [[row[name] for name in headers]])
            with (
                mock.patch.object(normalizer, "parse_args") as parse_args,
                mock.patch.object(gemini_review, "load_dotenv") as load_dotenv,
                mock.patch.object(gemini_review.genai, "Client") as genai_client,
            ):
                parse_args.return_value = type(
                    "Args",
                    (),
                    {
                        "contract": PROJECT_ROOT / "database" / "contracts" / "procedimentos.json",
                        "input": source,
                        "output": output,
                        "batch_size": 5,
                        "offline": True,
                    },
                )()
                result = normalizer.main()

            audit_path = output.with_suffix(output.suffix + ".audit.jsonl")
            audit_rows = [
                json.loads(line)
                for line in audit_path.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(result, 2)
        load_dotenv.assert_not_called()
        genai_client.assert_not_called()
        self.assertEqual(
            audit_rows[0]["gemini_assessment"]["status"],
            "not_called_offline",
        )
        self.assertEqual(audit_rows[0]["normalized"]["risco_cirurgico"], "incerto")

    def test_existing_output_is_not_overwritten(self):
        contract = load_contract("procedimentos")
        entry = {
            "row_index": 0,
            "source_line": 2,
            "raw_cells": [],
            "source_headers": [],
            "original": {},
            "normalized": make_valid_row(contract),
            "issues": [],
            "empty_optional_fields": [],
            "gemini_assessment": None,
            "status": "normalized",
        }
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "result.csv"
            audit = Path(folder) / "result.csv.audit.jsonl"
            output.write_text("existing\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                normalizer._write_artifacts(output, audit, [entry], contract)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing\n")
            self.assertFalse(audit.exists())


if __name__ == "__main__":
    unittest.main()
