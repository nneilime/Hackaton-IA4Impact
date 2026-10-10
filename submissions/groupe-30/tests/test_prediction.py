"""Check the multi-horizon prediction contract without trained models."""

import unittest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts.predict_equipment import predict_equipment, recommended_action, predict_failure_types
from scripts.build_monthly_training_table import failure_after
from scripts.train_failure_model import NON_FEATURE_COLUMNS
from datetime import timedelta


class PredictionTests(unittest.TestCase):
    def test_future_symptoms_are_never_input_features(self):
        self.assertIn('target_failure_symptom', NON_FEATURE_COLUMNS)
        self.assertIn('target_failure_intervention', NON_FEATURE_COLUMNS)

    def test_next_failure_excludes_preventive_and_horizon_boundary(self):
        snapshot = datetime(2025, 1, 1)
        events = [
            {'_timestamp': snapshot, 'type_intervention': 'Entretien préventif'},
            {'_timestamp': snapshot + timedelta(days=5), 'type_intervention': 'Dépannage', 'symptome': 'Fuite'},
            {'_timestamp': snapshot + timedelta(days=90), 'type_intervention': 'Remplacement'},
        ]
        self.assertEqual(failure_after(events, snapshot, timedelta(days=90))['symptome'], 'Fuite')
        self.assertIsNone(failure_after(events[2:], snapshot, timedelta(days=90)))

    def test_conditional_joint_probabilities_and_cost(self):
        folder = 'models'
        manifest = {'families': {'test': {'status': 'trained', 'model_file': 'test.cbm'}}}
        with patch.object(Path, 'read_text', return_value=json.dumps(manifest)):
            with patch('scripts.predict_equipment.CatBoostClassifier') as classifier:
                model = classifier.return_value
                model.feature_names_ = ['famille']
                model.get_cat_feature_indices.return_value = [0]
                model.classes_ = [json.dumps(['Dépannage', 'Fuite']), json.dumps(['Remplacement', 'Non renseigné'])]
                model.predict_proba.return_value = [[0.75, 0.25]]
                prices = {('test', 'Dépannage', 'Fuite'): 100, ('test', 'Remplacement', 'Non renseigné'): 500}
                result = predict_failure_types({'famille': 'test'}, 'test', 90, Path(folder), 0.4, prices)
                self.assertEqual(result['predictions'][0]['joint_probability'], 0.3)
                self.assertEqual(result['expected_price_if_failure'], 200)
                self.assertEqual(result['expected_cost_within_horizon'], 80)
                missing = predict_failure_types({'famille': 'test'}, 'test', 90, Path(folder), 0.4, {})
                self.assertIsNone(missing['expected_cost_within_horizon'])

    def test_all_horizons_use_their_own_models_and_thresholds(self):
        item = {"residence_id": "RES-A", "batiment_id": "BAT-A1", "libelle_famille": "Test", "famille": "test"}
        scores = [(0.1, 0.5), (0.2, 0.6), (0.7, 0.65), (0.8, 0.75)]
        with patch("scripts.predict_equipment.load_history", return_value=(item, [], [])), \
             patch("scripts.predict_equipment.build_feature_row", return_value={}), \
             patch("scripts.predict_equipment.load_prediction", side_effect=scores) as load, \
             patch("scripts.predict_equipment.read_csv", return_value=[]), \
             patch("scripts.predict_equipment.predict_failure_types", return_value={}) as types:
            result = predict_equipment("EQP-1", datetime(2025, 1, 1), artifacts_dir=Path("models"))
        for call, horizon, (probability, threshold) in zip(load.call_args_list, (90, 180, 365, 730), scores):
            self.assertEqual(call.args[0], Path("models") / f"{horizon}d" / f"catboost_failure_{horizon}d.cbm")
            self.assertEqual(result[f"failure_probability_{horizon}d"], probability)
            self.assertEqual(result[f"alert_threshold_{horizon}d"], threshold)
            self.assertEqual(result[f"predicted_alert_{horizon}d"], probability >= threshold)
        self.assertIn("douze", result["recommended_action"])
        self.assertEqual(types.call_count, 4)

    def test_shortest_alert_determines_action(self):
        self.assertIn("prioritaire", recommended_action(True, True, True, True))
        self.assertIn("six", recommended_action(False, True, True, True))
        self.assertIn("douze", recommended_action(False, False, True, True))
        self.assertIn("deux", recommended_action(False, False, False, True))
        self.assertIn("habituel", recommended_action(False, False, False, False))


if __name__ == "__main__":
    unittest.main()
