"""Regras determinísticas de normalização de campos e constantes de domínio."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .contracts import _canonical_token, _issue, _normalise_enum, _read_date

INTEGER_PATTERN = re.compile(r"^-?\d+$")

NUMBER_PATTERN = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")

CID_PATTERN = re.compile(r"^[A-Z][0-9A-Z]{2,5}$")

FORMULA_PREFIX_PATTERN = re.compile(r"^\s*[=+\-@＝＋－＠]")

REFERENCE_DATE = date(2026, 10, 23)

MUNICIPALITIES = {
    "alegrete": "Alegrete",
    "alvorada": "Alvorada",
    "bage": "Bagé",
    "cachoeira_do_sul": "Cachoeira do Sul",
    "cachoeirinha": "Cachoeirinha",
    "camaqua": "Camaquã",
    "canoas": "Canoas",
    "caxias_do_sul": "Caxias do Sul",
    "charqueadas": "Charqueadas",
    "cruz_alta": "Cruz Alta",
    "eldorado_do_sul": "Eldorado do Sul",
    "erechim": "Erechim",
    "esteio": "Esteio",
    "gravatai": "Gravataí",
    "guaiba": "Guaíba",
    "ijui": "Ijuí",
    "lajeado": "Lajeado",
    "montenegro": "Montenegro",
    "novo_hamburgo": "Novo Hamburgo",
    "osorio": "Osório",
    "palmeira_das_missoes": "Palmeira das Missões",
    "passo_fundo": "Passo Fundo",
    "pelotas": "Pelotas",
    "porto_alegre": "Porto Alegre",
    "rio_grande": "Rio Grande",
    "santa_cruz_do_sul": "Santa Cruz do Sul",
    "santa_maria": "Santa Maria",
    "santa_rosa": "Santa Rosa",
    "santana_do_livramento": "Santana do Livramento",
    "santo_angelo": "Santo Ângelo",
    "sao_borja": "São Borja",
    "sao_gabriel": "São Gabriel",
    "sao_leopoldo": "São Leopoldo",
    "sapucaia_do_sul": "Sapucaia do Sul",
    "taquara": "Taquara",
    "torres": "Torres",
    "tramandai": "Tramandaí",
    "uruguaiana": "Uruguaiana",
    "viamao": "Viamão",
}

PRIMARY_KEYS = {
    "fila_cirurgica": ("solicitacao_id",),
    "eventos_clinicos": ("evento_id",),
    "procedimentos": ("procedimento_id",),
    "referencias_swalis": ("classe",),
}

EVENT_RESULTS = {
    "biopsia": {"positivo", "negativo", "inconclusivo"},
    "hba1c": {"resultado"},
    "pronto_socorro": {"atendido_liberado", "observacao"},
    "internacao": {"alta"},
    "exame_imagem": {"estavel", "progressao"},
    "consulta_reavaliacao": {"piora", "estavel", "melhora"},
    "contato_telefonico": {
        "atendeu",
        "nao_atendeu",
        "relata_piora",
        "relata_melhora",
        "informou_cirurgia_outro_servico",
        "desistiu",
    },
    "falta": {"consulta", "exame", "avaliacao_pre_anestesica"},
}


def _normalise_field(value, field):
    original = value
    value = value.strip()
    issues = []
    if value != original:
        issues.append(
            _issue(
                "outer_whitespace",
                "info",
                field["name"],
                "Espaços externos removidos de forma determinística.",
                "safe_format_normalization",
            )
        )
    if not value:
        return value, issues, None

    if field["type"] == "string" and FORMULA_PREFIX_PATTERN.match(value):
        issues.append(
            _issue(
                "spreadsheet_formula_risk",
                "warning",
                field["name"],
                "Texto começa com caractere interpretável como fórmula por planilhas.",
                "keep_original_for_review",
            )
        )

    allowed = field.get("enum")
    if allowed is not None:
        canonical = _normalise_enum(value, allowed)
        if canonical is None:
            issues.append(
                _issue(
                    "unknown_category",
                    "error",
                    field["name"],
                    f"Categoria não reconhecida; valores válidos: {allowed}.",
                    "keep_original_for_review",
                )
            )
            return value, issues, None
        if canonical != value:
            value = canonical
            issues.append(
                _issue(
                    "category_canonicalized",
                    "info",
                    field["name"],
                    "Variação de caixa/acentuação mapeada para categoria existente.",
                    "safe_format_normalization",
                )
            )

    if field["name"].startswith("cid_"):
        canonical = re.sub(r"[.\s]", "", value).upper()
        if canonical != value:
            value = canonical
            issues.append(
                _issue(
                    "cid_canonicalized",
                    "info",
                    field["name"],
                    "Ponto, espaços e caixa do código CID normalizados.",
                    "safe_format_normalization",
                )
            )
        if not CID_PATTERN.fullmatch(value):
            issues.append(
                _issue(
                    "invalid_cid_format",
                    "warning",
                    field["name"],
                    "O código não corresponde ao formato sintático CID esperado.",
                    "keep_original_for_review",
                )
            )

    if field["name"] == "municipio":
        canonical = MUNICIPALITIES.get(_canonical_token(value))
        if canonical is None:
            canonical = value.title()
        if canonical != value:
            value = canonical
            issues.append(
            _issue(
                "municipality_canonicalized",
                "info",
                field["name"],
                "Nome do município padronizado sem inferir outra localidade.",
                "safe_format_normalization",
            )
            )

    field_type = field["type"]
    if field_type == "integer":
        if not INTEGER_PATTERN.fullmatch(value):
            issues.append(
                _issue(
                    "invalid_integer",
                    "error",
                    field["name"],
                    "Valor não pode ser interpretado sem ambiguidade como inteiro.",
                    "keep_original_for_review",
                )
            )
            return value, issues, None
        number = int(value)
        minimum = field.get("minimum")
        maximum = field.get("maximum")
        if (
            minimum is not None and number < minimum
        ) or (
            maximum is not None and number > maximum
        ):
            issues.append(
                _issue(
                    "out_of_range",
                    "error",
                    field["name"],
                    f"Valor fora do intervalo definido no contrato ({minimum}, {maximum}).",
                    "keep_original_for_review",
                )
            )
            return value, issues, None
        canonical = str(number)
        if canonical != value:
            issues.append(
                _issue(
                    "integer_canonicalized",
                    "info",
                    field["name"],
                    "Representação inteira normalizada sem alterar o valor.",
                    "safe_format_normalization",
                )
            )
        return canonical, issues, number

    if field_type == "number":
        if re.fullmatch(r"-?\d+,\d+", value) and "." not in value:
            if len(value.rsplit(",", 1)[1]) == 3:
                issues.append(
                    _issue(
                        "ambiguous_number_format",
                        "warning",
                        field["name"],
                        "Vírgula pode indicar decimal ou agrupamento de milhares; "
                        "nenhuma conversão foi aplicada.",
                        "keep_original_for_review",
                    )
                )
                return original.strip(), issues, None
            value = value.replace(",", ".")
            issues.append(
                _issue(
                    "decimal_separator_canonicalized",
                    "info",
                    field["name"],
                    "Vírgula decimal sem ambiguidade convertida para ponto.",
                    "safe_format_normalization",
                )
            )
        if not NUMBER_PATTERN.fullmatch(value):
            issues.append(
                _issue(
                    "invalid_number",
                    "error",
                    field["name"],
                    "Valor não pode ser interpretado sem ambiguidade como número decimal.",
                    "keep_original_for_review",
                )
            )
            return original.strip(), issues, None
        try:
            number = Decimal(value)
        except InvalidOperation:
            issues.append(
                _issue(
                    "invalid_number",
                    "error",
                    field["name"],
                    "Valor não pode ser interpretado como decimal.",
                    "keep_original_for_review",
                )
            )
            return original.strip(), issues, None
        minimum = field.get("minimum")
        maximum = field.get("maximum")
        if (
            minimum is not None and number < Decimal(str(minimum))
        ) or (
            maximum is not None and number > Decimal(str(maximum))
        ):
            issues.append(
                _issue(
                    "out_of_range",
                    "error",
                    field["name"],
                    f"Valor fora do intervalo definido no contrato ({minimum}, {maximum}).",
                    "keep_original_for_review",
                )
            )
            return original.strip(), issues, None
        canonical = format(number.normalize(), "f")
        if canonical != original.strip():
            value = canonical
            if not any(issue["code"] == "decimal_separator_canonicalized" for issue in issues):
                issues.append(
                    _issue(
                        "number_canonicalized",
                        "info",
                        field["name"],
                        "Representação decimal normalizada sem alterar o valor.",
                        "safe_format_normalization",
                    )
                )
        return value, issues, number

    if field_type == "date":
        parsed, source_format = _read_date(value)
        if parsed is None:
            issues.append(
                _issue(
                    "invalid_date",
                    "error",
                    field["name"],
                    "Data inválida ou em formato ambíguo; nenhum dia foi inferido.",
                    "keep_original_for_review",
                )
            )
            return value, issues, None
        canonical = parsed.isoformat()
        if source_format or canonical != value:
            value = canonical
            issues.append(
                _issue(
                    "date_format_canonicalized",
                    "info",
                    field["name"],
                    "Formato de data reconhecido sem alterar o dia.",
                    "safe_format_normalization",
                )
            )
        return value, issues, parsed

    return value, issues, None
