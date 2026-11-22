import os
import tempfile
import unittest
from pathlib import Path

from cryptography.fernet import Fernet

import database
from platform_ai import (
    init_platform_ai_db,
    get_platform_ai_settings,
    get_runtime_ai_config,
    save_platform_ai_settings,
)
from platform_team import (
    init_platform_team_db,
    get_platform_employee_profile,
    save_platform_employee_profile,
)


class PlatformControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp_dir.name) / "platform-controls.sqlite3")
        os.environ["PLATFORM_SECRETS_KEY"] = Fernet.generate_key().decode("ascii")
        os.environ.pop("GEMINI_API_KEY", None)
        init_platform_ai_db()
        init_platform_team_db()

    def tearDown(self):
        os.environ.pop("PLATFORM_SECRETS_KEY", None)
        self.temp_dir.cleanup()

    def test_provider_secret_is_encrypted_and_never_returned(self):
        secret = "test-gemini-secret-value"
        saved = save_platform_ai_settings(
            "gemini", "gemini-2.5-flash", "", 45, secret, False, "owner",
            "ollama", "qwen2.5:3b", "http://127.0.0.1:11434"
        )
        self.assertTrue(saved["has_api_key"])
        self.assertNotIn("api_key", saved)
        with database._connect() as conn:
            row = conn.execute(
                "SELECT encrypted_api_key FROM platform_ai_settings WHERE id=1"
            ).fetchone()
        self.assertNotEqual(row["encrypted_api_key"], secret)
        runtime = get_runtime_ai_config()
        self.assertEqual(runtime["api_key"], secret)
        self.assertEqual(runtime["fallback_provider"], "ollama")
        self.assertEqual(runtime["fallback_model"], "qwen2.5:3b")

    def test_provider_secret_can_be_cleared(self):
        save_platform_ai_settings(
            "gemini", "gemini-2.5-flash", "", 45, "test-gemini-secret-value", False, "owner"
        )
        cleared = save_platform_ai_settings(
            "demo", "demo", "", 45, None, True, "owner"
        )
        self.assertFalse(cleared["has_api_key"])
        self.assertEqual(get_runtime_ai_config()["api_key"], "")

    def test_employee_role_and_instruction_overrides_are_persistent(self):
        result = save_platform_employee_profile(
            "ابراهيم", "مدير عام المنصة", "الإدارة التنفيذية",
            "التعليمات التجريبية", "owner"
        )
        self.assertEqual(result["role"], "مدير عام المنصة")
        self.assertEqual(result["additional_instructions"], "التعليمات التجريبية")
        saved = get_platform_employee_profile("ابراهيم")
        self.assertEqual(saved["department"], "الإدارة التنفيذية")
        self.assertEqual(saved["additional_instructions"], "التعليمات التجريبية")

    def test_unknown_employee_cannot_be_created_through_profile_editor(self):
        self.assertIsNone(
            save_platform_employee_profile("موظف غير موجود", "دور", "قسم", "", "owner")
        )


if __name__ == "__main__":
    unittest.main()
