"""
Prepare Random Split (control / đối chứng) for CICIDS2017 Tuesday.

Protocol §5.2: Random split is a mandatory control that uses the same
pipeline/features but shuffles data instead of splitting by time.
Results from Random split are NOT the primary result.

This script reuses the same cleaning steps as prepare_splits.py
(schema, label scope, timestamp, duration, duplicates, infinity).
"""

from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


# ============================================================
# CONFIG — must match prepare_splits.py
# ============================================================

def resolve_data_path() -> Path:
    candidates = [
        Path("data/raw/Tuesday-WorkingHours.pcap_ISCX.csv"),
        Path("data/raw/cicids2017/GeneratedLabelledFlows/Tuesday-WorkingHours.pcap_ISCX.csv"),
    ]
    cfg_file = Path("configs/experiment.yaml")
    if cfg_file.exists():
        try:
            import yaml
            with cfg_file.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            if "input" in cfg and "csv" in cfg["input"]:
                candidates.insert(0, Path(cfg["input"]["csv"]))
        except Exception:
            pass
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]

DATA_PATH = resolve_data_path()

OUTPUT_DIR = Path(
    "data/processed/random_split_v1"
)

SOURCE_SHA256_EXPECTED = (
    "ae9c88e10c41a8eb1ff454ae98bc513454925097"
    "d0b0b57180f94e79de445815"
)

SEED = 42

Q_SECONDS = 60

VALID_LABELS = {
    "BENIGN",
    "FTP-Patator",
    "SSH-Patator",
}


# ============================================================
# UTILITIES — same as prepare_splits.py
# ============================================================

def sha256_file(path: Path, chunk_size=1024 * 1024) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)

    return h.hexdigest()


def reconstruct_timestamp(raw_timestamp: pd.Series) -> pd.Series:
    """
    Reconstruct Tuesday CICIDS2017 timestamp.
    Same policy as prepare_splits.py.
    """

    raw = raw_timestamp.astype(str).str.strip()

    parts = raw.str.extract(
        r"(?P<day>\d{1,2})/"
        r"(?P<month>\d{1,2})/"
        r"(?P<year>\d{4}) "
        r"(?P<hour>\d{1,2}):"
        r"(?P<minute>\d{2})"
    )

    for col in ["day", "month", "year", "hour", "minute"]:
        parts[col] = pd.to_numeric(
            parts[col],
            errors="coerce"
        )

    if parts.isna().any(axis=1).any():
        n_failed = int(parts.isna().any(axis=1).sum())
        raise ValueError(
            f"Timestamp parse failed for {n_failed} rows."
        )

    observed_hours = set(
        parts["hour"].astype(int).unique()
    )

    allowed_hours = {
        1, 2, 3, 4, 5,
        8, 9, 10, 11, 12,
    }

    unexpected = observed_hours - allowed_hours

    if unexpected:
        raise ValueError(
            "Unexpected raw hour values found: "
            f"{sorted(unexpected)}"
        )

    hour24 = parts["hour"].copy()

    afternoon = hour24.between(1, 5)
    hour24.loc[afternoon] += 12

    timestamp_fixed = pd.to_datetime(
        {
            "year": parts["year"],
            "month": parts["month"],
            "day": parts["day"],
            "hour": hour24,
            "minute": parts["minute"],
        },
        errors="raise",
    )

    return timestamp_fixed


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 80)
    print("PREPARE CICIDS2017 TUESDAY - RANDOM SPLIT V1")
    print("(Control split -- protocol section 5.2)")
    print("=" * 80)

    # --------------------------------------------------------
    # 1. Verify source
    # --------------------------------------------------------

    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Source file not found: {DATA_PATH}"
        )

    actual_hash = sha256_file(DATA_PATH)

    print("\n[1] SOURCE")
    print("Path:", DATA_PATH)
    print("SHA256:", actual_hash)

    if actual_hash != SOURCE_SHA256_EXPECTED:
        raise ValueError(
            "Source SHA256 does not match audited file.\n"
            f"Expected: {SOURCE_SHA256_EXPECTED}\n"
            f"Actual:   {actual_hash}"
        )

    # --------------------------------------------------------
    # 2. Load and clean (same as prepare_splits.py)
    # --------------------------------------------------------

    print("\n[2] LOAD & CLEAN")

    df = pd.read_csv(DATA_PATH)
    df.columns = df.columns.astype(str).str.strip()

    print("Rows raw:", len(df))

    # Label scope
    df["Label"] = (
        df["Label"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Label"].isin(VALID_LABELS)
    ].copy()

    # Subtype and binary label
    df["Subtype"] = df["Label"]

    df["BinaryLabel"] = (
        df["Label"]
        .isin(["FTP-Patator", "SSH-Patator"])
        .astype("int8")
    )

    # Timestamp
    df["Timestamp_fixed"] = reconstruct_timestamp(
        df["Timestamp"]
    )
    df["StartTime"] = df["Timestamp_fixed"]

    # Flow Duration validation
    duration = pd.to_numeric(
        df["Flow Duration"],
        errors="coerce"
    )

    invalid_duration = (
        duration.isna()
        | (duration < 0)
    )

    df = df.loc[
        ~invalid_duration
    ].copy()

    df["Flow Duration"] = pd.to_numeric(
        df["Flow Duration"],
        errors="raise"
    )

    # Duplicates
    duplicate_count = int(
        df.duplicated().sum()
    )

    df = (
        df
        .drop_duplicates(keep="first")
        .copy()
    )

    # Infinity -> NaN
    numeric_cols = (
        df.select_dtypes(
            include=[np.number]
        )
        .columns
    )

    inf_count = int(
        np.isinf(
            df[numeric_cols].to_numpy()
        ).sum()
    )

    df[numeric_cols] = (
        df[numeric_cols]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    # Remove Fwd Header Length.1
    duplicate_feature_removed = False

    if "Fwd Header Length.1" in df.columns:
        if "Fwd Header Length" in df.columns:
            identical = (
                df["Fwd Header Length.1"]
                .equals(
                    df["Fwd Header Length"]
                )
            )

            if identical:
                df = df.drop(
                    columns=["Fwd Header Length.1"]
                )
                duplicate_feature_removed = True

    print("Rows after clean:", len(df))
    print("Duplicates removed:", duplicate_count)
    print("Infinity converted:", inf_count)
    print(
        "Fwd Header Length.1 removed:",
        duplicate_feature_removed,
    )

    # Compute EndTime for exact schema parity with split_v1
    q = pd.Timedelta(seconds=Q_SECONDS)
    df["FlowDuration_td"] = pd.to_timedelta(
        df["Flow Duration"],
        unit="us"
    )
    df["EndTime"] = (
        df["StartTime"]
        + df["FlowDuration_td"]
        + q
    )

    # --------------------------------------------------------
    # 3. Stratified random split
    # --------------------------------------------------------

    print("\n[3] STRATIFIED RANDOM SPLIT")

    # Target ratios similar to Time-based split:
    # Train ~20%, Validation ~47%, Test ~33%
    # (from split_v1 metadata: 90273 / 203826 / 144157)

    # First: split off Train (20.6%)
    train, remaining = train_test_split(
        df,
        train_size=0.206,
        random_state=SEED,
        stratify=df["Label"],
    )

    # Second: split remaining into Val and Test
    # Val = ~58.6% of remaining → ~46.5% of total
    # Test = ~41.4% of remaining → ~32.9% of total
    validation, test = train_test_split(
        remaining,
        train_size=0.586,
        random_state=SEED,
        stratify=remaining["Label"],
    )

    for name, part in [
        ("Train", train),
        ("Validation", validation),
        ("Test", test),
    ]:
        classes = set(
            part["BinaryLabel"].unique()
        )

        if classes != {0, 1}:
            raise AssertionError(
                f"{name} does not contain "
                "both binary classes."
            )

    # --------------------------------------------------------
    # 4. Summary
    # --------------------------------------------------------

    print("\n[4] SUMMARY")

    def summarize(name, part):
        benign = int(
            (part["Label"] == "BENIGN").sum()
        )
        ftp = int(
            (part["Label"] == "FTP-Patator").sum()
        )
        ssh = int(
            (part["Label"] == "SSH-Patator").sum()
        )
        attack = ftp + ssh

        return {
            "split": name,
            "rows": int(len(part)),
            "BENIGN": benign,
            "FTP_Patator": ftp,
            "SSH_Patator": ssh,
            "Attack": attack,
            "Attack_percent": (
                round(100 * attack / len(part), 6)
                if len(part) > 0
                else None
            ),
        }

    split_summary = [
        summarize("Train", train),
        summarize("Validation", validation),
        summarize("Test", test),
    ]

    print(
        pd.DataFrame(split_summary)
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # 5. Save checkpoint
    # --------------------------------------------------------

    print("\n[5] SAVE CHECKPOINT")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Drop temporary columns
    cols_to_drop = [
        c for c in [
            "FlowDuration_td",
        ]
        if c in train.columns
    ]

    for name, part in [
        ("train", train),
        ("validation", validation),
        ("test", test),
    ]:
        save = part.drop(
            columns=cols_to_drop,
            errors="ignore",
        )

        save.to_csv(
            OUTPUT_DIR / f"{name}.csv.gz",
            index=False,
            compression="gzip",
        )

    # --------------------------------------------------------
    # 6. Save metadata
    # --------------------------------------------------------

    metadata = {
        "split_version": "random_v1",
        "strategy": "stratified random split",
        "random_seed": SEED,
        "stratify_by": "Label",

        "source": {
            "path": str(DATA_PATH),
            "sha256": actual_hash,
        },

        "cleaning": {
            "negative_or_invalid_duration_removed":
                int(invalid_duration.sum()),
            "raw_duplicates_removed":
                duplicate_count,
            "infinity_converted_to_nan":
                inf_count,
            "duplicated_feature_removed": (
                "Fwd Header Length.1"
                if duplicate_feature_removed
                else None
            ),
            "imputation_performed": False,
        },

        "splits": split_summary,

        "checkpoint_format": "csv.gz",

        "note": (
            "Random split is a mandatory control "
            "(protocol §5.2). Results from random "
            "split are NOT the primary result. "
            "Primary results use Time-based split."
        ),
    }

    metadata_path = (
        OUTPUT_DIR / "split_metadata.json"
    )

    with metadata_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        "Saved to:",
        OUTPUT_DIR,
    )
    print(
        "Metadata:",
        metadata_path,
    )

    print("\n" + "=" * 80)
    print("RANDOM SPLIT V1 CREATED SUCCESSFULLY")
    print("THIS IS A CONTROL SPLIT -- NOT PRIMARY")
    print("=" * 80)


if __name__ == "__main__":
    main()
