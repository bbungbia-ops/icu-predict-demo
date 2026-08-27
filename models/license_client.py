"""Client server-to-server để ICU Predict xác thực license key.

Payload chỉ chứa license key cùng mã nhận diện ứng dụng; không gửi dữ liệu bệnh
nhân hay bản ghi lâm sàng tới cổng quản trị license.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class LicenseCheckResult:
    valid: bool
    reason: str
    plan_code: str | None = None
    expires_at: str | None = None


def validate_icu_license(config, license_key: str | None = None) -> LicenseCheckResult:
    """Validate the configured license through license_admin.

    When enforcement is disabled, returning valid keeps local research/demo
    usage backwards compatible. When enabled, any missing configuration or
    network error fails closed.
    """
    if not config['LICENSE_ENFORCEMENT_ENABLED']:
        return LicenseCheckResult(valid=True, reason='enforcement_disabled')

    # A registered organization can have its own purchased key.  The configured
    # key remains a backward-compatible fallback for single-tenant deployments.
    license_key = (license_key or config.get('LICENSE_KEY', '')).strip()
    endpoint = config.get('LICENSE_VALIDATION_URL', '').strip()
    shared_secret = config.get('LICENSE_API_SHARED_SECRET', '')
    if not license_key or not endpoint or not shared_secret:
        return LicenseCheckResult(valid=False, reason='configuration_missing')

    payload = {
        'license_key': license_key,
        'client_id': config.get('LICENSE_CLIENT_ID', 'icu-predict-web'),
        'app_version': config.get('APP_VERSION', 'unknown'),
    }
    raw_body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(shared_secret.encode('utf-8'), raw_body, hashlib.sha256).hexdigest()
    request = Request(
        endpoint,
        data=raw_body,
        headers={
            'Content-Type': 'application/json',
            'X-ICU-License-Signature': signature,
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=config.get('LICENSE_VALIDATION_TIMEOUT_SECONDS', 5)) as response:
            body = response.read()
    except HTTPError as exc:
        if exc.code == 401:
            return LicenseCheckResult(valid=False, reason='authorization_failed')
        return LicenseCheckResult(valid=False, reason='validation_unavailable')
    except (URLError, TimeoutError, OSError):
        return LicenseCheckResult(valid=False, reason='validation_unavailable')

    try:
        result = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return LicenseCheckResult(valid=False, reason='invalid_response')
    return LicenseCheckResult(
        valid=bool(result.get('valid')),
        reason=str(result.get('reason', 'invalid')),
        plan_code=result.get('plan_code'),
        expires_at=result.get('expires_at'),
    )
