"""Human-readable evidence status for the research model.

Development metrics from an unverified demo dataset must never be shown as
clinical performance.  This helper keeps that boundary explicit in the UI.
"""

from __future__ import annotations

from typing import Any, Mapping


def evidence_status(metadata: Mapping[str, Any]) -> dict[str, str]:
    clinical_use = metadata.get("clinical_use", {})
    target = metadata.get("target", {})
    target_definition = target.get("definition") or "Chưa xác định trong bộ dữ liệu hiện có"
    horizon = target.get("prediction_horizon") or "Chưa xác định"
    return {
        "status": "Chưa xác thực lâm sàng",
        "model_state": str(clinical_use.get("status", "research_prototype_only")),
        "target_definition": str(target_definition),
        "prediction_horizon": str(horizon),
        "metrics_state": "Chưa có cohort Pilot với outcome đã định nghĩa để công bố sensitivity, specificity, AUROC hoặc calibration.",
        "next_step": "Chốt outcome, mốc thời gian, tiêu chuẩn đối chiếu và quy trình phê duyệt trước khi đánh giá hiệu năng.",
    }
