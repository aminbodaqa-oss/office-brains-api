import tempfile
import unittest
from pathlib import Path

import database
from platform_experiences import (
    get_experience, init_platform_experiences_db, list_experience_revisions,
    publish_experience, restore_experience_revision, save_experience_draft,
)


class PlatformExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp_dir.name) / "experiences.sqlite3")
        init_platform_experiences_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_draft_is_not_public_until_published(self):
        config = {"site_name": "Office Brains Test", "theme": {"accent": "#123456"}}
        saved = save_experience_draft("platform_site", None, config, "owner")
        self.assertEqual(saved["status"], "draft")
        self.assertIsNone(saved["published"])
        published = publish_experience("platform_site", None, "owner")
        self.assertEqual(published["version"], 1)
        self.assertEqual(published["published"]["site_name"], "Office Brains Test")
        self.assertEqual(published["published"]["theme"]["accent"], "#123456")

    def test_revision_restore_creates_a_new_draft(self):
        save_experience_draft("office_login", None, {"login_title": "Welcome"}, "owner")
        publish_experience("office_login", None, "owner")
        save_experience_draft("office_login", None, {"login_title": "Changed"}, "owner")
        restored = restore_experience_revision("office_login", None, 1, "owner")
        self.assertEqual(restored["draft"]["login_title"], "Welcome")
        self.assertEqual(restored["status"], "draft")
        self.assertEqual([x["version"] for x in list_experience_revisions("office_login")], [1])

    def test_customer_workspace_requires_scope_and_is_isolated(self):
        with self.assertRaises(ValueError):
            save_experience_draft("customer_workspace", None, {}, "owner")
        save_experience_draft("customer_workspace", "workspace-a", {"site_name": "A"}, "owner")
        save_experience_draft("customer_workspace", "workspace-b", {"site_name": "B"}, "owner")
        self.assertEqual(get_experience("customer_workspace", "workspace-a")["draft"]["site_name"], "A")
        self.assertEqual(get_experience("customer_workspace", "workspace-b")["draft"]["site_name"], "B")

    def test_invalid_colors_and_external_http_navigation_are_rejected(self):
        with self.assertRaises(ValueError):
            save_experience_draft("platform_site", None, {"theme": {"accent": "red"}}, "owner")
        with self.assertRaises(ValueError):
            save_experience_draft("platform_site", None, {"navigation": [{"label": "Bad", "url": "http://example.com"}]}, "owner")


if __name__ == "__main__":
    unittest.main()
