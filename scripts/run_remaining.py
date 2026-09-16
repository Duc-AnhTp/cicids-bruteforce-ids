"""W3-01..W3-09 + W4-01..W4-03: DT / RF / XGBoost trên model_ready.

Chỉ fit Train, chọn tham số trên Validation, freeze, rồi mở Test đúng một lần.
Không dùng python -m ids train (layout tuesday_temporal_v1 không tồn tại).

Chạy từ root repo, venv đã pip install -e ".[xai]":

    python scripts/run_remaining.py
    python scripts/run_remaining.py --phase train
    python scripts/run_remaining.py --phase test
    python scripts/run_remaining.py --phase shap
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.tree import DecisionTreeClassifier

SEED = 42
THRESHOLD = 0.5
N_JOBS = 2
SHAP_ROWS = 500

DT_GRID = {"max_depth": [6, 8, 12, None], "min_samples_leaf": [5, 10]}
RF_GRID = {"n_estimators": [100, 150, 300], "max_depth": [10, 16, None], "min_samples_leaf": [5]}
XGB_GRID = {"n_estimators": [100, 200], "max_depth": [3, 4, 6], "learning_rate": [0.08]}
XGB_FIXED = {
    "min_child_weight": 5,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "tree_method": "hist",
    "device": "cpu",
}

SPLITS = ("time", "random")
SCENARIOS = ("with_port", "without_port")
MODELS = ("decision_tree", "random_forest", "xgboost")

JOBS = {
    ("decision_tree", "time"): "W3-01",
    ("decision_tree", "random"): "W3-02",
    ("random_forest", "time"): "W3-03",
    ("random_forest", "random"): "W3-04",
    ("xgboost", "time"): "W3-05",
    ("xgboost", "random"): "W3-06",
}


def repo_root() -> Path:
    here = Path(__file__).resolve().parent
    if (here.parent / "data" / "model_ready").exists():
        return here.parent
    cwd = Path.cwd()
    if (cwd / "data" / "model_ready").exists():
        return cwd
    raise SystemExit("Không thấy data/model_ready. Chạy từ root repo.")


ROOT = repo_root()
OUT = ROOT / "artifacts" / "week3_week4"
FROZEN_PATH = OUT / "frozen.json"
MARKER_PATH = OUT / "TEST_OPENED.json"
TEST_METRICS_PATH = OUT / "test_metrics.json"


def json_default(value):
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value).__name__)


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=json_default) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def key_of(model: str, split: str, scenario: str) -> str:
    return f"{split}/{scenario}/{model}"


def load_xy(split: str, scenario: str, part: str, allow_test: bool = False):
    if part == "test" and not allow_test:
        raise RuntimeError("Không được load Test trước khi freeze + mở marker.")
    base = ROOT / "data" / "model_ready" / split / scenario
    X = pd.read_csv(base / f"X_{part}.csv")
    y = pd.read_csv(base / f"y_{part}.csv")["BinaryLabel"].astype(int)
    sub = pd.read_csv(base / f"y_{part}_subtype.csv")["Subtype"]
    if len(X) != len(y) or len(X) != len(sub):
        raise RuntimeError(f"Lệch số dòng {split}/{scenario}/{part}")
    arr = X.to_numpy(dtype=float)
    if np.isnan(arr).any() or np.isinf(arr).any():
        raise RuntimeError(f"NaN/Inf trong {split}/{scenario}/{part}")
    return X, y, sub


def attack_metrics(y_true, y_pred, scores=None) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    y_pred = np.asarray(y_pred, dtype=int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_attack": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall_attack": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1_attack": float(f1_score(y_true, y_pred, zero_division=0)),
        "fpr": float(fp / (fp + tn)) if (fp + tn) else None,
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
        "n": int(len(y_true)),
        "n_attack": int(y_true.sum()),
        "threshold": THRESHOLD,
    }
    if scores is not None and len(np.unique(y_true)) == 2:
        out["average_precision"] = float(average_precision_score(y_true, scores))
        out["roc_auc"] = float(roc_auc_score(y_true, scores))
    return out


def subtype_recall(subtypes, y_pred) -> dict:
    y_pred = np.asarray(y_pred, dtype=int)
    subtypes = np.asarray(subtypes)
    out = {}
    for name in ("FTP-Patator", "SSH-Patator"):
        mask = subtypes == name
        out[name] = {
            "support": int(mask.sum()),
            "recall": float(y_pred[mask].mean()) if mask.any() else None,
        }
    return out


def flatten_metrics(m: dict, sub: dict) -> dict:
    row = dict(m)
    row["ftp_recall"] = sub["FTP-Patator"]["recall"]
    row["ftp_support"] = sub["FTP-Patator"]["support"]
    row["ssh_recall"] = sub["SSH-Patator"]["recall"]
    row["ssh_support"] = sub["SSH-Patator"]["support"]
    return row


def sort_key(row: dict):
    f1 = row.get("f1_attack") or -1
    ap = row.get("average_precision") or -1
    fpr = row.get("fpr") if row.get("fpr") is not None else 1.0
    return (f1, ap, -fpr)


def make_estimator(model: str, params: dict, n_neg: int, n_pos: int):
    if model == "decision_tree":
        return DecisionTreeClassifier(
            random_state=SEED,
            class_weight="balanced",
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
        )
    if model == "random_forest":
        return RandomForestClassifier(
            random_state=SEED,
            class_weight="balanced",
            max_features="sqrt",
            n_jobs=N_JOBS,
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            min_samples_leaf=params["min_samples_leaf"],
        )
    if model == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            random_state=SEED,
            n_jobs=N_JOBS,
            scale_pos_weight=n_neg / n_pos,
            n_estimators=params["n_estimators"],
            max_depth=params["max_depth"],
            learning_rate=params["learning_rate"],
            **XGB_FIXED,
        )
    raise ValueError(model)


def grid_params(model: str) -> list[dict]:
    if model == "decision_tree":
        keys = DT_GRID
    elif model == "random_forest":
        keys = RF_GRID
    else:
        keys = XGB_GRID
    names = list(keys)
    rows = []
    for values in itertools.product(*[keys[n] for n in names]):
        rows.append(dict(zip(names, values)))
    return rows


def require_unopened() -> None:
    if MARKER_PATH.exists():
        raise SystemExit(
            f"Test đã mở ({MARKER_PATH}). Không train/tune lại. "
            "Chỉ được đọc test_metrics.json đã lưu."
        )


def train_phase() -> dict:
    if FROZEN_PATH.exists():
        print("frozen.json đã có — bỏ qua train.")
        return read_json(FROZEN_PATH)
    require_unopened()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "models").mkdir(exist_ok=True)
    grid_rows = []
    winners = {}
    cache = {}

    def cached(split, scenario, part):
        k = (split, scenario, part)
        if k not in cache:
            cache[k] = load_xy(split, scenario, part, allow_test=False)
        return cache[k]

    for split in SPLITS:
        for scenario in SCENARIOS:
            Xtr, ytr, _ = cached(split, scenario, "train")
            Xva, yva, sva = cached(split, scenario, "validation")
            n_neg, n_pos = int((ytr == 0).sum()), int((ytr == 1).sum())
            print(
                f"\n===== {split}/{scenario} train={Xtr.shape} val={Xva.shape} "
                f"pos_rate_train={n_pos / len(ytr):.4f} =====",
                flush=True,
            )
            for model in MODELS:
                combos = grid_params(model)
                local = []
                for i, params in enumerate(combos, 1):
                    est = make_estimator(model, params, n_neg, n_pos)
                    t0 = time.perf_counter()
                    est.fit(Xtr, ytr)
                    seconds = time.perf_counter() - t0
                    scores = est.predict_proba(Xva)[:, 1]
                    pred = (scores >= THRESHOLD).astype(int)
                    m = attack_metrics(yva, pred, scores)
                    sub = subtype_recall(sva, pred)
                    row = flatten_metrics(m, sub)
                    row.update(
                        {
                            "model": model,
                            "split": split,
                            "scenario": scenario,
                            "job": JOBS.get((model, split), ""),
                            "fit_seconds": round(seconds, 1),
                            **{k: ("None" if v is None else v) for k, v in params.items()},
                        }
                    )
                    local.append(row)
                    grid_rows.append(row)
                    print(
                        f"  {model} [{i}/{len(combos)}] {params} "
                        f"f1={m['f1_attack']:.4f} rec={m['recall_attack']:.4f} "
                        f"ssh={sub['SSH-Patator']['recall']} sec={seconds:.1f}",
                        flush=True,
                    )
                best = max(local, key=sort_key)
                best_params = {}
                source_grid = DT_GRID if model == "decision_tree" else RF_GRID if model == "random_forest" else XGB_GRID
                for k in source_grid:
                    raw = best[k]
                    best_params[k] = None if raw == "None" else raw
                winner_est = make_estimator(model, best_params, n_neg, n_pos)
                winner_est.fit(Xtr, ytr)
                rel = f"models/{split}_{scenario}_{model}.joblib"
                path = OUT / rel
                joblib.dump(winner_est, path)
                k = key_of(model, split, scenario)
                winners[k] = {
                    "file": rel,
                    "sha256": file_sha256(path),
                    "params": best_params,
                    "n_features": int(Xtr.shape[1]),
                    "feature_names": list(Xtr.columns),
                    "scale_pos_weight": None if model != "xgboost" else n_neg / n_pos,
                    "validation": {kk: best[kk] for kk in (
                        "f1_attack", "precision_attack", "recall_attack", "accuracy",
                        "average_precision", "roc_auc", "fpr", "tn", "fp", "fn", "tp",
                        "n", "n_attack", "threshold", "ftp_recall", "ssh_recall",
                        "ftp_support", "ssh_support", "fit_seconds",
                    )},
                    "job": JOBS.get((model, split), ""),
                }
                print(f"  WINNER {k}: {best_params} f1={best['f1_attack']:.4f}", flush=True)

    grid_df = pd.DataFrame(grid_rows)
    grid_df.to_csv(OUT / "grid_all.csv", index=False)

    winner_rows = []
    for k, entry in winners.items():
        split, scenario, model = k.split("/")
        row = {
            "key": k,
            "job": entry["job"],
            "model": model,
            "split": split,
            "scenario": scenario,
            **entry["params"],
            **entry["validation"],
        }
        winner_rows.append(row)
    winners_df = pd.DataFrame(winner_rows)
    winners_df.to_csv(OUT / "validation_winners.csv", index=False)

    primary = [r for r in winner_rows if r["split"] == "time" and r["scenario"] == "with_port"]
    overall = max(primary, key=sort_key)

    ablation_rows = []
    for model in MODELS:
        with_p = next(r for r in winner_rows if r["model"] == model and r["split"] == "time" and r["scenario"] == "with_port")
        no_p = next(r for r in winner_rows if r["model"] == model and r["split"] == "time" and r["scenario"] == "without_port")
        ablation_rows.append({
            "job": "W3-07",
            "model": model,
            "f1_with_port": with_p["f1_attack"],
            "f1_without_port": no_p["f1_attack"],
            "delta_f1": with_p["f1_attack"] - no_p["f1_attack"],
            "ssh_recall_with_port": with_p["ssh_recall"],
            "ssh_recall_without_port": no_p["ssh_recall"],
            "ftp_recall_with_port": with_p["ftp_recall"],
            "ftp_recall_without_port": no_p["ftp_recall"],
            "fpr_with_port": with_p["fpr"],
            "fpr_without_port": no_p["fpr"],
        })
    pd.DataFrame(ablation_rows).to_csv(OUT / "port_ablation_validation.csv", index=False)

    split_rows = []
    for model in MODELS:
        for scenario in SCENARIOS:
            t = next(r for r in winner_rows if r["model"] == model and r["split"] == "time" and r["scenario"] == scenario)
            r = next(r for r in winner_rows if r["model"] == model and r["split"] == "random" and r["scenario"] == scenario)
            split_rows.append({
                "job": "W4-02",
                "model": model,
                "scenario": scenario,
                "f1_time": t["f1_attack"],
                "f1_random": r["f1_attack"],
                "delta_f1_random_minus_time": r["f1_attack"] - t["f1_attack"],
                "ssh_recall_time": t["ssh_recall"],
                "ssh_recall_random": r["ssh_recall"],
                "ftp_recall_time": t["ftp_recall"],
                "ftp_recall_random": r["ftp_recall"],
            })
    pd.DataFrame(split_rows).to_csv(OUT / "split_diff_validation.csv", index=False)

    frozen = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "selection": "validation f1_attack then average_precision then lower fpr; threshold 0.5",
        "test_opened": False,
        "seed": SEED,
        "n_jobs": N_JOBS,
        "primary": "time/with_port",
        "winner_key": key_of(overall["model"], "time", "with_port"),
        "winner_model": overall["model"],
        "grids": {"decision_tree": DT_GRID, "random_forest": RF_GRID, "xgboost": XGB_GRID},
        "note": (
            "Train time-based chỉ có FTP-Patator; Test chỉ có SSH-Patator. "
            "Kết quả chính là time/with_port. Random split là đối chứng rò rỉ."
        ),
        "models": winners,
    }
    write_json(FROZEN_PATH, frozen)
    print(f"\nFROZEN winner={frozen['winner_key']} → {FROZEN_PATH}", flush=True)
    return frozen


def test_phase() -> dict:
    if not FROZEN_PATH.exists():
        raise SystemExit("Chưa có frozen.json. Chạy --phase train trước.")
    frozen = read_json(FROZEN_PATH)
    if TEST_METRICS_PATH.exists() and MARKER_PATH.exists():
        print("Test đã chạy — trả kết quả đã lưu, không predict lại.")
        return read_json(TEST_METRICS_PATH)

    opened_utc = datetime.now(timezone.utc).isoformat()
    try:
        with MARKER_PATH.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "opened_utc": opened_utc,
                    "frozen_sha256": file_sha256(FROZEN_PATH),
                    "protocol": "W3-09 open Test once; do not retune",
                },
                handle,
                indent=2,
            )
            handle.write("\n")
    except FileExistsError:
        raise SystemExit(
            "TEST_OPENED.json đã tồn tại nhưng chưa có test_metrics.json. "
            "Không mở lại. Kiểm tra log rồi xử lý tay."
        )

    results = {}
    rows = []
    fig_dir = OUT / "figures"
    fig_dir.mkdir(exist_ok=True)

    for k, entry in frozen["models"].items():
        split, scenario, model = k.split("/")
        Xte, yte, ste = load_xy(split, scenario, "test", allow_test=True)
        est = joblib.load(OUT / entry["file"])
        if list(Xte.columns) != entry["feature_names"]:
            raise SystemExit(f"Feature schema lệch: {k}")
        scores = est.predict_proba(Xte)[:, 1]
        pred = (scores >= THRESHOLD).astype(int)
        m = attack_metrics(yte, pred, scores)
        sub = subtype_recall(ste, pred)
        results[k] = {"overall": flatten_metrics(m, sub), "subtype": sub}
        rows.append({
            "key": k,
            "job": "W3-09",
            "model": model,
            "split": split,
            "scenario": scenario,
            "selected_before_test": k == frozen["winner_key"],
            **flatten_metrics(m, sub),
        })
        print(
            f"TEST {k}: f1={m['f1_attack']:.4f} rec={m['recall_attack']:.4f} "
            f"ssh={sub['SSH-Patator']['recall']} ftp={sub['FTP-Patator']['recall']}",
            flush=True,
        )

    test_df = pd.DataFrame(rows)
    test_df.to_csv(OUT / "test_comparison.csv", index=False)

    w4 = []
    for model in MODELS:
        for split in SPLITS:
            row = next(
                r for r in rows
                if r["model"] == model and r["split"] == split and r["scenario"] == "with_port"
            )
            w4.append({
                "job": "W4-01",
                "model": model,
                "split": split,
                "scenario": "with_port",
                "f1_attack": row["f1_attack"],
                "precision_attack": row["precision_attack"],
                "recall_attack": row["recall_attack"],
                "fpr": row["fpr"],
                "average_precision": row["average_precision"],
                "ftp_recall": row["ftp_recall"],
                "ssh_recall": row["ssh_recall"],
            })
    pd.DataFrame(w4).to_csv(OUT / "w4_01_comparison_3x2.csv", index=False)

    payload = {
        "opened_utc": opened_utc,
        "frozen_sha256": file_sha256(FROZEN_PATH),
        "winner_key": frozen["winner_key"],
        "winner_selected_on": "Validation, before Test opened",
        "models": results,
        "note": frozen["note"],
    }
    write_json(TEST_METRICS_PATH, payload)
    _write_figures(frozen, results)
    _write_results_md(frozen, results)
    print(f"TEST locked → {TEST_METRICS_PATH}", flush=True)
    return payload


def _write_figures(frozen: dict, results: dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = OUT / "figures"
    keys = [key_of(m, "time", "with_port") for m in MODELS]

    fig, ax = plt.subplots(figsize=(7, 5))
    y = None
    for name in keys:
        split, scenario, model = name.split("/")
        Xte, yte, _ = load_xy(split, scenario, "test", allow_test=True)
        est = joblib.load(OUT / frozen["models"][name]["file"])
        scores = est.predict_proba(Xte)[:, 1]
        precision, recall, _ = precision_recall_curve(yte, scores)
        ap = results[name]["overall"]["average_precision"]
        ax.plot(recall, precision, label=f"{model} (AP={ap:.3f})")
        y = np.asarray(yte)
    ax.axhline(y.mean(), color="gray", linestyle="--", label="Attack prevalence")
    ax.set(xlabel="Recall (Attack)", ylabel="Precision (Attack)", title="Test time/with_port — PR")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "precision_recall_test_time_with_port.png", dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for ax, name in zip(axes, keys):
        r = results[name]["overall"]
        matrix = np.array([[r["tn"], r["fp"]], [r["fn"], r["tp"]]])
        ax.imshow(matrix, cmap="Blues", alpha=0.65)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center")
        ax.set(
            xticks=[0, 1],
            yticks=[0, 1],
            xticklabels=["Normal", "Attack"],
            yticklabels=["Normal", "Attack"],
            xlabel="Predicted",
            ylabel="Actual",
            title=name.split("/")[-1],
        )
    fig.suptitle("Test time/with_port — confusion")
    fig.tight_layout()
    fig.savefig(fig_dir / "confusion_test_time_with_port.png", dpi=170)
    plt.close(fig)


def _write_results_md(frozen: dict, results: dict) -> None:
    lines = [
        "# Kết quả thực nghiệm (W3–W4)",
        "",
        f"Mô hình chọn trên Validation (time/with_port): **{frozen['winner_model']}**. Không chọn lại theo Test.",
        "",
        frozen["note"],
        "",
        "## Validation winners",
        "",
        "| Model | Split | Port | F1 | P | R | AP | FPR | FTP rec | SSH rec |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    winners_df = pd.read_csv(OUT / "validation_winners.csv")
    for _, r in winners_df.iterrows():
        lines.append(
            f"| {r['model']} | {r['split']} | {r['scenario']} | {r['f1_attack']:.4f} | "
            f"{r['precision_attack']:.4f} | {r['recall_attack']:.4f} | {r['average_precision']:.4f} | "
            f"{r['fpr']:.4f} | {r['ftp_recall']} | {r['ssh_recall']} |"
        )
    lines += [
        "",
        "## Test (mở một lần)",
        "",
        "| Model | Split | Port | F1 | P | R | AP | FPR | FTP rec | SSH rec | chọn trước Test |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    test_df = pd.read_csv(OUT / "test_comparison.csv")
    for _, r in test_df.iterrows():
        flag = "yes" if bool(r["selected_before_test"]) else ""
        lines.append(
            f"| {r['model']} | {r['split']} | {r['scenario']} | {r['f1_attack']:.4f} | "
            f"{r['precision_attack']:.4f} | {r['recall_attack']:.4f} | {r['average_precision']:.4f} | "
            f"{r['fpr']:.4f} | {r['ftp_recall']} | {r['ssh_recall']} | {flag} |"
        )
    lines += [
        "",
        "Test time-based không có FTP-Patator (support = 0) — không kết luận phát hiện FTP trên Test.",
        "Random split F1 cao là đối chứng rò rỉ, không phải kết quả chính.",
        "",
        "![PR](figures/precision_recall_test_time_with_port.png)",
        "",
        "![CM](figures/confusion_test_time_with_port.png)",
        "",
    ]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def shap_phase() -> dict:
    if not FROZEN_PATH.exists():
        raise SystemExit("Chưa freeze. Chạy --phase train trước.")
    try:
        import shap
    except ImportError:
        write_json(OUT / "shap" / "skipped.json", {"reason": "shap not installed"})
        print("SHAP chưa cài — bỏ qua. pip install shap")
        return {"skipped": True}

    frozen = read_json(FROZEN_PATH)
    key = frozen["winner_key"]
    split, scenario, model = key.split("/")
    Xva, yva, sva = load_xy(split, scenario, "validation", allow_test=False)
    rng = np.random.RandomState(SEED)
    n = min(SHAP_ROWS, len(Xva))
    idx = rng.choice(len(Xva), size=n, replace=False)
    sample = Xva.iloc[idx]
    est = joblib.load(OUT / frozen["models"][key]["file"])

    explainer = shap.TreeExplainer(est, feature_perturbation="tree_path_dependent", model_output="raw")
    values = explainer.shap_values(sample.to_numpy(dtype=float), check_additivity=False)
    expected = explainer.expected_value
    if isinstance(values, list):
        values = values[1]
    values = np.asarray(values)
    if values.ndim == 3:
        values = values[:, :, 1]
    if np.asarray(expected).size == 2:
        expected = float(np.asarray(expected).ravel()[1])
    else:
        expected = float(np.asarray(expected).ravel()[0])

    out = OUT / "shap"
    out.mkdir(exist_ok=True)
    names = list(Xva.columns)
    importance = (
        pd.DataFrame({"feature": names, "mean_abs_shap": np.abs(values).mean(axis=0)})
        .sort_values("mean_abs_shap", ascending=False)
        .reset_index(drop=True)
    )
    importance.to_csv(out / "feature_importance.csv", index=False)
    pd.DataFrame({"row_index": idx, "BinaryLabel": yva.iloc[idx].to_numpy(), "Subtype": sva.iloc[idx].to_numpy()}).to_csv(
        out / "sample_rows.csv", index=False
    )

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top = importance.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.barh(top["feature"], top["mean_abs_shap"])
    ax.set_xlabel("Mean |SHAP|")
    ax.set_title(f"{key} — Validation sample n={n}")
    fig.tight_layout()
    fig.savefig(out / "summary.png", dpi=170)
    plt.close(fig)

    meta = {
        "model_key": key,
        "partition": "validation",
        "n": n,
        "seed": SEED,
        "output_unit": "log-odds" if model == "xgboost" else "uncalibrated model score",
        "limitation": "Giải thích hành vi mô hình đã fit; không phải bằng chứng nhân quả hay bước chọn feature.",
        "top10": importance.head(10).to_dict(orient="records"),
    }
    write_json(out / "metadata.json", meta)
    print(f"SHAP → {out} top={importance.iloc[0]['feature']}", flush=True)
    return meta


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["train", "test", "shap", "all"], default="all")
    args = parser.parse_args(argv)
    print("ROOT", ROOT)
    print("OUT ", OUT)
    print("phase", args.phase)
    if args.phase in ("train", "all"):
        train_phase()
    if args.phase in ("test", "all"):
        test_phase()
    if args.phase in ("shap", "all"):
        shap_phase()
    return 0


if __name__ == "__main__":
    sys.exit(main())
