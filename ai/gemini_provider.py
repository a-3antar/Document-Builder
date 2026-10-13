"""Gemini provider via the google-genai SDK."""
from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Callable

from config.constants import DEFAULT_TIMEOUT_SECONDS, GEMINI_KEY_URL, ProviderId
from core.exceptions import (DependencyMissingError, DocumentBuilderError,
                             ModelNotAvailableError, ProviderAuthError, ProviderError,
                             ProviderQuotaError, ProviderTimeoutError, ProviderUnavailableError)
from core.interfaces import AiProvider, ModelInfo

log = logging.getLogger(__name__)

ClientFactory = Callable[[str, float], Any]


def _default_client(api_key: str, timeout: float) -> Any:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise DependencyMissingError("The 'google-genai' package is not installed.",
                                     hint="Run: pip install google-genai") from exc
    return genai.Client(api_key=api_key,
                        http_options=types.HttpOptions(timeout=int(timeout * 1000)))


def translate_error(exc: Exception) -> DocumentBuilderError:
    """Map SDK/transport exceptions to actionable app errors."""
    if isinstance(exc, DocumentBuilderError):
        return exc
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    name = type(exc).__name__
    msg = str(getattr(exc, "message", None) or exc)[:200]
    if code in (401, 403) or (code == 400 and "api key" in msg.lower()):
        return ProviderAuthError("Gemini rejected the API key or permissions.",
                                 hint=f"Check your key at {GEMINI_KEY_URL} and re-enter it.")
    if code == 429:
        return ProviderQuotaError("Gemini quota or rate limit reached.",
                                  hint="Wait and retry, or check your quota and billing.")
    if code == 404:
        return ModelNotAvailableError("The selected Gemini model was not found.",
                                      hint="Refresh the model list and pick another model.")
    if "Timeout" in name or isinstance(exc, TimeoutError):
        return ProviderTimeoutError("Gemini did not respond in time.",
                                    hint="Increase the timeout in AI Settings.")
    if "Connect" in name or "Network" in name or isinstance(exc, OSError):
        return ProviderUnavailableError("Cannot reach Gemini.", hint="Check your internet connection.")
    log.warning("Unmapped Gemini error: %s", name)
    return ProviderError(f"Gemini request failed: {msg}")


class GeminiProvider(AiProvider):
    id = ProviderId.GEMINI.value

    def __init__(self, key_provider: Callable[[], str | None],
                 timeout: float = DEFAULT_TIMEOUT_SECONDS,
                 client_factory: ClientFactory = _default_client) -> None:
        self._key = key_provider
        self._timeout = timeout
        self._factory = client_factory

    def _client(self) -> Any:
        key = self._key()
        if not key:
            raise ProviderAuthError("No Gemini API key is configured.",
                                    hint=f"Get a key at {GEMINI_KEY_URL} and enter it in AI Settings.")
        return self._factory(key, self._timeout)

    def check_connection(self) -> tuple[bool, str]:
        try:
            count = len(self.list_models())
        except DocumentBuilderError as exc:
            return False, f"{exc} {exc.hint}".strip()
        return True, f"Connected to Gemini ({count} models available)."

    def list_models(self) -> list[ModelInfo]:
        """Models that support generateContent; vision support is unknown (None)."""
        client = self._client()
        try:
            found = [m.name.removeprefix("models/") for m in client.models.list()
                     if "generateContent" in (getattr(m, "supported_actions", None) or [])]
        except Exception as exc:  # noqa: BLE001 - translated
            raise translate_error(exc) from exc
        return [ModelInfo(n, None) for n in sorted(found)]

    def generate_text(self, prompt: str, model: str, **options: Any) -> str:
        return self._generate([prompt], model, options)

    def analyze_image(self, image: Path, prompt: str, model: str, **options: Any) -> str:
        from google.genai import types  # only needed for image parts
        mime = mimetypes.guess_type(image.name)[0] or "image/png"
        part = types.Part.from_bytes(data=image.read_bytes(), mime_type=mime)
        return self._generate([part, prompt], model, options)

    def _generate(self, contents: list[Any], model: str, options: dict[str, Any]) -> str:
        client = self._client()
        config: dict[str, Any] = {}
        if options.get("json_mode"):
            config["response_mime_type"] = "application/json"
        if "temperature" in options:
            config["temperature"] = options["temperature"]
        try:
            resp = client.models.generate_content(model=model, contents=contents, config=config or None)
        except Exception as exc:  # noqa: BLE001 - translated
            raise translate_error(exc) from exc
        if not resp.text:
            raise ProviderError("Gemini returned no text (the response may have been blocked).")
        return resp.text
