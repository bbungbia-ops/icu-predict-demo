"""Descriptive time-series summaries for the ICU Predict pilot.

This module deliberately reports recorded changes only.  It does not infer a
clinical trajectory, predict an event, or classify a change as improvement or
deterioration.  Those claims need an approved protocol and validated cohort.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping


WINDOW_HOURS = (6, 12, 24)
DISPLAY_FIELDS = (
    ("sofa", "SOFA", "điểm", 1),
    ("map_value", "MAP", "mmHg", 1),
    ("pao2_fio2", "PaO2/FiO2", "", 1),
)


def parse_measurement_time(value: Any) -> datetime | None:
    """Return a timestamp only when the stored collection time is usable."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def build_trend_summary(
    current_record: Mapping[str, Any], previous_records: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build 6/12/24h descriptive deltas from explicitly timestamped samples.

    Each window compares the current record against the *earliest available*
    preceding sample in that window.  The actual elapsed duration is always
    displayed, so a sparse series is never presented as an exact six-hour
    measurement.
    """
    current_time = parse_measurement_time(current_record.get("measurement_time"))
    if current_time is None:
        return _not_ready("Bản ghi này chưa có thời điểm lấy mẫu hợp lệ nên không thể so sánh theo thời gian.")

    dated_records = []
    for record in previous_records:
        record_time = parse_measurement_time(record.get("measurement_time"))
        if record_time is not None and record_time < current_time:
            dated_records.append((record_time, record))

    if not dated_records:
        return _not_ready("Chưa có bản ghi trước đó cùng bệnh nhân với thời điểm lấy mẫu hợp lệ.")

    windows = []
    for hours in WINDOW_HOURS:
        lower_bound = current_time - timedelta(hours=hours)
        samples = [(at, record) for at, record in dated_records if at >= lower_bound]
        if not samples:
            windows.append({"hours": hours, "available": False, "reason": "Chưa có mẫu trước đó trong cửa sổ này."})
            continue
        baseline_time, baseline = min(samples, key=lambda item: item[0])
        changes = []
        for key, label, unit, decimals in DISPLAY_FIELDS:
            try:
                delta = round(float(current_record[key]) - float(baseline[key]), decimals)
            except (KeyError, TypeError, ValueError):
                continue
            changes.append({"key": key, "label": label, "unit": unit, "delta": delta})
        windows.append(
            {
                "hours": hours,
                "available": bool(changes),
                "sample_count": len(samples) + 1,
                "baseline_time": baseline_time.strftime("%d/%m/%Y %H:%M"),
                "observed_hours": round((current_time - baseline_time).total_seconds() / 3600, 1),
                "changes": changes,
                "reason": "" if changes else "Thiếu giá trị có thể so sánh trong cửa sổ này.",
            }
        )
    return {
        "available": any(window["available"] for window in windows),
        "current_time": current_time.strftime("%d/%m/%Y %H:%M"),
        "windows": windows,
        "reason": "",
    }


def _not_ready(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "current_time": None,
        "windows": [{"hours": hours, "available": False, "reason": reason} for hours in WINDOW_HOURS],
        "reason": reason,
    }
