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

REVIEW_OUTCOME_LABELS = {
    "appropriate": "Tín hiệu hỗ trợ ưu tiên phù hợp",
    "not_appropriate": "Tín hiệu chưa phù hợp với bối cảnh",
    "needs_follow_up": "Cần theo dõi thêm trước khi kết luận",
}

_CLINICAL_CONTEXT = {
    "map_value": ("giảm", "cần đối chiếu huyết động và tưới máu"),
    "pao2_fio2": ("giảm", "cần đối chiếu tình trạng oxy hóa máu"),
    "bilirubin": ("tăng", "cần đối chiếu chức năng gan"),
    "creatinine": ("tăng", "cần đối chiếu chức năng thận"),
    "platelet": ("giảm", "cần đối chiếu tình trạng huyết học"),
    "gcs": ("giảm", "cần đánh giá tri giác và thần kinh"),
}


def describe_signal(risk_level: str | None) -> dict[str, str]:
    """Trả nhãn điều phối phù hợp để hiển thị trên giao diện."""
    key = _LEVEL_TO_KEY.get(risk_level or "", "low")
    return dict(_PRESENTATIONS[key])


def explain_priority_reasons(
    feature_analysis: list[dict], signal: dict[str, str], out_of_distribution: object = False
) -> list[str]:
    """Return short, traceable screening reasons without making a clinical claim.

    The displayed ranges are only the demo's data-review ranges.  They are not
    treatment thresholds and are always paired with the clinician review step.
    """
    reasons: list[str] = []
    if out_of_distribution:
        reasons.append("Có giá trị ngoài phạm vi dữ liệu huấn luyện; cần kiểm tra thủ công.")

    for feature in feature_analysis:
        if feature.get("status") != "danger":
            continue
        unit = f" {feature['unit']}" if feature.get("unit") else ""
        if feature.get("key") == "sofa":
            reasons.append(
                f"SOFA có điểm suy cơ quan ({feature['value']}{unit}); cần đối chiếu cùng toàn bộ bối cảnh."
            )
        else:
            direction, context = _CLINICAL_CONTEXT.get(
                feature.get("key"), ("bất thường", "cần đối chiếu lâm sàng")
            )
            reasons.append(
                f"{feature['label']} {feature['value']}{unit}: {direction} so với khoảng tham chiếu "
                f"{feature['normal_min']}–{feature['normal_max']}; {context}."
            )
        if len(reasons) >= 3:
            break

    if not reasons:
        reasons.append(
            f"Tổ hợp dữ liệu tạo tín hiệu “{signal['label'].lower()}”; cần đối chiếu toàn bộ hồ sơ."
        )
    return reasons


def describe_review_outcome(value: str | None) -> str:
    """Translate optional Pilot feedback into safe, user-facing wording."""
    return REVIEW_OUTCOME_LABELS.get(value or "", "Chưa ghi nhận đánh giá Pilot")
