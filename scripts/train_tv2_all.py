"""
Master Training and Evaluation Script for TV2 - Decision Tree (W3-01 & W3-02)

This script automates the complete training, hyperparameter tuning,
and test set evaluation for Decision Tree models under both:
1. W3-01: Time-based split (real-world chronological evaluation)
2. W3-02: Random split (data leakage control)

Usage:
    python scripts/train_tv2_all.py
"""

from __future__ import annotations
import sys
import json
import time
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd
import joblib

# Ensure src/ is in python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ids.tune_decision_tree import tune_decision_tree
from ids.evaluate_tuned_model import evaluate_on_test
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix, classification_report
)


def run_phase1_tuning():
    """Phase 1: RandomizedSearchCV tuning trên data/processed/ và đánh giá Test."""
    print("\n" + "=" * 80)
    print("PHASE 1: DECISION TREE TUNING & TEST EVALUATION (processed splits)")
    print("=" * 80)

    jobs = [
        {
            "name": "W3-01",
            "split_dir": ROOT / "data" / "processed" / "split_v1",
            "output_dir": ROOT / "experiments" / "w3_01_dt_time",
        },
        {
            "name": "W3-02",
            "split_dir": ROOT / "data" / "processed" / "random_split_v1",
            "output_dir": ROOT / "experiments" / "w3_02_dt_random",
        },
    ]

    for job in jobs:
        model_file = job["output_dir"] / "best_decision_tree_model.pkl"
        test_metrics = job["output_dir"] / "test_eval" / "test_metrics.json"

        if model_file.exists() and test_metrics.exists():
            print(f"\n[SKIP] {job['name']} already complete at {job['output_dir']}")
            continue

        if not job["split_dir"].exists():
            print(f"\n[WARN] {job['name']}: {job['split_dir']} not found. Skipping.")
            continue

        # Tuning
        print(f"\n>>> [{job['name']}] Tuning Decision Tree: {job['split_dir']}")
        tune_decision_tree(
            split_dir=job["split_dir"],
            output_dir=job["output_dir"],
            n_iter=50,
            random_state=42,
            with_port=False,
        )

        # Test evaluation
        print(f"\n>>> [{job['name']}] Evaluating on Test set...")
        evaluate_on_test(
            model_path=model_file,
            split_dir=job["split_dir"],
            output_dir=job["output_dir"] / "test_eval",
        )


def run_phase2_artifacts():
    """Phase 2: Huấn luyện trên data/model_ready/ và xuất artifacts TV2."""
    print("\n" + "=" * 80)
    print("PHASE 2: GENERATING TV2 DELIVERABLE ARTIFACTS (artifacts/TV2_decision_tree)")
    print("=" * 80)

    out_dir = ROOT / "artifacts" / "TV2_decision_tree"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_ready = ROOT / "data" / "model_ready"
    if not model_ready.exists():
        print(f"[WARN] {model_ready} does not exist. Skipping Phase 2.")
        return

    scenarios = [
        {"split": "time",   "scenario": "with_port", "job": "W3-01"},
        {"split": "random", "scenario": "with_port", "job": "W3-02"},
    ]

    val_records = []
    test_records = []

    for sc in scenarios:
        split = sc["split"]
        scenario = sc["scenario"]
        job = sc["job"]
        print(f"\n>>> [{job}] Processing {split}/{scenario}...")

        base = model_ready / split / scenario

        # --- Load data (dùng đúng tên file trong model_ready/) ---
        X_train = pd.read_csv(base / "X_train.csv")
        y_train = pd.read_csv(base / "y_train.csv")["BinaryLabel"].astype(int)

        X_val = pd.read_csv(base / "X_validation.csv")
        y_val = pd.read_csv(base / "y_validation.csv")["BinaryLabel"].astype(int)
        val_sub = pd.read_csv(base / "y_validation_subtype.csv")["Subtype"]

        # --- Grid search trên Validation ---
        grid = {
            "criterion": ["gini", "entropy"],
            "max_depth": [4, 6, 8, 12, None],
            "min_samples_leaf": [5, 10, 20],
        }

        best_score = -1.0
        best_cfg = None
        best_clf = None

        for crit in grid["criterion"]:
            for depth in grid["max_depth"]:
                for leaf in grid["min_samples_leaf"]:
                    clf = DecisionTreeClassifier(
                        criterion=crit,
                        max_depth=depth,
                        min_samples_leaf=leaf,
                        class_weight="balanced",
                        random_state=42,
                    )
                    clf.fit(X_train, y_train)
                    val_pred = clf.predict(X_val)
                    f1 = f1_score(y_val, val_pred, zero_division=0)

                    if f1 > best_score:
                        best_score = f1
                        best_cfg = (crit, depth, leaf)
                        best_clf = clf

        print(f"  Best Val F1 = {best_score:.4f}"
              f" (criterion={best_cfg[0]}, max_depth={best_cfg[1]},"
              f" min_samples_leaf={best_cfg[2]})")

        # Save model
        joblib_path = out_dir / f"dt_{split}_{scenario}.joblib"
        joblib.dump(best_clf, joblib_path)
        print(f"  Saved model → {joblib_path.name}")

        # --- Validation metrics ---
        val_pred = best_clf.predict(X_val)
        val_proba = best_clf.predict_proba(X_val)[:, 1]
        val_records.append({
            "job": job, "split": split, "scenario": scenario,
            "criterion": best_cfg[0],
            "max_depth": best_cfg[1],
            "min_samples_leaf": best_cfg[2],
            "val_f1": round(f1_score(y_val, val_pred, zero_division=0), 4),
            "val_precision": round(precision_score(y_val, val_pred, zero_division=0), 4),
            "val_recall": round(recall_score(y_val, val_pred, zero_division=0), 4),
            "val_accuracy": round(accuracy_score(y_val, val_pred), 4),
            "val_roc_auc": round(roc_auc_score(y_val, val_proba), 4),
            "val_avg_precision": round(average_precision_score(y_val, val_proba), 4),
        })

        # --- Test set evaluation ---
        X_test = pd.read_csv(base / "X_test.csv")
        y_test = pd.read_csv(base / "y_test.csv")["BinaryLabel"].astype(int)
        test_sub = pd.read_csv(base / "y_test_subtype.csv")["Subtype"]

        test_pred = best_clf.predict(X_test)
        test_proba = best_clf.predict_proba(X_test)[:, 1]

        # Subtype recalls
        ssh_mask = (test_sub == "SSH-Patator")
        ftp_mask = (test_sub == "FTP-Patator")
        ssh_rec = float(test_pred[ssh_mask].mean()) if ssh_mask.any() else None
        ftp_rec = float(test_pred[ftp_mask].mean()) if ftp_mask.any() else None

        tn, fp, fn, tp = confusion_matrix(y_test, test_pred, labels=[0, 1]).ravel()

        test_records.append({
            "job": job, "split": split, "scenario": scenario,
            "criterion": best_cfg[0],
            "max_depth": best_cfg[1],
            "min_samples_leaf": best_cfg[2],
            "accuracy": round(accuracy_score(y_test, test_pred), 4),
            "precision": round(precision_score(y_test, test_pred, zero_division=0), 4),
            "recall": round(recall_score(y_test, test_pred, zero_division=0), 4),
            "f1_score": round(f1_score(y_test, test_pred, zero_division=0), 4),
            "fpr": round(float(fp / (fp + tn)), 6) if (fp + tn) > 0 else 0.0,
            "roc_auc": round(roc_auc_score(y_test, test_proba), 4),
            "avg_precision": round(average_precision_score(y_test, test_proba), 4),
            "ftp_recall": ftp_rec,
            "ssh_recall": ssh_rec,
        })
        print(f"  Test F1 = {f1_score(y_test, test_pred, zero_division=0):.4f}"
              f" | SSH Recall={ssh_rec} | FTP Recall={ftp_rec}")

    # --- Export CSV & JSON artifacts ---
    pd.DataFrame(val_records).to_csv(out_dir / "dt_validation_results.csv", index=False)
    pd.DataFrame(test_records).to_csv(out_dir / "dt_test_results.csv", index=False)

    final_params = {
        "author": "TV2 (Decision Tree Lead)",
        "timestamp": datetime.now().isoformat(),
        "models": {r["job"]: r for r in test_records},
        "note": (
            "W3-01 Time-based: zero-shot transfer challenge (Train=FTP only, Test=SSH only). "
            "W3-02 Random: control demonstrating data leakage inflates F1."
        ),
    }
    with open(out_dir / "dt_final_params.json", "w", encoding="utf-8") as f:
        json.dump(final_params, f, indent=2, ensure_ascii=False)

    print(f"\nAll TV2 artifacts saved to: {out_dir}")


def main():
    start_time = time.time()
    print("*" * 80)
    print("TV2 DECISION TREE — FULL TRAINING & EVALUATION PIPELINE")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("*" * 80)

    run_phase1_tuning()
    run_phase2_artifacts()

    elapsed = time.time() - start_time
    print("\n" + "*" * 80)
    print(f"ALL DONE IN {elapsed:.1f}s")
    print("*" * 80)


if __name__ == "__main__":
    main()
