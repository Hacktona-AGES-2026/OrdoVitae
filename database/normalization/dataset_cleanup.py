"""Remove duplicatas definidas e eventos sem vínculo confiável a paciente."""

import csv
import json
import os
import tempfile
from pathlib import Path


TABLE_FILES = {
    "procedimentos": Path("procedimentos.csv"),
    "fila_cirurgica": Path("fila_cirurgica.csv"),
    "eventos_clinicos": Path("eventos_clinicos.csv"),
    "referencias_swalis": Path("referencias") / "swalis.csv",
}


def _read_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError(f"CSV sem cabeçalho: {path}")
        return list(reader.fieldnames), list(reader)


def _read_audit(path, row_count):
    audit_path = path.with_suffix(path.suffix + ".audit.jsonl")
    with audit_path.open("r", encoding="utf-8") as source:
        records = [json.loads(line) for line in source if line.strip()]
    if len(records) != row_count:
        raise ValueError(
            f"Quantidade de linhas diverge entre {path} e {audit_path}."
        )
    return audit_path, records


def _write_atomically(path, writer):
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        writer(temporary_path)
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _write_csv(path, headers, rows):
    def write(temporary_path):
        with temporary_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(
                output, fieldnames=headers, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)

    _write_atomically(path, write)


def _write_audit(path, records):
    def write(temporary_path):
        with temporary_path.open("w", encoding="utf-8", newline="\n") as output:
            for record in records:
                output.write(json.dumps(record, ensure_ascii=False) + "\n")

    _write_atomically(path, write)


def _duplicate_key(table, headers, row):
    if table == "eventos_clinicos":
        required = ("evento_id", "solicitacao_id", "paciente_id")
        if any(not row.get(name, "").strip() for name in required):
            return None
        return tuple(row.get(name, "") for name in headers if name != "evento_id")
    if table == "fila_cirurgica":
        return tuple(row.get(name, "") for name in headers)
    return tuple(row.get(name, "") for name in headers)


def _event_orphan_reason(event, request_to_patient, patient_ids):
    patient_id = event.get("paciente_id", "").strip()
    if not patient_id or patient_id not in patient_ids:
        return "patient_not_found_in_surgical_queue"

    request_id = event.get("solicitacao_id", "").strip()
    linked_patient = request_to_patient.get(request_id)
    if linked_patient is not None and linked_patient != patient_id:
        return "event_patient_does_not_match_request"
    return None


def _classify_rows(table, headers, rows, audits, request_to_patient, patient_ids):
    excluded = {}
    kept_duplicate_groups = {}
    if table == "eventos_clinicos":
        for index, row in enumerate(rows):
            reason = _event_orphan_reason(
                row, request_to_patient, patient_ids
            )
            if reason:
                excluded[index] = {
                    "reason": reason,
                    "duplicate_of_source_line": None,
                }

    seen = {}
    for index, row in enumerate(rows):
        if index in excluded:
            continue
        key = _duplicate_key(table, headers, row)
        if key is None:
            key = tuple(row.get(name, "") for name in headers)
            reason = "exact_duplicate_record"
        elif table == "eventos_clinicos":
            reason = "duplicate_event_payload"
        else:
            reason = "exact_duplicate_record"
        if key in seen:
            first_index = seen[key]
            excluded[index] = {
                "reason": reason,
                "duplicate_of_source_line": audits[first_index].get("source_line"),
            }
            kept_duplicate_groups[first_index] = {
                "reason": reason,
                "duplicate_count": kept_duplicate_groups.get(
                    first_index, {"duplicate_count": 0}
                )["duplicate_count"] + 1,
            }
        else:
            seen[key] = index
    return excluded, kept_duplicate_groups


def clean_normalized_dataset(dataset_dir):
    """Clean generated CSVs while preserving every source row in its audit."""
    loaded = {}
    for table, relative_path in TABLE_FILES.items():
        path = dataset_dir / relative_path
        headers, rows = _read_csv(path)
        audit_path, audits = _read_audit(path, len(rows))
        for row, audit in zip(rows, audits):
            if audit.get("normalized") != row:
                raise ValueError(
                    f"Auditoria não corresponde à linha normalizada em {path}."
                )
        loaded[table] = {
            "path": path,
            "audit_path": audit_path,
            "headers": headers,
            "rows": rows,
            "audits": audits,
        }

    queue = loaded["fila_cirurgica"]["rows"]
    patient_ids = {
        row.get("paciente_id", "").strip()
        for row in queue
        if row.get("paciente_id", "").strip()
    }
    request_to_patient = {
        row.get("solicitacao_id", "").strip(): row.get("paciente_id", "").strip()
        for row in queue
        if row.get("solicitacao_id", "").strip()
    }
    summary = {
        "exact_duplicates_removed": 0,
        "duplicate_events_removed": 0,
        "orphan_events_removed": 0,
    }

    for table, data in loaded.items():
        excluded, kept_groups = _classify_rows(
            table,
            data["headers"],
            data["rows"],
            data["audits"],
            request_to_patient,
            patient_ids,
        )
        retained_rows = []
        for index, (row, audit) in enumerate(zip(data["rows"], data["audits"])):
            if index in excluded:
                reason = excluded[index]["reason"]
                audit["cleanup"] = {
                    "retained_in_dataset": False,
                    **excluded[index],
                }
                audit["status"] = (
                    "excluded_orphan"
                    if reason.startswith("patient_")
                    or reason.startswith("event_patient_")
                    else "excluded_duplicate"
                )
                if reason == "duplicate_event_payload":
                    summary["duplicate_events_removed"] += 1
                elif reason.startswith("patient_") or reason.startswith(
                    "event_patient_"
                ):
                    summary["orphan_events_removed"] += 1
                else:
                    summary["exact_duplicates_removed"] += 1
                continue

            cleanup = {"retained_in_dataset": True}
            if index in kept_groups:
                cleanup["duplicate_group"] = kept_groups[index]
            audit["cleanup"] = cleanup
            retained_rows.append(row)

        _write_csv(data["path"], data["headers"], retained_rows)
        _write_audit(data["audit_path"], data["audits"])

    return summary
