from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .common import ProtocolError
from .evaluate import verify_frozen
from .schema import normalize_columns


def predict_one(cfg: dict, path: str) -> dict:
    _, run, _, frozen = verify_frozen(cfg)
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProtocolError("Input must be a JSON object containing one completed flow's features.")
    frame = normalize_columns(pd.DataFrame([value]))
    features = frozen["feature_schema"]
    missing = set(features) - set(frame.columns)
    if missing:
        raise ProtocolError(f"Missing required features: {sorted(missing)}. Null is allowed for known missing values.")
    name = frozen["winner"]; entry = frozen["models"][name]
    pipeline = joblib.load(run / entry["file"])
    score = float(pipeline.predict_proba(frame[features])[0, 1])
    return {"label": "Attack" if score >= entry["threshold"] else "Normal",
            "model_score": score, "threshold": entry["threshold"], "model": name,
            "ignored_input_keys": sorted(set(frame.columns) - set(features)),
            "note": "Uncalibrated score. Requires completed-flow features; no raw-packet parsing."}

