from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from ids.common import ProtocolError, load_config, read_json
from ids.data import parse_timestamps, read_flows
from ids.evaluate import build_report, score_test_once
from ids.metrics import binary_metrics, choose_threshold, subtype_recall
from ids.preprocess import make_pipeline
from ids.schema import normalize_columns, pick_features
from ids.split import load_partition, prepare, temporal_split
from ids.train import build_estimators, fit_models
from make_demo_data import create_demo


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "fixture"
        self.cfg = load_config(create_demo(self.root, core_only=True))

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_timestamp_does_not_fall_back_to_row_order(self):
        path = self.root / self.cfg["input"]["csv"]
        frame = pd.read_csv(path).drop(columns=[" Timestamp"])
        frame.to_csv(path, index=False)
        with self.assertRaisesRegex(ProtocolError, "Timestamp"):
            read_flows(self.cfg)

    def test_label_scope_and_identifier_allowlist(self):
        frame, features, info = read_flows(self.cfg)
        self.assertEqual(info["excluded_rows"], 3)
        self.assertEqual(set(frame["_label"]), {"BENIGN", "FTP-PATATOR", "SSH-PATATOR"})
        self.assertNotIn("target_leak_do_not_use", features)
        self.assertNotIn("destination_port", features)
        self.assertNotIn("timestamp", features)

    def test_date_format_is_explicit(self):
        parsed = parse_timestamps(pd.Series(["04/07/2017 14:00"]), ["%d/%m/%Y %H:%M"])
        self.assertEqual(parsed[0], pd.Timestamp("2017-07-04 14:00"))
        with self.assertRaises(ProtocolError):
            parse_timestamps(pd.Series(["not a timestamp"]), ["%d/%m/%Y %H:%M"])

    def test_reconstruct_12h_afternoon(self):
        parsed = parse_timestamps(
            pd.Series(["04/07/2017 01:30", "04/07/2017 09:15", "04/07/2017 14:00"]),
            ["%d/%m/%Y %H:%M"],
            reconstruct_12h=True
        )
        self.assertEqual(parsed[0], pd.Timestamp("2017-07-04 13:30"))
        self.assertEqual(parsed[1], pd.Timestamp("2017-07-04 09:15"))
        self.assertEqual(parsed[2], pd.Timestamp("2017-07-04 14:00"))

    def test_training_only_median_and_constant_selection(self):
        train = pd.DataFrame({"flow_duration": [1.0, 3.0, np.nan], "total_fwd_packets": [4, 4, 4]})
        val = pd.DataFrame({"flow_duration": [10000.0, np.nan], "total_fwd_packets": [1, 999]})
        pipe = make_pipeline(DecisionTreeClassifier(random_state=42)).fit(train, [0, 1, 0])
        transformed = pipe[:-1].transform(val)
        self.assertEqual(pipe.named_steps["columns"].keep_, ["flow_duration"])
        self.assertEqual(pipe.named_steps["imputer"].statistics_[0], 2.0)
        self.assertEqual(transformed[1, 0], 2.0)

    def test_preprocessing_rejects_numeric_label_column(self):
        with self.assertRaises(ProtocolError):
            make_pipeline(DecisionTreeClassifier()).fit(pd.DataFrame({"label": [0, 1]}), [0, 1])

    def test_boundary_crossing_flow_is_purged(self):
        frame, _, _ = read_flows(self.cfg)
        idx = frame.index[frame["_start"] < pd.Timestamp(self.cfg["split"]["train_end"])][-1]
        row_id = frame.loc[idx, "_row_id"]
        frame.loc[idx, "_end"] = pd.Timestamp("2017-07-04 14:25")
        parts, _ = temporal_split(frame, self.cfg["split"])
        self.assertFalse(any(row_id in set(p["_row_id"]) for p in parts.values()))
        self.assertLess(parts["train"]["_end"].max(), parts["validation"]["_start"].min())

    def test_single_class_partition_stops(self):
        frame, _, _ = read_flows(self.cfg)
        spec = dict(self.cfg["split"], train_end="2017-07-04 16:00", validation_end="2017-07-04 16:30")
        with self.assertRaisesRegex(ProtocolError, "binary support"):
            temporal_split(frame, spec)

    def test_duplicate_records_removed_but_recurring_feature_patterns_retained(self):
        frame, _, _ = read_flows(self.cfg)
        parts, diag = temporal_split(frame, self.cfg["split"])
        self.assertEqual(diag["duplicate_records_removed"], 8)
        self.assertGreaterEqual(int(parts["test"]["_seen_feature_in_earlier_split"].sum()), 2)
        self.assertEqual(set(parts["train"]["_row_id"]) & set(parts["test"]["_row_id"]), set())

    def test_conflicting_record_labels_stop(self):
        frame, _, _ = read_flows(self.cfg)
        duplicate = frame.iloc[[0]].copy()
        duplicate["_label"] = "SSH-PATATOR" if frame.iloc[0]["_label"] == "BENIGN" else "BENIGN"
        with self.assertRaisesRegex(ProtocolError, "conflicting"):
            temporal_split(pd.concat([frame, duplicate], ignore_index=True), self.cfg["split"])

    def test_undefined_subtype_recall_is_null(self):
        subtypes = subtype_recall(["SSH-PATATOR", "BENIGN"], [0.9, 0.1], 0.5)
        self.assertIsNone(subtypes["FTP-PATATOR"]["recall"])
        self.assertEqual(subtypes["SSH-PATATOR"]["recall"], 1.0)
        metrics = binary_metrics([0, 0], [0.1, 0.2], 0.5)
        self.assertIsNone(metrics["average_precision"])
        self.assertIsNone(metrics["recall_attack"])

    def test_threshold_tuning_uses_validation_targets(self):
        threshold, _ = choose_threshold([0, 1, 1], [0.1, 0.3, 0.4], [0.2, 0.5])
        self.assertEqual(threshold, 0.2)

    def test_prepare_requires_clock_and_cutoff_review(self):
        self.cfg["input"]["clock_reviewed"] = False
        with self.assertRaisesRegex(ProtocolError, "clock"):
            prepare(self.cfg)

    def test_partition_hash_detects_changed_bytes(self):
        manifest = prepare(self.cfg)
        processed = self.root / self.cfg["paths"]["processed"]
        with (processed / "validation.csv.gz").open("ab") as handle:
            handle.write(b"modified")
        with self.assertRaisesRegex(ProtocolError, "bytes changed"):
            load_partition(processed, manifest, "validation")

    def test_end_to_end_core_does_not_read_test_during_training_and_locks_after(self):
        prepare(self.cfg)
        original = load_partition
        def guarded(processed, manifest, name):
            self.assertNotEqual(name, "test", "Training must not load Test")
            return original(processed, manifest, name)
        with patch("ids.train.load_partition", side_effect=guarded):
            fit_models(self.cfg)
        first = score_test_once(self.cfg)
        self.assertFalse(first["cached"])
        with patch("ids.evaluate.load_partition", side_effect=AssertionError("No re-read")):
            second = score_test_once(self.cfg)
        self.assertTrue(second["cached"])
        self.assertEqual(first["winner"], second["winner"])
        self.assertTrue(Path(build_report(self.cfg)["report"]).is_file())
        with self.assertRaisesRegex(ProtocolError, "already opened"):
            fit_models(self.cfg)

    @unittest.skipUnless(importlib.util.find_spec("xgboost"), "xgboost unavailable; full three-model integration not verified")
    def test_full_three_model_experiment(self):
        self.cfg["training"]["models"] = ["decision_tree", "random_forest", "xgboost"]
        prepare(self.cfg); fit_models(self.cfg); result = score_test_once(self.cfg)
        self.assertIn(result["winner"], self.cfg["training"]["models"])

    @unittest.skipUnless(importlib.util.find_spec("shap"), "shap unavailable; actual explanation not verified")
    def test_shap_on_frozen_winner(self):
        from ids.explain import explain_winner
        prepare(self.cfg); fit_models(self.cfg)
        result = explain_winner(self.cfg)
        self.assertLess(result["max_additivity_error"], 1e-3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

