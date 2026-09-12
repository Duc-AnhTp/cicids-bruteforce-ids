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

FIXED_EXCLUDE = {
    # metadata / leakage-prone
    "Flow ID",
    "Source IP",
    "Destination IP",
    "Timestamp",
    "Timestamp_fixed",
    "StartTime",
    "EndTime",

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
    """

    train = pd.read_csv(
        split_dir / "train.csv",
        index_col=0,
    )

    val = pd.read_csv(
        split_dir / "validation.csv",
        index_col=0,
    )

    test = pd.read_csv(
        split_dir / "test.csv",
        index_col=0,
    )

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
    Feature schema is decided from Train schema only.
    """

    features = [
        c
        for c in train.columns
        if c not in FIXED_EXCLUDE
    ]

    if not with_destination_port:
        features = [
            c
            for c in features
            if c != "Destination Port"
        ]

    return features


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
    # Check numeric schema
    # --------------------------------------------------------

    non_numeric = (
        X_train_raw
        .select_dtypes(exclude=[np.number])
        .columns.tolist()
    )

    if non_numeric:
        raise ValueError(
            f"Non-numeric features remain: {non_numeric}"
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
        index=True,
    )

    X_val_df.to_csv(
        out_dir / "X_validation.csv",
        index=True,
    )

    X_test_df.to_csv(
        out_dir / "X_test.csv",
        index=True,
    )

    # --------------------------------------------------------
    # Save y
    # --------------------------------------------------------

    y_train = make_target(train)
    y_val = make_target(val)
    y_test = make_target(test)

    y_train.to_frame(
        "BinaryLabel"
    ).to_csv(
        out_dir / "y_train.csv",
        index=True,
    )

    y_val.to_frame(
        "BinaryLabel"
    ).to_csv(
        out_dir / "y_validation.csv",
        index=True,
    )

    y_test.to_frame(
        "BinaryLabel"
    ).to_csv(
        out_dir / "y_test.csv",
        index=True,
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {
        "split": split_name,
        "scenario": scenario_name,

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