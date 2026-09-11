from __future__ import annotations

import numpy as np
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)

from .common import ProtocolError


def binary_metrics(y, scores, threshold: float) -> dict:
    y, scores = np.asarray(y, dtype=int), np.asarray(scores, dtype=float)
    if len(y) != len(scores) or not set(np.unique(y)).issubset({0, 1}):
        raise ProtocolError("Metrics need aligned binary targets and scores.")
    if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
        raise ProtocolError("Invalid model scores.")
    if len(y) == 0:
        return {"n": 0, "n_normal": 0, "n_attack": 0, "status": "N/A: empty subset"}
    pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    both = len(np.unique(y)) == 2
    return {
        "n": len(y), "n_normal": int((y == 0).sum()), "n_attack": int((y == 1).sum()),
        "threshold": float(threshold), "accuracy": float(accuracy_score(y, pred)),
        "precision_attack": float(precision_score(y, pred, zero_division=0)),
        "recall_attack": float(recall_score(y, pred, zero_division=0)) if (tp + fn) else None,
        "f1_attack": float(f1_score(y, pred, zero_division=0)) if (tp + fn) else None,
        "fpr": float(fp / (fp + tn)) if (fp + tn) else None,
        "average_precision": float(average_precision_score(y, scores)) if both else None,
        "roc_auc": float(roc_auc_score(y, scores)) if both else None,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "positive_prevalence": float(y.mean()),
        "status": "ok" if both else "single-class subset: ranking metrics N/A",
    }


def choose_threshold(y_validation, scores_validation, thresholds) -> tuple[float, list[dict]]:
    if set(np.unique(y_validation)) != {0, 1}:
        raise ProtocolError("Validation must contain Normal and Attack.")
    rows = [binary_metrics(y_validation, scores_validation, t) for t in sorted(set(thresholds))]
    # Predeclared tie-breaks, with a conservative larger threshold last.
    best = max(rows, key=lambda r: (r["f1_attack"], -r["fpr"], r["recall_attack"], r["threshold"]))
    return best["threshold"], rows


def subtype_recall(labels, scores, threshold) -> dict:
    labels = np.asarray(labels)
    pred = np.asarray(scores) >= threshold
    result = {}
    for name in ["FTP-PATATOR", "SSH-PATATOR"]:
        mask = labels == name
        result[name] = {"support": int(mask.sum()),
                        "recall": float(pred[mask].mean()) if mask.any() else None}
    return result

