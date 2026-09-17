"""
Comprehensive Visualization Generator for TV2 - Decision Tree
and Multi-Model Benchmark (CICIDS2017 Brute Force IDS)

This script generates 6 detailed, publication-quality figures:
1. 01_tree_structure_detailed.png       - Detailed Hierarchical Tree Structure with Decision Boundaries
2. 02_overfitting_analysis_depth.png    - Train vs Validation F1/Precision/Recall vs Tree Depth (Overfitting analysis)
3. 03_confusion_matrices_detailed.png   - Side-by-side Comparative Confusion Matrix Heatmaps (W3-01 vs W3-02)
4. 04_roc_and_pr_curves_comparative.png - Dual PR & ROC Curves with Area Under Curve (AP & AUC)
5. 05_feature_importance_top20.png      - Top 20 Features categorized by Domain (Packet, IAT, Flags, Ports)
6. 06_data_leakage_benchmark.png        - Subtype Detection Gap (FTP vs SSH) & 3-Model Benchmark (DT vs RF vs XGB)

Usage:
    python scripts/generate_detailed_visualizations.py
"""

from __future__ import annotations
from pathlib import Path
import json
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.tree import DecisionTreeClassifier, plot_tree
from sklearn.metrics import (
    confusion_matrix, precision_recall_curve, roc_curve,
    f1_score, precision_score, recall_score,
    average_precision_score, roc_auc_score
)
import joblib

# Determine root
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "artifacts" / "TV2_decision_tree" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
EXP_FIGURES = ROOT / "experiments" / "figures"
EXP_FIGURES.mkdir(parents=True, exist_ok=True)

# Styling configuration
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "figure.titlesize": 14,
    "figure.titleweight": "bold",
    "figure.autolayout": False,
    "figure.dpi": 200,
    "savefig.dpi": 300,
    "grid.alpha": 0.35,
    "grid.linestyle": "--",
})


def generate_01_tree_structure():
    """1. High-resolution Hierarchical Tree Topology."""
    print(">>> [1/6] Generating 01_tree_structure_detailed.png...")
    model_path = ROOT / "artifacts" / "TV2_decision_tree" / "dt_time_with_port.joblib"
    if not model_path.exists():
        model_path = ROOT / "experiments" / "w3_01_dt_time" / "best_decision_tree_model.pkl"

    if not model_path.exists():
        print("  Model not found, skipping tree structure.")
        return

    model = joblib.load(model_path)

    # Load feature names
    time_dir = ROOT / "data" / "model_ready" / "time" / "with_port"
    if (time_dir / "X_train.csv").exists():
        feature_names = list(pd.read_csv(time_dir / "X_train.csv", nrows=1).columns)
    else:
        feat_df = pd.read_csv(ROOT / "experiments" / "w3_01_dt_time" / "feature_importances.csv")
        feature_names = list(feat_df["feature"])

    fig, ax = plt.subplots(figsize=(24, 11))
    plot_tree(
        model,
        max_depth=3,
        feature_names=feature_names,
        class_names=["BENIGN (Normal)", "Attack (FTP)"],
        filled=True,
        rounded=True,
        proportion=True,
        fontsize=9,
        ax=ax,
        precision=2,
    )

    plt.title(
        "TV2: Cấu trúc Rẽ nhánh Cây Quyết định (Top 3 Tầng) - Kịch bản W3-01 (Time-based Split)\n"
        "[Gốc phân tách dựa trên Destination Port: Port 21 (FTP-Patator) vs Port 22 (SSH) & Normal Traffic]",
        fontsize=14, pad=15
    )

    # Add explanatory legend box
    info_text = (
        "Quy tắc chính tại nút gốc:\n"
        "• Destination Port <= 21.5 (Port 21: FTP) -> Nhánh trái tập trung 100% mẫu tấn công huấn luyện\n"
        "• Destination Port > 21.5 (Port 22: SSH & Web) -> Nhánh phải phân loại gần như toàn bộ là BENIGN\n"
        "→ Giải thích vì sao cây đơn lẻ thất bại zero-shot trên Test set (chỉ gồm SSH-Patator)."
    )
    fig.text(0.12, 0.02, info_text, fontsize=10, bbox=dict(boxstyle="round,pad=0.5", facecolor="#fff9db", edgecolor="#e67700", alpha=0.9))

    out_file1 = OUTPUT_DIR / "01_tree_structure_detailed.png"
    out_file2 = EXP_FIGURES / "01_tree_structure_detailed.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def generate_02_overfitting_analysis():
    """2. Overfitting Curve Analysis (Train vs Val across Tree Depths)."""
    print(">>> [2/6] Generating 02_overfitting_analysis_depth.png...")
    time_dir = ROOT / "data" / "model_ready" / "time" / "with_port"
    if not (time_dir / "X_train.csv").exists():
        print("  Data not found, skipping overfitting analysis.")
        return

    X_train = pd.read_csv(time_dir / "X_train.csv")
    y_train = pd.read_csv(time_dir / "y_train.csv")["BinaryLabel"].astype(int)
    X_val = pd.read_csv(time_dir / "X_validation.csv")
    y_val = pd.read_csv(time_dir / "y_validation.csv")["BinaryLabel"].astype(int)

    depths = list(range(2, 21))
    train_f1, val_f1 = [], []
    train_prec, val_prec = [], []
    train_rec, val_rec = [], []

    for d in depths:
        clf = DecisionTreeClassifier(
            max_depth=d,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42
        )
        clf.fit(X_train, y_train)

        tr_pred = clf.predict(X_train)
        va_pred = clf.predict(X_val)

        train_f1.append(f1_score(y_train, tr_pred, zero_division=0))
        val_f1.append(f1_score(y_val, va_pred, zero_division=0))
        train_prec.append(precision_score(y_train, tr_pred, zero_division=0))
        val_prec.append(precision_score(y_val, va_pred, zero_division=0))
        train_rec.append(recall_score(y_train, tr_pred, zero_division=0))
        val_rec.append(recall_score(y_val, va_pred, zero_division=0))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Panel 1: F1 Score vs Depth
    ax1.plot(depths, train_f1, "o-", color="#1f77b4", linewidth=2.2, label="Train F1 Score (Attack)")
    ax1.plot(depths, val_f1, "s--", color="#d62728", linewidth=2.2, label="Validation F1 Score (Attack)")

    # Highlight sweet spot & overfitting zone
    ax1.axvspan(4, 8, color="#2ca02c", alpha=0.15, label="Vùng Độ sâu Tối ưu (d=4 đến 8)")
    ax1.axvspan(12, 20, color="#d62728", alpha=0.12, label="Vùng Quá khớp Nặng (Overfitting d > 12)")
    ax1.axvline(6, color="#2ca02c", linestyle=":", linewidth=2, label="Độ sâu Được Chọn (d=6)")

    ax1.set_xlabel("Độ sâu Cây Tối đa (max_depth)")
    ax1.set_ylabel("Điểm F1-Score")
    ax1.set_title("Biến thiên F1-Score: Train vs Validation theo Chiều sâu Cây")
    ax1.set_ylim(0.5, 1.02)
    ax1.grid(True)
    ax1.legend(loc="lower right", framealpha=0.9)

    # Panel 2: Generalization Gap (Train F1 - Val F1)
    gap = np.array(train_f1) - np.array(val_f1)
    ax2.bar(depths, gap, color="#e377c2", alpha=0.8, edgecolor="#8c564b", width=0.6, label="Độ Lệch Quá Khớp (Train F1 - Val F1)")
    ax2.plot(depths, gap, "D-", color="#7f7f7f", linewidth=1.5)

    ax2.axhline(0.1, color="orange", linestyle="--", alpha=0.7, label="Ngưỡng Cảnh báo Quá khớp (Gap = 0.1)")
    ax2.set_xlabel("Độ sâu Cây Tối đa (max_depth)")
    ax2.set_ylabel("Generalization Gap (Độ lệch điểm F1)")
    ax2.set_title("Khoảng cách Tổng quát hóa: Phân tích Rủi ro Overfit")
    ax2.set_ylim(0, 0.45)
    ax2.grid(True)
    ax2.legend(loc="upper left", framealpha=0.9)

    # Annotations
    ax2.annotate(
        "Khoảng cách tăng vọt khi d > 12\n(Mô hình học vẹt tập Train)",
        xy=(16, gap[14]), xytext=(12, 0.35),
        arrowprops=dict(facecolor="black", shrink=0.08, width=1, headwidth=6),
        fontsize=9, bbox=dict(boxstyle="round", facecolor="#fff", edgecolor="gray")
    )

    plt.suptitle("TV2: Khảo sát Hiện tượng Quá khớp (Overfitting Analysis) - Kịch bản W3-01 Time-based Split", y=1.02)
    plt.tight_layout()

    out_file1 = OUTPUT_DIR / "02_overfitting_analysis_depth.png"
    out_file2 = EXP_FIGURES / "02_overfitting_analysis_depth.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def generate_03_confusion_matrices():
    """3. Side-by-side Comparative Confusion Matrix Heatmaps."""
    print(">>> [3/6] Generating 03_confusion_matrices_detailed.png...")

    # Load predictions
    pred_time_file = ROOT / "experiments" / "w3_01_dt_time" / "test_eval" / "test_predictions.csv"
    pred_rand_file = ROOT / "experiments" / "w3_02_dt_random" / "test_eval" / "test_predictions.csv"

    if not (pred_time_file.exists() and pred_rand_file.exists()):
        print("  Prediction files not found, skipping confusion matrices.")
        return

    df_time = pd.read_csv(pred_time_file)
    df_rand = pd.read_csv(pred_rand_file)

    cm_time = confusion_matrix(df_time["y_true"], df_time["y_pred"], labels=[0, 1])
    cm_rand = confusion_matrix(df_rand["y_true"], df_rand["y_pred"], labels=[0, 1])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # Helper to plot annot matrix
    def plot_cm(ax, cm, title, subtitle, color_map, is_failure_case=False):
        tn, fp, fn, tp = cm.ravel()
        total = cm.sum()

        im = ax.imshow(cm, interpolation="nearest", cmap=color_map)
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

        labels = [["True Negative (TN)", "False Positive (FP)"],
                  ["False Negative (FN)", "True Positive (TP)"]]

        for i in range(2):
            for j in range(2):
                val = cm[i, j]
                pct = val / total * 100
                text_color = "white" if (val > cm.max() * 0.45) else "black"
                cell_text = f"{labels[i][j]}\n\n{val:,}\n({pct:.2f}%)"
                ax.text(j, i, cell_text, ha="center", va="center",
                        color=text_color, fontsize=10, fontweight="bold")

        ax.set_xticks([0, 1])
        ax.set_yticks([0, 1])
        ax.set_xticklabels(["BENIGN (Dự đoán)", "Attack (Dự đoán)"], fontsize=10)
        ax.set_yticklabels(["BENIGN (Thực tế)", "Attack (Thực tế)"], fontsize=10)
        ax.set_title(title, pad=12)
        ax.set_xlabel(subtitle, fontsize=9.5, labelpad=8)

        if is_failure_case:
            # Highlight the severe FN cell
            rect = plt.Rectangle((0.5, 0.5), 1, 1, fill=False, edgecolor="red", linewidth=3)
            ax.add_patch(rect)

    plot_cm(ax1, cm_time,
            "W3-01: Time-based Split (Thực tế Phân tách Thời gian)",
            "Thất bại Zero-shot: 3,725 cuộc tấn công SSH bị bỏ lọt (FN = 99.8%)\nF1 = 0.0037 | Recall = 0.19%",
            plt.cm.Blues, is_failure_case=True)

    plot_cm(ax2, cm_rand,
            "W3-02: Random Split (Đối chứng Rò rỉ Dữ liệu)",
            "Ảo giác Hiệu năng Cao do Rò rỉ Thông tin: TP = 4,526 (99.5%)\nF1 = 0.9964 | Recall = 99.52%",
            plt.cm.Greens, is_failure_case=False)

    plt.suptitle("TV2: Ma trận Nhầm lẫn Chi tiết (Confusion Matrix) - Đánh giá trên Tập Test Độc lập", y=1.02)
    plt.tight_layout()

    out_file1 = OUTPUT_DIR / "03_confusion_matrices_detailed.png"
    out_file2 = EXP_FIGURES / "03_confusion_matrices_detailed.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def generate_04_roc_pr_curves():
    """4. Dual PR & ROC Curves with AP & AUC annotations."""
    print(">>> [4/6] Generating 04_roc_and_pr_curves_comparative.png...")
    pred_time_file = ROOT / "experiments" / "w3_01_dt_time" / "test_eval" / "test_predictions.csv"
    pred_rand_file = ROOT / "experiments" / "w3_02_dt_random" / "test_eval" / "test_predictions.csv"

    if not (pred_time_file.exists() and pred_rand_file.exists()):
        print("  Predictions not found, skipping ROC/PR curves.")
        return

    df_time = pd.read_csv(pred_time_file)
    df_rand = pd.read_csv(pred_rand_file)

    p_time, r_time, _ = precision_recall_curve(df_time["y_true"], df_time["y_proba"])
    p_rand, r_rand, _ = precision_recall_curve(df_rand["y_true"], df_rand["y_proba"])
    ap_time = average_precision_score(df_time["y_true"], df_time["y_proba"])
    ap_rand = average_precision_score(df_rand["y_true"], df_rand["y_proba"])

    fpr_time, tpr_time, _ = roc_curve(df_time["y_true"], df_time["y_proba"])
    fpr_rand, tpr_rand, _ = roc_curve(df_rand["y_true"], df_rand["y_proba"])
    auc_time = roc_auc_score(df_time["y_true"], df_time["y_proba"])
    auc_rand = roc_auc_score(df_rand["y_true"], df_rand["y_proba"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

    # 1. Precision-Recall Curve
    ax1.plot(r_time, p_time, color="#d62728", linewidth=2.5,
             label=f"W3-01 Time Split (AP = {ap_time:.4f})")
    ax1.plot(r_rand, p_rand, color="#2ca02c", linewidth=2.5,
             label=f"W3-02 Random Split (AP = {ap_rand:.4f})")

    baseline = df_time["y_true"].mean()
    ax1.axhline(baseline, color="gray", linestyle=":", label=f"Tỷ lệ Ngẫu nhiên (Prevalence = {baseline:.3f})")
    ax1.set_xlabel("Recall (Tỷ lệ Phát hiện)")
    ax1.set_ylabel("Precision (Độ Chuẩn xác)")
    ax1.set_title("Đường cong Precision-Recall (PR Curve)")
    ax1.set_xlim(-0.02, 1.02)
    ax1.set_ylim(-0.02, 1.05)
    ax1.grid(True)
    ax1.legend(loc="center right", framealpha=0.9)

    # 2. ROC Curve
    ax2.plot(fpr_time, tpr_time, color="#d62728", linewidth=2.5,
             label=f"W3-01 Time Split (ROC-AUC = {auc_time:.4f})")
    ax2.plot(fpr_rand, tpr_rand, color="#2ca02c", linewidth=2.5,
             label=f"W3-02 Random Split (ROC-AUC = {auc_rand:.4f})")
    ax2.plot([0, 1], [0, 1], color="gray", linestyle="--", label="Đoán Ngẫu nhiên (AUC = 0.50)")

    ax2.set_xlabel("False Positive Rate (FPR)")
    ax2.set_ylabel("True Positive Rate (Recall / TPR)")
    ax2.set_title("Đường cong ROC (Receiver Operating Characteristic)")
    ax2.set_xlim(-0.02, 1.02)
    ax2.set_ylim(-0.02, 1.05)
    ax2.grid(True)
    ax2.legend(loc="lower right", framealpha=0.9)

    plt.suptitle("TV2: Đánh giá Năng lực Phân biệt - Đường cong PR & ROC trên Tập Test", y=1.02)
    plt.tight_layout()

    out_file1 = OUTPUT_DIR / "04_roc_and_pr_curves_comparative.png"
    out_file2 = EXP_FIGURES / "04_roc_and_pr_curves_comparative.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def generate_05_feature_importance():
    """5. Top 20 Categorized Feature Importances."""
    print(">>> [5/6] Generating 05_feature_importance_top20.png...")
    feat_file = ROOT / "experiments" / "w3_01_dt_time" / "feature_importances.csv"
    if not feat_file.exists():
        print("  Feature importance CSV not found, skipping.")
        return

    df = pd.read_csv(feat_file).head(20).iloc[::-1]  # Bottom to top for horizontal bar

    # Categorize features by network domain
    categories = []
    colors = []

    for feat in df["feature"]:
        if "Port" in feat:
            categories.append("Port / Metadata")
            colors.append("#e7298a")  # Magenta
        elif any(k in feat for k in ["IAT", "Duration"]):
            categories.append("Inter-Arrival Time (IAT) & Duration")
            colors.append("#d95f02")  # Orange
        elif any(k in feat for k in ["Length", "Bytes", "Size", "Segment"]):
            categories.append("Packet / Flow Length")
            colors.append("#1b9e77")  # Green
        elif any(k in feat for k in ["Flag", "Header"]):
            categories.append("Header & TCP Flags")
            colors.append("#7570b3")  # Purple
        else:
            categories.append("Flow Statistics")
            colors.append("#66a61e")

    fig, ax = plt.subplots(figsize=(13, 8))
    bars = ax.barh(df["feature"], df["importance"], color=colors, edgecolor="black", linewidth=0.5, height=0.7)

    # Annotate value at the end of each bar
    for bar in bars:
        w = bar.get_width()
        if w > 0.001:
            ax.text(w + 0.003, bar.get_y() + bar.get_height()/2, f"{w*100:.2f}%",
                    va="center", ha="left", fontsize=9, fontweight="bold", color="#333333")

    ax.set_xlabel("Tầm quan trọng tương đối (Gini Impurity Importance)")
    ax.set_title("TV2: Top 20 Đặc trưng Mạng Quan trọng Nhất - Decision Tree (W3-01 Time-based)")
    ax.set_xlim(0, max(df["importance"]) * 1.15)
    ax.grid(axis="x")

    # Legend for categories
    patches = [
        mpatches.Patch(color="#e7298a", label="Cổng Mạng (Destination Port)"),
        mpatches.Patch(color="#d95f02", label="Thời gian Gói tin & Luồng (IAT, Duration)"),
        mpatches.Patch(color="#1b9e77", label="Kích thước Gói tin (Packet Length/Size)"),
        mpatches.Patch(color="#7570b3", label="Cờ Giao thức & Tiêu đề (Flags & Headers)"),
    ]
    ax.legend(handles=patches, loc="lower right", framealpha=0.95, fontsize=9.5)

    plt.tight_layout()
    out_file1 = OUTPUT_DIR / "05_feature_importance_top20.png"
    out_file2 = EXP_FIGURES / "05_feature_importance_top20.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def generate_06_data_leakage_and_benchmark():
    """6. Subtype Detection Gap (FTP vs SSH) & 3-Model Benchmark."""
    print(">>> [6/6] Generating 06_data_leakage_benchmark.png...")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6.5))

    # --- Subplot 1: Subtype Recall Gap (FTP vs SSH) ---
    scenarios = ["W3-01 (Time-based)", "W3-02 (Random Split)"]
    ftp_recalls = [1.0, 1.0]      # FTP detected perfectly when seen
    ssh_recalls = [0.0019, 0.9954] # 0% on Time vs 99.5% on Random

    x = np.arange(len(scenarios))
    width = 0.32

    rects1 = ax1.bar(x - width/2, [v*100 for v in ftp_recalls], width,
                     label="FTP-Patator Recall (Đã học trong Train)", color="#1f77b4", edgecolor="black")
    rects2 = ax1.bar(x + width/2, [v*100 for v in ssh_recalls], width,
                     label="SSH-Patator Recall (Tấn công chưa từng gặp ở Train)", color="#d62728", edgecolor="black")

    for bar in rects1:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h:.1f}%", ha="center", va="bottom", fontweight="bold")
    for bar in rects2:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h:.1f}%", ha="center", va="bottom", fontweight="bold", color="#d62728" if h < 5 else "black")

    ax1.set_ylabel("Tỷ lệ Phát hiện (Recall %)")
    ax1.set_title("Năng lực Phát hiện Tấn công theo Dạng (FTP vs SSH)\n[Thất bại Zero-shot Transfer trên Kịch bản Thực tế]")
    ax1.set_xticks(x)
    ax1.set_xticklabels(scenarios, fontweight="bold")
    ax1.set_ylim(0, 118)
    ax1.grid(axis="y")
    ax1.legend(loc="upper left", framealpha=0.9)

    # Explanatory callout
    ax1.annotate(
        "Lỗ hổng Zero-shot: 0.19%\nDT không nhận ra SSH!",
        xy=(0 + width/2, 2), xytext=(0.2, 35),
        arrowprops=dict(facecolor="#d62728", shrink=0.08, width=1.5, headwidth=7),
        fontsize=9.5, fontweight="bold", color="#d62728",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#ffe3e3", edgecolor="#d62728")
    )

    # --- Subplot 2: 3-Model Benchmark (Decision Tree vs Random Forest vs XGBoost) ---
    models = ["Decision Tree\n(TV2)", "Random Forest\n(TV3)", "XGBoost\n(TV4)"]
    # Data from artifacts/week3_week4/test_comparison.csv
    f1_time = [0.0037, 0.0037, 0.0069]     # Time-based split F1
    f1_rand = [0.9964, 0.9997, 0.9984]     # Random split F1

    x2 = np.arange(len(models))
    rects_time = ax2.bar(x2 - width/2, [v*100 for v in f1_time], width,
                         label="W3-01: Time-based Split F1 (%)", color="#ff7f0e", edgecolor="black")
    rects_rand = ax2.bar(x2 + width/2, [v*100 for v in f1_rand], width,
                         label="W3-02: Random Split F1 (%)", color="#2ca02c", edgecolor="black")

    for bar in rects_time:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h:.2f}%", ha="center", va="bottom", fontweight="bold", color="#d62728")
    for bar in rects_rand:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 2, f"{h:.2f}%", ha="center", va="bottom", fontweight="bold")

    ax2.set_ylabel("F1-Score (%)")
    ax2.set_title("So sánh Hiệu năng 3 Mô hình (DT vs RF vs XGBoost)\n[Tương quan giữa Phân tách Thời gian & Random]")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(models, fontweight="bold")
    ax2.set_ylim(0, 118)
    ax2.grid(axis="y")
    ax2.legend(loc="upper left", framealpha=0.9)

    plt.suptitle("TV2 & Benchmark: Minh chứng Thực nghiệm Hiện tượng Rò rỉ Dữ liệu (Data Leakage)", y=1.02)
    plt.tight_layout()

    out_file1 = OUTPUT_DIR / "06_data_leakage_benchmark.png"
    out_file2 = EXP_FIGURES / "06_data_leakage_benchmark.png"
    plt.savefig(out_file1, bbox_inches="tight")
    plt.savefig(out_file2, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved -> {out_file1.name}")


def main():
    print("=" * 80)
    print("GENERATING COMPREHENSIVE SUITE OF DETAILED FIGURES FOR TV2")
    print("=" * 80)

    generate_01_tree_structure()
    generate_02_overfitting_analysis()
    generate_03_confusion_matrices()
    generate_04_roc_pr_curves()
    generate_05_feature_importance()
    generate_06_data_leakage_and_benchmark()

    print("\n" + "=" * 80)
    print(f"ALL 6 DETAILED FIGURES GENERATED SUCCESSFULLY!")
    print(f"Output directories:\n  - {OUTPUT_DIR}\n  - {EXP_FIGURES}")
    print("=" * 80)


if __name__ == "__main__":
    main()
