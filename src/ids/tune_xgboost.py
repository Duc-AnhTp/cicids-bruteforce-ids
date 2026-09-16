"""
Hyperparameter tuning cho XGBoost sử dụng RandomizedSearchCV.
Chỉ dùng Train + Validation; Test không động đến.

Usage:
    python src/ids/tune_xgboost.py \
        --split data/processed/split_v1 \
        --output experiments/w3_05_time_tuning \
        --n-iter 50 \
        --seed 42
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import RandomizedSearchCV
from xgboost import XGBClassifier
from sklearn.metrics import make_scorer, f1_score
import joblib
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def load_split_data(split_dir: Path):
    """Load train và validation data từ split directory."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading data from {split_dir}...")
    
    train = pd.read_csv(split_dir / "train.csv.gz", compression='gzip')
    val = pd.read_csv(split_dir / "validation.csv.gz", compression='gzip')
    
    print(f"  Train shape: {train.shape}")
    print(f"  Validation shape: {val.shape}")
    
    # Identify target column
    if 'BinaryLabel' in train.columns:
        target_col = 'BinaryLabel'
    elif 'Label' in train.columns:
        # Convert Label to binary if needed
        target_col = 'Label'
        if train[target_col].dtype == object:
            train[target_col] = (train[target_col] != 'BENIGN').astype(int)
            val[target_col] = (val[target_col] != 'BENIGN').astype(int)
    else:
        raise ValueError("Cannot find target column (BinaryLabel or Label)")
    
    # Exclude non-feature columns
    exclude_cols = {
        'Label', 'BinaryLabel', 'Subtype', 'Timestamp_fixed', 'StartTime', 'EndTime',
        '_row_id', 'index', 'Unnamed: 0', 'Flow ID', 'Source IP', 'Destination IP',
        'Source Port', 'Destination Port', 'Protocol', 'TimeBin10', 'Timestamp'
    }
    
    feature_cols = [c for c in train.columns if c not in exclude_cols]
    
    # Ensure feature columns exist in both train and val
    feature_cols = [c for c in feature_cols if c in val.columns]
    
    X_train = train[feature_cols].copy()
    y_train = train[target_col].copy()
    
    X_val = val[feature_cols].copy()
    y_val = val[target_col].copy()
    
    # Handle any remaining infinities or NaNs
    X_train.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_val.replace([np.inf, -np.inf], np.nan, inplace=True)
    
    # Fill NaN with 0 (simple strategy)
    X_train.fillna(0, inplace=True)
    X_val.fillna(0, inplace=True)
    
    print(f"  Features: {len(feature_cols)}")
    print(f"  Target column: {target_col}")
    
    return X_train, y_train, X_val, y_val, feature_cols


def tune_xgboost(split_dir: Path, output_dir: Path, n_iter: int = 50, random_state: int = 42):
    """
    Tune XGBoost hyperparameters using RandomizedSearchCV.
    
    Args:
        split_dir: Path to data split (e.g., data/processed/split_v1)
        output_dir: Where to save tuning results
        n_iter: Number of parameter settings sampled
        random_state: Random seed
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load data
    X_train, y_train, X_val, y_val, feature_cols = load_split_data(split_dir)
    
    # Calculate scale_pos_weight
    n_normal = (y_train == 0).sum()
    n_attack = (y_train == 1).sum()
    scale_pos_weight = n_normal / n_attack
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Dataset statistics:")
    print(f"  Train: {len(y_train)} samples ({n_attack} attack, {n_normal} normal)")
    print(f"  Validation: {len(y_val)} samples ({(y_val == 1).sum()} attack, {(y_val == 0).sum()} normal)")
    print(f"  scale_pos_weight: {scale_pos_weight:.4f}")
    
    # Base model with fixed params
    base_model = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        scale_pos_weight=scale_pos_weight,
        tree_method='hist',
        device='cpu',
        random_state=random_state,
        n_jobs=-1
    )
    
    # Hyperparameter search space
    param_distributions = {
        'n_estimators': [100, 150, 200, 250, 300],
        'max_depth': [3, 4, 5, 6, 7],
        'learning_rate': [0.05, 0.08, 0.1, 0.12, 0.15],
        'min_child_weight': [3, 5, 7, 10],
        'subsample': [0.7, 0.8, 0.9],
        'colsample_bytree': [0.7, 0.8, 0.9],
        'reg_lambda': [0.5, 1.0, 1.5, 2.0],
        'gamma': [0, 0.1, 0.2]
    }
    
    # Use F1 score as optimization metric
    f1_scorer = make_scorer(f1_score, pos_label=1)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting RandomizedSearchCV...")
    print(f"  n_iter: {n_iter}")
    print(f"  Optimization metric: F1 score")
    print(f"  Search space size: ~{5*5*5*4*3*3*4*3:,} combinations")
    
    # Create custom CV split: train vs validation
    # We create indices for the combined dataset
    train_indices = np.arange(len(X_train))
    val_indices = np.arange(len(X_train), len(X_train) + len(X_val))
    cv_split = [(train_indices, val_indices)]
    
    search = RandomizedSearchCV(
        estimator=base_model,
        param_distributions=param_distributions,
        n_iter=n_iter,
        scoring=f1_scorer,
        cv=cv_split,
        verbose=2,
        random_state=random_state,
        n_jobs=1,  # XGBoost already uses n_jobs=-1
        return_train_score=True
    )
    
    # Combine train + val for CV split
    X_combined = pd.concat([X_train, X_val], axis=0).reset_index(drop=True)
    y_combined = pd.concat([y_train, y_val], axis=0).reset_index(drop=True)
    
    # Fit
    search.fit(X_combined, y_combined)
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Tuning complete!")
    print(f"  Best F1 on Validation: {search.best_score_:.4f}")
    print(f"  Best params:")
    for param, value in search.best_params_.items():
        print(f"    {param}: {value}")
    
    # Save best model
    best_model_path = output_dir / "best_xgboost_model.pkl"
    joblib.dump(search.best_estimator_, best_model_path)
    print(f"\n  Saved best model to {best_model_path}")
    
    # Save tuning results
    results = {
        'timestamp': datetime.now().isoformat(),
        'split_dir': str(split_dir),
        'n_iter': n_iter,
        'random_state': random_state,
        'scale_pos_weight': float(scale_pos_weight),
        'train_size': len(y_train),
        'train_attack': int(n_attack),
        'train_normal': int(n_normal),
        'validation_size': len(y_val),
        'validation_attack': int((y_val == 1).sum()),
        'validation_normal': int((y_val == 0).sum()),
        'best_score_f1': float(search.best_score_),
        'best_params': search.best_params_,
        'feature_count': len(feature_cols),
        'feature_columns': feature_cols,
    }
    
    results_path = output_dir / "tuning_results.json"
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"  Saved tuning results to {results_path}")
    
    # Save detailed CV results
    cv_results_df = pd.DataFrame(search.cv_results_)
    cv_results_path = output_dir / "cv_results.csv"
    cv_results_df.to_csv(cv_results_path, index=False)
    print(f"  Saved CV results to {cv_results_path}")
    
    # Save top 10 configurations
    top_10 = cv_results_df.nlargest(10, 'mean_test_score')[
        ['mean_test_score', 'std_test_score', 'params']
    ].copy()
    top_10['rank'] = range(1, len(top_10) + 1)
    top_10_path = output_dir / "top_10_configs.csv"
    top_10.to_csv(top_10_path, index=False)
    print(f"  Saved top 10 configs to {top_10_path}")
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Done!")
    
    return search.best_estimator_, results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Tune XGBoost hyperparameters using RandomizedSearchCV")
    parser.add_argument("--split", required=True, help="Split directory (e.g., data/processed/split_v1)")
    parser.add_argument("--output", required=True, help="Output directory for tuning results")
    parser.add_argument("--n-iter", type=int, default=50, help="Number of parameter settings to sample (default: 50)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    
    args = parser.parse_args()
    
    split_dir = Path(args.split)
    output_dir = Path(args.output)
    
    if not split_dir.exists():
        raise ValueError(f"Split directory does not exist: {split_dir}")
    
    print("=" * 80)
    print("XGBoost Hyperparameter Tuning")
    print("=" * 80)
    print(f"Split directory: {split_dir}")
    print(f"Output directory: {output_dir}")
    print(f"n_iter: {args.n_iter}")
    print(f"Random seed: {args.seed}")
    print("=" * 80)
    
    tune_xgboost(split_dir, output_dir, n_iter=args.n_iter, random_state=args.seed)
