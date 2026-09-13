from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd


# ============================================================
# CONFIG
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
    "data/processed/split_v1"
)

SOURCE_SHA256_EXPECTED = (
    "ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815"
)

A = pd.Timestamp("2017-07-04 10:00:00")
B = pd.Timestamp("2017-07-04 14:30:00")

Q_SECONDS = 60
G_SECONDS = 120

VALID_LABELS = {
    "BENIGN",
    "FTP-Patator",
    "SSH-Patator",
}


# ============================================================
# UTILITIES
# ============================================================

def sha256_file(path: Path, chunk_size=1024 * 1024) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)

    return h.hexdigest()


def reconstruct_timestamp(raw_timestamp: pd.Series) -> pd.Series:
    """
    Reconstruct Tuesday CICIDS2017 timestamp according to the
    policy validated during EDA:

    Raw hours observed:
        8-12 -> morning / noon, unchanged
        1-5  -> afternoon, add 12 hours

    IMPORTANT:
    - This rule does NOT use Label.
    - This rule does NOT use Destination Port.
    - It is specific to the audited Tuesday file.
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

    # Afternoon reconstruction, independent of Label
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


def summarize_split(name: str, df: pd.DataFrame) -> dict:
    benign = int((df["Label"] == "BENIGN").sum())
    ftp = int((df["Label"] == "FTP-Patator").sum())
    ssh = int((df["Label"] == "SSH-Patator").sum())

    attack = ftp + ssh

    return {
        "split": name,
        "rows": int(len(df)),
        "BENIGN": benign,
        "FTP_Patator": ftp,
        "SSH_Patator": ssh,
        "Attack": attack,
        "Attack_percent": (
            round(100 * attack / len(df), 6)
            if len(df) > 0
            else None
        ),
        "start": (
            df["StartTime"].min().isoformat()
            if len(df) > 0
            else None
        ),
        "end": (
            df["StartTime"].max().isoformat()
            if len(df) > 0
            else None
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 80)
    print("PREPARE CICIDS2017 TUESDAY - TIME SPLIT V1")
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
    # 2. Load and canonicalize schema
    # --------------------------------------------------------

    print("\n[2] LOAD")

    df = pd.read_csv(DATA_PATH)
    df.columns = df.columns.astype(str).str.strip()

    print("Rows raw:", len(df))
    print("Columns raw:", len(df.columns))

    required = {
        "Label",
        "Timestamp",
        "Flow Duration",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing required columns: {sorted(missing)}"
        )

    # --------------------------------------------------------
    # 3. Normalize label and enforce scope
    # --------------------------------------------------------

    print("\n[3] LABEL SCOPE")

    df["Label"] = (
        df["Label"]
        .astype(str)
        .str.strip()
    )

    unknown_labels = (
        set(df["Label"].unique())
        - VALID_LABELS
    )

    if unknown_labels:
        print(
            "Labels outside project scope:",
            sorted(unknown_labels)
        )

        df = df[
            df["Label"].isin(VALID_LABELS)
        ].copy()

    print(df["Label"].value_counts())

    # Keep subtype before creating binary label
    df["Subtype"] = df["Label"]

    df["BinaryLabel"] = (
        df["Label"]
        .isin(["FTP-Patator", "SSH-Patator"])
        .astype("int8")
    )

    # --------------------------------------------------------
    # 4. Reconstruct Timestamp
    # --------------------------------------------------------

    print("\n[4] TIMESTAMP")

    df["Timestamp_fixed"] = reconstruct_timestamp(
        df["Timestamp"]
    )

    print(
        "Min:",
        df["Timestamp_fixed"].min()
    )
    print(
        "Max:",
        df["Timestamp_fixed"].max()
    )

    print("\nBy Label:")

    print(
        df.groupby("Label")["Timestamp_fixed"]
        .agg(["min", "max", "count"])
    )

    # --------------------------------------------------------
    # 5. Flow Duration validation
    # --------------------------------------------------------

    print("\n[5] FLOW DURATION")

    duration = pd.to_numeric(
        df["Flow Duration"],
        errors="coerce"
    )

    invalid_duration = (
        duration.isna()
        | (duration < 0)
    )

    removed_invalid_duration = int(
        invalid_duration.sum()
    )

    print(
        "Invalid Flow Duration:",
        removed_invalid_duration
    )

    if removed_invalid_duration:
        print(
            df.loc[
                invalid_duration,
                "Label"
            ].value_counts()
        )

    df = df.loc[
        ~invalid_duration
    ].copy()

    # Recalculate duration after filtering
    df["Flow Duration"] = pd.to_numeric(
        df["Flow Duration"],
        errors="raise"
    )

    # --------------------------------------------------------
    # 6. Raw duplicates
    # --------------------------------------------------------

    print("\n[6] DUPLICATES")

    duplicate_count = int(
        df.duplicated().sum()
    )

    print(
        "Raw duplicate rows removed:",
        duplicate_count
    )

    df = (
        df
        .drop_duplicates(keep="first")
        .copy()
    )

    # --------------------------------------------------------
    # 7. Infinity -> NaN
    #    NO IMPUTATION HERE
    # --------------------------------------------------------

    print("\n[7] INFINITY -> NaN")

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

    print(
        "Infinity converted:",
        inf_count
    )

    df[numeric_cols] = (
        df[numeric_cols]
        .replace(
            [np.inf, -np.inf],
            np.nan
        )
    )

    print(
        "Total NaN after conversion:",
        int(df.isna().sum().sum())
    )

    # --------------------------------------------------------
    # 8. Remove confirmed duplicate feature column
    # --------------------------------------------------------

    print("\n[8] DUPLICATED FEATURE COLUMN")

    duplicate_feature_removed = False

    if "Fwd Header Length.1" in df.columns:

        if "Fwd Header Length" not in df.columns:
            raise ValueError(
                "Fwd Header Length.1 exists but "
                "original column is missing."
            )

        identical = (
            df["Fwd Header Length.1"]
            .equals(
                df["Fwd Header Length"]
            )
        )

        if not identical:
            raise ValueError(
                "Fwd Header Length.1 is not "
                "identical to Fwd Header Length."
            )

        df = df.drop(
            columns=["Fwd Header Length.1"]
        )

        duplicate_feature_removed = True

        print(
            "Removed Fwd Header Length.1"
        )

    # --------------------------------------------------------
    # 9. Temporal metadata for purge
    # --------------------------------------------------------

    print("\n[9] TEMPORAL METADATA")

    q = pd.Timedelta(
        seconds=Q_SECONDS
    )

    g = pd.Timedelta(
        seconds=G_SECONDS
    )

    df["StartTime"] = (
        df["Timestamp_fixed"]
    )

    df["FlowDuration_td"] = (
        pd.to_timedelta(
            df["Flow Duration"],
            unit="us"
        )
    )

    df["EndTime"] = (
        df["StartTime"]
        + df["FlowDuration_td"]
        + q
    )

    df["_row_id"] = np.arange(len(df), dtype=np.int64)

    # --------------------------------------------------------
    # 10. Time-based split
    # --------------------------------------------------------

    print("\n[10] TIME SPLIT")

    train_mask = (
        df["EndTime"] < A
    )

    val_mask = (
        (df["StartTime"] >= A + g)
        &
        (df["EndTime"] < B)
    )

    test_mask = (
        df["StartTime"] >= B + g
    )

    train = (
        df.loc[train_mask]
        .copy()
        .sort_values(
            ["StartTime", "Flow ID"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    validation = (
        df.loc[val_mask]
        .copy()
        .sort_values(
            ["StartTime", "Flow ID"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    test = (
        df.loc[test_mask]
        .copy()
        .sort_values(
            ["StartTime", "Flow ID"],
            kind="stable",
        )
        .reset_index(drop=True)
    )

    kept_mask = (
        train_mask
        | val_mask
        | test_mask
    )

    removed_boundary = df.loc[
        ~kept_mask
    ].copy()

    # --------------------------------------------------------
    # 11. Boundary audit
    # --------------------------------------------------------

    purge_a = df[
        (df["StartTime"] < A)
        &
        (df["EndTime"] >= A)
    ]

    embargo_a = df[
        (df["StartTime"] >= A)
        &
        (df["StartTime"] < A + g)
    ]

    purge_b = df[
        (df["StartTime"] >= A + g)
        &
        (df["StartTime"] < B)
        &
        (df["EndTime"] >= B)
    ]

    embargo_b = df[
        (df["StartTime"] >= B)
        &
        (df["StartTime"] < B + g)
    ]

    def boundary_summary(
        reason,
        x
    ):
        return {
            "reason": reason,
            "rows": int(len(x)),
            "BENIGN": int(
                (x["Label"] == "BENIGN")
                .sum()
            ),
            "FTP": int(
                (x["Label"] == "FTP-Patator")
                .sum()
            ),
            "SSH": int(
                (x["Label"] == "SSH-Patator")
                .sum()
            ),
        }

    boundary_audit = [
        boundary_summary(
            "purge_at_a",
            purge_a
        ),
        boundary_summary(
            "embargo_after_a",
            embargo_a
        ),
        boundary_summary(
            "purge_at_b",
            purge_b
        ),
        boundary_summary(
            "embargo_after_b",
            embargo_b
        ),
    ]

    # --------------------------------------------------------
    # 12. Sanity checks
    # --------------------------------------------------------

    print("\n[11] SANITY CHECK")

    total_check = (
        len(train)
        + len(validation)
        + len(test)
        + len(removed_boundary)
    )

    if total_check != len(df):
        raise AssertionError(
            "Split does not preserve total row count."
        )

    # 1. Row disjointness check via _row_id
    train_ids = set(train["_row_id"])
    val_ids = set(validation["_row_id"])
    test_ids = set(test["_row_id"])
    purged_ids = set(removed_boundary["_row_id"])

    if train_ids & val_ids:
        raise AssertionError(
            f"Train/Validation row overlap detected: {len(train_ids & val_ids)} rows."
        )

    if train_ids & test_ids:
        raise AssertionError(
            f"Train/Test row overlap detected: {len(train_ids & test_ids)} rows."
        )

    if val_ids & test_ids:
        raise AssertionError(
            f"Validation/Test row overlap detected: {len(val_ids & test_ids)} rows."
        )

    if (train_ids | val_ids | test_ids) & purged_ids:
        raise AssertionError(
            "Kept partitions overlap with purged/embargoed rows."
        )

    # 2. Strict flow completion and embargo boundary checks
    if train["EndTime"].max() >= validation["StartTime"].min():
        raise AssertionError(
            f"Train/Validation time overlap: train EndTime max ({train['EndTime'].max()}) "
            f">= validation StartTime min ({validation['StartTime'].min()})"
        )

    if validation["EndTime"].max() >= test["StartTime"].min():
        raise AssertionError(
            f"Validation/Test time overlap: validation EndTime max ({validation['EndTime'].max()}) "
            f">= test StartTime min ({test['StartTime'].min()})"
        )

    if train["EndTime"].max() >= test["StartTime"].min():
        raise AssertionError(
            f"Train/Test time overlap: train EndTime max ({train['EndTime'].max()}) "
            f">= test StartTime min ({test['StartTime'].min()})"
        )

    if train["EndTime"].max() >= A:
        raise AssertionError(
            f"Train EndTime max ({train['EndTime'].max()}) >= cutoff A ({A})"
        )

    if validation["StartTime"].min() < A + g:
        raise AssertionError(
            f"Validation StartTime min ({validation['StartTime'].min()}) < A + embargo ({A + g})"
        )

    if validation["EndTime"].max() >= B:
        raise AssertionError(
            f"Validation EndTime max ({validation['EndTime'].max()}) >= cutoff B ({B})"
        )

    if test["StartTime"].min() < B + g:
        raise AssertionError(
            f"Test StartTime min ({test['StartTime'].min()}) < B + embargo ({B + g})"
        )

    # Both binary classes must exist in each split
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

    print("Total preserved: OK")
    print("No overlap: OK")
    print("Both binary classes: OK")

    # --------------------------------------------------------
    # 13. Summary
    # --------------------------------------------------------

    split_summary = [
        summarize_split(
            "Train",
            train
        ),
        summarize_split(
            "Validation",
            validation
        ),
        summarize_split(
            "Test",
            test
        ),
    ]

    print("\n[12] FINAL SUMMARY")

    print(
        pd.DataFrame(split_summary)
        .to_string(index=False)
    )

    print(
        "\nRemoved by purge/embargo:",
        len(removed_boundary)
    )

    print(
        pd.DataFrame(boundary_audit)
        .to_string(index=False)
    )

    # --------------------------------------------------------
    # 14. Save checkpoint
    # --------------------------------------------------------

    print("\n[13] SAVE CHECKPOINT")

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Remove temporary timedelta helper and audit row ID before saving
    columns_to_drop = [
        "FlowDuration_td",
        "_row_id",
    ]

    train_save = train.drop(
        columns=columns_to_drop
    )

    val_save = validation.drop(
        columns=columns_to_drop
    )

    test_save = test.drop(
        columns=columns_to_drop
    )

    # Parquet preferred because dtype is preserved
    try:
        train_save.to_parquet(
            OUTPUT_DIR / "train.parquet",
            index=False
        )

        val_save.to_parquet(
            OUTPUT_DIR / "validation.parquet",
            index=False
        )

        test_save.to_parquet(
            OUTPUT_DIR / "test.parquet",
            index=False
        )

        checkpoint_format = "parquet"

    except ImportError:
        print(
            "pyarrow/fastparquet unavailable; "
            "falling back to CSV (gzip)."
        )

        train_save.to_csv(
            OUTPUT_DIR / "train.csv.gz",
            index=False,
            compression="gzip",
        )

        val_save.to_csv(
            OUTPUT_DIR / "validation.csv.gz",
            index=False,
            compression="gzip",
        )

        test_save.to_csv(
            OUTPUT_DIR / "test.csv.gz",
            index=False,
            compression="gzip",
        )

        checkpoint_format = "csv.gz"

    # --------------------------------------------------------
    # 15. Save metadata
    # --------------------------------------------------------

    metadata = {
        "source": {
            "path": str(DATA_PATH),
            "sha256": actual_hash,
            "raw_rows": 445909,
        },

        "split_version": "time_v1",

        "timestamp_policy": {
            "raw_format": "d/m/YYYY h:mm",
            "observed_raw_hours": [
                1, 2, 3, 4, 5,
                8, 9, 10, 11, 12
            ],
            "rule": (
                "hours 1-5 -> +12 hours; "
                "hours 8-12 unchanged"
            ),
            "uses_label": False,
            "uses_destination_port": False,
            "limitation": (
                "Timestamp_fixed is reconstructed "
                "from Tuesday CSV metadata and is "
                "not an absolute PCAP timestamp."
            ),
        },

        "cleaning": {
            "negative_or_invalid_duration_removed":
                removed_invalid_duration,

            "raw_duplicates_removed":
                duplicate_count,

            "infinity_converted_to_nan":
                inf_count,

            "duplicated_feature_removed":
                (
                    "Fwd Header Length.1"
                    if duplicate_feature_removed
                    else None
                ),

            "imputation_performed": False,
        },

        "time_split": {
            "a": A.isoformat(),
            "b": B.isoformat(),
            "q_seconds": Q_SECONDS,
            "g_seconds": G_SECONDS,
        },

        "boundary_audit": boundary_audit,

        "removed_by_purge_embargo":
            int(len(removed_boundary)),

        "splits": split_summary,

        "checkpoint_format":
            checkpoint_format,

        "known_limitation": (
            "Train contains early FTP-Patator (~68%) but no "
            "SSH-Patator; Validation contains tail FTP-Patator (~32%) "
            "and early SSH-Patator (~34%); Test contains tail "
            "SSH-Patator (~66%) but no FTP-Patator. "
            "Cutoff A=10:00 intentionally places early FTP in Train and tail FTP "
            "in Validation so Validation has both subtypes for model selection, "
            "with the trade-off of evaluating the same campaign across Train and Validation. "
            "Primary task remains binary Normal vs Attack."
        ),
    }

    metadata_path = (
        OUTPUT_DIR
        / "split_metadata.json"
    )

    with metadata_path.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            metadata,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        "Saved to:",
        OUTPUT_DIR
    )
    print(
        "Metadata:",
        metadata_path
    )

    print("\n" + "=" * 80)
    print("TIME-BASED SPLIT V1 CREATED SUCCESSFULLY")
    print("NO IMPUTATION / FEATURE SELECTION / MODEL FIT PERFORMED")
    print("=" * 80)


if __name__ == "__main__":
    main()