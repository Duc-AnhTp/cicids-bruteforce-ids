"""
Hyperparameter tuning cho Decision Tree sử dụng RandomizedSearchCV.
Chỉ dùng Train + Validation; Test không động đến.

Phục vụ kịch bản:
- W3-01: Time-based split (data/processed/split_v1)
- W3-02: Random split (data/processed/random_split_v1)

Usage:
    python src/ids/tune_decision_tree.py \
        --split data/processed/split_v1 \
        --output experiments/w3_01_dt_time \
        --n-iter 50 \
        --seed 42
"""

from __future__ import annotations
import argparse
import json
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, make_scorer
from sklearn.model_selection import RandomizedSearchCV
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

warnings.filterwarnings("ignore")


def load_split_data(split_dir: Path, with_port: bool = False):
    """Load train và validation data từ split directory hoặc model_ready directory."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading data from {split_dir}...")

    # Case 1: model_ready directory (has X_train.csv, y_train.csv)
    if (split_dir / "X_train.csv").exists():
        X_train = pd.read_csv(split_dir / "X_train.csv")
        y_train = pd.read_csv(split_dir / "y_train.csv")["BinaryLabel"].astype(int)
        X_val = pd.read_csv(split_dir / "X_validation.csv")
        y_val = pd.read_csv(split_dir / "y_validation.csv")["BinaryLabel"].astype(int)
        feature_cols = list(X_train.columns)
        print(f"  Loaded model-ready data: Train {X_train.shape}, Val {X_val.shape}")
        return X_train, y_train, X_val, y_val, feature_cols

    # Case 2: processed split directory (has train.csv.gz or train.csv)
    train_file = split_dir / "train.csv.gz" if (split_dir / "train.csv.gz").exists() else split_dir / "train.csv"
    val_file = split_dir / "validation.csv.gz" if (split_dir / "validation.csv.gz").exists() else split_dir / "validation.csv"

    if not train_file.exists() or not val_file.exists():
        raise FileNotFoundError(f"Cannot find train/validation data in {split_dir}")

    train = pd.read_csv(train_file, compression="gzip" if str(train_file).endswith(".gz") else None)
    val = pd.read_csv(val_file, compression="gzip" if str(val_file).endswith(".gz") else None)

    print(f"  Train shape: {train.shape}")
    print(f"  Validation shape: {val.shape}")

    # Identify target column
    if "BinaryLabel" in train.columns:
        target_col = "BinaryLabel"
    elif "Label" in train.columns:
        target_col = "Label"
        if train[target_col].dtype == object:
            train[target_col] = (train[target_col] != "BENIGN").astype(int)
            val[target_col] = (val[target_col] != "BENIGN").astype(int)
    else:
        raise ValueError("Cannot find target column (BinaryLabel or Label)")

    # Exclude non-feature columns
    exclude_cols = {
        "Label", "BinaryLabel", "Subtype", "Timestamp_fixed", "StartTime", "EndTime",
        "_row_id", "index", "Unnamed: 0", "Flow ID", "Source IP", "Destination IP",
        "Source Port", "Protocol", "TimeBin10", "Timestamp"
    }
    if not with_port:
        exclude_cols.add("Destination Port")

    feature_cols = [c for c in train.columns if c not in exclude_cols]
    feature_cols = [c for c in feature_cols if c in val.columns]

    X_train = train[feature_cols].copy()
    y_train = train[target_col].copy()
    X_val = val[feature_cols].copy()
    y_val = val[target_col].copy()

    # Handle NaNs and Infs
    X_train.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_val.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_train.fillna(0, inplace=True)
    X_val.fillna(0, inplace=True)

    print(f"  Features: {len(feature_cols)}")
    print(f"  Target column: {target_col}")

    return X_train, y_train, X_val, y_val, feature_cols


def tune_decision_tree(
    split_dir: Path,
    output_dir: Path,
    n_iter: int = 50,
    random_state: int = 42,
    with_port: bool = False,
):
    """
    Tune Decision Tree hyperparameters using RandomizedSearchCV.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    X_train, y_train, X_val, y_val, feature_cols = load_split_data(split_dir, with_port=with_port)

    n_normal = int((y_train == 0).sum())
    n_attack = int((y_train == 1).sum())

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Dataset statistics:")
    print(f"  Train: {len(y_train)} samples ({n_attack} attack, {n_normal} normal, attack_rate={n_attack/len(y_train):.4f})")
    print(f"  Validation: {len(y_val)} samples ({(y_val == 1).sum()} attack, {(y_val == 0).sum()} normal)")

    # Base model
    base_model = DecisionTreeClassifier(random_state=random_state)

    # Hyperparameter search space
    param_distributions = {
        "criterion": ["gini", "entropy", "log_loss"],
        "max_depth": [4, 6, 8, 10, 12, 16, 20, None],
        "min_samples_split": [2, 5, 10, 20, 50],
        "min_samples_leaf": [1, 2, 5, 10, 20],
        "max_features": [None, "sqrt", "log2"],
        "class_weight": ["balanced", None],
    }

    # Optimization metric: F1 score for Attack class (pos_label=1)
    f1_scorer = make_scorer(f1_score, pos_label=1)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting RandomizedSearchCV for Decision Tree...")
    print(f"  n_iter: {n_iter}")
    print(f"  Optimization metric: F1 score (pos_label=1)")

    # Custom train vs validation CV split (no data leakage, strictly respecting validation set)
    train_indices = np.arange(len(X_train))
    val_indices = np.arange(len(X_train), len(X_train) + len(X_val))
    cv_split = [(train_indices, val_indices)]

    X_combined = pd.concat([X_train, X_val], axis=0).reset_index(drop=True)
    y_combined = pd.concat([y_train, y_val], axis=0).reset_index(drop=True)

    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_distributions,
        n_iter=n_iter,
        scoring=f1_scorer,
        cv=cv_split,
        verbose=1,
        random_state=random_state,
        n_jobs=-1,
        return_train_score=True,
    )

    search.fit(X_combined, y_combined)

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Tuning complete!")
    print(f"  Best F1 on Validation: {search.best_score_:.4f}")
    print("  Best params:")
    for param, value in search.best_params_.items():
        print(f"    {param}: {value}")

    # Re-fit best model on Train only to ensure strict protocol
    best_estimator = DecisionTreeClassifier(
        random_state=random_state,
        **search.best_params_
    )
    best_estimator.fit(X_train, y_train)

    # Save best model
    best_model_path = output_dir / "best_decision_tree_model.pkl"
    joblib.dump(best_estimator, best_model_path)
    print(f"\n  Saved best model to {best_model_path}")

    # Save tuning results json
    results = {
        "timestamp": datetime.now().isoformat(),
        "model": "DecisionTreeClassifier",
        "split_dir": str(split_dir),
        "n_iter": n_iter,
        "random_state": random_state,
        "train_size": len(y_train),
        "train_attack": n_attack,
        "train_normal": n_normal,
        "validation_size": len(y_val),
        "validation_attack": int((y_val == 1).sum()),
        "validation_normal": int((y_val == 0).sum()),
        "best_score_f1": float(search.best_score_),
        "best_params": search.best_params_,
        "tree_depth": int(best_estimator.get_depth()),
        "tree_leaves": int(best_estimator.get_n_leaves()),
        "feature_count": len(feature_cols),
        "feature_columns": feature_cols,
    }
    results_path = output_dir / "tuning_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Saved tuning results to {results_path}")

    # Save CV results dataframe
    cv_results_df = pd.DataFrame(search.cv_results_)
    cv_results_path = output_dir / "cv_results.csv"
    cv_results_df.to_csv(cv_results_path, index=False)
    print(f"  Saved CV results to {cv_results_path}")

    # Save top 10 configurations
    top_10 = cv_results_df.nlargest(10, "mean_test_score")[
        ["mean_test_score", "std_test_score", "mean_train_score", "params"]
    ].copy()
    top_10["rank"] = range(1, len(top_10) + 1)
    top_10_path = output_dir / "top_10_configs.csv"
    top_10.to_csv(top_10_path, index=False)
    print(f"  Saved top 10 configs to {top_10_path}")

    # Export Top Decision Rules (Text)
    print("  Exporting decision rules...")
    rules_text = export_text(best_estimator, feature_names=feature_cols, max_depth=4)
    rules_path = output_dir / "tree_rules_top.txt"
    with open(rules_path, "w", encoding="utf-8") as f:
        f.write(f"# Top Decision Rules for DecisionTree (max_depth=4 preview)\n")
        f.write(f"# Total Depth: {best_estimator.get_depth()}, Leaves: {best_estimator.get_n_leaves()}\n\n")
        f.write(rules_text)
    print(f"  Saved decision rules to {rules_path}")

    # Export Tree Visualization (PNG)
    print("  Generating tree structure visualization...")
    fig, ax = plt.subplots(figsize=(22, 10))
    plot_tree(
        best_estimator,
        max_depth=3,
        feature_names=feature_cols,
        class_names=["Normal", "Attack"],
        filled=True,
        rounded=True,
        fontsize=9,
        ax=ax,
    )
    plt.title(
        f"Decision Tree Structure (Top 3 Levels Preview) | F1(Val) = {search.best_score_:.4f}",
        fontsize=14,
        fontweight="bold",
    )
    tree_img_path = output_dir / "tree_structure.png"
    plt.savefig(tree_img_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved tree structure image to {tree_img_path}")

    # Feature Importance Export
    feat_imp = pd.DataFrame({
        "feature": feature_cols,
        "importance": best_estimator.feature_importances_,
    }).sort_values("importance", ascending=False).reset_index(drop=True)
    feat_imp_path = output_dir / "feature_importances.csv"
    feat_imp.to_csv(feat_imp_path, index=False)

    fig, ax = plt.subplots(figsize=(10, 6))
    top_feats = feat_imp.head(15).iloc[::-1]
    ax.barh(top_feats["feature"], top_feats["importance"], color="#1f77b4")
    ax.set_xlabel("Gini Feature Importance")
    ax.set_title(f"Top 15 Feature Importances (Decision Tree) | Best F1 = {search.best_score_:.4f}")
    plt.tight_layout()
    feat_img_path = output_dir / "feature_importance_top15.png"
    plt.savefig(feat_img_path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved feature importance chart to {feat_img_path}")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Done!")
    return best_estimator, results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tune Decision Tree hyperparameters using RandomizedSearchCV")
    parser.add_argument("--split", required=True, help="Split directory (e.g., data/processed/split_v1)")
    parser.add_argument("--output", required=True, help="Output directory for tuning results")
    parser.add_argument("--n-iter", type=int, default=50, help="Number of parameter settings to sample (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("--with-port", action="store_true", help="Keep Destination Port feature")

    args = parser.parse_args()

    split_dir = Path(args.split)
    output_dir = Path(args.output)

    if not split_dir.exists():
        raise ValueError(f"Split directory does not exist: {split_dir}")

    print("=" * 80)
    print("Decision Tree Hyperparameter Tuning (TV2 - W3-01 / W3-02)")
    print("=" * 80)
    print(f"Split directory: {split_dir}")
    print(f"Output directory: {output_dir}")
    print(f"n_iter: {args.n_iter}")
    print(f"with_port: {args.with_port}")

    tune_decision_tree(
        split_dir=split_dir,
        output_dir=output_dir,
        n_iter=args.n_iter,
        random_state=args.seed,
        with_port=args.with_port,
    )
