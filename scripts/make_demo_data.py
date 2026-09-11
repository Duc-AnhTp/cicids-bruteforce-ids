"""Generate synthetic plumbing-test data. Never use these metrics in the report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


def create_demo(destination: Path, core_only: bool = False, n: int = 5400) -> Path:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"Destination must be new/empty: {destination}")
    (destination / "data/raw").mkdir(parents=True, exist_ok=True)
    (destination / "configs").mkdir(parents=True, exist_ok=True)
    template = Path(__file__).resolve().parents[1] / "configs/experiment.yaml"
    cfg = yaml.safe_load(template.read_text(encoding="utf-8"))
    rng = np.random.default_rng(812)
    start = pd.date_range("2017-07-04 08:00:00", "2017-07-04 17:00:00", periods=n)
    minute = start.hour * 60 + start.minute
    ftp = (minute >= 9 * 60 + 20) & (minute < 10 * 60 + 20)
    ssh = (minute >= 14 * 60) & (minute < 15 * 60)
    attacking = rng.random(n) < 0.5
    labels = np.where(ftp & attacking, "FTP-Patator", np.where(ssh & attacking, "SSH-Patator", "BENIGN"))
    y = labels != "BENIGN"
    raw = pd.DataFrame({
        "Flow ID": [f"synthetic-flow-{i}" for i in range(n)],
        " Source IP": "192.0.2.1", " Destination IP": "192.0.2.2",
        " Source Port": rng.integers(10000, 60000, n),
        " Destination Port": np.where(ssh, 22, np.where(ftp, 21, 443)),
        " Protocol": 6, " Timestamp": start.strftime("%d/%m/%Y %H:%M:%S"),
        " Flow Duration": rng.integers(1000, 20_000_000, n),
        " Total Fwd Packets": rng.poisson(10 + y * 15, n),
        " Total Backward Packets": rng.poisson(8 + y * 4, n),
        " Total Length of Fwd Packets": rng.normal(700 + y * 250, 180, n).clip(0),
        " Total Length of Bwd Packets": rng.normal(650 - y * 100, 160, n).clip(0),
        " Fwd Packet Length Max": rng.normal(350 + y * 90, 65, n).clip(0),
        " Fwd Packet Length Min": rng.integers(0, 50, n),
        " Fwd Packet Length Mean": rng.normal(180 + y * 60, 60, n).clip(0),
        " Fwd Packet Length Std": rng.uniform(1, 80, n),
        " Bwd Packet Length Max": rng.normal(300, 50, n).clip(0),
        " Flow Bytes/s": rng.lognormal(6 + y * 0.5, 1, n),
        " ACK Flag Count": 1,
        " Idle Mean": np.nan,
        " target_leak_do_not_use": y.astype(int),
        " Label": labels,
    })
    raw.loc[10:15, " Flow Bytes/s"] = np.inf
    raw.loc[25:30, " Fwd Packet Length Mean"] = np.nan
    raw.loc[40:42, " Label"] = "DoS Hulk"  # Must be excluded, not relabelled.
    # A truly duplicated exported record, plus recurrent features with different IDs/time.
    raw = pd.concat([raw, raw.iloc[:8]], ignore_index=True)
    feature_cols = [c for c in raw if c not in ["Flow ID", " Source IP", " Destination IP", " Source Port", " Destination Port", " Protocol", " Timestamp", " Label", "target_leak_do_not_use"]]
    for later, earlier in [(n - 2, 2), (n - 3, 3)]:
        raw.loc[later, feature_cols] = raw.loc[earlier, feature_cols].to_numpy()
    raw = raw.sample(frac=1, random_state=cfg["seed"]).reset_index(drop=True)
    raw.to_csv(destination / "data/raw/synthetic_tuesday.csv", index=False)
    cfg["experiment_id"] = "synthetic_core" if core_only else "synthetic_full"
    cfg["input"].update(csv="data/raw/synthetic_tuesday.csv", synthetic=True,
                        source_url="synthetic://local-fixture", source_note="Deterministic generated fixture; not CICIDS2017",
                        clock_basis="Synthetic 24-hour clock on a fixed date", clock_reviewed=True,
                        timestamp_precision_seconds=1)
    cfg["features"]["min_present"] = 8
    cfg["split"].update(cutoffs_reviewed=True, cutoff_reason="Synthetic fixture windows only", min_per_binary_class=10)
    cfg["training"]["random_forest"].update(n_estimators=25, max_depth=6)
    cfg["training"]["xgboost"].update(n_estimators=30, max_depth=3)
    cfg["training"]["n_jobs"] = 1
    if core_only:
        cfg["training"]["models"] = ["decision_tree", "random_forest"]
    cfg["explain"]["max_rows"] = 25
    cfg["paths"].update(processed="data/processed/demo", run="artifacts/demo")
    config_path = destination / "configs/demo.yaml"
    config_path.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    sample = raw.iloc[100][feature_cols].to_dict()
    sample = {k: (None if pd.isna(v) or not np.isfinite(v) else float(v)) for k, v in sample.items()}
    (destination / "example_flow.json").write_text(json.dumps(sample, indent=2, allow_nan=False), encoding="utf-8")
    return config_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("demo_workspace"))
    parser.add_argument("--core-only", action="store_true", help="Explicitly test DT/RF only on SYNTHETIC data")
    args = parser.parse_args()
    print(create_demo(args.output, args.core_only))

