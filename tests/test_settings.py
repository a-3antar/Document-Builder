import tempfile
import unittest
from pathlib import Path

from config.settings import AppSettings
from core.exceptions import SettingsValidationError
from repositories.settings_repository import SecretStore, SettingsRepository


class FakeKeyring:
    def __init__(self, fail=False):
        self.data, self.fail = {}, fail

    def set_password(self, s, n, v):
        if self.fail:
            raise RuntimeError("no backend")
        self.data[(s, n)] = v

    def get_password(self, s, n):
        if self.fail:
            raise RuntimeError("no backend")
        return self.data.get((s, n))

    def delete_password(self, s, n):
        self.data.pop((s, n), None)


class SettingsTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            repo = SettingsRepository(Path(d))
            s = AppSettings(output_dir="C:/out", ocr_languages="eng")
            repo.save(s)
            self.assertEqual(repo.load(), s)

    def test_invalid_values_rejected(self):
        with self.assertRaises(SettingsValidationError):
            AppSettings(provider="nope").validate()
        with self.assertRaises(SettingsValidationError):
            AppSettings(timeout_seconds=1).validate()

    def test_corrupt_file_falls_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            repo = SettingsRepository(Path(d))
            repo.path.write_text("{not json", encoding="utf-8")
            self.assertEqual(repo.load(), AppSettings())
            self.assertTrue(repo.path.with_suffix(".json.bak").exists())

    def test_unknown_keys_ignored(self):
        self.assertEqual(AppSettings.from_dict({"future_key": 1}), AppSettings())

    def test_no_secrets_in_settings_file(self):
        with tempfile.TemporaryDirectory() as d:
            repo = SettingsRepository(Path(d))
            repo.save(AppSettings())
            self.assertNotIn("api_key", repo.path.read_text().lower())


class SecretStoreTests(unittest.TestCase):
    def test_secure_store(self):
        store = SecretStore(FakeKeyring())
        self.assertTrue(store.set("gemini", "k"))
        self.assertEqual(store.get("gemini"), "k")

    def test_session_fallback_never_persists(self):
        kr = FakeKeyring(fail=True)
        store = SecretStore(kr)
        self.assertFalse(store.set("gemini", "k"))
        self.assertEqual(store.get("gemini"), "k")
        self.assertEqual(kr.data, {})


if __name__ == "__main__":
    unittest.main()
