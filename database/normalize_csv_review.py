#!/usr/bin/env python3
"""Fachada de compatibilidade para o pacote modular de normalização CSV."""

from normalization import cli as _cli
from normalization.contracts import (
    _canonical_token,
    _issue,
    _normalise_enum,
    _read_date,
    load_contract,
    read_entries,
)
from normalization.entry_validation import _add_cross_field_issues, prepare_entries
from normalization.field_rules import _normalise_field
from normalization.gemini_review import (
    DEFAULT_MODEL,
    ModelResponseError,
    MODEL_ACTIONS,
    build_review_prompt,
    genai,
    load_dotenv,
    request_gemini_reviews,
    review_response_schema,
)
from normalization.cli import _write_artifacts, parse_args


def main():
    return _cli.main(parse_args_fn=parse_args)


if __name__ == "__main__":
    main()
