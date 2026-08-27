import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path

from license_admin.app import create_app
from license_admin.database import create_order, get_connection, get_order


class LicenseAdminTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "license_admin_test.db")
        self.webhook_secret = "test-bank-secret"
        self.sepay_secret = "test-sepay-secret"
        self.integration_secret = "test-icu-secret"
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-session-secret",
                "DATABASE_PATH": self.db_path,
                "ADMIN_USERNAME": "license_admin",
                "ADMIN_PASSWORD": "admin123",
                "BANK_WEBHOOK_SECRET": self.webhook_secret,
                "SEPAY_WEBHOOK_SECRET": self.sepay_secret,
                "SEPAY_WEBHOOK_MAX_AGE_SECONDS": 300,
                "ICU_INTEGRATION_SHARED_SECRET": self.integration_secret,
                "DEMO_MODE": True,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        with self.client.session_transaction() as session:
            return session["csrf_token"]

    def login(self):
        self.client.get("/login")
        response = self.client.post(
            "/login",
            data={
                "username": "license_admin",
                "password": "admin123",
                "csrf_token": self.csrf_token(),
            },
        )
        self.assertEqual(response.status_code, 302)

    def make_order(self):
        return create_order(
            self.db_path,
            plan_code="core",
            organization_name="Bệnh viện Demo",
            contact_name="Nguyễn Minh Anh",
            contact_email="demo@example.com",
            amount_vnd=108_000_000,
            validity_days=365,
            max_devices=2,
            notes="Kiểm thử tự động",
        )

    def signed_post(self, url, payload, secret, header):
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        return self.client.post(url, data=raw_body, headers={"Content-Type": "application/json", header: signature})

    def signed_sepay_post(self, payload, timestamp: int | None = None):
        raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        timestamp_text = str(timestamp if timestamp is not None else int(time.time()))
        signing_input = timestamp_text.encode("ascii") + b"." + raw_body
        signature = "sha256=" + hmac.new(
            self.sepay_secret.encode("utf-8"), signing_input, hashlib.sha256
        ).hexdigest()
        return self.client.post(
            "/webhooks/sepay/payment",
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "X-SePay-Signature": signature,
                "X-SePay-Timestamp": timestamp_text,
            },
        )

    def test_admin_can_create_pending_license_order(self):
        self.login()
        response = self.client.post(
            "/orders/new",
            data={
                "csrf_token": self.csrf_token(),
                "plan_code": "pilot",
                "organization_name": "Bệnh viện Demo",
                "contact_name": "Trần Thu Hà",
                "contact_email": "ha@example.com",
                "max_devices": "1",
                "notes": "Pilot demo",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("ICU-", response.get_data(as_text=True))
        connection = get_connection(self.db_path)
        order = connection.execute("SELECT * FROM orders").fetchone()
        key = connection.execute("SELECT * FROM license_keys").fetchone()
        connection.close()
        self.assertEqual(order["payment_status"], "pending")
        self.assertEqual(key["status"], "pending_payment")

    def test_valid_bank_webhook_activates_key_and_icu_api_accepts_it(self):
        order_id = self.make_order()
        connection = get_connection(self.db_path)
        order = get_order(connection, order_id)
        connection.close()
        webhook_response = self.signed_post(
            "/webhooks/bank/payment",
            {
                "event_id": "evt-payment-001",
                "transaction_id": "bank-tx-001",
                "status": "success",
                "amount": order["amount_vnd"],
                "transfer_content": order["transfer_content"],
                "payer_name": "Nguyen Minh Anh",
            },
            self.webhook_secret,
            "X-Bank-Signature",
        )
        self.assertEqual(webhook_response.status_code, 200)
        self.assertEqual(webhook_response.get_json()["status"], "activated")
        api_response = self.signed_post(
            "/api/v1/licenses/validate",
            {"license_key": order["license_key"], "client_id": "test-icu", "app_version": "test"},
            self.integration_secret,
            "X-ICU-License-Signature",
        )
        self.assertEqual(api_response.status_code, 200)
        self.assertTrue(api_response.get_json()["valid"])
        self.assertEqual(api_response.get_json()["plan_code"], "core")

    def test_wrong_amount_does_not_activate_key(self):
        order_id = self.make_order()
        connection = get_connection(self.db_path)
        order = get_order(connection, order_id)
        connection.close()
        response = self.signed_post(
            "/webhooks/bank/payment",
            {
                "event_id": "evt-payment-wrong-amount",
                "transaction_id": "bank-tx-wrong-amount",
                "status": "success",
                "amount": order["amount_vnd"] - 1,
                "transfer_content": order["transfer_content"],
            },
            self.webhook_secret,
            "X-Bank-Signature",
        )
        self.assertEqual(response.get_json()["status"], "amount_mismatch")
        connection = get_connection(self.db_path)
        refreshed = get_order(connection, order_id)
        connection.close()
        self.assertEqual(refreshed["payment_status"], "pending")
        self.assertEqual(refreshed["license_status"], "pending_payment")

    def test_invalid_bank_signature_is_rejected(self):
        response = self.client.post(
            "/webhooks/bank/payment",
            data=b'{"event_id":"evt-invalid"}',
            headers={"Content-Type": "application/json", "X-Bank-Signature": "invalid"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "invalid_signature")

    def test_valid_sepay_webhook_activates_key_once(self):
        order_id = self.make_order()
        connection = get_connection(self.db_path)
        order = get_order(connection, order_id)
        connection.close()
        payload = {
            "id": 92704,
            "gateway": "MBBank",
            "transactionDate": "2026-08-26 13:20:00",
            "accountNumber": "0123456789",
            "code": order["transfer_content"],
            "content": f"Thanh toan {order['transfer_content']}",
            "transferType": "in",
            "description": "NGUYEN MINH ANH chuyen tien",
            "transferAmount": order["amount_vnd"],
            "referenceCode": "MB20260826001",
        }

        response = self.signed_sepay_post(payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})
        duplicate_response = self.signed_sepay_post(payload)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(duplicate_response.get_json(), {"success": True})

        connection = get_connection(self.db_path)
        refreshed = get_order(connection, order_id)
        event_count = connection.execute(
            "SELECT COUNT(*) AS count FROM webhook_events WHERE provider_event_id = 'sepay:92704'"
        ).fetchone()["count"]
        connection.close()
        self.assertEqual(refreshed["payment_status"], "paid")
        self.assertEqual(refreshed["license_status"], "active")
        self.assertEqual(refreshed["bank_transaction_id"], "SEPAY-92704")
        self.assertEqual(event_count, 1)

    def test_sepay_wrong_amount_keeps_order_pending(self):
        order_id = self.make_order()
        connection = get_connection(self.db_path)
        order = get_order(connection, order_id)
        connection.close()
        response = self.signed_sepay_post(
            {
                "id": 92705,
                "code": order["transfer_content"],
                "transferType": "in",
                "transferAmount": order["amount_vnd"] - 1,
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True})
        connection = get_connection(self.db_path)
        refreshed = get_order(connection, order_id)
        connection.close()
        self.assertEqual(refreshed["payment_status"], "pending")
        self.assertEqual(refreshed["license_status"], "pending_payment")

    def test_sepay_rejects_bad_or_stale_signature(self):
        payload = {"id": 92706, "transferType": "in", "transferAmount": 15_000_000}
        invalid_response = self.client.post(
            "/webhooks/sepay/payment",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-SePay-Signature": "sha256=invalid",
                "X-SePay-Timestamp": str(int(time.time())),
            },
        )
        self.assertEqual(invalid_response.status_code, 401)
        self.assertFalse(invalid_response.get_json()["success"])

        stale_response = self.signed_sepay_post(payload, timestamp=int(time.time()) - 301)
        self.assertEqual(stale_response.status_code, 401)
        self.assertFalse(stale_response.get_json()["success"])


if __name__ == "__main__":
    unittest.main()
