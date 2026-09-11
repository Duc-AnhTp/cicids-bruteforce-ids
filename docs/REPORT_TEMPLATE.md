# Khung báo cáo để điền từ kết quả thật

Không điền số từ `demo_workspace`; tất cả số phải trích từ run có `synthetic=false`.

## 1. Bài toán và phạm vi

Mục tiêu: phân loại flow hoàn tất thành BENIGN hoặc FTP/SSH-Patator trong Tuesday.
Nêu phạm vi rút gọn 3 ngày; liệt kê Random split và port ablation không thực hiện.

## 2. Nguồn dữ liệu

Điền: URL thực lấy file, tên file/archive/phiên bản, SHA-256, ngày tải, nguồn nhãn,
Timestamp format, múi giờ/clock basis, độ chính xác timestamp và đơn vị duration.
Nêu số dòng raw, dòng giữ, dòng loại theo nhãn, lỗi/thiếu số, duplicate.

## 3. Thiết kế thời gian

Chèn `audit/timeline.png`. Ghi train_end, validation_end, embargo, lý do chọn trước
khi xem điểm. Báo số flow purge/dedup và support BENIGN/FTP/SSH từng tập.
Nêu việc audit phân bố nhãn được dùng khi chọn cutoffs và giới hạn hồi cứu.

## 4. Pipeline và mô hình

Nêu allowlist, các cột bỏ trước; fit cột hằng/median trên Train. Ba preset,
trọng số từ Train, metric/ngưỡng chọn trên Validation, không refit sau khi khóa.
Ghi cấu hình máy thực dùng, Python/dependencies, seed và thời gian fit đo được.

## 5. Kết quả

Chèn bảng Validation riêng để giải thích lựa chọn. Sau đó bảng Test ba model đã
khóa, threshold, Precision/Recall/F1/AP/FPR/FP/FN, dummy baseline và support.
Chèn PR curve, confusion matrix, recall FTP/SSH. Không điền N/A bằng 0 hoặc 100%.
Không đổi model đã chọn chỉ vì bảng Test xếp hạng khác.

## 6. Phân tích lỗi và giải thích

Nêu FP ảnh hưởng báo động giả, FN ảnh hưởng bỏ sót. So sánh trên cùng tập và ngưỡng
đã khóa. Nếu có SHAP: báo model, sample Validation, số mẫu/nhãn, output unit,
feature dependence và tính không nhân quả. Nếu không có, ghi không thực hiện.

## 7. Giới hạn

Một ngày; cùng môi trường và campaign; Test có thể thiếu FTP; phụ thuộc giữa flow;
chất lượng nhãn chưa được tái kiểm bằng PCAP; không đo latency; bỏ cổng chưa có ablation;
không random đối chứng; score chưa hiệu chuẩn; không chứng nhận triển khai IDS thực tế.

## 8. Tái lập và kết luận

Đường dẫn config/manifest/environment/model/predictions, chuỗi lệnh và thời điểm khóa.
Kết luận theo support Test và lỗi thực đo, không theo kỳ vọng điểm cao.

## Gợi ý 6 slide

1. Bài toán, phạm vi và câu hỏi có thể trả lời.
2. Timeline dữ liệu và giới hạn FTP/SSH.
3. Split/pipeline chống leakage.
4. Lựa chọn bằng Validation và kết quả Test.
5. Lỗi FP/FN, subtype support, SHAP nếu có.
6. Giới hạn và các phần chưa làm.

