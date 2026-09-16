from __future__ import annotations

from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve

from .common import ProtocolError, file_sha256, read_json, write_json
from .metrics import binary_metrics, subtype_recall
from .split import check_manifest, load_partition


def verify_frozen(cfg: dict):
    processed, run, manifest = check_manifest(cfg)
    path = run / "frozen.json"
    if not path.exists():
        raise ProtocolError("Train and freeze models before evaluation.")
    frozen = read_json(path)
    if frozen["manifest_sha256"] != file_sha256(processed / "manifest.json"):
        raise ProtocolError("Manifest changed after model selection.")
    if frozen["config_sha256"] != manifest["config_sha256"]:
        raise ProtocolError("Frozen config/manifest mismatch.")
    for entry in frozen["models"].values():
        if file_sha256(run / entry["file"]) != entry["sha256"]:
            raise ProtocolError("A fitted model was modified after freezing.")
    marker = run / "TEST_OPENED.json"
    if marker.exists() and read_json(marker)["frozen_sha256"] != file_sha256(path):
        raise ProtocolError("Frozen decisions changed after Test was opened.")
    return processed, run, manifest, frozen


def score_test_once(cfg: dict) -> dict:
    processed, run, manifest, frozen = verify_frozen(cfg)
    result_path = run / "test_metrics.json"
    if result_path.exists():
        result = read_json(result_path)
        return {"cached": True, "winner": result["winner"], "metrics": result["models"][result["winner"]]["overall"],
                "synthetic": result["synthetic"]}
    marker = run / "TEST_OPENED.json"
    try:
        with marker.open("x", encoding="utf-8") as handle:
            import json
            json.dump({"opened_utc": datetime.now(timezone.utc).isoformat(),
                       "frozen_sha256": file_sha256(run / "frozen.json")}, handle)
    except FileExistsError as exc:
        raise ProtocolError("Test was opened but evaluation did not finish. Preserve the log and diagnose; do not silently reopen or retune.") from exc
    test = load_partition(processed, manifest, "test")
    X, y = test[frozen["feature_schema"]], test["_target"].to_numpy()
    output = test[["_row_id", "_start", "_label", "_target", "_seen_feature_in_earlier_split"]].copy()
    results = {}
    for name, entry in frozen["models"].items():
        pipeline = joblib.load(run / entry["file"])
        score = pipeline.predict_proba(X)[:, 1]
        threshold = entry["threshold"]
        unseen = ~test["_seen_feature_in_earlier_split"].to_numpy()
        results[name] = {
            "overall": binary_metrics(y, score, threshold),
            "at_0_5": binary_metrics(y, score, 0.5),
            "by_attack_subtype": subtype_recall(test["_label"], score, threshold),
            "previously_unseen_exact_feature_vectors": binary_metrics(y[unseen], score[unseen], threshold),
        }
        output[f"{name}_score"] = score
        output[f"{name}_prediction"] = (score >= threshold).astype(int)
    train_counts = {int(k): v for k, v in frozen["train_counts"].items()}
    majority = max([0, 1], key=lambda c: train_counts.get(c, 0))
    baseline = binary_metrics(y, np.full(len(y), float(majority)), 0.5)
    predictions_path = run / "test_predictions.csv.gz"
    output.to_csv(predictions_path, index=False, compression={"method": "gzip", "mtime": 0})
    result = {
        "winner": frozen["winner"], "winner_selected_on": "Validation, before Test opened",
        "frozen_sha256": file_sha256(run / "frozen.json"), "predictions_sha256": file_sha256(predictions_path),
        "models": results, "dummy_majority": baseline,
        "synthetic": cfg["input"]["synthetic"],
        "diagnostic_note": "Exact-feature-novel subset is descriptive and conditional, not a second split or proof of independent attacks.",
    }
    write_json(result_path, result)
    pd.DataFrame([{"model": n, "selected_before_test": n == frozen["winner"], **r["overall"]}
                  for n, r in results.items()]).to_csv(run / "test_comparison.csv", index=False)
    return {"cached": False, "winner": frozen["winner"], "metrics": results[frozen["winner"]]["overall"],
            "synthetic": cfg["input"]["synthetic"]}


def build_report(cfg: dict) -> dict:
    _, run, _, frozen = verify_frozen(cfg)
    if not (run / "test_metrics.json").exists():
        raise ProtocolError("No final metrics; run evaluate first.")
    result = read_json(run / "test_metrics.json")
    if result["frozen_sha256"] != file_sha256(run / "frozen.json"):
        raise ProtocolError("Frozen decisions changed after Test.")
    predictions_path = run / "test_predictions.csv.gz"
    if file_sha256(predictions_path) != result["predictions_sha256"]:
        raise ProtocolError("Saved predictions were modified; do not render inconsistent figures.")
    predictions = pd.read_csv(predictions_path, float_precision="round_trip")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = run / "figures"; figures.mkdir(exist_ok=True)
    y = predictions["_target"].to_numpy()
    fig, ax = plt.subplots(figsize=(7, 5))
    for name in frozen["models"]:
        precision, recall, _ = precision_recall_curve(y, predictions[f"{name}_score"])
        ap = result["models"][name]["overall"]["average_precision"]
        ax.plot(recall, precision, label=f"{name} (AP={ap:.3f})")
    ax.axhline(y.mean(), color="gray", linestyle="--", label="Attack prevalence")
    ax.set(xlabel="Recall (Attack)", ylabel="Precision (Attack)", title="SYNTHETIC TEST" if result["synthetic"] else "Temporal Test: precision-recall")
    ax.legend(); fig.tight_layout(); fig.savefig(figures / "precision_recall.png", dpi=170); plt.close(fig)
    count = len(frozen["models"])
    fig, axes = plt.subplots(1, count, figsize=(4 * count, 4), squeeze=False)
    if result["synthetic"]:
        fig.suptitle("SYNTHETIC DATA — software check only", fontsize=11)
    for ax, name in zip(axes.ravel(), frozen["models"]):
        r = result["models"][name]["overall"]
        matrix = np.array([[r["tn"], r["fp"]], [r["fn"], r["tp"]]])
        ax.imshow(matrix, cmap="Blues", alpha=0.65)
        for i in range(2):
            for j in range(2):
                ax.text(j, i, str(matrix[i, j]), ha="center", va="center", color="black")
        ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["Normal", "Attack"], yticklabels=["Normal", "Attack"],
               xlabel="Predicted", ylabel="Actual", title=name)
    fig.tight_layout(rect=(0, 0, 1, 0.94) if result["synthetic"] else (0, 0, 1, 1))
    fig.savefig(figures / "confusion_matrices.png", dpi=170); plt.close(fig)
    lines = ["# Kết quả thực nghiệm", ""]
    if result["synthetic"]:
        lines += ["**DỮ LIỆU GIẢ LẬP — chỉ kiểm tra phần mềm; không phải kết quả CICIDS2017.**", ""]
    lines += [f"Mô hình đã chọn trên Validation: **{result['winner']}**. Không chọn lại theo bảng Test.", "",
              "| Model | Ngưỡng | Precision | Recall | F1 | AP | FPR | FP | FN |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    def _fmt(val, prec=4):
        return "N/A" if val is None else f"{val:.{prec}f}"

    for name in frozen["models"]:
        r = result["models"][name]["overall"]
        lines.append(f"| {name} | {_fmt(r['threshold'], 2)} | {_fmt(r['precision_attack'])} | {_fmt(r['recall_attack'])} | {_fmt(r['f1_attack'])} | {_fmt(r['average_precision'])} | {_fmt(r['fpr'])} | {r['fp']} | {r['fn']} |")
    lines += ["", "AP = average_precision_score, không phải diện tích PR tích phân hình thang.", "",
              "| Model | Nhãn tấn công | Support | Recall |", "|---|---|---:|---:|"]
    for name in frozen["models"]:
        for subtype, info in result["models"][name]["by_attack_subtype"].items():
            recall_text = "N/A" if info["recall"] is None else f"{info['recall']:.4f}"
            lines.append(f"| {name} | {subtype} | {info['support']} | {recall_text} |")
    lines += ["", "Giới hạn: một ngày, cùng môi trường/campaign; không chứng minh tổng quát hóa sang mạng hoặc chiến dịch mới.",
              "Không có support FTP/SSH thì không kết luận khả năng phát hiện subtype đó.",
              "Các đặc trưng toàn flow chỉ sẵn sàng sau khi flow hoàn tất; đây là đánh giá offline.", "",
              "![PR curve](figures/precision_recall.png)", "", "![Confusion matrices](figures/confusion_matrices.png)", "",
              "Xem `test_metrics.json`, `split_summary.json` và `frozen.json` để đọc số mẫu, chồng lặp đặc trưng, provenance và cấu hình đầy đủ."]
    (run / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"report": str(run / "RESULTS.md")}
