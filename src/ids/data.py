from __future__ import annotations

from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from .common import ProtocolError, file_sha256, resolve, write_json
from .schema import LABELS, normalize_columns, pick_features


def parse_timestamps(values: pd.Series, formats: list[str], reconstruct_12h: bool = False) -> pd.Series:
    """Explicit formats only. Never infer dates from labels or CSV row order.

    If reconstruct_12h is True, raw hours 1-5 (afternoon without PM marker in CICIDS2017 Tuesday)
    are shifted by +12 hours (mapping to 13-17) independent of label or port.
    """
    result = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    values = values.astype("string").str.strip()
    for fmt in formats:
        pending = result.isna()
        result.loc[pending] = pd.to_datetime(values.loc[pending], format=fmt, errors="coerce")
    if result.isna().any():
        examples = values.loc[result.isna()].head(4).tolist()
        raise ProtocolError(f"Unparseable Timestamp values: {examples}. Specify exact formats; do not guess.")
    if reconstruct_12h:
        afternoon = result.dt.hour.between(1, 5)
        if afternoon.any():
            result.loc[afternoon] += pd.Timedelta(hours=12)
    return result


def numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)


def read_flows(cfg: dict) -> tuple[pd.DataFrame, list[str], dict]:
    path = resolve(cfg, cfg["input"]["csv"])
    if not path.is_file():
        raise ProtocolError(f"CSV missing: {path}. Read docs/DATA_AND_PROTOCOL.md.")
    sha = file_sha256(path)
    rows = []; raw_counts = Counter(); quality = Counter(); offset = 0
    features = None; ignored = None; source_columns = None
    reader = pd.read_csv(path, encoding=cfg["input"]["encoding"], dtype=str,
                         chunksize=cfg["input"]["chunksize"], on_bad_lines="error")
    try:
        for raw in reader:
            raw = normalize_columns(raw)
            needed = {"timestamp", "label", "flow_duration"}
            if not needed.issubset(raw.columns):
                raise ProtocolError(f"Missing {sorted(needed - set(raw.columns))}. Genuine Timestamp is required; row order is not time.")
            if features is None:
                features = pick_features(raw.columns, cfg["features"]["min_present"])
                ignored = sorted(set(raw.columns) - set(features))
                source_columns = list(raw.columns)
            labels = raw["label"].str.strip().str.upper()
            raw_counts.update(labels.fillna("<MISSING>").tolist())
            selected = labels.isin(LABELS)
            ordinal = np.arange(offset, offset + len(raw))[selected.to_numpy()]
            offset += len(raw)
            raw = raw.loc[selected].copy()
            if raw.empty:
                continue
            X = numeric_frame(raw[features])
            for name in features:
                quality[f"{name}:missing_after_numeric"] += int(X[name].isna().sum())
            duration = X["flow_duration"]
            if duration.isna().any() or (duration < 0).any():
                raise ProtocolError("Flow Duration has missing/nonfinite/negative values; cannot establish completion time. Investigate source before splitting.")
            if (duration > pd.Timedelta(days=1).total_seconds() * 1e6).any():
                raise ProtocolError("Flow Duration exceeds one day. Verify duration units/export.")
            reconstruct_12h = (
                cfg["input"].get("reconstruct_12h_afternoon", False)
                or "1-5" in str(cfg["input"].get("clock_basis", ""))
            )
            start = parse_timestamps(raw["timestamp"], cfg["input"]["timestamp_formats"], reconstruct_12h=reconstruct_12h)
            expected = cfg["input"].get("expected_date")
            if expected and not (start.dt.date == pd.Timestamp(expected).date()).all():
                raise ProtocolError(f"Timestamp dates disagree with expected_date={expected}. Check day/month order.")
            out = X.copy()
            out["_start"] = start
            precision = cfg["input"]["timestamp_precision_seconds"]
            if precision < 0:
                raise ProtocolError("timestamp_precision_seconds must be >= 0.")
            out["_end"] = start + pd.to_timedelta(duration, unit="us") + pd.Timedelta(seconds=precision)
            out["_label"] = labels.loc[selected]
            out["_target"] = out["_label"].map(LABELS).astype("int8")
            out["_row_id"] = [f"{sha[:16]}:{i}" for i in ordinal]
            # Record identity excludes Label: contradictory copies must stop the run.
            identity_cols = [c for c in raw.columns if c != "label" and not c.startswith("unnamed")]
            identity = raw[identity_cols].fillna("<NA>").apply(lambda s: s.str.strip())
            out["_record_hash"] = pd.util.hash_pandas_object(identity, index=False).astype("uint64")
            out["_feature_hash"] = pd.util.hash_pandas_object(X.astype("float64"), index=False).astype("uint64")
            rows.append(out)
    finally:
        reader.close()
    if not rows:
        raise ProtocolError("No BENIGN / FTP-Patator / SSH-Patator rows found.")
    frame = pd.concat(rows, ignore_index=True).sort_values(["_start", "_row_id"], kind="stable").reset_index(drop=True)
    summary = {
        "raw_sha256": sha, "raw_rows": offset, "selected_rows": len(frame),
        "excluded_rows": offset - len(frame), "raw_label_counts": dict(raw_counts),
        "feature_columns": features, "ignored_columns": ignored,
        "source_columns": source_columns, "numeric_quality_counts": dict(quality),
        "start_min": frame["_start"].min(), "start_max": frame["_start"].max(),
        "source_url": cfg["input"]["source_url"], "source_note": cfg["input"]["source_note"],
        "synthetic": cfg["input"]["synthetic"],
    }
    return frame, features, summary


def audit(cfg: dict) -> dict:
    frame, _, summary = read_flows(cfg)
    out = resolve(cfg, cfg["paths"]["run"]) / "audit"
    out.mkdir(parents=True, exist_ok=True)
    timeline = frame.groupby([frame["_start"].dt.floor("5min"), "_label"]).size().unstack(fill_value=0)
    timeline.to_csv(out / "timeline_5min.csv", index_label="timestamp")
    windows = frame.groupby("_label").agg(n=("_label", "size"), start=("_start", "min"), end=("_end", "max"))
    windows.to_csv(out / "label_windows.csv")
    summary["exact_record_duplicate_rows"] = int(frame["_record_hash"].duplicated().sum())
    summary["feature_duplicate_rows"] = int(frame["_feature_hash"].duplicated().sum())
    summary["clock_review_required"] = True
    summary["note"] = "Audit label/time support only; do not choose features or cutoffs from model scores. No constant-column selection here."
    write_json(out / "audit.json", summary)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    axes = timeline.plot(subplots=True, figsize=(11, 7), sharex=True, legend=True)
    for ax in np.atleast_1d(axes).ravel():
        ax.set_ylabel("Flow count")
    plt.suptitle("SYNTHETIC fixture" if cfg["input"]["synthetic"] else "Tuesday: label counts by 5-minute bin")
    plt.tight_layout()
    plt.savefig(out / "timeline.png", dpi=160)
    plt.close("all")
    return summary

