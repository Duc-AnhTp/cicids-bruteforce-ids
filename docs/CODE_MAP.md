# Bản đồ code và hợp đồng giữa các bước

## 1. Cấu trúc repo

| Đường dẫn | Trách nhiệm |
|---|---|
| `pyproject.toml` | Python package, dependency, entry point `ids` |
| `configs/experiment.yaml` | Nguồn dữ liệu, clock, cutoffs, feature policy, preset, ngưỡng, đường dẫn |
| `src/ids/common.py` | Lỗi protocol, config validation, SHA-256, JSON, environment, dấu mốc Test |
| `src/ids/schema.py` | Tên cột chuẩn hóa, allowlist, nhãn trong phạm vi |
| `src/ids/data.py` | Đọc CSV theo chunk, parse timestamp, numeric conversion, audit timeline |
| `src/ids/split.py` | Purge/embargo, record duplicate, support gates, checkpoint và kiểm tra hash |
| `src/ids/preprocess.py` | sklearn transformers chỉ fit trên Train; numeric → cột hợp lệ → median |
| `src/ids/metrics.py` | Metric nhị phân, threshold grid, recall theo subtype |
| `src/ids/train.py` | Khởi tạo 3 model, pipeline fit, chọn trên Validation, freeze |
| `src/ids/evaluate.py` | Kiểm tra model đã khóa, Test một lần, predictions và báo cáo |
| `src/ids/explain.py` | SHAP cho model thắng, sample cố định, kiểm tra output/additivity |
| `src/ids/predict.py` | Một flow JSON → schema → pipeline → score/label với ngưỡng đã khóa |
| `src/ids/cli.py`, `__main__.py` | Điều phối lệnh, lỗi dừng rõ ràng |
| `scripts/make_demo_data.py` | Tạo dữ liệu giả có timestamp, nhãn, missing/inf, duplicate và cột bẫy leakage |
| `scripts/smoke_test.py` | Thực thi pipeline trên workspace giả mới |
| `tests/test_protocol.py` | Kiểm tra các rủi ro làm sai kết quả, dùng unittest có sẵn |
| `.github/workflows/ci.yml` | Cài dependencies, chạy unit/integration và smoke test khi đưa lên GitHub |
| `docs/` | Protocol, phân công, phạm vi, trạng thái kiểm chứng và khung báo cáo |

Không cần backend/frontend, Docker, MLflow, DVC, Airflow hoặc notebook làm nguồn code chính. Các công cụ đó không giải quyết rủi ro timestamp và đánh giá trong phạm vi 3 ngày.

## 2. Hợp đồng dữ liệu

`read_flows(cfg) -> (frame, feature_names, audit_summary)`.

Trong `frame`, cột thống kê hợp lệ là dữ liệu số. Metadata dùng tiền tố `_`:

| Cột | Ý nghĩa | Vào model? |
|---|---|---|
| `_row_id` | Mã băm nguồn rút gọn + số thứ tự dòng khi đọc | Không |
| `_start` | Timestamp đã parse | Không |
| `_end` | Cận trên thời điểm hoàn tất: start + duration + độ chính xác timestamp | Không |
| `_label` | Nhãn gốc đã uppercase | Không |
| `_target` | 0 = BENIGN, 1 = FTP/SSH | Chỉ y |
| `_record_hash` | Fingerprint bản ghi, không chứa nhãn | Không |
| `_feature_hash` | Fingerprint vector feature trước fit | Không |
| `_seen_feature_in_earlier_split` | Vector này từng có ở tập thời gian sớm hơn | Không |

Train gọi `pipeline.fit(train[feature_names], train['_target'])`. Model không nhận cả DataFrame metadata. `NumericGuard` kiểm tra allowlist thêm một lần để tránh vô tình truyền cột nhãn.

## 3. Vì sao lưu CSV gzip?

Dữ liệu một ngày vừa đủ cho định dạng này; không cần thêm Arrow chỉ để chạy đồ án. Split lưu `.csv.gz`, đọc timestamp rõ ràng, giữ fingerprint `uint64` và dùng `float_precision="round_trip"`. Mỗi file được băm byte thực tế và kiểm tra trước khi dùng. Không khẳng định bitwise output giống nhau trên mọi phiên bản/thư viện hay hệ điều hành; cùng seed không thay thế việc pin môi trường.

`chunksize` giảm chi phí đọc dữ liệu thô nhưng sau lọc các dòng vẫn được ghép vào RAM để sort và train; repo **không** là pipeline streaming/out-of-core. Không `df.sample()` trên toàn bộ Tuesday trước split. Nếu thiếu RAM, giảm số cột theo protocol trước khi khóa hoặc dùng máy đủ RAM, không giảm bớt Test để có điểm thuận lợi.

## 4. Luồng thực thi

| Lệnh | Đọc | Ghi | Có fit? | Có đọc Test để dự đoán? |
|---|---|---|---|---|
| `audit` | CSV toàn ngày | Audit, timeline | Không | Không; có xem nhãn/thời gian để thiết kế split |
| `prepare` | CSV toàn ngày | Ba split và manifest | Không | Không; tạo Test và kiểm tra support |
| `train` | Train, Validation, manifest | Model, Val tables, frozen | Chỉ Train | Không |
| `evaluate` | Model đã khóa và Test | Final metrics, predictions, marker | Không | Một phiên đã khai báo |
| `report` | Predictions/metrics đã lưu | Markdown và PNG | Không | Không đọc lại partition Test |
| `explain` | Validation và model thắng | CSV SHAP, PNG, metadata | Không fit classifier | Không |
| `predict` | JSON một flow và artifacts đã khóa | JSON stdout | Không | Không |

Một số lệnh đọc metadata chung để kiểm tra hash và nguồn. “Không đọc Test” ở train nghĩa là không đọc file partition Test hoặc score Test; không có nghĩa manifest phải che luôn số mẫu đã audit.

## 5. Các quyết định cố ý đơn giản hóa

- Ba preset, không tuning rộng, không XGBoost early stopping để tránh thêm đường truyền eval_set qua preprocessing.
- Không scaling cho các model cây; không SMOTE.
- Loại feature hằng/toàn thiếu thay vì thêm hàng loạt missing indicators; median được fit đúng Train.
- Threshold grid nhỏ trên Validation; không thêm calibration trong 3 ngày.
- Không refit model sau khi ngưỡng đã chọn; model file bao gồm preprocessing.
- SHAP dựa trên Validation, không chọn ví dụ Test đẹp; một biểu đồ global và một waterfall của mẫu đầu trong sample cố định.
- Random split và port ablation không có công tắc “tự chạy khi lỗi” để tránh thay đổi ý nghĩa thí nghiệm âm thầm.
- Mọi output giả đều được đánh dấu `synthetic`; thí nghiệm thật yêu cầu đủ ba model.

## 6. Phối hợp Git tối thiểu

Một branch cho thay đổi dữ liệu/protocol; một branch cho thay đổi model/report khi thật sự cần. Trước `prepare` chính thức: review, gộp code, chốt config, ghi commit. Sau đó dùng cùng commit và cùng manifest. Không để mỗi người tự chuẩn hóa, chia tập và train bằng một notebook riêng.

Tệp raw, model lớn và dữ liệu đã chia đã nằm trong `.gitignore`. Cả nhóm có thể chia sẻ chúng qua thư mục chung do nhóm quản lý; luôn đối chiếu SHA-256 trong manifest. Giữ mã, config, tài liệu và kết quả báo cáo đã chọn trong Git bằng cách chủ động đưa các tệp kết quả cần nộp vào thư mục riêng, không commit toàn bộ dataset.

`code_sha256` khóa các module `src/ids/*.py`. Nếu sửa mã sau prepare, repo dừng. Trước Test có thể tạo phiên bản run mới có ghi lý do; sau Test không sửa phương pháp dựa trên điểm rồi nhận đó là kiểm định độc lập. Hash và marker không phải hệ thống kiểm soát truy cập chống người cố ý sửa artifact.

