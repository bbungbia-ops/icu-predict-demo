import tempfile
import unittest
from pathlib import Path

from app import create_app
from config import Config
from license_admin.plans import PLAN_CATALOG
from models.database import get_db_connection, init_db
from license_admin.database import activate_order, get_connection as get_license_connection, get_order


class ClinicalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "workflow_test.db")
        self.license_db_path = str(Path(self.temp_dir.name) / "license_admin_test.db")
        init_db(self.db_path, Config.ADMIN_USERNAME, Config.ADMIN_PASSWORD)

        self.app = create_app()
        self.app.config.update(
            TESTING=True,
            DATABASE_PATH=self.db_path,
            LICENSE_ADMIN_DATABASE_PATH=self.license_db_path,
            PAYMENT_BANK_NAME='TPBank',
            PAYMENT_BANK_CODE='TPBank',
            PAYMENT_ACCOUNT_NUMBER='0123456789',
            PAYMENT_ACCOUNT_NAME='NGUYEN TRUNG DUNG',
        )
        self.client = self.app.test_client()
        login = self.client.post(
            "/login", data={"username": Config.ADMIN_USERNAME, "password": Config.ADMIN_PASSWORD}
        )
        self.assertEqual(login.status_code, 302)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_shows_review_queue(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Danh sách ưu tiên cần bác sĩ xem xét".encode(), response.data)
        self.assertIn("AI chỉ hỗ trợ nhận diện tín hiệu cần chú ý sớm".encode(), response.data)
        self.assertIn("Ưu tiên đánh giá".encode(), response.data)
        self.assertIn("Vì sao cần xem trước".encode(), response.data)

    def test_customer_layout_includes_mobile_navigation_and_table_hint(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="mobileNavToggle"', response.data)
        self.assertIn(b"table-scroll-hint", response.data)

    def test_demo_patients_have_vietnamese_names(self):
        conn = get_db_connection(self.db_path)
        patient = conn.execute("SELECT name, gender FROM patients WHERE patient_code = 'BN002'").fetchone()
        conn.close()
        self.assertEqual(patient["name"], "Trần Thu Hà")
        self.assertEqual(patient["gender"], "Nữ")

    def test_acknowledgement_writes_audit_trail(self):
        response = self.client.post(
            "/predict/result/2/acknowledge",
            data={
                "acknowledgement_note": "Đã đối chiếu hồ sơ trong môi trường kiểm thử.",
                "review_outcome": "appropriate",
                "utility_score": "4",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Đã có bác sĩ đánh giá".encode(), response.data)
        self.assertIn("Tín hiệu hỗ trợ ưu tiên phù hợp".encode(), response.data)

        conn = get_db_connection(self.db_path)
        record = conn.execute(
            "SELECT acknowledged_at, acknowledged_by, acknowledgement_note, review_outcome, utility_score "
            "FROM predictions WHERE id = 2"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(record["acknowledged_at"])
        self.assertEqual(record["acknowledgement_note"], "Đã đối chiếu hồ sơ trong môi trường kiểm thử.")
        self.assertEqual(record["review_outcome"], "appropriate")
        self.assertEqual(record["utility_score"], 4)

    def test_pilot_page_shows_measures_without_invented_results(self):
        response = self.client.get("/pilot")
        self.assertEqual(response.status_code, 200)
        self.assertIn("01 ICU · 10–20 giường".encode(), response.data)
        self.assertIn("Thời gian tiết kiệm".encode(), response.data)
        self.assertIn("Cần thu thập baseline trước Pilot".encode(), response.data)

    def test_about_page_sets_safe_coordination_positioning(self):
        response = self.client.get("/about")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Không thay thế bác sĩ".encode(), response.data)
        self.assertIn("Đã được rà soát chưa?".encode(), response.data)

    def test_result_explains_priority_and_marks_trend_as_not_ready(self):
        response = self.client.get("/predict/result/4")
        self.assertEqual(response.status_code, 200)
        self.assertIn("VÌ SAO CẦN XEM TRƯỚC?".encode(), response.data)
        self.assertIn("Khung theo dõi 6–12–24 giờ".encode(), response.data)
        self.assertIn("Chưa đủ chuỗi thời gian".encode(), response.data)

    def test_pdf_is_a_research_summary_not_treatment_advice(self):
        response = self.client.get("/report/2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertTrue(response.data.startswith(b"%PDF"))

    def test_subscription_page_shows_current_plan(self):
        response = self.client.get("/account/subscription")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tài khoản & gói dịch vụ".encode(), response.data)
        self.assertIn("Pilot có giám sát".encode(), response.data)
        self.assertIn("ICU Cơ bản".encode(), response.data)
        self.assertIn("15 triệu".encode(), response.data)
        self.assertIn("9 triệu".encode(), response.data)
        self.assertIn("Thanh toán 15 triệu / tháng".encode(), response.data)
        self.assertIn("Thanh toán 9 triệu / tháng".encode(), response.data)

    def test_plan_catalog_charges_the_monthly_prices(self):
        self.assertEqual(PLAN_CATALOG['pilot']['monthly_amount_vnd'], 15_000_000)
        self.assertEqual(PLAN_CATALOG['core']['monthly_amount_vnd'], 9_000_000)
        self.assertEqual(PLAN_CATALOG['pro']['monthly_amount_vnd'], 18_000_000)
        self.assertEqual(PLAN_CATALOG['core']['amount_vnd'], 9_000_000)
        self.assertEqual(PLAN_CATALOG['core']['validity_days'], 30)

    def test_registered_customer_can_create_a_license_order(self):
        customer = self.app.test_client()
        customer.get('/register')
        with customer.session_transaction() as session:
            csrf_token = session['csrf_token']
        response = customer.post(
            '/register',
            data={
                'csrf_token': csrf_token,
                'organization_name': 'Bệnh viện Khởi Nghiệp',
                'full_name': 'Nguyễn Minh Anh',
                'email': 'minhanh@example.vn',
                'username': 'minh.anh',
                'password': 'matkhau-demo-123',
                'password_confirm': 'matkhau-demo-123',
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Đã tạo tài khoản tổ chức".encode(), response.data)

        with customer.session_transaction() as session:
            csrf_token = session['csrf_token']
        response = customer.post(
            '/account/purchase',
            data={'csrf_token': csrf_token, 'plan_code': 'core'},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Hoàn tất thanh toán để kích hoạt key".encode(), response.data)
        self.assertIn("9.000.000 đ".encode(), response.data)
        self.assertIn("Mã QR thanh toán SePay".encode(), response.data)
        self.assertIn("THANHTOAN MINHANH".encode(), response.data)
        self.assertIn("Thanh toán theo tháng".encode(), response.data)
        self.assertIn(b"checkout-payment-body", response.data)

        conn = get_db_connection(self.db_path)
        organization = conn.execute(
            "SELECT organization_code, license_key, license_order_id FROM organizations WHERE name = ?",
            ('Bệnh viện Khởi Nghiệp',),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(organization['license_key'])
        license_conn = get_license_connection(self.license_db_path)
        order = get_order(license_conn, organization['license_order_id'])
        license_conn.close()
        self.assertEqual(order['plan_code'], 'core')
        self.assertEqual(order['amount_vnd'], 9_000_000)
        self.assertEqual(order['validity_days'], 30)
        self.assertTrue(order['transfer_content'].startswith('THANHTOAN MINHANH '))
        self.assertEqual(order['customer_organization_code'], organization['organization_code'])

        status_response = customer.get(f"/account/orders/{order['id']}/status")
        self.assertEqual(status_response.get_json()['license_status'], 'pending_payment')

        license_conn = get_license_connection(self.license_db_path)
        activate_order(
            license_conn,
            order_id=order['id'],
            transaction_id='demo-bank-transaction-001',
            payer_name='Nguyễn Minh Anh',
        )
        license_conn.close()
        response = customer.get(f"/account/orders/{order['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("License đang hoạt động".encode(), response.data)
        self.assertIn(order['license_key'].encode(), response.data)
        with customer.session_transaction() as session:
            self.assertTrue(session['license_valid'])
            self.assertEqual(session['license_plan'], 'core')


if __name__ == "__main__":
    unittest.main()
