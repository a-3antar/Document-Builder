import unittest

from ai.gemini_provider import GeminiProvider, translate_error
from ai.model_registry import ModelRegistry, ProviderRegistry
from ai.ollama_provider import OllamaProvider
from ai.prompts import build_generation_prompt
from config.constants import ContentKind
from core.exceptions import (ModelNotAvailableError, ProviderAuthError, ProviderQuotaError,
                             ProviderUnavailableError)
from core.interfaces import AiProvider, ModelInfo
from core.schema_validator import SchemaValidator
from document.template_registry import Template
from services.ai_service import AiService

try:
    import jsonschema  # noqa: F401
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class OllamaTests(unittest.TestCase):
    def _provider(self, routes):
        calls = []

        def http(method, url, body, timeout):
            calls.append((url, body))
            handler = routes[url.rsplit("/api/", 1)[1]]
            if isinstance(handler, Exception):
                raise handler
            return handler(body) if callable(handler) else handler
        return OllamaProvider(http=http), calls

    def test_check_connection_ok_and_down(self):
        p, _ = self._provider({"version": {"version": "0.5"}})
        self.assertEqual(p.check_connection(), (True, "Ollama 0.5 is running."))
        p, _ = self._provider({"version": ProviderUnavailableError("down", hint="start it")})
        ok, msg = p.check_connection()
        self.assertFalse(ok)
        self.assertIn("start it", msg)

    def test_list_models_vision_tristate(self):
        def show(body):
            if body["model"] == "llava":
                return {"capabilities": ["completion", "vision"]}
            if body["model"] == "qwen":
                return {"capabilities": ["completion"]}
            return {}
        p, _ = self._provider({"tags": {"models": [{"name": "qwen"}, {"name": "llava"}, {"name": "x"}]},
                               "show": show})
        got = {m.name: m.supports_vision for m in p.list_models()}
        self.assertEqual(got, {"llava": True, "qwen": False, "x": None})

    def test_generate_json_mode(self):
        p, calls = self._provider({"generate": {"response": "{}"}})
        self.assertEqual(p.generate_text("hi", "m", json_mode=True), "{}")
        self.assertEqual(calls[0][1]["format"], "json")
        self.assertFalse(calls[0][1]["stream"])


class _Err(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code, self.message = code, message


class _Model:
    def __init__(self, name, actions):
        self.name, self.supported_actions = name, actions


class _FakeClient:
    def __init__(self, models=(), text="ok", error=None):
        self._models, self._text, self._error = models, text, error
        self.models = self

    def list(self):
        if self._error:
            raise self._error
        return iter(self._models)

    def generate_content(self, model, contents, config):
        if self._error:
            raise self._error
        return type("R", (), {"text": self._text})()


class GeminiTests(unittest.TestCase):
    def test_missing_key(self):
        p = GeminiProvider(lambda: None, client_factory=lambda k, t: _FakeClient())
        with self.assertRaises(ProviderAuthError):
            p.list_models()
        self.assertFalse(p.check_connection()[0])

    def test_list_filters_generate_content(self):
        client = _FakeClient([_Model("models/b", ["generateContent"]), _Model("models/emb", ["embedContent"]),
                              _Model("models/a", ["generateContent"])])
        p = GeminiProvider(lambda: "k", client_factory=lambda k, t: client)
        self.assertEqual([m.name for m in p.list_models()], ["a", "b"])

    def test_error_mapping(self):
        self.assertIsInstance(translate_error(_Err(429)), ProviderQuotaError)
        self.assertIsInstance(translate_error(_Err(403)), ProviderAuthError)
        self.assertIsInstance(translate_error(_Err(400, "API key not valid")), ProviderAuthError)
        self.assertIsInstance(translate_error(_Err(404)), ModelNotAvailableError)

    def test_generate_and_error(self):
        p = GeminiProvider(lambda: "k", client_factory=lambda k, t: _FakeClient(text="hello"))
        self.assertEqual(p.generate_text("x", "m", json_mode=True), "hello")
        bad = GeminiProvider(lambda: "k", client_factory=lambda k, t: _FakeClient(error=_Err(429)))
        with self.assertRaises(ProviderQuotaError):
            bad.generate_text("x", "m")


class _Scripted(AiProvider):
    id = "fake"

    def __init__(self, responses, models=()):
        self.responses, self.prompts, self._models = list(responses), [], list(models)

    def check_connection(self):
        return True, "ok"

    def list_models(self):
        return self._models

    def generate_text(self, prompt, model, **options):
        self.prompts.append(prompt)
        return self.responses.pop(0)


GOOD = '{"schema_version":"1.0","metadata":{"title":"T"},"blocks":[{"type":"paragraph","text":"hi"}]}'
BAD = '{"schema_version":"1.0","metadata":{"title":"T"},"blocks":[{"type":"heading"}]}'
TEMPLATE = Template("t", "T", "d", ContentKind.DOCUMENT, "document_content.schema.json", {}, {}, {})


class ModelRegistryTests(unittest.TestCase):
    def test_require(self):
        prov = _Scripted([], [ModelInfo("a", False), ModelInfo("b", None)])
        reg = ProviderRegistry()
        reg.register("fake", lambda: prov)
        models = ModelRegistry(reg)
        self.assertEqual(models.require("fake", "b", vision=True).name, "b")
        with self.assertRaises(ModelNotAvailableError):
            models.require("fake", "a", vision=True)
        with self.assertRaises(ModelNotAvailableError):
            models.require("fake", "zzz")


@unittest.skipUnless(HAS_JSONSCHEMA, "jsonschema not installed")
class AiServiceTests(unittest.TestCase):
    def _run(self, responses):
        prov = _Scripted(responses)
        reg = ProviderRegistry()
        reg.register("fake", lambda: prov)
        result = AiService(reg, SchemaValidator()).generate_structured("fake", "m", "make doc", TEMPLATE)
        return result, prov

    def test_valid_first_try(self):
        result, prov = self._run([GOOD])
        self.assertTrue(result.ok)
        self.assertEqual(len(prov.prompts), 1)

    def test_repair_succeeds_once(self):
        result, prov = self._run([BAD, GOOD])
        self.assertTrue(result.ok)
        self.assertEqual(result.raw, BAD)
        self.assertEqual(len(prov.prompts), 2)

    def test_still_invalid_preserves_raw_and_stops(self):
        result, prov = self._run([BAD, "not json"])
        self.assertFalse(result.ok)
        self.assertIsNone(result.content)
        self.assertEqual(result.raw, BAD)
        self.assertTrue(result.issues)
        self.assertEqual(len(prov.prompts), 2)  # at most one retry

    def test_prompt_contains_schema(self):
        self.assertIn("DocumentContent", build_generation_prompt("x", SchemaValidator().schema(TEMPLATE.schema)))


if __name__ == "__main__":
    unittest.main()
