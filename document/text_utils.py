"""Text helpers shared by all exporters."""
from __future__ import annotations

import re
import unicodedata
from typing import Literal, Sequence

Direction = Literal["ltr", "rtl"]

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
_ARABIC_RE = re.compile("[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]")


def clean_text(text: str) -> str:
    """Drop control characters that XML-based writers reject (keeps tab/newline)."""
    return _CONTROL_RE.sub("", text)


def has_arabic(text: str) -> bool:
    return _ARABIC_RE.search(text) is not None


def resolve_direction(text: str, hint: str = "auto") -> Direction:
    """Explicit hint wins; otherwise the first strong character decides (UBA rule P2)."""
    if hint in ("ltr", "rtl"):
        return hint  # type: ignore[return-value]
    for ch in text:
        bidi = unicodedata.bidirectional(ch)
        if bidi in ("R", "AL"):
            return "rtl"
        if bidi == "L":
            return "ltr"
    return "ltr"


def normalize_table(headers: Sequence[str], rows: Sequence[Sequence[str]]
                    ) -> tuple[list[str], list[list[str]], str | None]:
    """Make every row exactly as wide as the header; extra columns get blank headers."""
    width = max([len(headers), *(len(r) for r in rows)] or [0])
    note = None
    if width > len(headers):
        note = "A table had rows wider than its header; blank headers were added."
    head = [clean_text(h) for h in headers] + [""] * (width - len(headers))
    body = [[clean_text(c) for c in r] + [""] * (width - len(r)) for r in rows]
    return head, body, note
