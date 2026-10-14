"""Formula-injection protection: only explicit, validated formulas reach Excel."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from config.constants import FORMULA_ALLOWED_FUNCTIONS, FORMULA_MAX_LENGTH
from core.exceptions import FormulaPolicyError

_CHARS_RE = re.compile(r'^=[A-Za-z0-9_ .,:;+\-*/^()$%<>="]*$')
_FUNC_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*\(")


def is_formula_like(text: str) -> bool:
    """True if Excel/CSV consumers could read the text as a formula."""
    if text[:1] in ("\t", "\r"):
        return True
    for ch in text:
        if ch.isspace() or unicodedata.category(ch) == "Cc":
            continue
        return ch in "=+-@"
    return False


def write_text_cell(cell: Any, text: str) -> None:
    """Store untrusted text as a string cell, never as a formula."""
    cell.value = ILLEGAL_CHARACTERS_RE.sub("", text)
    cell.data_type = "s"  # override openpyxl's '=' -> formula detection
    if is_formula_like(cell.value):
        cell.quotePrefix = True  # keeps it text if the user edits the cell


def validate_formula(formula: str) -> str:
    """Return the formula if it satisfies the restricted policy, else raise."""
    if not formula.startswith("=") or len(formula) < 2:
        raise FormulaPolicyError("A formula must start with '=' and not be empty.")
    if len(formula) > FORMULA_MAX_LENGTH:
        raise FormulaPolicyError(f"Formula is longer than {FORMULA_MAX_LENGTH} characters.")
    if not _CHARS_RE.match(formula) or formula.count('"') % 2:
        raise FormulaPolicyError("Formula contains characters that are not allowed.")
    for name in _FUNC_RE.findall(formula):
        if name.upper() not in FORMULA_ALLOWED_FUNCTIONS:
            raise FormulaPolicyError(f"Function '{name}' is not allowed.",
                                     hint="Allowed: " + ", ".join(sorted(FORMULA_ALLOWED_FUNCTIONS)))
    return formula
