# Phát hiện SSH/FTP Brute Force — repo cho 3 ngày

Repo này triển khai **thí nghiệm phân loại offline trên các flow đã hoàn tất**, với CICIDS2017 Tuesday, nhãn `BENIGN / FTP-Patator / SSH-Patator`, một cách chia thời gian và ba mô hình cây. Đây là bộ khung có logic thực thi, kiểm tra dữ liệu và xuất kết quả; không phải notebook chỉ để điền `TODO`.

**Chưa kèm CSV CICIDS2017 hoặc kết quả thực nghiệm thật.** Bộ sinh dữ liệu giả chỉ dùng kiểm tra phần mềm. Xem [tình trạng kiểm chứng](docs/VERIFICATION.md) trước khi dùng.

## Quyết định phạm vi

| Giữ | Cắt trong bản 3 ngày |
|---|---|
| Audit timestamp và nhãn; Train/Validation/Test liên tiếp | Random split đối chứng |
| Decision Tree, Random Forest, XGBoost; một cấu hình/model | So sánh có/không Destination Port |
| Pipeline chung; fit tiền xử lý trên Train | SMOTE, scaling, tìm tham số diện rộng |
| Chọn model/ngưỡng bằng Validation; Test sau khi khóa | Time-series CV, deep learning |
| Precision/Recall/F1, AP, FPR, FP/FN, support subtype | Giao diện, API, triển khai IDS thời gian thực |
| SHAP cho model thắng trên tối đa 500 mẫu Validation, nếu kịp | SHAP cho toàn bộ dữ liệu hoặc cả ba model |

**Giới hạn thiết kế:** một ngày có FTP buổi sáng và SSH buổi chiều không đủ để có cả hai loại tấn công trong cả ba tập thời gian liên tiếp. Mốc ví dụ trong repo đặt trong đợt SSH, vì vậy Test có thể chỉ có SSH. `FTP recall = N/A` khi support bằng 0; không đổi thành 0% hay 100%.

Đọc [phân tích đề cương và kế hoạch 3 ngày](docs/PLAN_3_DAYS.md), [dữ liệu và protocol](docs/DATA_AND_PROTOCOL.md), [bản đồ code](docs/CODE_MAP.md).

## Chạy nhanh

Khuyến nghị Python 3.12, CPU, một máy chạy chính. Mở terminal trong thư mục repo.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[xai]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_test.py --output demo_workspace --explain
```

Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[xai]"
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/smoke_test.py --output demo_workspace --explain
```

Ở các lệnh dưới đây, `python` là Python của môi trường vừa tạo. Có thể gọi bằng đường dẫn đầy đủ tương ứng để không cần activate.

Nếu chỉ cần kiểm tra lõi DT/RF với các thư viện sẵn có:

```bash
python scripts/smoke_test.py --output demo_core --core-only
```

Chế độ này ghi rõ **SYNTHETIC**, chỉ chạy hai model; không thay thế kiểm thử đủ ba model hoặc thực nghiệm thật. `demo_workspace`/`demo_core` phải là thư mục mới để không ghi đè kết quả trước.

## Chạy trên dữ liệu thật

1. Lấy bản CSV Tuesday có **Timestamp thật**, lưu ở `data/raw/`. Trang nguồn: [UNB CICIDS2017](https://www.unb.ca/cic/datasets/ids-2017.html). Ghi lại archive/mirror và ngày tải trong `input.source_note`. Không cần xử lý dữ liệu các ngày khác; máy chủ có thể vẫn yêu cầu tải cả archive CSV để giải nén riêng Tuesday.
2. Sửa đường dẫn và `timestamp_formats` trong `configs/experiment.yaml` theo file đang có. Giữ `synthetic: false`.
3. Chạy audit, mở hình timeline và bảng giờ bắt đầu/kết thúc theo nhãn.

```bash
python -m ids audit --config configs/experiment.yaml
```

4. Xác nhận ngày/tháng, đồng hồ 24 giờ, múi giờ nguồn và độ chính xác timestamp. Chốt mốc chia dựa trên support theo thời gian, trước khi xem điểm model. Điền `clock_basis`, `cutoff_reason`, rồi đặt `clock_reviewed` và `cutoffs_reviewed` thành `true`. **Không bật hai cờ khi chưa kiểm tra.** Đây là bước ghi nhận quyết định nghiên cứu, không phải thao tác làm cho lệnh hết báo lỗi.
5. Chạy lần lượt:

```bash
python -m ids prepare --config configs/experiment.yaml
python -m ids train --config configs/experiment.yaml
python -m ids evaluate --config configs/experiment.yaml
python -m ids report --config configs/experiment.yaml
python -m ids explain --config configs/experiment.yaml
```

`train` chạy ba model và tự khóa lựa chọn/ngưỡng trong `frozen.json`. `evaluate` mở Test một lần cho cả ba cấu hình đã chốt. Gọi lại chỉ đọc kết quả đã lưu, không tính lại. `report` dựng hình từ dự đoán đã lưu nên có thể chạy lại. `explain` chỉ đọc Validation và model đã khóa, không dùng để sửa mô hình.

Sau khi cả nhóm cài và chạy đủ thư viện thành công, một người xuất cùng môi trường cho cả nhóm:

```bash
python -m pip freeze > artifacts/environment_full.txt
```

`pyproject.toml` là ràng buộc tương thích và pin XGBoost/SHAP, không phải lockfile đầy đủ đã kiểm chứng mọi dependency. Lưu bản freeze thực tế cùng kết quả.

## Kết quả nằm ở đâu?

| Tệp trong `artifacts/tuesday_temporal_v1/` | Ý nghĩa |
|---|---|
| `audit/timeline.png`, `timeline_5min.csv`, `label_windows.csv` | Kiểm tra phân bố tấn công theo thời gian |
| `split_summary.json` | Support từng tập, flow loại ở ranh giới, trùng lặp |
| `environment.json` | Python và phiên bản thư viện |
| `validation_comparison.csv`, `validation_thresholds.csv` | Cơ sở chọn model/ngưỡng |
| `models/*.joblib`, `frozen.json` | Pipeline đã fit, ngưỡng và model đã chọn |
| `TEST_OPENED.json` | Dấu mốc mở Test |
| `test_metrics.json`, `test_comparison.csv` | Kết quả cuối; toàn bộ model đã chốt |
| `test_predictions.csv.gz` | Dự đoán dùng lại khi làm báo cáo |
| `RESULTS.md`, `figures/*.png` | Bảng và hình cho báo cáo |
| `shap/feature_importance.csv`, `summary.png`, `example_waterfall.png` | Giải thích model thắng |

Trong `data/processed/tuesday_temporal_v1/` có `train.csv.gz`, `validation.csv.gz`, `test.csv.gz` và `manifest.json`. Đây là checkpoint cả nhóm dùng chung. Mã băm SHA-256 kiểm tra thay đổi tệp; fingerprint 64-bit của pandas chỉ dùng audit dòng trùng, không phải chứng minh mật mã về từng flow.

## Demo CLI tùy chọn

```bash
python -m ids predict --config configs/experiment.yaml --input path/to/one_completed_flow.json
```

Đầu vào phải là một object JSON có đầy đủ các cột thuộc `feature_schema` đã khóa. Tên gốc có khoảng trắng được chuẩn hóa; có thể dùng tên snake_case. Giá trị chưa biết dùng `null`. Thiếu tên cột sẽ bị từ chối. Cột thừa bị bỏ và liệt kê trong đầu ra. Không đưa packet/PCAP, IP hay một câu mô tả vào rồi kỳ vọng repo tự trích flow.

Ví dụ đầy đủ cho dữ liệu giả được sinh ở `demo_workspace/example_flow.json`.

## Khi cần dừng để sửa

- Thiếu Timestamp: lấy đúng bản dữ liệu; không dùng số thứ tự dòng làm thời gian.
- Sai ngày/tháng hoặc giờ chiều thành giờ sáng: xác minh nguồn, không sửa bằng nhãn tấn công.
- Thiếu Attack/Normal sau chia: xem lại bảng giờ và phạm vi kết luận; không tự chuyển random.
- Config/mã/split đổi sau `prepare`: hàng rào dừng để tránh nhóm dùng pipeline khác nhau. Chốt bản cuối trước khi prepare chính thức; sửa lỗi trước mở Test thì ghi nhận và tạo run mới.
- Sau mở Test: không đổi feature, cutoffs, tham số, model hay threshold theo kết quả. Tệp khóa là hàng rào chống nhầm lẫn, không ngăn được người dùng cố ý xóa hay đọc dữ liệu trực tiếp.
- Nếu đánh giá bị ngắt sau mở Test: giữ nguyên tệp khóa/log, ghi lại sự cố; không âm thầm xóa marker. Sửa lỗi báo cáo bằng dự đoán đã lưu nếu có. Nếu phải đánh giá lại do lỗi thực thi, công khai lần chạy lại và giữ nguyên các quyết định đã khóa; không gọi Test đó là chưa từng xem.

Chỉ nạp `.joblib` do nhóm tự tạo hoặc từ nguồn tin cậy. Bộ mã không tự gửi traffic, không dò mật khẩu và không thu thập mạng.

