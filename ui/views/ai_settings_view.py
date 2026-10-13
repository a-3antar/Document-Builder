"""AI Settings: provider, model discovery, Gemini key, connection and model tests."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from config.constants import GEMINI_KEY_URL, GEMINI_SECRET_NAME, OLLAMA_INSTALL_URL, ProviderId
from config.settings import AppSettings
from core.exceptions import DocumentBuilderError
from core.interfaces import ModelInfo
from services.app_services import AppServices
from services.task_service import EventKind, TaskEvent
from ui.theme import PAD
from ui.views.base_view import BaseView, error_text

_NOTES = {
    ProviderId.OLLAMA.value: ("Local processing: nothing leaves this computer. "
                              f"Requires Ollama ({OLLAMA_INSTALL_URL}) and an installed model."),
    ProviderId.GEMINI.value: ("Cloud processing: your text and images are sent to Google Gemini. "
                              f"Get an API key at {GEMINI_KEY_URL}."),
}
_SOURCES = {"session": "this session only", "keyring": "Windows secure storage",
            "environment": "environment variable", None: "not configured"}


class AiSettingsView(BaseView):
    title = "AI Settings"
    subtitle = "Choose the AI provider and model used to generate content."

    def __init__(self, parent: Any, settings: AppSettings, services: AppServices,
                 on_save: Callable[[AppSettings], None]) -> None:
        super().__init__(parent)
        self._settings, self._svc, self._on_save = settings, services, on_save
        self._models: list[ModelInfo] = []
        self._vars = {
            "provider": tk.StringVar(value=settings.provider),
            "model": tk.StringVar(value=settings.models.get(settings.provider, "")),
            "timeout": tk.StringVar(value=str(settings.timeout_seconds)),
            "key": tk.StringVar(),
        }
        self._note, self._model_info = tk.StringVar(), tk.StringVar()
        self._key_status, self._status = tk.StringVar(), tk.StringVar()

        form = ttk.Frame(self)
        form.pack(anchor="w", fill="x")
        ttk.Label(form, text="Provider").grid(row=0, column=0, sticky="w", pady=4, padx=(0, PAD))
        provider = ttk.Combobox(form, textvariable=self._vars["provider"], state="readonly",
                                values=[p.value for p in ProviderId], width=20)
        provider.grid(row=0, column=1, sticky="w")
        provider.bind("<<ComboboxSelected>>", lambda _e: self._provider_changed())
        ttk.Label(form, textvariable=self._note, style="Subtle.TLabel", wraplength=620,
                  justify="left").grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, PAD))

        ttk.Label(form, text="Model").grid(row=2, column=0, sticky="w", pady=4)
        row = ttk.Frame(form)
        row.grid(row=2, column=1, sticky="w")
        self._model_box = ttk.Combobox(row, textvariable=self._vars["model"], width=36)
        self._model_box.pack(side="left")
        self._model_box.bind("<<ComboboxSelected>>", lambda _e: self._model_changed())
        ttk.Button(row, text="Refresh models", command=self._refresh).pack(side="left", padx=PAD // 2)
        ttk.Label(form, textvariable=self._model_info, style="Subtle.TLabel").grid(
            row=3, column=1, sticky="w")

        ttk.Label(form, text="Timeout (seconds)").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Spinbox(form, from_=5, to=3600, textvariable=self._vars["timeout"], width=8).grid(
            row=4, column=1, sticky="w")

        self._key_frame = ttk.Frame(form)
        self._key_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(PAD, 0))
        ttk.Label(self._key_frame, text="Gemini API key").grid(row=0, column=0, sticky="w", padx=(0, PAD))
        ttk.Entry(self._key_frame, textvariable=self._vars["key"], show="*", width=38).grid(row=0, column=1)
        ttk.Button(self._key_frame, text="Save key", command=self._save_key).grid(
            row=0, column=2, padx=PAD // 2)
        ttk.Label(self._key_frame, textvariable=self._key_status, style="Subtle.TLabel").grid(
            row=1, column=1, sticky="w")

        buttons = ttk.Frame(self)
        buttons.pack(anchor="w", pady=PAD)
        ttk.Button(buttons, text="Check connection", command=self._check).pack(side="left")
        ttk.Button(buttons, text="Test model", command=self._test_model).pack(side="left", padx=PAD // 2)
        ttk.Button(buttons, text="Save settings", command=self._save).pack(side="left")
        ttk.Label(self, textvariable=self._status, wraplength=700, justify="left").pack(anchor="w")
        self._provider_changed(keep_model=True)

    # --- helpers ---
    @property
    def _provider(self) -> str:
        return self._vars["provider"].get()

    def _run(self, work: Callable[..., Any], handler: Callable[[TaskEvent], None], message: str) -> None:
        self._status.set(message)
        self._svc.tasks.submit(work, on_event=handler)

    def _failed(self, event: TaskEvent) -> bool:
        """Show error/cancel events; True when the event was not a success."""
        if event.kind is EventKind.ERROR:
            self._status.set(error_text(event.payload))
        elif event.kind is EventKind.CANCELLED:
            self._status.set("Cancelled.")
        return event.kind is not EventKind.RESULT

    def on_show(self) -> None:
        self._update_key_status()

    def _update_key_status(self) -> None:
        self._key_status.set(f"Key: {_SOURCES[self._svc.secrets.source(GEMINI_SECRET_NAME)]}")

    # --- provider/model ---
    def _provider_changed(self, keep_model: bool = False) -> None:
        provider = self._provider
        self._note.set(_NOTES[provider])
        self._models = []
        self._model_box.configure(values=[])
        if not keep_model:
            self._vars["model"].set(self._settings.models.get(provider, ""))
        self._model_info.set("")
        self._status.set("")
        if provider == ProviderId.GEMINI.value:
            self._key_frame.grid()
            self._update_key_status()
        else:
            self._key_frame.grid_remove()

    def _model_changed(self) -> None:
        info = next((m for m in self._models if m.name == self._vars["model"].get()), None)
        if info is None:
            self._model_info.set("")
        elif info.supports_vision is None:
            self._model_info.set("Image input: unknown (use Test model to check)")
        else:
            self._model_info.set("Image input: " + ("supported" if info.supports_vision else "not supported"))

    def _refresh(self) -> None:
        provider = self._provider
        self._run(lambda ctx: self._svc.models.refresh(provider), self._on_models, "Refreshing models...")

    def _on_models(self, event: TaskEvent) -> None:
        if self._failed(event):
            return
        self._models = event.payload
        self._model_box.configure(values=[m.name for m in self._models])
        if not self._models:
            hint = ("Install one with: ollama pull <model>" if self._provider == ProviderId.OLLAMA.value
                    else "No models support content generation for this key.")
            self._status.set(f"No models found. {hint}")
        else:
            self._status.set(f"{len(self._models)} models found. Select one and save.")
        self._model_changed()

    def _check(self) -> None:
        provider = self._provider
        self._run(lambda ctx: self._svc.providers.create(provider).check_connection(),
                  self._on_checked, "Checking connection...")

    def _on_checked(self, event: TaskEvent) -> None:
        if not self._failed(event):
            self._status.set(("OK: " if event.payload[0] else "Problem: ") + event.payload[1])

    def _test_model(self) -> None:
        model = self._vars["model"].get().strip()
        if not model:
            messagebox.showinfo("Test model", "Select a model first.")
            return
        if not messagebox.askokcancel(
                "Test model", "This sends a tiny request to the model and may use local resources "
                              "or cloud quota. Continue?"):
            return
        provider = self._provider
        self._run(lambda ctx: self._svc.providers.create(provider).generate_text(
            "Reply with the single word OK.", model), self._on_tested, "Testing model...")

    def _on_tested(self, event: TaskEvent) -> None:
        if not self._failed(event):
            self._status.set(f"Model responded: {str(event.payload).strip()[:80]!r}")

    # --- persistence ---
    def _save_key(self) -> None:
        key = self._vars["key"].get().strip()
        if not key:
            messagebox.showinfo("API key", "Enter an API key first.")
            return
        secure = self._svc.secrets.set(GEMINI_SECRET_NAME, key)
        self._vars["key"].set("")
        self._update_key_status()
        self._status.set("Key saved in Windows secure storage." if secure else
                         "Secure storage is unavailable; the key is kept for this session only.")

    def _save(self) -> None:
        try:
            timeout = int(self._vars["timeout"].get())
        except ValueError:
            messagebox.showerror("Invalid settings", "Timeout must be a whole number.")
            return
        data = self._settings.to_dict()
        models = dict(data["models"])
        if self._vars["model"].get().strip():
            models[self._provider] = self._vars["model"].get().strip()
        try:
            updated = AppSettings.from_dict({**data, "provider": self._provider,
                                             "models": models, "timeout_seconds": timeout})
        except DocumentBuilderError as exc:
            messagebox.showerror("Invalid settings", error_text(exc))
            return
        self._on_save(updated)

    def settings_changed(self, settings: AppSettings) -> None:
        self._settings = settings
