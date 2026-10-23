"""Row-formula templates: '{qty}*{price}' -> '=C2*D2', checked by the formula policy."""
from __future__ import annotations

import re
from typing import Mapping

from core.exceptions import FormulaPolicyError
from document.formula_safety import validate_formula

PLACEHOLDER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def template_keys(template: str) -> list[str]:
    """Column keys referenced by the template."""
    return PLACEHOLDER_RE.findall(template)


def validate_template(template: str) -> None:
    """Raise FormulaPolicyError unless the template passes the restricted policy."""
    if template.lstrip().startswith("="):
        raise FormulaPolicyError("Write the formula template without a leading '='.")
    validate_formula("=" + PLACEHOLDER_RE.sub("A1", template))


def resolve_template(template: str, refs: Mapping[str, str]) -> str:
    """Replace {key} with cell references and return a formula string."""
    return "=" + PLACEHOLDER_RE.sub(lambda m: refs[m.group(1)], template)