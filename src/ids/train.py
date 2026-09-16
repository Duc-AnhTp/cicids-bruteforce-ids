from __future__ import annotations

import time

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier

from .common import (ProtocolError, config_hash, environment, file_sha256,
                     require_unopened, write_json)
from .metrics import binary_metrics, choose_threshold, subtype_recall
from .preprocess import make_pipeline
from .split import check_manifest, load_partition

def build_estimators(cfg: dict, y_train) -> dict:
    p = cfg["training"]; seed = cfg["seed"]
    n0, n1 = int((y_train == 0).sum()), int((y_train == 1).sum())
    if not n0 or not n1:
        raise ProtocolError("Train needs both classes for class weights.")
    estimators = {
        "decision_tree": DecisionTreeClassifier(random_state=seed, class_weight="balanced", **p["decision_tree"]),
        "random_forest": RandomForestClassifier(random_state=seed, class_weight="balanced",
                                                n_jobs=p["n_jobs"], **p["random_forest"]),
    }
    if "xgboost" in p["models"]:
        try:
            from xgboost import XGBClassifier
        except ImportError as exc:
            raise ProtocolError("Install xgboost; the three-model experiment must not silently omit it.") from exc
        estimators["xgboost"] = XGBClassifier(objective="binary:logistic", eval_metric="logloss", tree_method="hist",
                                            device="cpu", random_state=seed, n_jobs=p["n_jobs"],
                                            scale_pos_weight=n0 / n1, **p["xgboost"])
    return {name: estimators[name] for name in p["models"]}


def fit_models(cfg: dict) -> dict:
    processed, run, manifest = check_manifest(cfg)
    require_unopened(run)
    if (run / "frozen.json").exists():
        raise ProtocolError("Models/thresholds are already frozen. Proceed to evaluate.")
    # Test partition is deliberately not loaded or hashed in this command.
    train = load_partition(processed, manifest, "train")
    val = load_partition(processed, manifest, "validation")
    features = manifest["features"]
    X, y = train[features], train["_target"]
    Xv, yv = val[features], val["_target"]
    estimators = build_estimators(cfg, y)
    model_dir = run / "models"; model_dir.mkdir(parents=True, exist_ok=True)
    entries = {}; comparison = []; all_thresholds = []
    for name in cfg["training"]["models"]:
        print(f"Training {name} on {len(train):,} rows / {len(features)} raw features", flush=True)
        pipeline = make_pipeline(estimators[name])
        started = time.perf_counter()
        pipeline.fit(X, y)
        seconds = time.perf_counter() - started
        scores = pipeline.predict_proba(Xv)[:, 1]
        threshold, grid = choose_threshold(yv, scores, cfg["training"]["thresholds"])
        metrics = binary_metrics(yv, scores, threshold)
        path = model_dir / f"{name}.joblib"
        joblib.dump(pipeline, path)
        entries[name] = {
            "file": path.relative_to(run).as_posix(), "sha256": file_sha256(path),
            "threshold": threshold, "validation": metrics,
            "validation_at_0_5": binary_metrics(yv, scores, 0.5),
            "validation_subtypes": subtype_recall(val["_label"], scores, threshold),
            "fit_seconds": seconds,
            "kept_features": pipeline.named_steps["columns"].keep_,
            "dropped_train_constant_or_missing": pipeline.named_steps["columns"].dropped_,
            "hyperparameters": {**cfg["training"][name], "random_state": cfg["seed"],
                                 "weighting": "balanced" if name != "xgboost" else float((y == 0).sum() / (y == 1).sum())},
        }
        comparison.append({"model": name, "fit_seconds": seconds, **metrics})
        all_thresholds.extend({"model": name, **row} for row in grid)
    # Stable order breaks an exact tie; never examine Test to choose the winner.
    winner = max(cfg["training"]["models"], key=lambda n: (entries[n]["validation"]["f1_attack"],
                                            entries[n]["validation"]["average_precision"],
                                            -entries[n]["validation"]["fpr"]))
    frozen = {
        "winner": winner, "selection": "validation F1, then AP, then lower FPR, then declared model order",
        "config_sha256": config_hash(cfg), "manifest_sha256": file_sha256(processed / "manifest.json"),
        "models": entries, "feature_schema": features,
        "train_counts": y.value_counts().to_dict(), "train_only_fit": True,
        "refit_train_plus_validation": False, "environment": environment(),
        "synthetic": cfg["input"]["synthetic"],
        "score_note": "predict_proba outputs are uncalibrated model scores, not validated attack probabilities",
    }
    pd.DataFrame(comparison).to_csv(run / "validation_comparison.csv", index=False)
    pd.DataFrame(all_thresholds).to_csv(run / "validation_thresholds.csv", index=False)
    write_json(run / "frozen.json", frozen)
    return {"winner": winner, "validation": entries[winner]["validation"], "synthetic": frozen["synthetic"]}
