"""
Evaluate tuned XGBoost model on Test set.
CHỈ CHẠY SAU KHI ĐÃ HOÀN THÀNH TUNING.

Usage:
    python src/ids/evaluate_tuned_model.py \
        --model experiments/w3_05_time_tuning/best_xgboost_model.pkl \
        --split data/processed/split_v1 \
        --output experiments/w3_05_time_tuning/test_eval
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from pathlib import Path
import joblib
import json
from datetime import datetime
from sklearn.metrics import (
    classification_report, confusion_matrix, 
    accuracy_score, f1_score, precision_score, recall_score, 
    roc_auc_score, average_precision_score
)
import warnings
warnings.filterwarnings('ignore')


def load_test_data(split_dir: Path):
    """Load test data từ split directory."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loading test data from {split_dir}...")
    
    test = pd.read_csv(split_dir / "test.csv.gz", compression='gzip')
    
    print(f"  Test shape: {test.shape}")
    
    # Identify target column
    if 'BinaryLabel' in test.columns:
        target_col = 'BinaryLabel'
    elif 'Label' in test.columns:
        target_col = 'Label'
        if test[target_col].dtype == object:
            test[target_col] = (test[target_col] != 'BENIGN').astype(int)
    else:
        raise ValueError("Cannot find target column (BinaryLabel or Label)")
    
    # Exclude non-feature columns
    exclude_cols = {
        'Label', 'BinaryLabel', 'Subtype', 'Timestamp_fixed', 'StartTime', 'EndTime',
        '_row_id', 'index', 'Unnamed: 0', 'Flow ID', 'Source IP', 'Destination IP',
        'Source Port', 'Destination Port', 'Protocol', 'TimeBin10', 'Timestamp'
    }
    
    feature_cols = [c for c in test.columns if c not in exclude_cols]
    
    X_test = test[feature_cols].copy()
    y_test = test[target_col].copy()
    
    # Handle infinities and NaNs
    X_test.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_test.fillna(0, inplace=True)
    
    print(f"  Features: {len(feature_cols)}")
    print(f"  Target column: {target_col}")
    print(f"  Test samples: {len(y_test)} ({(y_test == 1).sum()} attack, {(y_test == 0).sum()} normal)")
    
    return X_test, y_test, feature_cols


def evaluate_on_test(model_path: Path, split_dir: Path, output_dir: Path):
    """
    Evaluate tuned model on Test set.
    
    Args:
        model_path: Path to best_xgboost_model.pkl
        split_dir: Path to data split
        output_dir: Where to save evaluation results
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load model
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Loading model from {model_path}...")
    model = joblib.load(model_path)
    print(f"  Model loaded: {type(model).__name__}")
    
    # Load test data
    X_test, y_test, feature_cols = load_test_data(split_dir)
    
    # Predict
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Predicting...")
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    # Calculate metrics
    metrics = {
        'accuracy': float(accuracy_score(y_test, y_pred)),
        'precision': float(precision_score(y_test, y_pred, zero_division=0)),
        'recall': float(recall_score(y_test, y_pred, zero_division=0)),
        'f1_score': float(f1_score(y_test, y_pred, zero_division=0)),
        'roc_auc': float(roc_auc_score(y_test, y_proba)),
        'average_precision': float(average_precision_score(y_test, y_proba)),
        'confusion_matrix': confusion_matrix(y_test, y_pred).tolist(),
        'test_size': len(y_test),
        'test_attack': int((y_test == 1).sum()),
        'test_normal': int((y_test == 0).sum())
    }
    
    # Confusion matrix breakdown
    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    metrics['confusion_matrix_breakdown'] = {
        'true_negative': int(tn),
        'false_positive': int(fp),
        'false_negative': int(fn),
        'true_positive': int(tp)
    }
    
    print("\n" + "=" * 80)
    print("TEST SET EVALUATION RESULTS")
    print("=" * 80)
    print(f"Accuracy:           {metrics['accuracy']:.4f}")
    print(f"Precision:          {metrics['precision']:.4f}")
    print(f"Recall:             {metrics['recall']:.4f}")
    print(f"F1 Score:           {metrics['f1_score']:.4f}")
    print(f"ROC-AUC:            {metrics['roc_auc']:.4f}")
    print(f"Average Precision:  {metrics['average_precision']:.4f}")
    print("\nConfusion Matrix:")
    print(f"                 Predicted")
    print(f"               BENIGN  Attack")
    print(f"Actual BENIGN   {tn:6d}  {fp:6d}")
    print(f"       Attack   {fn:6d}  {tp:6d}")
    print("=" * 80)
    
    # Save metrics
    results_path = output_dir / "test_metrics.json"
    with open(results_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved metrics to {results_path}")
    
    # Save predictions
    predictions = pd.DataFrame({
        'y_true': y_test,
        'y_pred': y_pred,
        'y_proba': y_proba
    })
    predictions_path = output_dir / "test_predictions.csv"
    predictions.to_csv(predictions_path, index=False)
    print(f"Saved predictions to {predictions_path}")
    
    # Classification report
    report = classification_report(y_test, y_pred, target_names=['BENIGN', 'Attack'], zero_division=0)
    print(f"\nClassification Report:")
    print(report)
    
    report_path = output_dir / "classification_report.txt"
    with open(report_path, 'w') as f:
        f.write("TEST SET EVALUATION RESULTS\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Accuracy:           {metrics['accuracy']:.4f}\n")
        f.write(f"Precision:          {metrics['precision']:.4f}\n")
        f.write(f"Recall:             {metrics['recall']:.4f}\n")
        f.write(f"F1 Score:           {metrics['f1_score']:.4f}\n")
        f.write(f"ROC-AUC:            {metrics['roc_auc']:.4f}\n")
        f.write(f"Average Precision:  {metrics['average_precision']:.4f}\n\n")
        f.write("Confusion Matrix:\n")
        f.write(f"                 Predicted\n")
        f.write(f"               BENIGN  Attack\n")
        f.write(f"Actual BENIGN   {tn:6d}  {fp:6d}\n")
        f.write(f"       Attack   {fn:6d}  {tp:6d}\n\n")
        f.write("=" * 80 + "\n\n")
        f.write(report)
    print(f"Saved classification report to {report_path}")
    
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Evaluation complete!")
    
    return metrics


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate tuned XGBoost model on Test set")
    parser.add_argument("--model", required=True, help="Path to best model .pkl file")
    parser.add_argument("--split", required=True, help="Split directory (e.g., data/processed/split_v1)")
    parser.add_argument("--output", required=True, help="Output directory for evaluation results")
    
    args = parser.parse_args()
    
    model_path = Path(args.model)
    split_dir = Path(args.split)
    output_dir = Path(args.output)
    
    if not model_path.exists():
        raise ValueError(f"Model file does not exist: {model_path}")
    
    if not split_dir.exists():
        raise ValueError(f"Split directory does not exist: {split_dir}")
    
    print("=" * 80)
    print("XGBoost Model Evaluation on Test Set")
    print("=" * 80)
    print(f"Model: {model_path}")
    print(f"Split directory: {split_dir}")
    print(f"Output directory: {output_dir}")
    print("=" * 80)
    
    evaluate_on_test(model_path, split_dir, output_dir)
