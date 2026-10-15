"""Structured editor widget: block list + a form per block type. Logic is in EditorViewModel."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

from core.content_editor import (DIRECTIONS, KINDS, LANGUAGES, EditorIssue, EditorViewModel,
                                 block_summary, block_to_text, kind_of, text_to_block)
from core.models import DocumentContentModel, Heading, ListBlock, Paragraph, Table
from ui.theme import PAD

_LABELS = {"heading": "Heading", "paragraph": "Paragraph", "list": "List", "table": "Table"}
_BY_LABEL = {v: k for k, v in _LABELS.items()}


class StructuredEditor(ttk.Frame):
    """Edit headings, paragraphs, lists and simple tables of a DocumentContentModel."""

    def __init__(self, parent: Any, on_change: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self._vm = EditorViewModel(DocumentContentModel())
        self._index: int | None = None          # block currently shown in the form
        self._changed = on_change or (lambda: None)
        self._title, self._lang = tk.StringVar(), tk.StringVar(value="en")
        self._convert = tk.StringVar()
        self._level, self._heading = tk.StringVar(value="2"), tk.StringVar()
        self._direction, self._ordered = tk.StringVar(value="auto"), tk.BooleanVar(value=False)
        self._caption = tk.StringVar()
        self._texts: dict[str, tk.Text] = {}
        self._forms: dict[str, ttk.Frame] = {}
        self._build()

    # --- public API ---
    def set_content(self, content: DocumentContentModel) -> None:
        self._vm = EditorViewModel(content)
        self._title.set(content.metadata.title)
        self._lang.set(content.metadata.language if content.metadata.language in LANGUAGES else "en")
        self._index = None
        self._refresh()
        if self._vm.blocks:
            self._select(0)
        else:
            self._show(None)

    def get_content(self) -> DocumentContentModel:
        """Commit pending edits and return a snapshot."""
        self._commit()
        self._vm.set_metadata(title=self._title.get(), language=self._lang.get())
        return self._vm.to_model()

    def issues(self) -> list[EditorIssue]:
        self.get_content()
        return self._vm.issues()

    # --- layout ---
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x")
        ttk.Label(top, text="Title").pack(side="left")
        title = ttk.Entry(top, textvariable=self._title, width=44)
        title.pack(side="left", padx=PAD)
        title.bind("<KeyRelease>", lambda _e: self._changed())
        ttk.Label(top, text="Language").pack(side="left")
        lang = ttk.Combobox(top, textvariable=self._lang, values=LANGUAGES, state="readonly", width=7)
        lang.pack(side="left", padx=PAD)
        lang.bind("<<ComboboxSelected>>", lambda _e: self._changed())

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, pady=(PAD, 0))
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        self._list = tk.Listbox(left, width=44, height=16, exportselection=False, activestyle="none")
        scroll = ttk.Scrollbar(left, command=self._list.yview)
        self._list.configure(yscrollcommand=scroll.set)
        self._list.grid(row=0, column=0, sticky="ns")
        scroll.grid(row=0, column=1, sticky="ns")
        left.rowconfigure(0, weight=1)
        self._list.bind("<<ListboxSelect>>", self._on_select)

        add = ttk.Frame(left)
        add.grid(row=1, column=0, columnspan=2, sticky="w", pady=(PAD // 2, 0))
        for kind in KINDS:
            ttk.Button(add, text=f"+ {_LABELS[kind]}",
                       command=lambda k=kind: self._add(k)).pack(side="left", padx=(0, 2))
        ops = ttk.Frame(left)
        ops.grid(row=2, column=0, columnspan=2, sticky="w", pady=2)
        for text, cmd in (("Up", lambda: self._move(-1)), ("Down", lambda: self._move(1)),
                          ("Delete", self._remove)):
            ttk.Button(ops, text=text, command=cmd).pack(side="left", padx=(0, 2))
        conv = ttk.Frame(left)
        conv.grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(conv, text="Change type").pack(side="left")
        box = ttk.Combobox(conv, textvariable=self._convert, values=list(_BY_LABEL),
                           state="readonly", width=12)
        box.pack(side="left", padx=PAD // 2)
        box.bind("<<ComboboxSelected>>", self._on_convert)

        self._right = ttk.Frame(body)
        self._right.pack(side="left", fill="both", expand=True, padx=(PAD, 0))
        self._hint = ttk.Label(self._right, text="Select or add a block to edit it.",
                               style="Subtle.TLabel")
        self._build_heading_form()
        self._build_paragraph_form()
        self._build_list_form()
        self._build_table_form()
        self._show(None)

    def _text_form(self, kind: str, label: str) -> ttk.Frame:
        """Create a form with a text box; returns the option bar above it."""
        frame = ttk.Frame(self._right)
        bar = ttk.Frame(frame)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(frame, text=label, style="Subtle.TLabel").pack(anchor="w")
        box = tk.Text(frame, wrap="none" if kind == "table" else "word", height=14, undo=True)
        box.pack(fill="both", expand=True)
        box.bind("<KeyRelease>", self._live)
        self._texts[kind], self._forms[kind] = box, frame
        return bar

    def _build_heading_form(self) -> None:
        frame = ttk.Frame(self._right)
        self._forms["heading"] = frame
        ttk.Label(frame, text="Level").grid(row=0, column=0, sticky="w", pady=4)
        spin = ttk.Spinbox(frame, from_=1, to=4, width=4, textvariable=self._level, command=self._live)
        spin.grid(row=0, column=1, sticky="w")
        spin.bind("<KeyRelease>", self._live)
        ttk.Label(frame, text="Text").grid(row=1, column=0, sticky="w", pady=4, padx=(0, PAD))
        entry = ttk.Entry(frame, textvariable=self._heading, width=60)
        entry.grid(row=1, column=1, sticky="w")
        entry.bind("<KeyRelease>", self._live)

    def _build_paragraph_form(self) -> None:
        bar = self._text_form("paragraph", "Paragraph text")
        ttk.Label(bar, text="Direction").pack(side="left")
        combo = ttk.Combobox(bar, textvariable=self._direction, values=DIRECTIONS,
                             state="readonly", width=6)
        combo.pack(side="left", padx=PAD // 2)
        combo.bind("<<ComboboxSelected>>", self._live)

    def _build_list_form(self) -> None:
        bar = self._text_form("list", "One item per line (leading '-', '*' or '1.' is removed)")
        ttk.Checkbutton(bar, text="Numbered list", variable=self._ordered,
                        command=self._live).pack(side="left")

    def _build_table_form(self) -> None:
        bar = self._text_form("table", "First line is the header; one row per line; "
                                       "separate cells with ' | ' (use \\| for a literal pipe)")
        ttk.Label(bar, text="Caption").pack(side="left")
        entry = ttk.Entry(bar, textvariable=self._caption, width=40)
        entry.pack(side="left", padx=PAD // 2)
        entry.bind("<KeyRelease>", self._live)

    # --- form <-> model ---
    def _show(self, kind: str | None) -> None:
        for form in self._forms.values():
            form.pack_forget()
        self._hint.pack_forget()
        if kind is None:
            self._hint.pack(anchor="nw")
        else:
            self._forms[kind].pack(fill="both", expand=True)

    def _body(self, kind: str) -> str:
        return self._texts[kind].get("1.0", "end-1c")

    def _set_body(self, kind: str, text: str) -> None:
        box = self._texts[kind]
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.edit_reset()

    def _level_value(self) -> int:
        try:
            return min(max(int(self._level.get()), 1), 4)
        except ValueError:
            return 2

    def _load(self, index: int) -> None:
        block = self._vm.blocks[index]
        kind = kind_of(block)
        self._show(kind)
        if isinstance(block, Heading):
            self._level.set(str(block.level))
            self._heading.set(block.text)
        elif isinstance(block, Paragraph):
            self._direction.set(block.direction)
            self._set_body("paragraph", block.text)
        elif isinstance(block, ListBlock):
            self._ordered.set(block.ordered)
            self._set_body("list", block_to_text(block))
        else:
            self._caption.set(block.caption)
            self._set_body("table", block_to_text(block))

    def _commit(self) -> None:
        """Write the visible form back into the view model."""
        i = self._index
        if i is None or not 0 <= i < len(self._vm.blocks):
            return
        kind = kind_of(self._vm.blocks[i])
        if kind == "heading":
            new = Heading(" ".join(self._heading.get().split()), self._level_value())
        elif kind == "paragraph":
            new = text_to_block("paragraph", self._body("paragraph"),
                                Paragraph("", self._direction.get()))  # type: ignore[arg-type]
        elif kind == "list":
            new = text_to_block("list", self._body("list"), ListBlock((), self._ordered.get()))
        else:
            new = text_to_block("table", self._body("table"), Table((), (), self._caption.get().strip()))
        if new != self._vm.blocks[i]:
            self._vm.replace(i, new)
            self._update_label(i)

    def _live(self, _event: Any = None) -> None:
        self._commit()
        self._changed()

    # --- list handling ---
    def _refresh(self) -> None:
        self._list.delete(0, "end")
        for block in self._vm.blocks:
            self._list.insert("end", block_summary(block))

    def _update_label(self, i: int) -> None:
        selected = self._list.curselection()
        self._list.delete(i)
        self._list.insert(i, block_summary(self._vm.blocks[i]))
        for s in selected:
            self._list.selection_set(s)

    def _select(self, i: int) -> None:
        self._list.selection_clear(0, "end")
        self._list.selection_set(i)
        self._list.see(i)
        self._index = i
        self._load(i)

    def _on_select(self, _event: Any = None) -> None:
        sel = self._list.curselection()
        if not sel or sel[0] == self._index:
            return
        self._commit()                      # save the block we are leaving
        self._index = sel[0]
        self._load(sel[0])

    # --- operations ---
    def _add(self, kind: str) -> None:
        self._commit()
        i = self._vm.add(kind, self._index)
        self._refresh()
        self._select(i)
        self._changed()

    def _remove(self) -> None:
        i = self._index
        if i is None:
            return
        self._vm.remove(i)
        self._index = None
        self._refresh()
        if self._vm.blocks:
            self._select(min(i, len(self._vm.blocks) - 1))
        else:
            self._show(None)
        self._changed()

    def _move(self, delta: int) -> None:
        if self._index is None:
            return
        self._commit()
        new = self._vm.move(self._index, delta)
        self._refresh()
        self._select(new)
        self._changed()

    def _on_convert(self, _event: Any = None) -> None:
        kind = _BY_LABEL.get(self._convert.get())
        self._convert.set("")
        if kind is None or self._index is None:
            return
        self._commit()
        self._vm.convert(self._index, kind)
        self._refresh()
        self._select(self._index)
        self._changed()