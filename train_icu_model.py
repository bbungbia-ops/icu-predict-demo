"""Train the ICU research-risk prototype and write a traceable model artifact.

This script is for development and validation workflow only. The supplied
dataset has unverified provenance and is not suitable for a clinical claim.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.clinical_schema import INPUT_LIMITS, MODEL_FEATURES


PROJECT_DIR = Path(__file__).resolve().parent
DATA_PATH = PROJECT_DIR / "data.json"
OUTPUT_DIR = PROJECT_DIR / "ai_model"
MODEL_PATH = OUTPUT_DIR / "icu_risk_model.joblib"
REPORT_PATH = OUTPUT_DIR / "icu_risk_model_report.json"
RANDOM_STATE = 42

SOURCE_COLUMNS = {
    "map_value": "MAP",
    "pao2_fio2": "PaO2_FiO2",
    "bilirubin": "Bilirubin",
    "creatinine": "Creatinine",
    "platelet": "Platelet",
    "gcs": "GCS",
}

# Vietnamese labels for features
FEATURE_LABELS = {
    "map_value": "MAP\n(mmHg)",
    "pao2_fio2": "PaO2/FiO2",
    "bilirubin": "Bilirubin\n(mg/dL)",
    "creatinine": "Creatinine\n(mg/dL)",
    "platelet": "Tiểu cầu\n(x10⁹/L)",
    "gcs": "GCS\n(điểm)",
}


def load_dataset(path: Path) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    required = set(SOURCE_COLUMNS.values()) | {"Outcome"}
    if not rows or any(not required.issubset(row) for row in rows):
        raise ValueError("Dataset thiếu cột đầu vào hoặc Outcome cần thiết.")

    x = np.asarray(
        [[float(row[SOURCE_COLUMNS[feature]]) for feature in MODEL_FEATURES] for row in rows],
        dtype=float,
    )
    y = np.asarray([int(row["Outcome"]) for row in rows], dtype=int)
    if set(np.unique(y)) != {0, 1}:
        raise ValueError("Outcome phải có cả hai lớp 0 và 1.")
    if not np.isfinite(x).all():
        raise ValueError("Dataset có giá trị không hợp lệ.")
    return x, y, rows


def build_pipeline() -> Pipeline:
    """Use an interpretable baseline; scaling occurs only inside each fit."""
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("classifier", LogisticRegression(max_iter=2000, random_state=RANDOM_STATE)),
        ]
    )


def binary_metrics(y_true: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    predicted = (probabilities >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, predicted, labels=[0, 1]).ravel()
    return {
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "average_precision": round(float(average_precision_score(y_true, probabilities)), 4),
        "brier_score": round(float(brier_score_loss(y_true, probabilities)), 4),
        "sensitivity": round(float(recall_score(y_true, predicted, zero_division=0)), 4),
        "specificity": round(float(tn / (tn + fp)) if tn + fp else 0.0, 4),
        "precision": round(float(precision_score(y_true, predicted, zero_division=0)), 4),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def confidence_interval(values: np.ndarray) -> list[float]:
    return [round(float(np.quantile(values, 0.025)), 4), round(float(np.quantile(values, 0.975)), 4)]


def cross_validation_summary(x: np.ndarray, y: np.ndarray) -> dict[str, object]:
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    scores = cross_validate(
        build_pipeline(),
        x,
        y,
        cv=cv,
        scoring={"roc_auc": "roc_auc", "average_precision": "average_precision", "neg_brier": "neg_brier_score"},
        n_jobs=1,
    )
    return {
        "folds": 5,
        "roc_auc": {"mean": round(float(np.mean(scores["test_roc_auc"])), 4), "range": [round(float(np.min(scores["test_roc_auc"])), 4), round(float(np.max(scores["test_roc_auc"])), 4)]},
        "average_precision": {"mean": round(float(np.mean(scores["test_average_precision"])), 4), "range": [round(float(np.min(scores["test_average_precision"])), 4), round(float(np.max(scores["test_average_precision"])), 4)]},
        "brier_score": {"mean": round(float(np.mean(-scores["test_neg_brier"])), 4), "range": [round(float(np.min(-scores["test_neg_brier"])), 4), round(float(np.max(-scores["test_neg_brier"])), 4)]},
    }


# =============================================
#  CHART GENERATION — saved as PNG to ai_model/
# =============================================

def generate_evaluation_charts(
    y_test: np.ndarray,
    test_proba: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    final_model: Pipeline,
    cv_summary: dict,
) -> list[Path]:
    """Generate all evaluation charts and save to OUTPUT_DIR. Returns list of saved paths."""
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "figure.facecolor": "#ffffff",
        "axes.facecolor": "#fafbfc",
        "axes.edgecolor": "#e2e8f0",
        "axes.grid": True,
        "grid.color": "#f1f5f9",
        "grid.linewidth": 0.8,
    })

    TEAL = "#009e89"
    TEAL_LIGHT = "#00bfa5"
    CORAL = "#ef4444"
    AMBER = "#f59e0b"
    BLUE = "#3b82f6"
    SLATE = "#64748b"

    saved = []

    # ── 1. Confusion Matrix Heatmap ──
    fig, ax = plt.subplots(figsize=(7, 6))
    predicted = (test_proba >= 0.5).astype(int)
    cm = confusion_matrix(y_test, predicted, labels=[0, 1])
    teal_cmap = LinearSegmentedColormap.from_list("teal", ["#e6faf8", "#009e89"])
    im = ax.imshow(cm, interpolation="nearest", cmap=teal_cmap, aspect="auto")
    fig.colorbar(im, ax=ax, shrink=0.8)
    labels = ["Âm tính (0)", "Dương tính (1)"]
    ax.set_xticks([0, 1])
    ax.set_yticks([0, 1])
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Dự đoán", fontsize=12, fontweight="bold")
    ax.set_ylabel("Thực tế", fontsize=12, fontweight="bold")
    ax.set_title("Confusion Matrix — Holdout Test Set", pad=16)
    for i in range(2):
        for j in range(2):
            cell_labels = [["TN", "FP"], ["FN", "TP"]]
            text_color = "white" if cm[i, j] > cm.max() / 2 else "#1e293b"
            ax.text(j, i, f"{cell_labels[i][j]}\n{cm[i, j]}",
                    ha="center", va="center", fontsize=16, fontweight="bold", color=text_color)
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_confusion_matrix.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # ── 2. ROC Curve ──
    fig, ax = plt.subplots(figsize=(7, 6))
    fpr, tpr, _ = roc_curve(y_test, test_proba)
    auc_val = roc_auc_score(y_test, test_proba)
    ax.fill_between(fpr, tpr, alpha=0.15, color=TEAL)
    ax.plot(fpr, tpr, color=TEAL, linewidth=2.5, label=f"ROC (AUC = {auc_val:.4f})")
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.4, label="Random (AUC = 0.5)")
    ax.set_xlabel("Tỷ lệ dương tính giả (FPR)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Tỷ lệ dương tính đúng (TPR)", fontsize=12, fontweight="bold")
    ax.set_title("ROC Curve — Holdout Test Set", pad=16)
    ax.legend(loc="lower right", fontsize=11, framealpha=0.9)
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.05)
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_roc_curve.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # ── 3. Precision-Recall Curve ──
    fig, ax = plt.subplots(figsize=(7, 6))
    prec_vals, rec_vals, _ = precision_recall_curve(y_test, test_proba)
    ap = average_precision_score(y_test, test_proba)
    ax.fill_between(rec_vals, prec_vals, alpha=0.15, color=BLUE)
    ax.plot(rec_vals, prec_vals, color=BLUE, linewidth=2.5, label=f"PR (AP = {ap:.4f})")
    ax.set_xlabel("Recall (Sensitivity)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Precision", fontsize=12, fontweight="bold")
    ax.set_title("Precision-Recall Curve — Holdout Test Set", pad=16)
    ax.legend(loc="lower left", fontsize=11, framealpha=0.9)
    ax.set_xlim(-0.02, 1.05)
    ax.set_ylim(-0.02, 1.05)
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_precision_recall.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # ── 4. Feature Importance (Logistic Regression coefficients) ──
    fig, ax = plt.subplots(figsize=(8, 5))
    coefs = final_model.named_steps["classifier"].coef_[0]
    feature_names = [FEATURE_LABELS.get(f, f) for f in MODEL_FEATURES]
    sorted_idx = np.argsort(np.abs(coefs))
    colors = [TEAL if c >= 0 else CORAL for c in coefs[sorted_idx]]
    bars = ax.barh(range(len(coefs)), coefs[sorted_idx], color=colors, edgecolor="white", height=0.6)
    ax.set_yticks(range(len(coefs)))
    ax.set_yticklabels([feature_names[i] for i in sorted_idx], fontsize=11)
    ax.set_xlabel("Hệ số (Coefficient)", fontsize=12, fontweight="bold")
    ax.set_title("Feature Importance — Logistic Regression Coefficients", pad=16)
    ax.axvline(x=0, color="#94a3b8", linewidth=0.8)
    for bar, val in zip(bars, coefs[sorted_idx]):
        x_pos = bar.get_width()
        ax.text(x_pos + 0.02 * np.sign(x_pos), bar.get_y() + bar.get_height() / 2,
                f"{val:.3f}", va="center", ha="left" if val >= 0 else "right",
                fontsize=10, fontweight="bold", color="#334155")
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_feature_importance.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # ── 5. Cross-Validation Summary Bar Chart ──
    fig, ax = plt.subplots(figsize=(8, 5))
    metric_names = ["ROC AUC", "Average\nPrecision", "Brier Score"]
    means = [
        cv_summary["roc_auc"]["mean"],
        cv_summary["average_precision"]["mean"],
        cv_summary["brier_score"]["mean"],
    ]
    ranges_low = [
        cv_summary["roc_auc"]["range"][0],
        cv_summary["average_precision"]["range"][0],
        cv_summary["brier_score"]["range"][0],
    ]
    ranges_high = [
        cv_summary["roc_auc"]["range"][1],
        cv_summary["average_precision"]["range"][1],
        cv_summary["brier_score"]["range"][1],
    ]
    errors = [[m - lo for m, lo in zip(means, ranges_low)],
              [hi - m for m, hi in zip(means, ranges_high)]]
    bar_colors = [TEAL, BLUE, AMBER]
    bars = ax.bar(metric_names, means, color=bar_colors, edgecolor="white",
                  width=0.5, yerr=errors, capsize=8, error_kw={"linewidth": 2, "color": "#475569"})
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f"{val:.4f}", ha="center", va="bottom", fontsize=12, fontweight="bold", color="#1e293b")
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Giá trị", fontsize=12, fontweight="bold")
    ax.set_title(f"Cross-Validation ({cv_summary['folds']}-Fold) — Mean ± Range", pad=16)
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_cross_validation.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    # ── 6. Dataset Distribution ──
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    # Pie chart
    pos = int(y.sum())
    neg = int((1 - y).sum())
    wedges, texts, autotexts = axes[0].pie(
        [neg, pos], labels=["Âm tính (0)", "Dương tính (1)"],
        colors=[TEAL_LIGHT, CORAL], autopct="%1.1f%%",
        startangle=90, textprops={"fontsize": 12},
        wedgeprops={"edgecolor": "white", "linewidth": 2}
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_color("white")
    axes[0].set_title("Phân bố Outcome", fontsize=14, fontweight="bold", pad=16)

    # Feature box plots
    bp = axes[1].boxplot(
        [x[:, i] for i in range(x.shape[1])],
        labels=[FEATURE_LABELS.get(f, f) for f in MODEL_FEATURES],
        patch_artist=True, widths=0.5,
        medianprops={"color": "#1e293b", "linewidth": 2},
    )
    box_colors = [TEAL, BLUE, AMBER, CORAL, TEAL_LIGHT, SLATE]
    for patch, color in zip(bp["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
        patch.set_edgecolor("#64748b")
    axes[1].set_title("Phân bố đặc trưng (Box Plot)", fontsize=14, fontweight="bold", pad=16)
    axes[1].set_ylabel("Giá trị", fontsize=11)
    axes[1].tick_params(axis="x", labelsize=9)
    fig.tight_layout()
    p = OUTPUT_DIR / "chart_dataset_distribution.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(p)

    return saved


def main() -> None:
    x, y, rows = load_dataset(DATA_PATH)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=RANDOM_STATE
    )

    # Evaluation is isolated from all preprocessing and fitting steps.
    evaluation_model = build_pipeline().fit(x_train, y_train)
    test_probabilities = evaluation_model.predict_proba(x_test)[:, 1]

    # Final artifact is refit on all available development data after evaluation.
    final_model = build_pipeline().fit(x, y)
    feature_bounds = {
        feature: {"min": float(x[:, index].min()), "max": float(x[:, index].max())}
        for index, feature in enumerate(MODEL_FEATURES)
    }
    data_sha256 = hashlib.sha256(DATA_PATH.read_bytes()).hexdigest()

    cv_summary = cross_validation_summary(x, y)

    metadata = {
        "model_version": "icu-risk-research-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_type": "standardized_logistic_regression",
        "feature_order": list(MODEL_FEATURES),
        "excluded_feature": {
            "name": "sofa",
            "reason": "SOFA is a composite of organ-system measures already represented by the raw inputs.",
        },
        "target": {
            "source_column": "Outcome",
            "definition": "Unknown in the supplied dataset; must be explicitly defined before clinical validation.",
            "prediction_horizon": "Unknown; no 24-hour, 48-hour, mortality, or deterioration claim is permitted.",
        },
        "dataset": {
            "file": DATA_PATH.name,
            "sha256": data_sha256,
            "rows": int(len(rows)),
            "positive_cases": int(y.sum()),
            "negative_cases": int((1 - y).sum()),
            "provenance": "Unverified / demonstration dataset",
        },
        "input_plausibility_limits": {
            key: {"min": value.minimum, "max": value.maximum} for key, value in INPUT_LIMITS.items()
        },
        "training_feature_bounds": feature_bounds,
        "evaluation": {
            "holdout": {"test_rows": int(len(y_test)), "threshold": 0.5, "metrics": binary_metrics(y_test, test_probabilities)},
            "cross_validation": cv_summary,
        },
        "clinical_use": {
            "status": "research_prototype_only",
            "prohibited_claims": [
                "clinical accuracy", "mortality prediction", "deterioration within a stated time horizon", "treatment recommendation"
            ],
            "required_before_clinical_use": [
                "clinician-defined target and cohort", "approved de-identified data", "temporal and external validation",
                "calibration and threshold governance", "privacy, security, and regulatory review"
            ],
        },
    }
    artifact = {"pipeline": final_model, "metadata": metadata}
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"✅ Saved model  : {MODEL_PATH}")
    print(f"✅ Saved report : {REPORT_PATH}")

    # Generate evaluation charts
    print("\n📊 Generating evaluation charts...")
    chart_paths = generate_evaluation_charts(
        y_test, test_probabilities, x, y, final_model, cv_summary,
    )
    for cp in chart_paths:
        print(f"   📈 {cp.name}")
    print(f"\n🎉 Done! {len(chart_paths)} charts saved to {OUTPUT_DIR}/")
    print("   Clinical use status: research prototype only")


if __name__ == "__main__":
    main()

