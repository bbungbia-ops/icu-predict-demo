import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from config import Config
from models.database import init_db
from models.license_client import LicenseCheckResult


class LicenseEnforcementTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "icu_license_test.db")
        init_db(self.db_path, Config.ADMIN_USERNAME, Config.ADMIN_PASSWORD)
        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            DATABASE_PATH=self.db_path,
            LICENSE_ENFORCEMENT_ENABLED=True,
            LICENSE_KEY="ICU-TEST-KEY",
            LICENSE_VALIDATION_URL="https://license.example.test/api/v1/licenses/validate",
            LICENSE_API_SHARED_SECRET="test-secret",
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_login_is_blocked_when_license_is_invalid(self):
        with patch(
            "routes.auth.validate_icu_license",
            return_value=LicenseCheckResult(valid=False, reason="expired"),
        ):
            response = self.client.post(
                "/login",
                data={"username": Config.ADMIN_USERNAME, "password": Config.ADMIN_PASSWORD},
                follow_redirects=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("License ICU Predict đã hết hạn".encode(), response.data)

    def test_login_succeeds_when_license_is_valid(self):
        with patch(
            "routes.auth.validate_icu_license",
            return_value=LicenseCheckResult(valid=True, reason="valid", plan_code="core", expires_at="2027-01-01"),
        ):
            response = self.client.post(
                "/login",
                data={"username": Config.ADMIN_USERNAME, "password": Config.ADMIN_PASSWORD},
            )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertEqual(session["license_plan"], "core")
            self.assertEqual(session["license_expires_at"], "2027-01-01")

    def test_pending_customer_can_only_open_commercial_screens(self):
        with patch(
            "routes.auth.validate_icu_license",
            return_value=LicenseCheckResult(valid=False, reason="pending_payment"),
        ):
            response = self.client.post(
                "/login",
                data={"username": Config.ADMIN_USERNAME, "password": Config.ADMIN_PASSWORD},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/subscription", response.location)
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/subscription", response.location)


if __name__ == "__main__":
    unittest.main()
