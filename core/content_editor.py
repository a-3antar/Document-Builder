"""Tk-free editing logic for structured document content (unit-testable)."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Iterable, Iterator, Literal, get_args

from config.constants import OCR_UNCERTAIN_OPEN
from core.models import (Block, DocumentContentModel, Heading, ListBlock, Metadata,
                         Paragraph, Table)

BlockKind = Literal["heading", "paragraph", "list", "table"]
KINDS: tuple[str, ...] = get_args(BlockKind)
LANGUAGES: tuple[str, ...] = ("en", "ar", "mixed")
DIRECTIONS: tuple[str, ...] = ("auto", "ltr", "rtl")

_CELL_SPLIT = re.compile(r"(?<!\\)\|")           # a pipe not escaped as \|
_BULLET_RE = re.compile(r"^\s*(?:[-•*]|\d+[.)])\s+")
_DEFAULTS: dict[str, Block] = {
    "heading": Heading("New heading", 2),
    "paragraph": Paragraph(""),
    "list": ListBlock(("Item",)),
    "table": Table(("Column 1", "Column 2"), (("", ""),)),
}


@dataclass(frozen=True)
class EditorIssue:
    """A problem found in the edited content; blocking issues stop the export."""
    index: int | None          # zero-based block index, None for document-level
    message: str
    blocking: bool = True

    def __str__(self) -> str:
        return self.message if self.index is None else f"Block {self.index + 1}: {self.message}"


def kind_of(block: Block) -> BlockKind:
    if isinstance(block, Heading):
        return "heading"
    if isinstance(block, ListBlock):
        return "list"
    if isinstance(block, Table):
        return "table"
    return "paragraph"


# --- table <-> text ("a | b" per line, first line is the header) ---
def encode_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    def cell(text: str) -> str:
        return text.replace("\n", " ").replace("|", "\\|")

    lines = [" | ".join(cell(c) for c in headers)]
    lines += [" | ".join(cell(c) for c in row) for row in rows]
    return "\n".join(lines)


def decode_table(text: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    grid = [tuple(c.strip().replace("\\|", "|") for c in _CELL_SPLIT.split(ln)) for ln in lines]
    if not grid:
        return (), ()
    return grid[0], tuple(grid[1:])


# --- block <-> text (used by the editor forms and by type conversion) ---
def block_to_text(block: Block) -> str:
    if isinstance(block, (Heading, Paragraph)):
        return block.text
    if isinstance(block, ListBlock):
        return "\n".join(block.items)
    return encode_table(block.headers, block.rows)


def text_to_block(kind: str, text: str, like: Block | None = None) -> Block:
    """Build a block from text; `like` supplies settings (level, direction, ...)."""
    if kind == "heading":
        return Heading(" ".join(text.split()), like.level if isinstance(like, Heading) else 2)
    if kind == "paragraph":
        return Paragraph(text.strip(), like.direction if isinstance(like, Paragraph) else "auto")
    if kind == "list":
        items = tuple(s for ln in text.splitlines() if (s := _BULLET_RE.sub("", ln).strip()))
        return ListBlock(items, like.ordered if isinstance(like, ListBlock) else False)
    if kind == "table":
        headers, rows = decode_table(text)
        return Table(headers, rows, like.caption if isinstance(like, Table) else "")
    raise ValueError(f"Unknown block kind: {kind}")


def block_summary(block: Block, width: int = 56) -> str:
    """One-line label for the block list."""
    def short(text: str) -> str:
        one = " ".join(text.split())
        return one if len(one) <= width else one[: width - 1] + "…"

    if isinstance(block, Heading):
        return f"H{block.level}  {short(block.text) or '(empty)'}"
    if isinstance(block, Paragraph):
        return f"¶  {short(block.text) or '(empty)'}"
    if isinstance(block, ListBlock):
        return f"List ({len(block.items)} items)  {short(block.items[0]) if block.items else ''}"
    return f"Table ({len(block.headers)} col x {len(block.rows)} rows)  {short(block.caption)}"


def iter_texts(blocks: Iterable[Block]) -> Iterator[str]:
    for b in blocks:
        if isinstance(b, (Heading, Paragraph)):
            yield b.text
        elif isinstance(b, ListBlock):
            yield from b.items
        else:
            yield b.caption
            yield from b.headers
            for row in b.rows:
                yield from row


def count_markers(blocks: Iterable[Block]) -> int:
    """Number of unresolved OCR uncertainty markers."""
    return sum(t.count(OCR_UNCERTAIN_OPEN) for t in iter_texts(blocks))


class EditorViewModel:
    """Mutable working copy of a document; blocks themselves stay immutable."""

    def __init__(self, content: DocumentContentModel) -> None:
        self.metadata: Metadata = content.metadata
        self.blocks: list[Block] = list(content.blocks)
        self._schema_version = content.schema_version

    def set_metadata(self, *, title: str | None = None, language: str | None = None) -> None:
        changes: dict[str, str] = {}
        if title is not None:
            changes["title"] = title.strip()
        if language in LANGUAGES:
            changes["language"] = language
        self.metadata = replace(self.metadata, **changes)

    def add(self, kind: str, after: int | None = None) -> int:
        """Insert a default block after `after` (or at the end); return its index."""
        if kind not in _DEFAULTS:
            raise ValueError(f"Unknown block kind: {kind}")
        pos = len(self.blocks) if after is None else min(after + 1, len(self.blocks))
        self.blocks.insert(pos, _DEFAULTS[kind])
        return pos

    def remove(self, index: int) -> None:
        del self.blocks[index]

    def replace(self, index: int, block: Block) -> None:
        self.blocks[index] = block

    def move(self, index: int, delta: int) -> int:
        """Move a block by `delta`; returns the new index (unchanged at the edges)."""
        new = index + delta
        if not 0 <= new < len(self.blocks):
            return index
        self.blocks[index], self.blocks[new] = self.blocks[new], self.blocks[index]
        return new

    def convert(self, index: int, kind: str) -> Block:
        """Change a block's type, carrying its text over."""
        old = self.blocks[index]
        new = text_to_block(kind, block_to_text(old), old)
        self.blocks[index] = new
        return new

    def to_model(self) -> DocumentContentModel:
        """Snapshot for export; the user has reviewed it, so needs_review is cleared."""
        return DocumentContentModel(self.metadata, list(self.blocks), needs_review=False,
                                    schema_version=self._schema_version)

    def issues(self) -> list[EditorIssue]:
        out: list[EditorIssue] = []
        if not self.blocks:
            out.append(EditorIssue(None, "The document has no content blocks."))
        if not self.metadata.title.strip():
            out.append(EditorIssue(None, "The document has no title.", blocking=False))
        for i, b in enumerate(self.blocks):
            if isinstance(b, Heading) and not b.text.strip():
                out.append(EditorIssue(i, "Heading text is empty."))
            elif isinstance(b, Paragraph) and not b.text.strip():
                out.append(EditorIssue(i, "Paragraph is empty.", blocking=False))
            elif isinstance(b, ListBlock) and not b.items:
                out.append(EditorIssue(i, "List has no items."))
            elif isinstance(b, Table):
                if not b.headers:
                    out.append(EditorIssue(i, "Table has no header row."))
                elif any(len(r) != len(b.headers) for r in b.rows):
                    out.append(EditorIssue(
                        i, "Some rows have a different number of cells than the header.",
                        blocking=False))
        if (n := count_markers(self.blocks)):
            out.append(EditorIssue(None, f"{n} uncertain OCR marker(s) '[? ?]' remain.",
                                   blocking=False))
        return out