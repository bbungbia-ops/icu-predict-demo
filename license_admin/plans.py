"""Danh mục gói license dùng chung cho toàn bộ ICU Predict.

Đây là nguồn dữ liệu duy nhất cho tên gói, mức giá và thời hạn. Cổng quản trị
license lẫn website người dùng đều nhập trực tiếp từ đây để tránh sai khác giá
khi giới thiệu, tạo đơn hàng hoặc xác thực key.
"""

PLAN_CATALOG = {
    "pilot": {
        "name": "Pilot có giám sát",
        "amount_vnd": 15_000_000,
        "monthly_amount_vnd": 15_000_000,
        "validity_days": 30,
        "description": "Một khoa ICU, giai đoạn thử nghiệm có giám sát theo tháng.",
        "badge": "Dành cho thử nghiệm",
        "features": [
            "Một khoa ICU trong 30 ngày",
            "Tối đa 15 giường theo phạm vi thử nghiệm",
            "Tối đa 15 tài khoản sử dụng",
            "Báo cáo tổng kết giai đoạn pilot",
        ],
        "max_devices": 1,
    },
    "core": {
        "name": "ICU Cơ bản",
        "amount_vnd": 9_000_000,
        "monthly_amount_vnd": 9_000_000,
        "validity_days": 30,
        "description": "Một khoa ICU, giấy phép sử dụng và thanh toán theo tháng.",
        "badge": "Phổ biến",
        "features": [
            "Một khoa ICU trong 30 ngày",
            "Tối đa 15 giường theo phạm vi triển khai",
            "Hàng đợi đánh giá và nhật ký kiểm toán",
            "Hỗ trợ tiêu chuẩn",
        ],
        "max_devices": 1,
    },
    "pro": {
        "name": "ICU Chuyên sâu",
        "amount_vnd": 18_000_000,
        "monthly_amount_vnd": 18_000_000,
        "validity_days": 30,
        "description": "ICU quy mô lớn, hỗ trợ phạm vi tích hợp theo tháng.",
        "badge": "Tích hợp dữ liệu",
        "features": [
            "ICU quy mô lớn trong 30 ngày",
            "Phạm vi tích hợp HIS/EMR theo hợp đồng",
            "Phân quyền và nhật ký kiểm toán nâng cao",
            "Hỗ trợ ưu tiên",
        ],
        "max_devices": 3,
    },
    "enterprise": {
        "name": "Doanh nghiệp",
        "amount_vnd": None,
        "monthly_amount_vnd": None,
        "validity_days": None,
        "description": "Nhiều khoa hoặc toàn bệnh viện; giá và thời hạn theo hợp đồng.",
        "badge": "Toàn bệnh viện",
        "features": [
            "Nhiều khoa hoặc toàn bệnh viện",
            "Hạ tầng, tích hợp và SLA theo yêu cầu",
            "Đào tạo, quản trị tập trung",
            "Lộ trình xác thực theo từng đơn vị",
        ],
        "max_devices": 10,
    },
}


def format_vnd(value: int | None) -> str:
    if value is None or value == 0:
        return "Báo giá theo hợp đồng"
    return f"{value:,.0f} đ".replace(",", ".")


def format_vnd_millions(value: int | None) -> str:
    """Format a monthly reference price without hiding the actual order total."""
    if value is None or value == 0:
        return "Báo giá theo hợp đồng"
    if value % 1_000_000 == 0:
        return f"{value // 1_000_000} triệu"
    return format_vnd(value)


def payment_term_label(plan: dict) -> str:
    """Describe the amount charged for the license term shown to customers."""
    amount = plan.get("amount_vnd")
    if amount is None:
        return "Giá và thời hạn theo hợp đồng"
    if plan.get("validity_days") == 30:
        return f"Thanh toán {format_vnd_millions(amount)} / tháng"
    days = plan.get("validity_days")
    return f"Thanh toán {format_vnd(amount)} / {days} ngày"
