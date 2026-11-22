import os
import tempfile
import unittest
from pathlib import Path

import database
from cryptography.fernet import Fernet
from platform_tenants import init_platform_tenants_db
from platform_billing import init_platform_billing_db
from platform_ai import (
    init_platform_ai_db,
    get_platform_ai_settings,
    get_runtime_ai_config,
    save_platform_ai_settings,
)


class PlatformAISettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp_dir.name) / "ai-test.sqlite3")
        self.previous_key = os.environ.get("PLATFORM_SECRETS_KEY")
        os.environ["PLATFORM_SECRETS_KEY"] = Fernet.generate_key().decode()
        os.environ["BRAIN_PROVIDER"] = "demo"
        init_platform_tenants_db()
        init_platform_billing_db()
        init_platform_ai_db()

    def tearDown(self):
        if self.previous_key is None:
            os.environ.pop("PLATFORM_SECRETS_KEY", None)
        else:
            os.environ["PLATFORM_SECRETS_KEY"] = self.previous_key
        self.temp_dir.cleanup()

    def test_api_key_is_encrypted_and_never_returned_by_settings(self):
        secret = "test-api-key-123456789"
        settings = save_platform_ai_settings(
            "gemini", "gemini-test-model", "", 60, secret, False, "owner"
        )
        self.assertTrue(settings["has_api_key"])
        self.assertEqual(settings["key_source"], "database")
        self.assertNotIn("api_key", settings)
        self.assertEqual(get_runtime_ai_config()["api_key"], secret)
        with database._connect() as conn:
            stored = conn.execute(
                "SELECT encrypted_api_key FROM platform_ai_settings WHERE id=1"
            ).fetchone()["encrypted_api_key"]
        self.assertNotIn(secret, stored)

    def test_clear_api_key_removes_database_credential(self):
        save_platform_ai_settings(
            "gemini", "gemini-test-model", "", 60,
            "test-api-key-123456789", False, "owner"
        )
        settings = save_platform_ai_settings(
            "demo", "demo", "", 60, None, True, "owner"
        )
        self.assertFalse(settings["has_api_key"])
        self.assertEqual(get_runtime_ai_config()["api_key"], "")

    def test_ollama_requires_valid_http_endpoint(self):
        with self.assertRaises(ValueError):
            save_platform_ai_settings(
                "ollama", "qwen2.5:3b", "not-a-url", 60, None, False, "owner"
            )


if __name__ == "__main__":
    unittest.main()
