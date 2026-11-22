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
from platform_settings import init_platform_settings_db, get_platform_settings, save_platform_settings
from platform_branding import init_platform_branding_db, get_site_settings, save_site_settings
from platform_experiences import (init_platform_experiences_db, get_experience, save_experience_draft, publish_experience, list_experience_revisions)


class PlatformControlsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp_dir.name) / "platform-controls.sqlite3")
        os.environ["PLATFORM_SECRETS_KEY"] = Fernet.generate_key().decode("ascii")
        os.environ.pop("GEMINI_API_KEY", None)
        init_platform_ai_db()
        init_platform_team_db()
        init_platform_settings_db()
        init_platform_branding_db()
        init_platform_experiences_db()

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

    def test_platform_settings_control_customer_creation_and_public_site(self):
        updated = save_platform_settings({
            "public_site_enabled": False,
            "allow_customer_creation": False,
            "site_notice_enabled": True,
            "site_notice_text": "تحديثات مجدولة"
        }, "owner")
        self.assertFalse(updated["public_site_enabled"])
        self.assertFalse(updated["allow_customer_creation"])
        self.assertTrue(updated["site_notice_enabled"])
        self.assertEqual(get_platform_settings()["site_notice_text"], "تحديثات مجدولة")

    def test_website_branding_settings_are_persisted_and_validated(self):
        updated = save_site_settings({
            "site_name": "Office Brains Test",
            "brand_accent": "#123456",
            "primary_cta_url": "frontend/"
        }, "owner")
        self.assertEqual(updated["site_name"], "Office Brains Test")
        self.assertEqual(get_site_settings()["brand_accent"], "#123456")
        with self.assertRaises(ValueError):
            save_site_settings({"primary_cta_url": "javascript:alert(1)"}, "owner")

    def test_website_experience_draft_is_not_published_until_explicit_publish(self):
        initial = get_experience("platform_site")
        self.assertIsNone(initial["published"])
        draft = save_experience_draft(
            "platform_site", None,
            {"site_name": "مسودة غير منشورة", "headline": "عنوان تجريبي"},
            "owner"
        )
        self.assertEqual(draft["draft"]["site_name"], "مسودة غير منشورة")
        self.assertIsNone(draft["published"])
        published = publish_experience("platform_site", None, "owner")
        self.assertEqual(published["published"]["site_name"], "مسودة غير منشورة")
        self.assertEqual(published["version"], 1)
        self.assertEqual(len(list_experience_revisions("platform_site")), 1)

    def test_unknown_employee_cannot_be_created_through_profile_editor(self):
        self.assertIsNone(
            save_platform_employee_profile("موظف غير موجود", "دور", "قسم", "", "owner")
        )


if __name__ == "__main__":
    unittest.main()
