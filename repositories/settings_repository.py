"""Settings persistence (JSON, atomic writes) and secret storage (keyring)."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from config.constants import KEYRING_SERVICE, SETTINGS_FILE_NAME
from config.settings import AppSettings
from core.exceptions import SecretStorageUnavailableError, SettingsStorageError, SettingsValidationError

log = logging.getLogger(__name__)


class SettingsRepository:
    def __init__(self, config_dir: Path) -> None:
        self._path = config_dir / SETTINGS_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        """Return saved settings, or defaults if missing/corrupt (corrupt file kept as .bak)."""
        if not self._path.is_file():
            return AppSettings()
        try:
            return AppSettings.from_dict(json.loads(self._path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError, AttributeError, SettingsValidationError) as exc:
            log.warning("Settings invalid, using defaults: %s", exc)
            try:
                os.replace(self._path, self._path.with_suffix(".json.bak"))
            except OSError:
                pass
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        settings.validate()
        tmp = ""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(settings.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)
        except OSError as exc:
            if tmp:
                Path(tmp).unlink(missing_ok=True)
            raise SettingsStorageError(f"Could not save settings: {exc}",
                                       hint="Check folder permissions and free disk space.") from exc


class SecretStore:
    """API keys via keyring; never plaintext. Falls back to a session-only cache."""

    def __init__(self, backend: Any = None) -> None:
        self._backend = backend
        self._session: dict[str, str] = {}

    def _kr(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            import keyring
        except ImportError as exc:
            raise SecretStorageUnavailableError("The 'keyring' package is not installed.",
                                                hint="Run: pip install keyring") from exc
        return keyring

    def set(self, name: str, value: str, *, session_only: bool = False) -> bool:
        """Store a secret. True = persisted securely, False = session-only."""
        if not session_only:
            try:
                self._kr().set_password(KEYRING_SERVICE, name, value)
                self._session.pop(name, None)
                return True
            except Exception as exc:  # noqa: BLE001 - backend errors vary
                log.warning("Secure storage unavailable (%s); using session-only key", type(exc).__name__)
        self._session[name] = value
        return False

    def get(self, name: str) -> str | None:
        if name in self._session:
            return self._session[name]
        try:
            return self._kr().get_password(KEYRING_SERVICE, name)
        except Exception:  # noqa: BLE001
            return None

    def delete(self, name: str) -> None:
        self._session.pop(name, None)
        try:
            self._kr().delete_password(KEYRING_SERVICE, name)
        except Exception:  # noqa: BLE001
            pass
