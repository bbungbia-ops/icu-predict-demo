import unittest
from pathlib import Path

from models.clinical_schema import InputValidationError, MODEL_FEATURES
from models.ml_model import ICUPredictor


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_DIR / "ai_model" / "icu_risk_model.joblib"


class RiskModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.predictor = ICUPredictor(MODEL_PATH)

    def test_model_excludes_composite_sofa_from_feature_vector(self):
        self.assertEqual(tuple(self.predictor.metadata["feature_order"]), MODEL_FEATURES)
        self.assertNotIn("sofa", self.predictor.metadata["feature_order"])

    def test_valid_input_returns_traceable_research_assessment(self):
        result = self.predictor.predict(4, 80, 300, 0.9, 1.0, 250, 14)
        self.assertGreaterEqual(result["risk_score"], 0)
        self.assertLessEqual(result["risk_score"], 100)
        self.assertEqual(result["model_status"], "research_prototype_only")
        self.assertIn("model_version", result)
        self.assertTrue(result["warnings"])
        self.assertIn(result["signal"]["key"], {"high", "medium", "low"})
        self.assertNotIn("xác suất", result["signal"]["label"].lower())

    def test_invalid_gcs_is_rejected(self):
        with self.assertRaises(InputValidationError):
            self.predictor.predict(2, 85, 350, 0.5, 0.7, 280, 16)

    def test_input_outside_training_range_is_flagged(self):
        result = self.predictor.predict(4, 120, 300, 0.9, 1.0, 250, 14)
        self.assertTrue(result["out_of_distribution"])
        self.assertEqual(result["out_of_distribution"][0]["feature"], "map_value")


if __name__ == "__main__":
    unittest.main()
