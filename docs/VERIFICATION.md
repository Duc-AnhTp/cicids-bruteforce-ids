# Tình trạng kiểm chứng khi bàn giao — 11/09/2026

## Đã thực hiện

- Đọc đầy đủ đề cương người dùng cung cấp; đối chiếu các phần cam kết và tùy chọn.
- Đọc trang CICIDS2017 của UNB và tài liệu chính thức scikit-learn, XGBoost, SHAP.
- Kiểm tra cú pháp toàn bộ package, scripts và tests.
- Chạy 16 kiểm thử: **14 đạt, 2 bỏ qua do thiếu thư viện**.
- Chạy đầy đủ đường dữ liệu giả: audit → prepare → train Decision Tree/Random Forest → freeze → evaluate → report → predict một flow.
- Kiểm tra hình timeline và confusion matrix do code tạo ra.
- Kiểm tra riêng train không đọc partition Test; gọi evaluate lần hai dùng kết quả lưu; train bị chặn sau khi Test đã mở.
- Kiểm tra median và loại cột hằng chỉ fit trên Train; identifier không vào model; nhãn ngoài phạm vi bị loại; flow vượt ranh giới bị purge; support thiếu thì dừng; split bị sửa byte thì bị phát hiện.

## Chưa được kiểm chứng khi chạy

- Huấn luyện XGBoost thực tế và tương thích toàn bộ môi trường đủ ba model.
- SHAP thực tế, gồm adapter XGBoost, output dimensions và hiệu năng.
- Cài package từ đầu bằng pip trên máy người dùng/Windows và CI GitHub.
- Bất kỳ kết quả nào trên CSV CICIDS2017 thật; người dùng chưa cung cấp file này.
- Thời gian train, RAM và chất lượng dự đoán trên máy/dữ liệu thật.

Môi trường soạn mã không có XGBoost/SHAP; lần cài dependency không hoàn tất do quyền truy cập mạng không được chấp thuận. Không dùng một model sklearn thay tên thành XGBoost và không dùng importance thông thường giả làm SHAP. Hai kiểm thử tương ứng báo **skipped**, không báo passed.

## Môi trường kiểm tra phần lõi

| Thành phần | Phiên bản |
|---|---|
| Python | 3.12.14 |
| NumPy | 2.3.5 |
| pandas | 2.2.3 |
| scikit-learn | 1.8.0 |
| PyYAML | 6.0.3 |
| joblib | 1.5.3 |
| matplotlib | 3.10.8 |
| XGBoost | Chưa cài; repo yêu cầu 3.0.5 |
| SHAP | Chưa cài; tùy chọn repo yêu cầu 0.48.0 |

## Việc cần làm đầu ngày 1

```bash
python -m pip install -e ".[xai]"
python -m unittest discover -s tests -v
python scripts/smoke_test.py --output first_full_check --explain
```

Khi môi trường đủ, hai kiểm thử bỏ qua phải được chạy thật; smoke test phải có đủ `decision_tree`, `random_forest`, `xgboost`, đồng thời sinh SHAP. Nếu có lỗi tương thích, giữ log, sửa trước khi prepare thí nghiệm thật và ghi lại môi trường sau sửa. Không lấy trạng thái phần lõi đã đạt để mặc định hai nhánh còn lại đã đạt.

Đầu ra giả chỉ chứng minh phần mềm có thể nối các bước với nhau; không chứng minh phương pháp phù hợp với nguồn timestamp chưa được kiểm tra, hay đạt chất lượng phát hiện trên dữ liệu thật.

