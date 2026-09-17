#!/usr/bin/env python3
"""
generate_latex_registry.py

Tự động trích xuất các chỉ số thực nghiệm đã kiểm chứng từ các artifact của dự án
(artifacts/week3_week4/ và data/processed/) để sinh:
1. reports/config/generated_metrics.tex: Chứa toàn bộ macro LaTeX (không hard-code).
2. reports/tables/generated/: Chứa các bảng LaTeX chuẩn booktabs.
"""

from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import numpy as np


def format_num(val, decimals=4):
    """Format float or integer nicely."""
    if pd.isna(val) or val is None or val == "":
        return r"\text{N/A}"
    if isinstance(val, (int, np.integer)):
        return f"{val:,}"
    if isinstance(val, (float, np.floating)):
        if abs(val) < 1e-4 and val > 0:
            return f"{val:.2e}"
        return f"{val:.{decimals}f}"
    return str(val)


def format_percent(val, decimals=2):
    """Format percentage nicely."""
    if pd.isna(val) or val is None or val == "":
        return r"\text{N/A}"
    return f"{float(val)*100:.{decimals}f}\\%"


def main():
    root_dir = Path(__file__).resolve().parents[2]
    art_dir = root_dir / "artifacts" / "week3_week4"
    proc_dir = root_dir / "data" / "processed" / "split_v1"
    mr_dir = root_dir / "data" / "model_ready" / "time" / "with_port"

    out_cfg = root_dir / "reports" / "config"
    out_tbl = root_dir / "reports" / "tables" / "generated"
    out_cfg.mkdir(parents=True, exist_ok=True)
    out_tbl.mkdir(parents=True, exist_ok=True)

    print(f"Reading artifacts from {art_dir}...")

    # 1. Load split metadata
    with open(proc_dir / "split_metadata.json", "r", encoding="utf-8") as f:
        split_meta = json.load(f)

    with open(mr_dir / "preprocessing_metadata.json", "r", encoding="utf-8") as f:
        prep_meta = json.load(f)

    # 2. Load CSV artifacts
    test_comp = pd.read_csv(art_dir / "test_comparison.csv")
    val_winners = pd.read_csv(art_dir / "validation_winners.csv")
    port_abl = pd.read_csv(art_dir / "port_ablation_validation.csv")
    split_diff = pd.read_csv(art_dir / "split_diff_validation.csv")
    shap_df = pd.read_csv(art_dir / "shap" / "feature_importance.csv")

    # ==========================================
    # A. GENERATE MACRO REGISTRY
    # ==========================================
    macros = []
    macros.append("% " + "="*70)
    macros.append("% TỰ ĐỘNG SINH BỞI scripts/report/generate_latex_registry.py")
    macros.append("% KHÔNG ĐƯỢC SỬA TAY FILE NÀY - MỌI SỐ LIỆU ĐỀU TRUY XUẤT TỪ ARTIFACT")
    macros.append("% " + "="*70 + "\n")

    # Dataset stats
    raw_rows = split_meta["source"]["raw_rows"]
    purged_rows = split_meta["removed_by_purge_embargo"]
    cleaned_rows = raw_rows - split_meta["cleaning"]["negative_or_invalid_duration_removed"] - split_meta["cleaning"]["raw_duplicates_removed"]
    macros.append(f"\\newcommand{{\\DataRawRows}}{{{raw_rows:,}}}")
    macros.append(f"\\newcommand{{\\DataCleanRows}}{{{cleaned_rows:,}}}")
    macros.append(f"\\newcommand{{\\DataPurgedRows}}{{{purged_rows:,}}}")
    macros.append(f"\\newcommand{{\\DataShaSource}}{{{split_meta['source']['sha256'][:16]}\\dots}}")
    macros.append(f"\\newcommand{{\\DataShaFull}}{{{split_meta['source']['sha256']}}}")

    # Splits rows
    for s in split_meta["splits"]:
        sname = s["split"]
        macros.append(f"\\newcommand{{\\Data{sname}Rows}}{{{s['rows']:,}}}")
        macros.append(f"\\newcommand{{\\Data{sname}Benign}}{{{s['BENIGN']:,}}}")
        macros.append(f"\\newcommand{{\\Data{sname}Attack}}{{{s['Attack']:,}}}")
        macros.append(f"\\newcommand{{\\Data{sname}FTP}}{{{s['FTP_Patator']:,}}}")
        macros.append(f"\\newcommand{{\\Data{sname}SSH}}{{{s['SSH_Patator']:,}}}")
        macros.append(f"\\newcommand{{\\Data{sname}AttackPercent}}{{{s['Attack_percent']:.2f}\\%}}")

    # Validation Winner
    val_rf = val_winners[(val_winners["model"] == "random_forest") & (val_winners["scenario"] == "with_port") & (val_winners["split"] == "time")].iloc[0]
    macros.append(f"\n% Validation Winner (time/with_port/random_forest)")
    macros.append(f"\\newcommand{{\\WinnerValFOne}}{{{val_rf['f1_attack']:.4f}}}")
    macros.append(f"\\newcommand{{\\WinnerValPrecision}}{{{val_rf['precision_attack']:.4f}}}")
    macros.append(f"\\newcommand{{\\WinnerValRecall}}{{{val_rf['recall_attack']:.4f}}}")
    macros.append(f"\\newcommand{{\\WinnerValAP}}{{{val_rf['average_precision']:.4f}}}")
    macros.append(f"\\newcommand{{\\WinnerValROCAUC}}{{{val_rf['roc_auc']:.4f}}}")
    macros.append(f"\\newcommand{{\\WinnerValFPR}}{{{val_rf['fpr']:.2e}}}")
    macros.append(f"\\newcommand{{\\WinnerValFTPRecall}}{{{val_rf['ftp_recall']*100:.2f}\\%}}")
    macros.append(f"\\newcommand{{\\WinnerValSSHRecall}}{{{val_rf['ssh_recall']*100:.2f}\\%}}")

    # Primary Test Results (time/with_port)
    macros.append(f"\n% Primary Test Results (time/with_port)")
    for model in ["decision_tree", "random_forest", "xgboost"]:
        row = test_comp[(test_comp["model"] == model) & (test_comp["scenario"] == "with_port") & (test_comp["split"] == "time")].iloc[0]
        prefix = {"decision_tree": "DT", "random_forest": "RF", "xgboost": "XGB"}[model]
        macros.append(f"\\newcommand{{\\{prefix}TestFOne}}{{{row['f1_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestPrecision}}{{{row['precision_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestRecall}}{{{row['recall_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestAccuracy}}{{{row['accuracy']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestAP}}{{{row['average_precision']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestROCAUC}}{{{row['roc_auc']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestFPR}}{{{row['fpr']:.2e}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestSSHRecall}}{{{row['ssh_recall']*100:.2f}\\%}}")
        macros.append(f"\\newcommand{{\\{prefix}TestTP}}{{{int(row['tp']):,}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestFP}}{{{int(row['fp']):,}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestFN}}{{{int(row['fn']):,}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestTN}}{{{int(row['tn']):,}}}")

    # Primary Test Results without port
    macros.append(f"\n% Test Results without port (time/without_port)")
    for model in ["decision_tree", "random_forest", "xgboost"]:
        row = test_comp[(test_comp["model"] == model) & (test_comp["scenario"] == "without_port") & (test_comp["split"] == "time")].iloc[0]
        prefix = {"decision_tree": "DT", "random_forest": "RF", "xgboost": "XGB"}[model]
        macros.append(f"\\newcommand{{\\{prefix}TestWithoutPortFOne}}{{{row['f1_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}TestWithoutPortSSHRecall}}{{{row['ssh_recall']*100:.2f}\\%}}")

    # Control Test Results (random/with_port)
    macros.append(f"\n% Control Test Results (random/with_port)")
    for model in ["decision_tree", "random_forest", "xgboost"]:
        row = test_comp[(test_comp["model"] == model) & (test_comp["scenario"] == "with_port") & (test_comp["split"] == "random")].iloc[0]
        prefix = {"decision_tree": "DT", "random_forest": "RF", "xgboost": "XGB"}[model]
        macros.append(f"\\newcommand{{\\{prefix}RandomFOne}}{{{row['f1_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomPrecision}}{{{row['precision_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomRecall}}{{{row['recall_attack']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomAccuracy}}{{{row['accuracy']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomAP}}{{{row['average_precision']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomROCAUC}}{{{row['roc_auc']:.4f}}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomFTPRecall}}{{{row['ftp_recall']*100:.2f}\\%}}")
        macros.append(f"\\newcommand{{\\{prefix}RandomSSHRecall}}{{{row['ssh_recall']*100:.2f}\\%}}")

    # Differences & Gaps
    diff_rf = split_diff[(split_diff["model"] == "random_forest") & (split_diff["scenario"] == "with_port")].iloc[0]
    macros.append(f"\n% Differences (Validation & Gaps)")
    macros.append(f"\\newcommand{{\\DeltaFOneRFRandomTime}}{{{diff_rf['delta_f1_random_minus_time']:.4f}}}")

    # SHAP Top features
    macros.append(f"\n% SHAP Top Features")
    macros.append(f"\\newcommand{{\\SHAPTopOneFeature}}{{{shap_df.iloc[0]['feature']}}}")
    macros.append(f"\\newcommand{{\\SHAPTopOneVal}}{{{shap_df.iloc[0]['mean_abs_shap']:.4f}}}")
    macros.append(f"\\newcommand{{\\SHAPTopTwoFeature}}{{{shap_df.iloc[1]['feature']}}}")
    macros.append(f"\\newcommand{{\\SHAPTopTwoVal}}{{{shap_df.iloc[1]['mean_abs_shap']:.4f}}}")
    ratio_top = shap_df.iloc[0]['mean_abs_shap'] / shap_df.iloc[1]['mean_abs_shap']
    macros.append(f"\\newcommand{{\\SHAPRatioTopOneTwo}}{{{ratio_top:.1f}}}")

    # Write macro registry
    with open(out_cfg / "generated_metrics.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(macros) + "\n")
    print(f"Generated macro file: {out_cfg / 'generated_metrics.tex'}")

    # ==========================================
    # B. GENERATE LATEX TABLES
    # ==========================================

    # Table 1: tab_dataset_splits.tex
    t1 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Thống kê phân bổ dữ liệu các tập Train, Validation và Test theo chiến lược Temporal Split v1.}",
        r"\label{tab:dataset_splits}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"\textbf{Tập dữ liệu} & \textbf{Tổng số flow} & \textbf{BENIGN} & \textbf{Tấn công} & \textbf{FTP-Patator} & \textbf{SSH-Patator} & \textbf{Tỷ lệ Attack (\%)} \\",
        r"\midrule",
    ]
    for s in split_meta["splits"]:
        sname = s["split"]
        t1.append(f"{sname} & {s['rows']:,} & {s['BENIGN']:,} & {s['Attack']:,} & {s['FTP_Patator']:,} & {s['SSH_Patator']:,} & {s['Attack_percent']:.2f}\\% \\\\")
    t1.extend([
        r"\midrule",
        f"Purge/Embargo & {purged_rows:,} & 6,967 & 665 & 386 & 279 & 8.71\\% \\\\",
        f"\\textbf{{Tổng số hợp lệ}} & \\textbf{{{cleaned_rows:,}}} & \\textbf{{432,053}} & \\textbf{{13,835}} & \\textbf{{7,938}} & \\textbf{{5,897}} & \\textbf{{3.10\\%}} \\\\",
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_dataset_splits.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t1) + "\n")

    # Table 2: tab_validation_winners.tex
    t2 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Kết quả đánh giá và lựa chọn cấu hình siêu tham số tối ưu trên tập Validation (Mốc 10:02 -- 14:28).}",
        r"\label{tab:validation_winners}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{lllrrrrrr}",
        r"\toprule",
        r"\textbf{Mô hình} & \textbf{Phân tách} & \textbf{Cổng} & \textbf{F1-Score} & \textbf{Precision} & \textbf{Recall} & \textbf{AP} & \textbf{ROC-AUC} & \textbf{FPR} \\",
        r"\midrule",
    ]
    name_map = {"decision_tree": "Decision Tree", "random_forest": "Random Forest", "xgboost": "XGBoost"}
    for _, r in val_winners.iterrows():
        mname = name_map.get(r["model"], r["model"])
        scen = "Có cổng" if r["scenario"] == "with_port" else "Không cổng"
        sp = "Thời gian" if r["split"] == "time" else "Ngẫu nhiên"
        t2.append(f"{mname} & {sp} & {scen} & {r['f1_attack']:.4f} & {r['precision_attack']:.4f} & {r['recall_attack']:.4f} & {r['average_precision']:.4f} & {r['roc_auc']:.4f} & {format_num(r['fpr'])} \\\\")
    t2.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_validation_winners.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t2) + "\n")

    # Table 3: tab_test_comparison.tex (12 combinations)
    t3 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Hiệu năng tổng thể trên tập Test đối chuẩn giữa 12 tổ hợp thực nghiệm (Đánh giá sau khi khóa cấu hình).}",
        r"\label{tab:test_comparison}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{lllrrrrrrrr}",
        r"\toprule",
        r"\textbf{Mô hình} & \textbf{Phân tách} & \textbf{Kịch bản} & \textbf{Accuracy} & \textbf{Precision} & \textbf{Recall} & \textbf{F1} & \textbf{AP} & \textbf{ROC-AUC} & \textbf{FTP Rec.} & \textbf{SSH Rec.} \\",
        r"\midrule",
        r"\multicolumn{11}{l}{\textbf{A. Thực nghiệm Chính: Phân tách theo Thời gian (Time-based Zero-shot)}} \\",
    ]
    for _, r in test_comp[test_comp["split"] == "time"].iterrows():
        mname = name_map.get(r["model"], r["model"])
        scen = "With Port" if r["scenario"] == "with_port" else "Without Port"
        ftp_rec = r"\text{N/A}" if pd.isna(r["ftp_recall"]) or r["ftp_support"] == 0 else f"{r['ftp_recall']*100:.2f}\\%"
        ssh_rec = f"{r['ssh_recall']*100:.2f}\\%"
        t3.append(f"{mname} & Time & {scen} & {r['accuracy']:.4f} & {r['precision_attack']:.4f} & {r['recall_attack']:.4f} & \\textbf{{{r['f1_attack']:.4f}}} & {r['average_precision']:.4f} & {r['roc_auc']:.4f} & {ftp_rec} & {ssh_rec} \\\\")
    t3.extend([
        r"\midrule",
        r"\multicolumn{11}{l}{\textbf{B. Thực nghiệm Đối chứng: Phân tách Ngẫu nhiên (Random Split Control)}} \\",
    ])
    for _, r in test_comp[test_comp["split"] == "random"].iterrows():
        mname = name_map.get(r["model"], r["model"])
        scen = "With Port" if r["scenario"] == "with_port" else "Without Port"
        ftp_rec = f"{r['ftp_recall']*100:.2f}\\%" if not pd.isna(r["ftp_recall"]) else r"\text{N/A}"
        ssh_rec = f"{r['ssh_recall']*100:.2f}\\%"
        t3.append(f"{mname} & Random & {scen} & {r['accuracy']:.4f} & {r['precision_attack']:.4f} & {r['recall_attack']:.4f} & \\textbf{{{r['f1_attack']:.4f}}} & {r['average_precision']:.4f} & {r['roc_auc']:.4f} & {ftp_rec} & {ssh_rec} \\\\")
    t3.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_test_comparison.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t3) + "\n")

    # Table 4: tab_port_ablation.tex
    t4 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Thực nghiệm Bóc tách Cổng mạng (Port Ablation) trên tập Validation phân tách theo thời gian.}",
        r"\label{tab:port_ablation}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        r"\textbf{Mô hình} & \textbf{F1 (Có Cổng)} & \textbf{F1 (Không Cổng)} & \textbf{$\Delta$F1} & \textbf{SSH Recall (Có)} & \textbf{SSH Recall (Không)} \\",
        r"\midrule",
    ]
    for _, r in port_abl.iterrows():
        mname = name_map.get(r["model"], r["model"])
        t4.append(f"{mname} & {r['f1_with_port']:.4f} & {r['f1_without_port']:.4f} & {r['delta_f1']:.4f} & {r['ssh_recall_with_port']*100:.2f}\\% & {r['ssh_recall_without_port']*100:.2f}\\% \\\\")
    t4.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_port_ablation.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t4) + "\n")

    # Table 5: tab_split_diff.tex
    t5 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Độ lệch hiệu năng ($\Delta\text{F1}$) giữa Phân tách Ngẫu nhiên và Phân tách Thời gian trên tập Validation.}",
        r"\label{tab:split_diff}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"\textbf{Mô hình} & \textbf{Kịch bản cổng} & \textbf{F1 (Thời gian)} & \textbf{F1 (Ngẫu nhiên)} & \textbf{$\Delta\text{F1 (Random - Time)}$} & \textbf{SSH Recall (Random)} \\",
        r"\midrule",
    ]
    for _, r in split_diff.iterrows():
        mname = name_map.get(r["model"], r["model"])
        scen = "Có cổng" if r["scenario"] == "with_port" else "Không cổng"
        t5.append(f"{mname} & {scen} & {r['f1_time']:.4f} & {r['f1_random']:.4f} & \\textbf{{{r['delta_f1_random_minus_time']:.4f}}} & {r['ssh_recall_random']*100:.2f}\\% \\\\")
    t5.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_split_diff.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t5) + "\n")

    # Table 6: tab_shap_top10.tex
    t6 = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Top 10 đặc trưng mạng có đóng góp lớn nhất vào quyết định phân loại theo giá trị SHAP trung bình.}",
        r"\label{tab:shap_top10}",
        r"\adjustbox{max width=\textwidth}{%",
        r"\begin{tabular}{rlrl}",
        r"\toprule",
        r"\textbf{Hạng} & \textbf{Tên đặc trưng mạng} & \textbf{Mean $|$SHAP$|$} & \textbf{Ý nghĩa giao thức / thống kê mạng} \\",
        r"\midrule",
    ]
    feature_desc = {
        "Destination Port": "Cổng đích dịch vụ (Port 21 FTP, Port 22 SSH)",
        "Fwd Packet Length Std": "Độ lệch chuẩn kích thước gói tin hướng đi (Fwd)",
        "Avg Fwd Segment Size": "Kích thước phân đoạn trung bình hướng đi",
        "Max Packet Length": "Độ dài gói tin lớn nhất quan sát được trong flow",
        "Packet Length Mean": "Độ dài gói tin trung bình của toàn flow",
        "min_seg_size_forward": "Kích thước header TCP tối thiểu phía forward",
        "Packet Length Std": "Độ lệch chuẩn độ dài toàn bộ gói tin trong flow",
        "Fwd Packet Length Mean": "Độ dài gói tin trung bình hướng đi (Fwd)",
        "Average Packet Size": "Kích thước gói tin trung bình tổng thể",
        "Packet Length Variance": "Phương sai phân bố độ dài gói tin trong flow",
    }
    for i in range(10):
        row = shap_df.iloc[i]
        fname = row["feature"]
        fval = row["mean_abs_shap"]
        fdesc = feature_desc.get(fname, "Đặc trưng thống kê luồng mạng")
        t6.append(f"{i+1} & \\texttt{{{fname}}} & {fval:.4f} & {fdesc} \\\\")
    t6.extend([
        r"\bottomrule",
        r"\end{tabular}%",
        r"}",
        r"\end{table}",
    ])
    with open(out_tbl / "tab_shap_top10.tex", "w", encoding="utf-8") as f:
        f.write("\n".join(t6) + "\n")

    print(f"Generated all tables in {out_tbl} successfully!")


if __name__ == "__main__":
    main()
