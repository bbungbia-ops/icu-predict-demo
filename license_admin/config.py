"""Cấu hình cho license_admin.

Không đưa giá trị thật của các biến bên dưới vào Git. Chế độ demo chỉ phù hợp
với môi trường trình diễn cục bộ.
"""

from __future__ import annotations

import os
from pathlib import Path


def as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    SECRET_KEY = os.environ.get("LICENSE_ADMIN_SECRET_KEY", "license-admin-demo-change-before-deployment")
    # Khi triển khai chung với ICU Predict, hai app cùng dùng DATABASE_URL của
    # Supabase. SQLite chỉ được dùng khi chạy demo cục bộ.
    DATABASE_PATH = (
        os.environ.get("LICENSE_ADMIN_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("LICENSE_ADMIN_DATABASE_PATH", str(BASE_DIR / "license_admin.db"))
    )
    ADMIN_USERNAME = os.environ.get("LICENSE_ADMIN_USERNAME", "license_admin")
    ADMIN_PASSWORD = os.environ.get("LICENSE_ADMIN_PASSWORD", "admin123")
    BANK_WEBHOOK_SECRET = os.environ.get("BANK_WEBHOOK_SECRET", "bank-webhook-demo-secret")
    # SePay ký mỗi webhook bằng HMAC-SHA256. Không đặt giá trị mặc định: khi
    # thiếu secret, endpoint sẽ từ chối toàn bộ request để tránh kích hoạt key
    # nhầm trong môi trường triển khai.
    SEPAY_WEBHOOK_SECRET = os.environ.get("SEPAY_WEBHOOK_SECRET", "")
    SEPAY_WEBHOOK_MAX_AGE_SECONDS = int(os.environ.get("SEPAY_WEBHOOK_MAX_AGE_SECONDS", "300"))
    ICU_INTEGRATION_SHARED_SECRET = os.environ.get(
        "ICU_INTEGRATION_SHARED_SECRET", "icu-license-integration-demo-secret"
    )
    DEMO_MODE = as_bool(os.environ.get("LICENSE_ADMIN_DEMO_MODE"), default=True)
    DEBUG = as_bool(os.environ.get("FLASK_DEBUG"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = as_bool(os.environ.get("SESSION_COOKIE_SECURE"), default=not DEMO_MODE)
    SESSION_COOKIE_NAME = "license_admin_session"
