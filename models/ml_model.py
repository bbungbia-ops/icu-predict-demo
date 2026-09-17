"""Runtime wrapper for the ICU research-risk prototype."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import joblib
import numpy as np

from models.clinical_schema import MODEL_FEATURES, InputValidationError, validate_inputs
from models.signal_presentation import describe_signal


class ICUPredictor:
    """Load a versioned research artifact and return a traceable assessment.

    This class does not make a clinical claim. Its ``risk_score`` is a model
    output for research/demo use only until the artifact has been validated on
    an approved clinical cohort.
    """

    NORMAL_RANGES = {
        "sofa": {"min": 0, "max": 0, "label": "SOFA", "unit": "điểm", "desc": "Điểm tổng hợp suy cơ quan; không phải đặc trưng AI"},
        "map_value": {"min": 70, "max": 100, "label": "MAP", "unit": "mmHg", "desc": "Huyết áp động mạch trung bình"},
        "pao2_fio2": {"min": 300, "max": 500, "label": "PaO2/FiO2", "unit": "", "desc": "Tỷ lệ oxy hóa máu"},
        "bilirubin": {"min": 0.1, "max": 1.2, "label": "Bilirubin", "unit": "mg/dL", "desc": "Dấu ấn chức năng gan"},
        "creatinine": {"min": 0.6, "max": 1.2, "label": "Creatinine", "unit": "mg/dL", "desc": "Dấu ấn chức năng thận"},
        "platelet": {"min": 150, "max": 400, "label": "Tiểu cầu", "unit": "x10^9/L", "desc": "Số lượng tiểu cầu"},
        "gcs": {"min": 13, "max": 15, "label": "GCS", "unit": "điểm", "desc": "Thang điểm ý thức Glasgow"},
    }

    def __init__(self, model_path: str | Path):
        artifact = joblib.load(model_path)
        if not isinstance(artifact, Mapping) or "pipeline" not in artifact or "metadata" not in artifact:
            raise ValueError("Model artifact không đúng định dạng phiên bản.")
        self.pipeline = artifact["pipeline"]
        self.metadata = artifact["metadata"]
        if tuple(self.metadata.get("feature_order", ())) != MODEL_FEATURES:
            raise ValueError("Thứ tự đặc trưng của model artifact không khớp ứng dụng.")

    def predict(self, sofa, map_value, pao2_fio2, bilirubin, creatinine, platelet, gcs):
        values = validate_inputs(
            {
                "sofa": sofa,
                "map_value": map_value,
                "pao2_fio2": pao2_fio2,
                "bilirubin": bilirubin,
                "creatinine": creatinine,
                "platelet": platelet,
                "gcs": gcs,
            }
        )
        feature_vector = np.asarray([[values[feature] for feature in MODEL_FEATURES]], dtype=float)
        probability = float(self.pipeline.predict_proba(feature_vector)[0][1])
        risk_score = round(probability * 100, 1)
        risk_level = "Cao" if risk_score >= 70 else "Trung bình" if risk_score >= 40 else "Thấp"

        out_of_distribution = self._outside_training_range(values)
        signal = describe_signal(risk_level)
        warnings = [
            "Mô hình nghiên cứu/demo: không dùng kết quả để chẩn đoán, kê đơn hoặc thay thế đánh giá của bác sĩ.",
            "Outcome và thời hạn dự báo của bộ dữ liệu chưa được xác minh; không diễn giải điểm này là nguy cơ, dự báo 24 giờ/48 giờ hoặc xác suất lâm sàng.",
        ]
        if out_of_distribution:
            warnings.append(
                "Ít nhất một giá trị nằm ngoài phạm vi dữ liệu đã huấn luyện; kết quả cần được bác sĩ đánh giá thủ công và không nên diễn giải định lượng."
            )

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "signal": signal,
            "feature_analysis": self._analyze_features(values),
            "model_version": self.metadata["model_version"],
            "model_status": self.metadata["clinical_use"]["status"],
            "out_of_distribution": out_of_distribution,
            "warnings": warnings,
        }

    def _outside_training_range(self, values: Mapping[str, float]) -> list[dict[str, float]]:
        bounds = self.metadata["training_feature_bounds"]
        outside = []
        for feature in MODEL_FEATURES:
            value = values[feature]
            lower, upper = bounds[feature]["min"], bounds[feature]["max"]
            if value < lower or value > upper:
                outside.append({"feature": feature, "value": value, "training_min": lower, "training_max": upper})
        return outside

    def _analyze_features(self, values: Mapping[str, float]) -> list[dict]:
        analysis = []
        for key, value in values.items():
            info = self.NORMAL_RANGES[key]
            normal_min, normal_max = info["min"], info["max"]

            if key == "sofa":
                status = "danger" if value > 0 else "normal"
                status_text = "Có điểm suy cơ quan" if value > 0 else "0 điểm"
                normalized = min(100, value / 24 * 100)
            elif key in ("map_value", "pao2_fio2", "platelet", "gcs"):
                status = "danger" if value < normal_min else "normal"
                status_text = "Cần đối chiếu" if status == "danger" else "Trong khoảng tham khảo"
                normalized = min(100, max(0, value / normal_max * 100))
            else:
                status = "danger" if value > normal_max else "normal"
                status_text = "Cần đối chiếu" if status == "danger" else "Trong khoảng tham khảo"
                normalized = min(100, max(0, value / (normal_max * 2) * 100))

            analysis.append(
                {
                    "key": key,
                    "label": info["label"],
                    "value": value,
                    "unit": info["unit"],
                    "description": info["desc"],
                    "normal_min": normal_min,
                    "normal_max": normal_max,
                    "status": status,
                    "status_text": status_text,
                    "normalized": round(normalized, 1),
                }
            )
        return analysis


__all__ = ["ICUPredictor", "InputValidationError"]
