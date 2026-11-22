import tempfile
import unittest
from pathlib import Path

import database
from platform_tenants import init_platform_tenants_db, create_platform_customer
from platform_billing import (
    init_platform_billing_db,
    save_platform_plan,
    create_platform_subscription,
    update_platform_subscription,
    expire_due_platform_subscriptions,
)


class PlatformBillingTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = str(Path(self.temp_dir.name) / "billing-test.sqlite3")
        init_platform_tenants_db()
        init_platform_billing_db()
        self.customer = create_platform_customer(
            "شركة الاختبار", "مسؤول الاختبار", "billing-test@example.com",
            "01000000000", "starter", "owner"
        )
        save_platform_plan(
            "starter", "باقة البداية", "اختبار",
            9900, 99000, {"employees": 5}, True, "owner"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _new_subscription(self):
        return create_platform_subscription(
            self.customer["id"], "starter", "monthly", None, "", "owner"
        )

    def test_new_subscription_waits_for_manual_payment(self):
        sub = self._new_subscription()
        self.assertEqual(sub["status"], "pending_payment")
        self.assertEqual(sub["payment_status"], "unpaid")

    def test_confirmed_payment_activates_customer_and_workspace(self):
        sub = self._new_subscription()
        update_platform_subscription(sub["id"], "paid", None, None, "owner")
        with database._connect() as conn:
            customer = conn.execute(
                "SELECT status,plan_code FROM platform_customers WHERE id=?",
                (self.customer["id"],),
            ).fetchone()
            workspace = conn.execute(
                "SELECT status FROM platform_workspaces WHERE customer_id=?",
                (self.customer["id"],),
            ).fetchone()
        self.assertEqual(customer["status"], "active")
        self.assertEqual(customer["plan_code"], "starter")
        self.assertEqual(workspace["status"], "active")

    def test_cancelling_one_subscription_keeps_other_paid_subscription_active(self):
        first = self._new_subscription()
        second = self._new_subscription()
        update_platform_subscription(first["id"], "paid", None, None, "owner")
        update_platform_subscription(second["id"], "paid", None, None, "owner")
        update_platform_subscription(first["id"], None, "cancelled", None, "owner")
        with database._connect() as conn:
            customer = conn.execute(
                "SELECT status FROM platform_customers WHERE id=?",
                (self.customer["id"],),
            ).fetchone()
        self.assertEqual(customer["status"], "active")

    def test_unpaid_active_subscription_suspends_without_other_coverage(self):
        sub = self._new_subscription()
        update_platform_subscription(sub["id"], "paid", None, None, "owner")
        update_platform_subscription(sub["id"], "unpaid", None, None, "owner")
        with database._connect() as conn:
            customer = conn.execute(
                "SELECT status FROM platform_customers WHERE id=?",
                (self.customer["id"],),
            ).fetchone()
        self.assertEqual(customer["status"], "suspended")

    def test_expired_subscription_suspends_customer(self):
        sub = self._new_subscription()
        update_platform_subscription(sub["id"], "paid", None, None, "owner")
        with database._connect() as conn:
            conn.execute(
                "UPDATE platform_subscriptions SET ends_at='2000-01-01T00:00:00+00:00' WHERE id=?",
                (sub["id"],),
            )
        self.assertEqual(expire_due_platform_subscriptions(), 1)
        with database._connect() as conn:
            customer = conn.execute(
                "SELECT status FROM platform_customers WHERE id=?",
                (self.customer["id"],),
            ).fetchone()
        self.assertEqual(customer["status"], "suspended")


if __name__ == "__main__":
    unittest.main()
