# Phát hiện SSH/FTP Brute Force trên CICIDS2017: Nghiên cứu Ảnh hưởng của Chiến lược Chia Dữ liệu

Dự án nghiên cứu và đánh giá mô hình học máy (Machine Learning) trong bài toán Hệ thống Phát hiện Xâm nhập Mạng (NIDS) phát hiện tấn công **Brute Force FTP và SSH** trên tập dữ liệu chuẩn **CICIDS2017 Tuesday** (nhãn `BENIGN / FTP-Patator / SSH-Patator`).

Trọng tâm nghiên cứu là **phân tích tác động của chiến lược chia dữ liệu theo thời gian (Time-based Split) so với chia ngẫu nhiên (Random Split)**, đánh giá khả năng tổng quát hóa thực tế của các mô hình học máy dạng cây (Decision Tree, Random Forest, XGBoost) khi đối mặt với các biến thể tấn công mới theo thời gian.

---

## 🎯 Câu hỏi Nghiên cứu (Research Questions)

1. **RQ1 (Khả năng tổng quát hóa theo thời gian & Chuyển giao Zero-Shot)**: Khi mô hình chỉ được huấn luyện trên dữ liệu quá khứ chứa `FTP-Patator` (buổi sáng), liệu mô hình có thể phát hiện được cuộc tấn công `SSH-Patator` (buổi chiều) trong dữ liệu tương lai hay không?
2. **RQ2 (Độ lệch đánh giá của phép chia ngẫu nhiên - Optimistic Evaluation Bias)**: Việc phân chia dữ liệu ngẫu nhiên (Random Split) — vốn phổ biến trong các nghiên cứu học thuật — làm sai lệch kết quả đánh giá như thế nào do vi phạm tính độc lập thời gian giữa các flow cùng chiến dịch tấn công?
3. **RQ3 (Độ phụ thuộc vào cổng dịch vụ - Port Ablation & Diễn giải mô hình)**: Việc đưa cổng đích (`Destination Port`) vào không gian đặc trưng ảnh hưởng như thế nào đến khả năng tổng quát hóa, và mô hình thực sự học được các đặc trưng hành vi mạng nào (thông qua SHAP và Cây quyết định)?

---

## 👥 Phân công Vai trò & Sản phẩm Thực nghiệm (Week 3 – Week 4)

Dự án được phân chia thành 4 mảng công việc chuyên biệt với kết quả đã hoàn thiện và được lưu trữ đầy đủ trong repository:

| Thành viên | Vai trò | Mã công việc | Trọng tâm & Đóng góp | Sản phẩm & Thư mục Artifacts |
|---|---|---|---|---|
| **TV1** | Data Preprocessing Lead | W3-00 | • Phục hồi chuỗi thời gian 24h (1–5h → 13–17h chiều).<br>• Xây dựng pipeline chia dữ liệu thời gian (`split_v1`) và ngẫu nhiên (`random_split_v1`).<br>• Chuẩn hóa dữ liệu mô hình hóa. | • `scripts/prepare_splits.py`<br>• `scripts/generate_model_ready.py`<br>• `data/model_ready/` |
| **TV2** | Decision Tree Lead | W3-01<br>W3-02 | • Tinh chỉnh siêu tham số Decision Tree (`criterion`, `max_depth`, `min_samples_leaf`).<br>• Trực quan hóa cấu trúc cây, trích xuất quy tắc phân lớp logic.<br>• Phân tích quá khớp theo độ sâu (`max_depth`) và sinh bộ 6 biểu đồ khoa học 300 DPI. | • `notebooks/TV2_DecisionTree_W3-01_W3-02.ipynb`<br>• `scripts/train_tv2_all.py`<br>• `scripts/generate_detailed_visualizations.py`<br>• `artifacts/TV2_decision_tree/`<br>• `experiments/figures/` |
| **TV3** | Random Forest Lead | W3-03<br>W3-04 | • Huấn luyện & tinh chỉnh Random Forest.<br>• Thực nghiệm loại bỏ cổng mạng (Port Ablation: `with_port` vs `without_port`).<br>• Giải thích mô hình bằng SHAP (TreeExplainer). | • `notebooks/TV3_RandomForest_W3-03_W3-04.ipynb`<br>• `artifacts/TV3_random_forest/` |
| **TV4** | XGBoost Lead | W3-05<br>W3-06 | • Xây dựng kịch bản tuning tự động `RandomizedSearchCV` cho XGBoost.<br>• Đánh giá hiệu năng trên cả 2 kịch bản phân tách dữ liệu.<br>• Nghiên cứu hiện tượng tác động của cơ chế refit protocol. | • `src/ids/tune_xgboost.py`<br>• `src/ids/evaluate_tuned_model.py`<br>• `experiments/w3_05_time_tuning/`<br>• `experiments/w3_06_random_tuning/` |
| **Nhóm** | Benchmark Hợp nhất | W3–W4 | • Đánh giá đối chuẩn 3 mô hình trên 2 kịch bản phân tách và 2 không gian đặc trưng.<br>• Ghi nhận kết quả test mở đúng một lần (Single-open Test rule). | • `artifacts/week3_week4/test_comparison.csv`<br>• `artifacts/week3_week4/RESULTS.md`<br>• `docs/BAO_CAO_THUC_NGHIEM_W3_W4.md` |

---

## 📊 Tóm tắt Kết quả Thực nghiệm Chính (Canonical Benchmark)

Kết quả đối chuẩn hợp nhất trên tập Test mở đúng một lần (`artifacts/week3_week4/test_comparison.csv`):

### 1. Kịch bản Thời gian (Time-based Split) — Thử thách Zero-Shot Transfer
> **Điều kiện**: Huấn luyện **chỉ trên tập Train** (trước 10:00, 100% `FTP-Patator`). Đánh giá trên tập **Test** (sau 14:30, 100% `SSH-Patator`).

| Mô hình | Không gian đặc trưng | Test Accuracy | Precision (Attack) | Recall (Attack) | F1-Score (Attack) | SSH Recall | FTP Recall | Nhận xét học thuật |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **Decision Tree** | With Port (67 feats) | 0.9740 | 0.0000 | 0.0000 | **0.0000** | 0.00% | N/A | Cây rẽ nhánh `Port <= 21.5`, bỏ sót toàn bộ 3,732 flow SSH |
| **Random Forest** | With Port (67 feats) | **0.9742** | **1.0000** | **0.0019** | **0.0037** | **0.19%** | N/A | Bắt được 7/3,732 flow SSH nhờ cơ chế lấy mẫu ngẫu nhiên feature |
| **XGBoost (gốc)** | With Port (67 feats) | 0.9741 | 0.0000 | 0.0000 | **0.0000** | 0.00% | N/A | Bất lực trước port mới, toàn bộ flow SSH bị gán nhãn BENIGN |
| **Decision Tree** | Without Port (66 feats)| 0.9741 | 0.4375 | 0.0019 | **0.0037** | 0.19% | N/A | Bỏ port không giải quyết được zero-shot do đặc trưng gói tin khác biệt |
| **Random Forest** | Without Port (66 feats)| 0.9739 | 0.2414 | 0.0038 | **0.0074** | 0.38% | N/A | Tăng nhẹ recall nhưng sinh thêm báo động giả (FP = 44) |
| **XGBoost (gốc)** | Without Port (66 feats)| 0.9740 | 0.2653 | 0.0035 | **0.0069** | 0.35% | N/A | Tương tự RF, hiệu năng zero-shot thực tế vẫn dưới 1% |

*Lưu ý: Test time-based không có `FTP-Patator` (`support = 0`), do đó `FTP Recall = N/A` (không gán 0% hoặc 100%).*

### 2. Kịch bản Đối chứng Ngẫu nhiên (Random Split Control) — Độ lệch Lạc quan
> **Điều kiện**: Xáo trộn ngẫu nhiên toàn bộ flow trong ngày Tuesday giữa Train, Validation và Test.

| Mô hình | Không gian đặc trưng | Test Accuracy | Precision (Attack) | Recall (Attack) | F1-Score (Attack) | SSH Recall | FTP Recall |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Decision Tree** | With Port (67 feats) | 0.9996 | 0.9904 | 0.9980 | **0.9942** | 99.54% | 100.0% |
| **Random Forest** | With Port (67 feats) | 0.9999 | 1.0000 | 0.9993 | **0.9997** | 99.85% | 100.0% |
| **XGBoost** | With Port (67 feats) | 0.9999 | 0.9993 | 1.0000 | **0.9997** | 100.0% | 100.0% |
| **Decision Tree** | Without Port (66 feats)| 0.9989 | 0.9700 | 0.9949 | **0.9823** | 99.23% | 99.69% |
| **Random Forest** | Without Port (66 feats)| 0.9997 | 0.9934 | 0.9954 | **0.9944** | 99.28% | 99.73% |
| **XGBoost** | Without Port (66 feats)| 0.9999 | 0.9980 | 0.9987 | **0.9984** | 99.79% | 99.92% |

👉 **Kết luận cốt lõi**: Random split đạt F1 xấp xỉ 99.9% không phải do mô hình thông minh hơn, mà do **các flow thuộc cùng một chiến dịch tấn công (cùng host, cùng hành vi) bị xé lẻ vào cả hai tập**, khiến mô hình chỉ cần "nhận diện lại" các mẫu tương tự đã thấy. Khi triển khai thực tế theo thứ tự thời gian (Time-based), mô hình phải đối mặt với biến thể tấn công mới và sụp đổ hoàn toàn.

---

## 🔍 Lưu ý Quan trọng về Protocol & Kỹ thuật

### 1. Hai Đường ống Xử lý Timestamp trong Repo
- **Pipeline chuẩn chính thức (`scripts/prepare_splits.py`)**: Đọc dữ liệu raw Tuesday, áp dụng quy tắc phục hồi timestamp 24h: các giờ từ 1–5 buổi chiều được cộng thêm 12 giờ thành 13–17h theo kết quả phân tích EDA timeline. Dữ liệu chuẩn được xuất ra `data/processed/split_v1` và `data/model_ready/`.
- **Pipeline CLI cơ bản (`src/ids/data.py`)**: Bộ parser cơ bản chỉ đọc format chuỗi ngày giờ thuần túy, phù hợp cho dữ liệu đã có sẵn định dạng 24h hoặc dữ liệu giả lập (`synthetic: true`).

### 2. Sự khác biệt về Protocol Refit của XGBoost
- Trong benchmark hợp nhất (`artifacts/week3_week4/test_comparison.csv`), mô hình XGBoost tuân thủ **Strict Train-only fit** (chỉ huấn luyện trên Train gồm FTP), nên đạt F1 = 0.0000 trên Test (chỉ gồm SSH).
- Trong script tuning mở rộng `src/ids/tune_xgboost.py`, việc sử dụng `RandomizedSearchCV` mà không tắt `refit` (mặc định `refit=True`) dẫn đến việc mô hình sau khi chọn tham số được tự động huấn luyện lại trên toàn bộ tập gộp `Train + Validation`. Vì tập Validation chứa 1,886 flow `SSH-Patator`, mô hình đã được "học mồi" dạng tấn công SSH trước khi nộp vào Test, khiến F1 đạt 0.9910. Trong báo cáo, đây được ghi nhận là **thực nghiệm Few-shot / Seen Subtype** có chủ đích để so sánh với kịch bản Zero-Shot gốc.

---

## 🚀 Hướng dẫn Cài đặt & Chạy Thực nghiệm

### 1. Thiết lập Môi trường Python
Khuyến nghị sử dụng Python 3.10 – 3.12 trên môi trường ảo:

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[xai]"
```

### 2. Sinh Bộ 6 Biểu đồ Khoa học Chi tiết (TV2)
Chạy script chuyên biệt để tự động tạo trọn bộ 6 biểu đồ chuẩn công bố (300 DPI):

```powershell
python scripts/generate_detailed_visualizations.py
```
*Đầu ra được lưu tại `artifacts/TV2_decision_tree/figures/` và `experiments/figures/`:*
1. `01_tree_structure_detailed.png`: Cấu trúc cây quyết định 3 tầng đầu và ngưỡng rẽ nhánh cổng dịch vụ.
2. `02_overfitting_analysis_depth.png`: Đồ thị quá khớp giữa Train và Validation F1 theo độ sâu cây (`max_depth`).
3. `03_confusion_matrices_detailed.png`: Ma trận nhầm lẫn đối chiếu Time-based vs Random split.
4. `04_roc_and_pr_curves_comparative.png`: So sánh đường cong PR & ROC giữa 2 kịch bản.
5. `05_feature_importance_top20.png`: Top 20 đặc trưng quan trọng nhất phân theo nhóm mạng.
6. `06_data_leakage_benchmark.png`: Đối chứng tỷ lệ phát hiện theo subtype và benchmark 3 mô hình.

### 3. Chạy Notebook Thực nghiệm
Khởi động Jupyter Notebook hoặc VS Code để xem và chạy các phân tích tương tác:
- `notebooks/TV2_DecisionTree_W3-01_W3-02.ipynb` (Phân tích chuyên sâu Cây quyết định)
- `notebooks/TV3_RandomForest_W3-03_W3-04.ipynb` (Phân tích Random Forest & SHAP)

### 4. Chạy Tinh chỉnh Mô hình Độc lập
```powershell
# Huấn luyện toàn diện TV2
python scripts/train_tv2_all.py

# Tuning XGBoost (TV4)
python src/ids/tune_xgboost.py --split data/processed/split_v1 --output experiments/w3_05_time_tuning --n-iter 30
```

---

## 📂 Cấu trúc Repository

```text
cicids-bruteforce-ids/
├── artifacts/
│   ├── TV2_decision_tree/      # Mô hình .joblib, metrics, figures của TV2
│   ├── TV3_random_forest/      # Mô hình .joblib, docx nháp, SHAP của TV3
│   └── week3_week4/            # Benchmark hợp nhất 3 mô hình (RESULTS.md, test_comparison.csv)
├── configs/
│   └── experiment.yaml         # Cấu hình mốc thời gian, tham số audit và tiền xử lý
├── data/
│   ├── model_ready/            # Dữ liệu CSV phân tách chuẩn hóa (time & random, with/without port)
│   └── processed/split_v1/     # Checkpoint dữ liệu phân tách theo thời gian
├── docs/
│   ├── BAO_CAO_THUC_NGHIEM_W3_W4.md  # Báo cáo thực nghiệm học thuật đầy đủ
│   ├── DATA_AND_PROTOCOL.md          # Tài liệu quy chuẩn giao thức dữ liệu
│   ├── CODE_MAP.md                   # Bản đồ kiến trúc mã nguồn
│   └── quy_trinh_thu_thap_tien_xu_ly_CICIDS2017.md # Quy trình tiền xử lý & phục hồi timestamp
├── experiments/
│   ├── figures/                # 6 biểu đồ khoa học chất lượng cao phục vụ báo cáo
│   ├── w3_01_dt_time/          # Kết quả tuning Decision Tree time-based
│   └── w3_02_dt_random/        # Kết quả tuning Decision Tree random split
├── notebooks/
│   ├── TV2_DecisionTree_W3-01_W3-02.ipynb
│   └── TV3_RandomForest_W3-03_W3-04.ipynb
├── scripts/
│   ├── generate_detailed_visualizations.py  # Script sinh 6 biểu đồ khoa học
│   ├── prepare_splits.py                    # Script chuẩn hóa thời gian & chia dữ liệu
│   ├── generate_model_ready.py              # Script tạo dữ liệu model_ready
│   └── train_tv2_all.py                     # Master script huấn luyện TV2
└── src/ids/                                 # Package mã nguồn lõi của hệ thống
    ├── tune_decision_tree.py
    ├── tune_xgboost.py
    └── evaluate_tuned_model.py
```

---

## 📜 Trích dẫn & Giấy phép
- Bộ dữ liệu nguồn: **CICIDS2017** phát hành bởi Canadian Institute for Cybersecurity (UNB).
- Đồ án môn học: An toàn bảo mật thông tin / Ứng dụng Machine Learning trong NIDS.
