"""Ollama provider: local HTTP API, stdlib only."""
from __future__ import annotations

import base64
import json
import logging
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from config.constants import (DEFAULT_TIMEOUT_SECONDS, OLLAMA_DEFAULT_URL,
                              OLLAMA_INSTALL_URL, ProviderId)
from core.exceptions import (ModelNotAvailableError, ProviderError,
                             ProviderTimeoutError, ProviderUnavailableError)
from core.interfaces import AiProvider, ModelInfo

log = logging.getLogger(__name__)

# (method, url, json body, timeout) -> parsed JSON
HttpFn = Callable[[str, str, "dict[str, Any] | None", float], dict[str, Any]]

_PING_TIMEOUT = 5.0


def urllib_json(method: str, url: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
    """Default transport; translates transport failures into provider errors."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # must precede URLError
        if exc.code == 404:
            raise ModelNotAvailableError(
                "Ollama could not find the requested model.",
                hint="Install it with: ollama pull <model>") from exc
        raise ProviderError(f"Ollama returned HTTP {exc.code}.") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise ProviderTimeoutError("Ollama did not respond in time.",
                                   hint="Increase the timeout in AI Settings.") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise ProviderTimeoutError("Ollama did not respond in time.",
                                       hint="Increase the timeout in AI Settings.") from exc
        raise ProviderUnavailableError(
            "Ollama is not reachable.",
            hint=f"Install it from {OLLAMA_INSTALL_URL} or start the Ollama app, then refresh.") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError("Ollama returned an invalid response.") from exc


class OllamaProvider(AiProvider):
    id = ProviderId.OLLAMA.value

    def __init__(self, base_url: str = OLLAMA_DEFAULT_URL,
                 timeout: float = DEFAULT_TIMEOUT_SECONDS, http: HttpFn = urllib_json) -> None:
        self._url = base_url.rstrip("/")
        self._timeout = timeout
        self._http = http

    def check_connection(self) -> tuple[bool, str]:
        try:
            data = self._http("GET", f"{self._url}/api/version", None, _PING_TIMEOUT)
        except ProviderError as exc:
            return False, f"{exc} {exc.hint}".strip()
        return True, f"Ollama {data.get('version', '?')} is running."

    def list_models(self) -> list[ModelInfo]:
        """Installed models; vision support is read from metadata, else unknown."""
        data = self._http("GET", f"{self._url}/api/tags", None, self._timeout)
        names = [m["name"] for m in data.get("models", []) if "name" in m]
        return [ModelInfo(n, self._vision_from_metadata(n)) for n in sorted(names)]

    def _vision_from_metadata(self, name: str) -> bool | None:
        """Metadata lookup only (no inference). None when capabilities are not reported."""
        try:
            info = self._http("POST", f"{self._url}/api/show", {"model": name}, _PING_TIMEOUT)
        except ProviderError:
            return None
        caps = info.get("capabilities")
        return ("vision" in caps) if isinstance(caps, list) else None

    def generate_text(self, prompt: str, model: str, **options: Any) -> str:
        return self._generate({"prompt": prompt}, model, options)

    def analyze_image(self, image: Path, prompt: str, model: str, **options: Any) -> str:
        encoded = base64.b64encode(image.read_bytes()).decode("ascii")
        return self._generate({"prompt": prompt, "images": [encoded]}, model, options)

    def _generate(self, payload: dict[str, Any], model: str, options: dict[str, Any]) -> str:
        body: dict[str, Any] = {"model": model, "stream": False, **payload}
        if options.get("json_mode"):
            body["format"] = "json"
        if "temperature" in options:
            body["options"] = {"temperature": options["temperature"]}
        data = self._http("POST", f"{self._url}/api/generate", body, self._timeout)
        if "response" not in data:
            raise ProviderError("Ollama returned an unexpected response.")
        return str(data["response"])
