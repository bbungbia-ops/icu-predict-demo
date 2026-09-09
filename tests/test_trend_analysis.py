import unittest

from models.trend_analysis import build_trend_summary


class TrendAnalysisTests(unittest.TestCase):
    def test_compares_only_explicitly_timestamped_prior_samples(self):
        current = {
            'measurement_time': '2026-09-09T12:00', 'sofa': 8, 'map_value': 65,
            'pao2_fio2': 180,
        }
        previous = [
            {'measurement_time': '2026-09-09T06:00', 'sofa': 6, 'map_value': 70, 'pao2_fio2': 220},
            {'measurement_time': None, 'sofa': 2, 'map_value': 110, 'pao2_fio2': 500},
        ]
        summary = build_trend_summary(current, previous)
        self.assertTrue(summary['available'])
        window = summary['windows'][0]
        self.assertTrue(window['available'])
        self.assertEqual(window['observed_hours'], 6.0)
        self.assertEqual(window['changes'][0]['delta'], 2.0)
        self.assertEqual(window['changes'][1]['delta'], -5.0)

    def test_refuses_to_make_a_trend_without_collection_time(self):
        summary = build_trend_summary({'sofa': 8}, [])
        self.assertFalse(summary['available'])
        self.assertIn('thời điểm lấy mẫu', summary['reason'])
