# Phân tích và kế hoạch hoàn thành trong 3 ngày

> **Ghi chú lịch sử thực hiện**: Tài liệu này phản ánh kế hoạch rút gọn phạm vi ban đầu (giai đoạn 3 ngày đầu). Trong các giai đoạn tiếp theo (Tuần 3 – Tuần 4), nhóm đã triển khai mở rộng đầy đủ toàn bộ các cam kết trong đề cương gốc bao gồm: **Random Split đối chứng**, **Port Ablation (có/không Destination Port)**, **Hyperparameter Tuning diện rộng** và **Trực quan hóa diễn giải chuyên sâu**. Vui lòng tham khảo [README.md](../README.md), [DATA_AND_PROTOCOL.md](DATA_AND_PROTOCOL.md) và [BAO_CAO_THUC_NGHIEM_W3_W4.md](BAO_CAO_THUC_NGHIEM_W3_W4.md) để xem quy chuẩn và kết quả thực nghiệm hoàn chỉnh hiện tại.

## 1. Sửa cách ước lượng nguồn lực

Nếu giữ giả định gốc 5 người × 20 ngày làm việc, nguồn lực danh nghĩa là 100 person-day.

| Phương án | Nguồn lực danh nghĩa | So với giả định gốc |
|---|---:|---:|
| 5 người × 20 ngày | 100 person-day | 100% |
| 2–3 người × 6 ngày | 12–18 person-day | 12–18% |
| 2–3 người × 3 ngày | 6–9 person-day | 6–9% |

Con số 10–18% trong nhận xét ban đầu là làm tròn; theo đúng phép tính là 12–18%. Với mục tiêu mới 3 ngày, còn 6–9%. Nếu mỗi người có 6 giờ tập trung/ngày thì có khoảng 36–54 giờ-người. Đây là giả định lập kế hoạch, không phải thời gian đo được.

Giảm người và giảm ngày nhân vào **capacity**. Không có công thức từ đó suy ra xác suất vỡ tiến độ cũng nhân tương ứng. Công việc nối tiếp, năng lực Python/ML và thời gian sửa dữ liệu khiến capacity hữu dụng không tỷ lệ tuyến tính với số người. Đề cương cũ cũng chỉ là dự kiến, chưa chứng minh thực sự cần 100 ngày-người.

Mục tiêu khả thi: một thí nghiệm nhỏ có giới hạn rõ, chạy được và tái lập được. Không cam kết F1 hay thời gian train vài phút khi chưa đo máy và dữ liệu.

## 2. Đối chiếu trực tiếp với đề cương đã gửi

| Nội dung | Đề cương thực sự viết | Quyết định cho 3 ngày |
|---|---|---|
| Time-based split | Phương án chính | Giữ |
| Random split | Cam kết ở phạm vi 3.2, kết quả 4, mục 5.4.4 | Cắt rõ trong đề cương rút gọn; không nói đã hoàn thành |
| Có/không Destination Port | Cam kết ở mục 5.5 | Cắt ablation; bỏ cổng theo lựa chọn thiết kế trước khi chạy |
| SHAP | Bước 8 nói **model tốt nhất** | Giữ đúng một model nếu kịp; không cần SHAP cả ba |
| Demo | Ghi tùy chọn | CLI đã có; không làm giao diện |
| Time-series CV | Mở rộng nếu còn thời gian | Không thực hiện |
| Chọn model sau bảng Test | Bước 7 có cách viết dễ gây hiểu sai; mục 5.6 lại chọn trên Validation | Sửa thống nhất: chọn trên Validation, Test chỉ đánh giá |
| Cột hằng số | EDA gợi ý loại sớm | Chỉ quyết định loại dựa trên Train |

Không có rubric trong tệp đính kèm nên chưa biết Random split có ảnh hưởng điểm bắt buộc không. Tuy nhiên nó **đã được nhóm cam kết trong đề cương**, vì vậy báo cáo rút gọn cần ghi phần thay đổi phạm vi. Việc xây bản rút gọn không cần chờ mới bắt đầu code.

## 3. Chốt câu hỏi nghiên cứu vừa với dữ liệu

“Với các flow đã hoàn tất trong ngày Tuesday của CICIDS2017, ba mô hình cây phát hiện nhãn FTP/SSH brute force như thế nào khi huấn luyện trên quá khứ và đánh giá trên phần thời gian muộn hơn?”

Phạm vi kết luận phải dựa vào **support subtype của Test**, không chỉ tên đề tài. Nếu Test chỉ có SSH: kết quả trực tiếp chỉ đo phát hiện SSH trong đoạn muộn của cùng ngày. Việc Train chứa FTP không biến thành bằng chứng Test phát hiện FTP tốt.

UNB công bố FTP-Patator 09:20–10:20 và SSH-Patator 14:00–15:00 ngày 04/07/2017. Đây là lịch do tác giả công bố, chưa thay thế việc đọc Timestamp của bản CSV nhóm tải. [Nguồn UNB](https://www.unb.ca/cic/datasets/ids-2017.html)

Với hai đợt tách nhau, không thể dùng ba đoạn thời gian liên tiếp mà mỗi đoạn đều phủ cả FTP lẫn SSH. Phải chọn đánh giá trong cùng đợt muộn, hoặc thiết kế bài toán chuyển từ subtype này sang subtype khác và chấp nhận nó là câu hỏi khác. Repo chọn phương án đầu, với mốc minh họa trong đợt SSH; không tự trộn cửa sổ rải rác để tạo vẻ cân bằng.

## 4. Phân công: theo luồng công việc, không theo ba notebook riêng

| Vai trò | Người thứ nhất | Người thứ hai | Người thứ ba nếu có |
|---|---|---|---|
| Chính | Dữ liệu, đồng hồ, protocol, một máy chạy chính | Mô hình, đọc kết quả, kiểm tra pipeline | Báo cáo, hình, nguồn, SHAP và kiểm thử CLI |
| Cùng kiểm tra | Nhãn theo thời gian, checkpoint, Test lock | Cùng người thứ nhất trước mỗi mốc khóa | Kiểm tra bảng không suy diễn quá support |
| Không làm | Tự tạo split riêng theo sở thích | Chạy notebook fit trên cả data | Chọn lại model theo Test |

Nếu chỉ hai người, người thứ hai bắt đầu khung báo cáo từ ngày 1; người thứ nhất phụ trách thao tác chạy chung. Chỉ một người chạy `prepare`, sau đó phân phối đúng checkpoint/hash. Các góp ý code tích hợp trước lần prepare chính thức. Không để 2–3 người đồng thời ghi vào cùng thư mục run.

## 5. Lịch 3 ngày — mỗi ngày khoảng 6 giờ tập trung/người

| Ngày / thời điểm | Việc phải xong | Sản phẩm kiểm tra được | Điều kiện qua mốc |
|---|---|---|---|
| Ngày 1, 0–2 giờ | Cài môi trường, chạy smoke test; lấy đúng Tuesday CSV | Môi trường chạy; header có Timestamp; ghi URL/phiên bản | Không thay CSV có thời gian bằng file đã mất thời gian |
| Ngày 1, 2–4 giờ | Audit label windows, ngày/tháng, đồng hồ, duration, schema | Timeline, quality counts, quyết định cổng và nhãn | Không có lỗi thời gian chưa giải thích |
| Ngày 1, 4–6 giờ | Khóa config và code; `prepare`; kiểm tra support/purge | Một checkpoint Train/Val/Test + manifest | Cả ba tập đủ hai lớp nhị phân; xác định subtype vắng mặt |
| Ngày 2, 0–3 giờ | `train` ba model theo preset; chọn threshold trên Val | Model files, validation table, frozen.json | Không đọc Test, không thất lạc preprocessing |
| Ngày 2, 3–5 giờ | Soát quyết định và số liệu Val; giải thích nếu đủ thời gian | SHAP một model, hoặc ghi không thực hiện | Không đổi feature sau khi xem SHAP đã khóa |
| Ngày 2, 5–6 giờ | Mở Test một lần; xuất dự đoán và báo cáo | test_metrics, test_predictions, bảng và hình | Giữ model thắng đã chọn trước Test |
| Ngày 3, 0–3 giờ | Hoàn thiện phần phương pháp và phân tích lỗi | Báo cáo có FP/FN, FPR, subtype support và giới hạn | Không lấy F1 cao làm bằng chứng hết leakage |
| Ngày 3, 3–4 giờ | Chạy lại phần đọc kết quả/CLI trên máy khác | Report tái tạo từ dự đoán; demo một flow | Không fit lại hay mở lại Test |
| Ngày 3, 4–6 giờ | Đóng gói, slide ngắn, diễn tập bảo vệ; buffer | Repo, config, môi trường, kết quả và tài liệu | Mọi con số có tệp nguồn; không có số liệu giả |

Checkpoint dữ liệu phải có **cuối ngày 1**, không phải ngày 2 như kế hoạch một tuần. Cuối ngày 2 khóa kết quả. Ngày 3 dành cho giải thích và giao nộp, không bổ sung mô hình.

## 6. Nếu bị trễ

Thứ tự cắt: giao diện/demo trình diễn → SHAP → tăng ngân sách train/tuning → nội dung mở rộng của báo cáo. Random split, ablation cổng và CV đã không nằm trong bản thực thi này.

Không cắt kiểm tra thời gian, tách tập, fit preprocessing trên Train, hay lưu model/ngưỡng. Không nên cứu deadline bằng một kết quả temporal giả. Nếu đến cuối buổi đầu chưa có thời gian đáng tin cậy, báo rõ dữ liệu đang chặn protocol; ưu tiên tìm đúng bản labelled flows. Một phương án random khác chỉ có thể được trình bày là thay đổi câu hỏi/phạm vi, không phải fallback tương đương.

Nếu chưa quen Python/ML, dành buổi đầu chạy dữ liệu giả và đọc luồng code. Khi đó hãy xem 3 ngày là mục tiêu cần điều chỉnh theo dữ liệu thực tế, không là cam kết chắc chắn. Một pipeline có sẵn giảm phần viết mã, không thay thế hiểu ý nghĩa dữ liệu.

## 7. Bản phạm vi thay thế có thể đưa vào báo cáo

Đồ án được thu hẹp cho nhóm 2–3 thành viên thực hiện trong 3 ngày, tập trung vào phân loại offline các flow BENIGN và FTP/SSH-Patator trong CICIDS2017 Tuesday. Nhóm sử dụng một cách chia Train/Validation/Test liên tiếp theo thời gian; huấn luyện Decision Tree, Random Forest và XGBoost trên cùng dữ liệu và quy trình tiền xử lý chỉ được fit trên Train. Mô hình và ngưỡng được chọn bằng Validation, sau đó đánh giá một lần trên Test. Không thực hiện Random split đối chứng, ablation Destination Port hay cross-validation mở rộng. Giải thích bằng SHAP cho mô hình đã chọn được thực hiện nếu hoàn thành trong thời gian cho phép. Kết luận chỉ áp dụng cho môi trường, giai đoạn và các nhãn thực sự có support trong Test; không khẳng định khả năng tổng quát hóa sang chiến dịch hoặc mạng mới.

