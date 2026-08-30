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

    def test_system_admin_bypasses_invalid_license(self):
        with patch(
            "routes.auth.validate_icu_license",
            return_value=LicenseCheckResult(valid=False, reason="expired"),
        ):
            response = self.client.post(
                "/login",
                data={"username": Config.ADMIN_USERNAME, "password": Config.ADMIN_PASSWORD},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.location)
        dashboard = self.client.get("/dashboard")
        self.assertEqual(dashboard.status_code, 200)

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

    def test_new_customer_can_open_empty_trial_workspace(self):
        self.client.get('/register')
        with self.client.session_transaction() as session:
            csrf_token = session['csrf_token']
        response = self.client.post(
            '/register',
            data={
                'csrf_token': csrf_token,
                'organization_name': 'ICU Trial',
                'full_name': 'Nguyễn Dùng Thử',
                'email': 'trial@example.vn',
                'username': 'icu.trial',
                'password': 'matkhau-demo-123',
                'password_confirm': 'matkhau-demo-123',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard', response.location)
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn('Bạn đang dùng thử ICU Predict'.encode(), response.data)


if __name__ == "__main__":
    unittest.main()
