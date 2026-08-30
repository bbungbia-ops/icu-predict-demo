import os


def as_bool(value, default=False):
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


def positive_int(value, default):
    """Read a positive integer setting without making startup fragile."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class Config:
    # Giá trị mặc định chỉ phục vụ môi trường demo cục bộ. Khi triển khai phải
    # đặt SECRET_KEY và thông tin quản trị bằng biến môi trường riêng.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'icu-predict-demo-only-change-before-deployment')
    # Trên Render, DATABASE_URL là chuỗi kết nối PostgreSQL do Supabase cung
    # cấp. Không đặt chuỗi này vào source; SQLite chỉ là fallback cho demo máy.
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    DATABASE_PATH = os.environ.get(
        'ICU_PREDICT_DATABASE_URL',
        DATABASE_URL or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icu_predict.db'),
    )
    # Cả ICU Predict và License Admin dùng chung một PostgreSQL trong bản
    # online. Nhờ đó đơn hàng/key không thể bị lệch giữa hai khu vực.
    LICENSE_ADMIN_DATABASE_PATH = os.environ.get(
        'LICENSE_ADMIN_DATABASE_URL',
        DATABASE_URL or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'license_admin', 'license_admin.db'),
    )
    MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_model', 'icu_risk_model.joblib')
    ADMIN_USERNAME = os.environ.get('ICU_PREDICT_ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ICU_PREDICT_ADMIN_PASSWORD', 'admin123')
    DEBUG = as_bool(os.environ.get('FLASK_DEBUG'))
    DEMO_MODE = as_bool(os.environ.get('ICU_PREDICT_DEMO_MODE'), default=True)
    # Khi bật, ICU Predict kiểm tra key với license_admin ở mỗi lần đăng nhập
    # thành công. Mặc định tắt để bản demo cục bộ vẫn chạy độc lập.
    LICENSE_ENFORCEMENT_ENABLED = as_bool(
        os.environ.get('ICU_LICENSE_ENFORCEMENT_ENABLED'), default=not DEMO_MODE
    )
    # Tổ chức mới bắt đầu bằng dữ liệu trống. Họ có thể tự tạo một số ca thử
    # nghiệm trước khi cần mua key; quản trị viên hệ thống không bị giới hạn.
    TRIAL_PATIENT_LIMIT = positive_int(os.environ.get('ICU_TRIAL_PATIENT_LIMIT'), 3)
    TRIAL_ASSESSMENT_LIMIT = positive_int(os.environ.get('ICU_TRIAL_ASSESSMENT_LIMIT'), 3)
    LICENSE_KEY = os.environ.get('ICU_LICENSE_KEY', '')
    LICENSE_VALIDATION_URL = os.environ.get('LICENSE_VALIDATION_URL', '')
    LICENSE_API_SHARED_SECRET = os.environ.get('ICU_INTEGRATION_SHARED_SECRET', '')
    LICENSE_CLIENT_ID = os.environ.get('ICU_LICENSE_CLIENT_ID', 'icu-predict-web')
    APP_VERSION = os.environ.get('ICU_PREDICT_APP_VERSION', 'demo-2026.08')
    LICENSE_VALIDATION_TIMEOUT_SECONDS = float(os.environ.get('LICENSE_VALIDATION_TIMEOUT_SECONDS', '5'))
    PAYMENT_BANK_NAME = os.environ.get('PAYMENT_BANK_NAME', 'Ngân hàng mô phỏng cho bản demo')
    PAYMENT_BANK_CODE = os.environ.get('PAYMENT_BANK_CODE', '')
    PAYMENT_ACCOUNT_NUMBER = os.environ.get('PAYMENT_ACCOUNT_NUMBER', '0000 0000 0000')
    PAYMENT_ACCOUNT_NAME = os.environ.get('PAYMENT_ACCOUNT_NAME', 'ICU PREDICT DEMO')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = as_bool(os.environ.get('SESSION_COOKIE_SECURE'), default=not DEMO_MODE)
    SESSION_COOKIE_NAME = 'icu_predict_session'
