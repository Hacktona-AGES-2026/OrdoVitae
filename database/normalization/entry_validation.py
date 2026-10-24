"""Checagens entre campos, detecção de duplicatas e classificação para revisão."""

from datetime import date
from decimal import Decimal, InvalidOperation
import re

from .contracts import _issue, _normalise_enum
from .field_rules import EVENT_RESULTS, PRIMARY_KEYS, REFERENCE_DATE, _normalise_field


def _add_cross_field_issues(entry, contract, typed_values):
    table = contract["table"]
    data = entry["normalized"]

    if table == "eventos_clinicos":
        event_type = data.get("tipo_evento", "")
        result = data.get("resultado", "")
        allowed = EVENT_RESULTS.get(event_type)
        canonical_result = (
            _normalise_enum(result, sorted(allowed)) if allowed is not None else None
        )
        if canonical_result is not None and canonical_result != result:
            data["resultado"] = canonical_result
            entry["issues"].append(
                _issue(
                    "event_result_canonicalized",
                    "info",
                    "resultado",
                    "Variação de caixa/acentuação mapeada para resultado permitido.",
                    "safe_format_normalization",
                )
            )
            result = canonical_result
        if allowed is not None and result not in allowed:
            entry["issues"].append(
                _issue(
                    "event_result_mismatch",
                    "error",
                    "resultado",
                    f"Resultado incompatível ou desconhecido para tipo_evento={event_type!r}.",
                    "keep_original_for_review",
                )
            )

        numeric_value = data.get("valor_numerico", "").strip()
        if event_type in {"hba1c", "internacao"} and not numeric_value:
            entry["issues"].append(
                _issue(
                    "missing_event_measurement",
                    "warning",
                    "valor_numerico",
                    f"Evento {event_type!r} sem a medida numérica esperada.",
                    "preserve_missing_information",
                )
            )
        elif event_type == "hba1c" and numeric_value:
            try:
                if Decimal(numeric_value) > Decimal("30"):
                    entry["issues"].append(
                        _issue(
                            "suspected_hba1c_outlier",
                            "warning",
                            "valor_numerico",
                            "Valor acima do limite amplo de validação (30); conferir "
                            "unidade, separador decimal e fonte.",
                            "keep_original_for_review",
                        )
                    )
            except InvalidOperation:
                pass
        elif event_type not in {"hba1c", "internacao"} and numeric_value:
            entry["issues"].append(
                _issue(
                    "unexpected_event_measurement",
                    "warning",
                    "valor_numerico",
                    f"Evento {event_type!r} tem valor numérico não previsto pelo dicionário.",
                    "keep_original_for_review",
                )
            )

        event_date = typed_values.get("data_evento")
        if isinstance(event_date, date) and event_date > REFERENCE_DATE:
            entry["issues"].append(
                _issue(
                    "future_event_date",
                    "warning",
                    "data_evento",
                    "Data do evento posterior à referência do dataset; "
                    "preservar e confirmar a origem.",
                    "keep_original_for_review",
                )
            )

        if event_type == "internacao" and numeric_value:
            try:
                if Decimal(numeric_value) <= 0:
                    entry["issues"].append(
                        _issue(
                            "invalid_stay_duration",
                            "error",
                            "valor_numerico",
                            "Dias de internação devem ser maiores que zero.",
                            "keep_original_for_review",
                        )
                    )
            except InvalidOperation:
                pass

    if table == "fila_cirurgica":
        entered = typed_values.get("data_entrada_fila")
        days = typed_values.get("dias_em_fila")
        if isinstance(entered, date) and isinstance(days, int):
            calculated = (REFERENCE_DATE - entered).days
            if calculated < 0 or calculated != days:
                entry["issues"].append(
                    _issue(
                        "waiting_time_mismatch",
                        "warning",
                        "dias_em_fila",
                        f"Data de referência 2026-10-23 implica {calculated} dia(s), "
                        f"mas o CSV informa {days}; nenhum dos valores foi sobrescrito.",
                        "keep_original_for_review",
                    )
                )

        cid = data.get("cid_principal", "")
        oncological_flag = data.get("flag_oncologico", "")
        if cid.startswith("C") and oncological_flag == "nao":
            entry["issues"].append(
                _issue(
                    "oncology_flag_conflict",
                    "warning",
                    "flag_oncologico",
                    "CID iniciado por C diverge da flag_oncologico; preservar ambos para revisão.",
                    "keep_original_for_review",
                )
            )
        elif oncological_flag == "sim" and not cid.startswith("C"):
            entry["issues"].append(
                _issue(
                    "oncology_flag_conflict",
                    "warning",
                    "flag_oncologico",
                    "Flag oncológica diverge do CID principal; outros eventos "
                    "podem explicar a divergência, então preservar ambos.",
                    "keep_original_for_review",
                )
            )

        diabetic_flag = data.get("flag_diabetico", "")
        diabetes_evidence = (
            data.get("cid_secundario", "").startswith("E11")
            or re.search(
                r"\b(dm2?|diabetes)\b",
                data.get("comorbidades", ""),
                flags=re.IGNORECASE,
            )
            is not None
        )
        if (diabetic_flag == "nao" and diabetes_evidence) or (
            diabetic_flag == "sim" and not diabetes_evidence
        ):
            entry["issues"].append(
                _issue(
                    "diabetes_flag_conflict",
                    "warning",
                    "flag_diabetico",
                    "Flag de diabetes e CID/comorbidades não coincidem; "
                    "preservar valores para revisão.",
                    "keep_original_for_review",
                )
            )

        hba1c = data.get("hba1c_ultima", "").strip()
        hba1c_date = data.get("data_hba1c_ultima", "").strip()
        if bool(hba1c) != bool(hba1c_date):
            entry["issues"].append(
                _issue(
                    "incomplete_hba1c_pair",
                    "warning",
                    "hba1c_ultima",
                    "HbA1c e data correspondente não foram informadas em conjunto; "
                    "não inferir o valor ou a data ausentes.",
                    "preserve_missing_information",
                )
            )


def prepare_entries(entries, contract):
    fields = {field["name"]: field for field in contract["fields"]}
    required = set(contract.get("required", [])) | {
        name for name, field in fields.items() if not field["nullable"]
    }

    for entry in entries:
        typed_values = {}
        for name, field in fields.items():
            original = entry["original"].get(name, "")
            value = original.strip()
            if not value:
                if name in required:
                    entry["issues"].append(
                        _issue(
                            "missing_required_value",
                            "error",
                            name,
                            "Campo obrigatório vazio; o modelo não deve inventar um valor.",
                            "preserve_missing_information",
                        )
                    )
                elif name in entry["source_headers"]:
                    entry["empty_optional_fields"].append(name)
                entry["normalized"][name] = original
                continue

            normalized, issues, typed = _normalise_field(value, field)
            entry["normalized"][name] = normalized
            entry["issues"].extend(issues)
            typed_values[name] = typed

        _add_cross_field_issues(entry, contract, typed_values)

    key_fields = PRIMARY_KEYS.get(contract["table"], ())
    seen = {}
    for entry in entries:
        key = tuple(entry["original"].get(name, "").strip() for name in key_fields)
        if not key_fields or any(not value for value in key):
            continue
        if key in seen:
            first_entry = seen[key]
            duplicate_message = (
                f"Chave {key!r} repetida nas linhas de origem "
                f"{first_entry['source_line']} e {entry['source_line']}."
            )
            duplicate_issue = _issue(
                "duplicate_primary_key",
                "error",
                key_fields[0],
                duplicate_message,
                "preserve_possible_duplicate",
            )
            first_entry["issues"].append(duplicate_issue)
            entry["issues"].append(dict(duplicate_issue))
        else:
            seen[key] = entry

    if contract["table"] == "fila_cirurgica":
        requests = {}
        for entry in entries:
            key = (
                entry["original"].get("paciente_id", "").strip(),
                entry["original"].get("procedimento_id", "").strip(),
            )
            if not all(key):
                continue
            if key in requests:
                issue = _issue(
                    "possible_duplicate_request",
                    "warning",
                    "solicitacao_id",
                    "Paciente e procedimento já aparecem em outra solicitação; "
                    "pode ser duplicata ou solicitação legítima distinta.",
                    "preserve_possible_duplicate",
                )
                requests[key]["issues"].append(dict(issue))
                entry["issues"].append(issue)
            else:
                requests[key] = entry

    if contract["table"] == "eventos_clinicos":
        payloads = {}
        for entry in entries:
            signature = tuple(
                entry["original"].get(field["name"], "")
                for field in contract["fields"]
                if field["name"] != "evento_id"
            )
            if signature in payloads:
                issue = _issue(
                    "possible_duplicate_event",
                    "warning",
                    "evento_id",
                    "Conteúdo igual ao de outro evento; manter ambos porque podem "
                    "ser registros históricos legítimos.",
                    "preserve_possible_duplicate",
                )
                payloads[signature]["issues"].append(dict(issue))
                entry["issues"].append(issue)
            else:
                payloads[signature] = entry

    for entry in entries:
        if any(issue["severity"] in {"warning", "error"} for issue in entry["issues"]):
            entry["status"] = "review_required"
        elif entry["issues"]:
            entry["status"] = "normalized_with_notes"
        else:
            entry["status"] = "normalized"
    return entries
