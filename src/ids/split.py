from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import (ProtocolError, code_hash, config_hash, environment, file_sha256,
                     locations, public_config, read_json, require_unopened, write_json)
from .data import read_flows


def temporal_split(frame: pd.DataFrame, spec: dict) -> tuple[dict, dict]:
    a, b = pd.Timestamp(spec["train_end"]), pd.Timestamp(spec["validation_end"])
    gap = pd.Timedelta(seconds=spec["embargo_seconds"])
    if not a < b or gap < pd.Timedelta(0) or a + gap >= b:
        raise ProtocolError("Cutoffs/embargo do not define three ordered, nonempty periods.")
    # Local duplicate integrity checking; never remove all copies using future labels.
    conflicts = frame.groupby("_record_hash")["_label"].nunique()
    if (conflicts > 1).any():
        raise ProtocolError("Identical records have conflicting labels. Resolve provenance; no majority-vote relabeling.")
    before = len(frame)
    frame = frame.sort_values(["_start", "_row_id"], kind="stable").drop_duplicates("_record_hash", keep="first").copy()
    masks = {
        "train": frame["_end"] < a,
        "validation": (frame["_start"] >= a + gap) & (frame["_end"] < b),
        "test": frame["_start"] >= b + gap,
    }
    parts = {name: frame.loc[mask].reset_index(drop=True) for name, mask in masks.items()}
    for name, part in parts.items():
        counts = part["_target"].value_counts()
        if any(counts.get(label, 0) < spec["min_per_binary_class"] for label in [0, 1]):
            raise ProtocolError(f"{name}: insufficient binary support {counts.to_dict()}. Inspect timeline; never silently fall back to random split.")
    if not parts["train"]["_end"].max() < parts["validation"]["_start"].min():
        raise ProtocolError("Train flows overlap the validation period.")
    if not parts["validation"]["_end"].max() < parts["test"]["_start"].min():
        raise ProtocolError("Validation flows overlap the test period.")
    seen = set()
    for name, part in parts.items():
        part["_seen_feature_in_earlier_split"] = part["_feature_hash"].isin(seen)
        seen.update(part["_feature_hash"].tolist())
    kept_ids = set().union(*(set(p["_row_id"]) for p in parts.values()))
    purged = frame.loc[~frame["_row_id"].isin(kept_ids), ["_row_id", "_start", "_end", "_label"]]
    diagnostic = {
        "duplicate_records_removed": before - len(frame),
        "boundary_or_embargo_rows_removed": len(purged),
        "purged_label_counts": purged["_label"].value_counts().to_dict(),
        "population_policy": "Exact full-record copies deduplicated; repeated feature patterns retained and flagged, not deleted from test.",
        "split_counts": {name: {
            "n": len(p), "labels": p["_label"].value_counts().to_dict(),
            "start_min": p["_start"].min(), "start_max": p["_start"].max(),
            "completion_max_conservative": p["_end"].max(),
            "feature_seen_earlier": int(p["_seen_feature_in_earlier_split"].sum()),
        } for name, p in parts.items()},
    }
    return parts, diagnostic


def prepare(cfg: dict) -> dict:
    processed, run = locations(cfg)
    require_unopened(run)
    if (processed / "manifest.json").exists() or (run / "frozen.json").exists():
        raise ProtocolError("Prepared/frozen experiment exists. Reuse it; do not overwrite shared splits.")
    if not cfg["input"]["clock_reviewed"] or not cfg["split"]["cutoffs_reviewed"]:
        raise ProtocolError("Run audit; document clock and cutoffs in config before prepare. Example cutoffs are not approved data facts.")
    if any("REPLACE" in str(v) for v in [cfg["input"]["clock_basis"], cfg["input"]["source_note"], cfg["split"]["cutoff_reason"]]):
        raise ProtocolError("Fill source_note, clock_basis and cutoff_reason with observed evidence.")
    frame, features, raw_summary = read_flows(cfg)
    parts, diagnostic = temporal_split(frame, cfg["split"])
    processed.mkdir(parents=True, exist_ok=True); run.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for name, part in parts.items():
        path = processed / f"{name}.csv.gz"
        part.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})
        hashes[path.name] = file_sha256(path)
    manifest = {
        "config_sha256": config_hash(cfg), "code_sha256": code_hash(),
        "config": public_config(cfg), "files": hashes, "features": features,
        "raw": raw_summary, "split": diagnostic, "environment": environment(),
        "limitations": [
            "Same day, same capture environment; campaign independence is not established.",
            "Binary support does not imply both FTP and SSH are represented in every split.",
            "Label/time audit was used before freezing cutoffs; this is a retrospective design.",
            "Embargo is an engineering buffer, not a proven independence interval.",
        ],
    }
    write_json(processed / "manifest.json", manifest)
    write_json(run / "split_summary.json", diagnostic)
    write_json(run / "environment.json", environment())
    return manifest


def check_manifest(cfg: dict) -> tuple[Path, Path, dict]:
    processed, run = locations(cfg)
    path = processed / "manifest.json"
    if not path.exists():
        raise ProtocolError("No prepared dataset. Run prepare first.")
    manifest = read_json(path)
    if manifest["config_sha256"] != config_hash(cfg):
        raise ProtocolError("Config changed after prepare; restore the frozen config.")
    if manifest["code_sha256"] != code_hash():
        raise ProtocolError("Source code changed after prepare; restore code or document a new experiment before opening Test.")
    return processed, run, manifest


def load_partition(processed: Path, manifest: dict, name: str) -> pd.DataFrame:
    if name not in {"train", "validation", "test"}:
        raise ProtocolError("Unknown split.")
    path = processed / f"{name}.csv.gz"
    if file_sha256(path) != manifest["files"][path.name]:
        raise ProtocolError(f"{name} partition bytes changed. Shared splits must be immutable.")
    return pd.read_csv(path, parse_dates=["_start", "_end"], float_precision="round_trip",
                       dtype={"_record_hash": "uint64", "_feature_hash": "uint64", "_target": "int8"})
