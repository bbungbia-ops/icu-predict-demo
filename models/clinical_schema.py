"""Shared input contract for the ICU research-risk prototype.

This module deliberately keeps the total SOFA score out of the model feature
vector. SOFA is calculated from several organ-system measures that are already
entered separately, so using both would double-count related information.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


# These are the six raw measures used by the research model, in this exact order.
MODEL_FEATURES = (
    "map_value",
    "pao2_fio2",
    "bilirubin",
    "creatinine",
    "platelet",
    "gcs",
)

# SOFA remains display-only clinical context. It is never passed to the model.
ALL_INPUTS = ("sofa",) + MODEL_FEATURES


@dataclass(frozen=True)
class InputLimit:
    minimum: float
    maximum: float
    label: str


# Broad plausibility limits catch likely unit/data-entry errors without rejecting
# an unusual but possible critically ill patient. They are not treatment ranges.
INPUT_LIMITS = {
    "sofa": InputLimit(0, 24, "SOFA"),
    "map_value": InputLimit(0, 250, "MAP (mmHg)"),
    "pao2_fio2": InputLimit(0, 800, "PaO2/FiO2"),
    "bilirubin": InputLimit(0, 60, "Bilirubin (mg/dL)"),
    "creatinine": InputLimit(0, 30, "Creatinine (mg/dL)"),
    "platelet": InputLimit(0, 2000, "Tiểu cầu (x10^9/L)"),
    "gcs": InputLimit(3, 15, "GCS"),
}


class InputValidationError(ValueError):
    """Raised when a prediction input is missing, non-numeric, or implausible."""


def validate_inputs(values: Mapping[str, float]) -> dict[str, float]:
    """Return validated float inputs, rejecting impossible or non-finite values."""
    validated: dict[str, float] = {}
    for key in ALL_INPUTS:
        if key not in values:
            raise InputValidationError(f"Thiếu chỉ số {INPUT_LIMITS[key].label}.")
        try:
            value = float(values[key])
        except (TypeError, ValueError) as exc:
            raise InputValidationError(
                f"{INPUT_LIMITS[key].label} phải là một số hợp lệ."
            ) from exc

        limit = INPUT_LIMITS[key]
        if not isfinite(value) or not limit.minimum <= value <= limit.maximum:
            raise InputValidationError(
                f"{limit.label} phải nằm trong khoảng {limit.minimum:g}–{limit.maximum:g}. "
                "Hãy kiểm tra lại đơn vị và dữ liệu nhập."
            )
        validated[key] = value
    return validated
