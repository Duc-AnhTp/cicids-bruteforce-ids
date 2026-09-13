from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer


# ============================================================
# CONFIG
# ============================================================

SPLITS = {
    "time": Path("data/processed/split_v1"),
    "random": Path("data/processed/random_split_v1"),
}

OUTPUT_ROOT = Path("data/model_ready")

ATTACK_LABELS = {
    "FTP-Patator",
    "SSH-Patator",
}

# 76 canonical features matching src/ids/schema.py
CANONICAL_FEATURES = [
    "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
    "Total Length of Fwd Packets", "Total Length of Bwd Packets",
    "Fwd Packet Length Max", "Fwd Packet Length Min", "Fwd Packet Length Mean",
    "Fwd Packet Length Std", "Bwd Packet Length Max", "Bwd Packet Length Min",
    "Bwd Packet Length Mean", "Bwd Packet Length Std", "Flow Bytes/s",
    "Flow Packets/s", "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max",
    "Flow IAT Min", "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std",
    "Fwd IAT Max", "Fwd IAT Min", "Bwd IAT Total", "Bwd IAT Mean",
    "Bwd IAT Std", "Bwd IAT Max", "Bwd IAT Min", "Fwd PSH Flags",
    "Bwd PSH Flags", "Fwd URG Flags", "Bwd URG Flags", "Fwd Header Length",
    "Bwd Header Length", "Fwd Packets/s", "Bwd Packets/s", "Min Packet Length",
    "Max Packet Length", "Packet Length Mean", "Packet Length Std",
    "Packet Length Variance", "FIN Flag Count", "SYN Flag Count",
    "RST Flag Count", "PSH Flag Count", "ACK Flag Count", "URG Flag Count",
    "CWE Flag Count", "ECE Flag Count", "Down/Up Ratio", "Average Packet Size",
    "Avg Fwd Segment Size", "Avg Bwd Segment Size", "Fwd Avg Bytes/Bulk",
    "Fwd Avg Packets/Bulk", "Fwd Avg Bulk Rate", "Bwd Avg Bytes/Bulk",
    "Bwd Avg Packets/Bulk", "Bwd Avg Bulk Rate", "Subflow Fwd Packets",
    "Subflow Fwd Bytes", "Subflow Bwd Packets", "Subflow Bwd Bytes",
    "Init_Win_bytes_forward", "Init_Win_bytes_backward", "act_data_pkt_fwd",
    "min_seg_size_forward", "Active Mean", "Active Std", "Active Max",
    "Active Min", "Idle Mean", "Idle Std", "Idle Max", "Idle Min"
]

FIXED_EXCLUDE = {
    # metadata / leakage-prone
    "Flow ID",
    "Source IP",
    "Destination IP",
    "Timestamp",
    "Timestamp_fixed",
    "StartTime",
    "EndTime",
    "_row_id",
    "Unnamed: 0",
    "index",

    # EDA-only
    "TimeBin10",

    # target / label metadata
    "Label",
    "Subtype",
    "BinaryLabel",

    # feature-policy v1
    "Source Port",
    "Protocol",
}


# ============================================================
# LOAD
# ============================================================

def load_split(split_dir: Path):
    """
    Load Train / Validation / Test checkpoints.

    Important:
    Test is loaded here only to APPLY already-fitted preprocessing.
    No statistics or decisions are learned from Test.

    Supports both .csv.gz (new) and .csv (legacy) files.
    """

    def _read(name):
        gz = split_dir / f"{name}.csv.gz"
        plain = split_dir / f"{name}.csv"
        path = gz if gz.exists() else plain
        df = pd.read_csv(path)
        unnamed = [
            c for c in df.columns
            if c.startswith("Unnamed:") or c.lower() in ("index", "unnamed: 0")
        ]
        if unnamed:
            df = df.drop(columns=unnamed)
        return df

    train = _read("train")
    val = _read("validation")
    test = _read("test")

    for df in (train, val, test):
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
        )

        df["Label"] = (
            df["Label"]
            .astype(str)
            .str.strip()
        )

    return train, val, test


# ============================================================
# TARGET
# ============================================================

def make_target(df: pd.DataFrame):
    """
    0 = BENIGN
    1 = FTP-Patator / SSH-Patator
    """

    return (
        df["Label"]
        .isin(ATTACK_LABELS)
        .astype(np.int8)
    )


# ============================================================
# FEATURE SCHEMA
# ============================================================

def get_initial_features(
    train: pd.DataFrame,
    with_destination_port: bool,
):
    """
    Feature schema is strictly derived using CANONICAL_FEATURES allowlist.
    """
    allowed = list(CANONICAL_FEATURES)
    if with_destination_port:
        allowed = ["Destination Port"] + allowed

    missing = [c for c in allowed if c not in train.columns]
    if missing:
        raise ValueError(
            f"Required canonical features missing from Train: {missing}"
        )

    return [
        c for c in allowed
        if c in train.columns and c not in FIXED_EXCLUDE
    ]


# ============================================================
# PREPROCESSING
# ============================================================

def fit_transform_preprocessing(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    initial_features,
):
    """
    Learn preprocessing ONLY from Train.

    Train:
        - detect all-missing
        - detect constant
        - fit median imputer

    Validation/Test:
        - transform only
    """

    X_train_raw = train[initial_features].copy()
    X_val_raw = val[initial_features].copy()
    X_test_raw = test[initial_features].copy()

    # --------------------------------------------------------
    # Guard: CICFlowMeter 32-bit integer overflow → NaN
    # Values exceeding float32 range are overflow artifacts
    # (e.g. Fwd Header Length = -32 billion).
    # Mirrors src/ids/preprocess.py NumericGuard.
    # --------------------------------------------------------

    f32_max = np.finfo(np.float32).max

    # Columns that represent sizes/lengths and cannot physically be negative
    non_negative_size_cols = [
        "Fwd Header Length",
        "Bwd Header Length",
        "min_seg_size_forward",
    ]

    for label, X_raw in [
        ("train", X_train_raw),
        ("validation", X_val_raw),
        ("test", X_test_raw),
    ]:
        # 1. Float32 unrepresentable overflow
        overflow_mask = X_raw.abs() > f32_max

        # 2. Negative artifacts in size/length columns (CICFlowMeter 32-bit signed int overflow)
        for col in non_negative_size_cols:
            if col in X_raw.columns:
                neg_mask = X_raw[col] < 0
                overflow_mask[col] = overflow_mask[col] | neg_mask

        n_overflow = int(
            overflow_mask.sum().sum()
        )

        if n_overflow > 0:
            print(
                f"  {label}: {n_overflow} "
                f"overflow/invalid size values -> NaN"
            )

            X_raw.where(
                ~overflow_mask,
                other=np.nan,
                inplace=True,
            )

        # 3. Flow IAT Min packet capture jitter (clip negative to 0.0)
        if "Flow IAT Min" in X_raw.columns:
            neg_iat = int((X_raw["Flow IAT Min"] < 0).sum())
            if neg_iat > 0:
                print(
                    f"  {label}: {neg_iat} "
                    f"negative Flow IAT Min values clipped to 0.0"
                )
                X_raw["Flow IAT Min"] = X_raw["Flow IAT Min"].clip(lower=0.0)

    # --------------------------------------------------------
    # Check numeric schema across all partitions
    # --------------------------------------------------------

    for split_label, X_part in [
        ("train", X_train_raw),
        ("validation", X_val_raw),
        ("test", X_test_raw),
    ]:
        non_numeric = (
            X_part.select_dtypes(exclude=[np.number])
            .columns.tolist()
        )
        if non_numeric:
            raise ValueError(
                f"Non-numeric features in {split_label}: {non_numeric}"
            )

    # --------------------------------------------------------
    # All-missing - Train only
    # --------------------------------------------------------

    all_missing = [
        c
        for c in X_train_raw.columns
        if X_train_raw[c].isna().all()
    ]

    # --------------------------------------------------------
    # Constant - Train only
    # --------------------------------------------------------

    nunique = X_train_raw.nunique(
        dropna=True
    )

    constant = (
        nunique[nunique <= 1]
        .index.tolist()
    )

    dropped = sorted(
        set(all_missing + constant)
    )

    final_features = [
        c
        for c in initial_features
        if c not in dropped
    ]

    if not final_features:
        raise RuntimeError(
            "No features remain after preprocessing."
        )

    X_train = X_train_raw[final_features]
    X_val = X_val_raw[final_features]
    X_test = X_test_raw[final_features]

    # --------------------------------------------------------
    # Imputer - FIT ONLY ON TRAIN
    # --------------------------------------------------------

    imputer = SimpleImputer(
        strategy="median"
    )

    X_train_imp = imputer.fit_transform(
        X_train
    )

    X_val_imp = imputer.transform(
        X_val
    )

    X_test_imp = imputer.transform(
        X_test
    )

    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------

    for name, X in [
        ("train", X_train_imp),
        ("validation", X_val_imp),
        ("test", X_test_imp),
    ]:

        if np.isnan(X).any():
            raise RuntimeError(
                f"NaN remains after preprocessing: {name}"
            )

        if np.isinf(X).any():
            raise RuntimeError(
                f"Infinity remains after preprocessing: {name}"
            )

    median_values = {
        feature: float(value)
        for feature, value in zip(
            final_features,
            imputer.statistics_,
        )
    }

    return {
        "X_train": X_train_imp,
        "X_val": X_val_imp,
        "X_test": X_test_imp,

        "initial_features": initial_features,
        "final_features": final_features,

        "all_missing": all_missing,
        "constant": constant,
        "median_values": median_values,
    }


# ============================================================
# SAVE
# ============================================================

def save_scenario(
    split_name,
    scenario_name,
    train,
    val,
    test,
    prep,
):
    out_dir = (
        OUTPUT_ROOT
        / split_name
        / scenario_name
    )

    out_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    features = prep["final_features"]

    # --------------------------------------------------------
    # Save X
    # --------------------------------------------------------

    X_train_df = pd.DataFrame(
        prep["X_train"],
        columns=features,
        index=train.index,
    )

    X_val_df = pd.DataFrame(
        prep["X_val"],
        columns=features,
        index=val.index,
    )

    X_test_df = pd.DataFrame(
        prep["X_test"],
        columns=features,
        index=test.index,
    )

    X_train_df.to_csv(
        out_dir / "X_train.csv",
        index=False,
    )

    X_val_df.to_csv(
        out_dir / "X_validation.csv",
        index=False,
    )

    X_test_df.to_csv(
        out_dir / "X_test.csv",
        index=False,
    )

    # --------------------------------------------------------
    # Save y (both binary target and subtype reference)
    # --------------------------------------------------------

    y_train = make_target(train)
    y_val = make_target(val)
    y_test = make_target(test)

    def get_subtype_series(part):
        return part["Subtype"] if "Subtype" in part.columns else part["Label"]

    for name, part, y_part in [
        ("train", train, y_train),
        ("validation", val, y_val),
        ("test", test, y_test),
    ]:
        # Standard 1-column binary target for model training
        y_part.to_frame(
            "BinaryLabel"
        ).to_csv(
            out_dir / f"y_{name}.csv",
            index=False,
        )

        # 2-column target + subtype for detailed evaluation / audit
        pd.DataFrame({
            "BinaryLabel": y_part.values,
            "Subtype": get_subtype_series(part).values,
        }).to_csv(
            out_dir / f"y_{name}_subtype.csv",
            index=False,
        )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {
        "split": split_name,
        "scenario": scenario_name,

        "subtypes": {
            "train": {str(k): int(v) for k, v in get_subtype_series(train).value_counts().items()},
            "validation": {str(k): int(v) for k, v in get_subtype_series(val).value_counts().items()},
            "test": {str(k): int(v) for k, v in get_subtype_series(test).value_counts().items()},
        },

        "preprocessing_version":
            "preprocess_v1",

        "fit_policy":
            "all learned preprocessing fitted on Train only",

        "initial_feature_count":
            len(prep["initial_features"]),

        "final_feature_count":
            len(prep["final_features"]),

        "all_missing_features":
            prep["all_missing"],

        "constant_features":
            prep["constant"],

        "final_features":
            prep["final_features"],

        "median_values":
            prep["median_values"],

        "rows": {
            "train": int(len(train)),
            "validation": int(len(val)),
            "test": int(len(test)),
        },

        "class_support": {
            "train_normal":
                int((y_train == 0).sum()),

            "train_attack":
                int((y_train == 1).sum()),

            "validation_normal":
                int((y_val == 0).sum()),

            "validation_attack":
                int((y_val == 1).sum()),

            "test_normal":
                int((y_test == 0).sum()),

            "test_attack":
                int((y_test == 1).sum()),
        },

        "excluded_fixed":
            sorted(FIXED_EXCLUDE),
    }

    with (
        out_dir
        / "preprocessing_metadata.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            metadata,
            f,
            indent=2,
            ensure_ascii=False,
        )

    return metadata


# ============================================================
# RUN ONE SPLIT
# ============================================================

def run_split(
    split_name,
    split_dir,
):
    print("\n" + "=" * 80)
    print(
        f"PREPROCESS SPLIT: "
        f"{split_name.upper()}"
    )
    print("=" * 80)

    train, val, test = load_split(
        split_dir
    )

    scenarios = {
        "with_port": True,
        "without_port": False,
    }

    for scenario_name, with_port in scenarios.items():

        print(
            f"\nScenario: {scenario_name}"
        )

        initial_features = (
            get_initial_features(
                train,
                with_destination_port=with_port,
            )
        )

        prep = (
            fit_transform_preprocessing(
                train,
                val,
                test,
                initial_features,
            )
        )

        metadata = save_scenario(
            split_name,
            scenario_name,
            train,
            val,
            test,
            prep,
        )

        print(
            "Initial features:",
            metadata["initial_feature_count"]
        )

        print(
            "Constant:",
            len(
                metadata[
                    "constant_features"
                ]
            )
        )

        print(
            "All-missing:",
            len(
                metadata[
                    "all_missing_features"
                ]
            )
        )

        print(
            "Final features:",
            metadata["final_feature_count"]
        )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 80)
    print("PREPROCESS DATA FOR MODEL TRAINING")
    print("=" * 80)

    print(
        "\nPolicy:"
        "\n- preprocessing fit on Train only"
        "\n- Validation/Test transform only"
        "\n- no model training"
    )

    for split_name, split_dir in SPLITS.items():

        run_split(
            split_name,
            split_dir,
        )

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)

    print(
        "\nOutput:",
        OUTPUT_ROOT
    )


if __name__ == "__main__":
    main()