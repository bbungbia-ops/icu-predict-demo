"""Lớp trình bày an toàn cho tín hiệu nội bộ của mô hình nghiên cứu.

Các giá trị ``risk_level`` được lưu để tương thích với bản ghi demo cũ. Chúng
không được hiển thị trực tiếp cho người dùng vì không phải là mức nguy cơ lâm
sàng đã được xác thực.
"""

from __future__ import annotations


_PRESENTATIONS = {
    "high": {
        "key": "high",
        "label": "Ưu tiên đánh giá",
        "description": "Cần bác sĩ rà soát trong quy trình nghiên cứu.",
    },
    "medium": {
        "key": "medium",
        "label": "Theo dõi ưu tiên",
        "description": "Cần được đối chiếu với toàn bộ bối cảnh lâm sàng.",
    },
    "low": {
        "key": "low",
        "label": "Theo dõi thường quy",
        "description": "Vẫn cần đánh giá theo quy trình chuyên môn hiện hành.",
    },
}

_LEVEL_TO_KEY = {
    "Cao": "high",
    "Trung bình": "medium",
    "Trung binh": "medium",  # Bản ghi demo cũ không dấu.
    "Thấp": "low",
}


def describe_signal(risk_level: str | None) -> dict[str, str]:
    """Trả nhãn điều phối phù hợp để hiển thị trên giao diện."""
    key = _LEVEL_TO_KEY.get(risk_level or "", "low")
    return dict(_PRESENTATIONS[key])
