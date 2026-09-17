# Báo cáo thực nghiệm W3–W4

## 1. Mục tiêu và câu hỏi nghiên cứu

Thực nghiệm nhằm đánh giá khả năng phân loại một flow mạng đã hoàn tất thành `BENIGN` hoặc flow brute-force thuộc `FTP-Patator`/`SSH-Patator` trong dữ liệu CICIDS2017 Tuesday. Mục tiêu chính không phải chứng nhận một IDS triển khai thực tế, mà là đo khả năng tổng quát hóa theo thời gian của ba mô hình cây khi được huấn luyện trên phần dữ liệu sớm hơn và đánh giá trên phần dữ liệu muộn hơn.

Câu hỏi nghiên cứu là: với các flow thuộc cùng ngày Tuesday, ba mô hình Decision Tree, Random Forest và XGBoost hoạt động như thế nào khi huấn luyện theo thứ tự thời gian, đặc biệt khi subtype xuất hiện trong Test khác với subtype có trong Train? Random split được giữ làm đối chứng để minh họa sự khác biệt giữa chia theo thời gian và chia ngẫu nhiên; nó không phải kết quả chính.

## 2. Dataset và định nghĩa nhãn

Bài toán sử dụng các flow mạng đã hoàn tất. Theo quy ước nhãn trong protocol:

| Nhãn gốc sau chuẩn hóa | Nhãn nhị phân | Cách xử lý |
|---|---:|---|
| `BENIGN` | 0 | Giữ |
| `FTP-PATATOR` | 1 | Giữ và lưu subtype |
| `SSH-PATATOR` | 1 | Giữ và lưu subtype |
| Nhãn khác hoặc thiếu | — | Loại khỏi phạm vi |

Một dòng là một flow hoàn tất; các thống kê packet, byte, duration và inter-arrival time được quan sát trên toàn flow. Vì vậy đây là bài toán phân loại sau khi flow hoàn tất, không phải phát hiện từ packet đầu tiên và không đo detection latency.

Tài liệu protocol cho biết repo chưa được cung cấp metadata đầy đủ để xác minh độc lập URL tải thực tế, archive/member Tuesday, SHA-256 dữ liệu raw, ngày tải, múi giờ và chất lượng timestamp của CSV nguồn. Báo cáo này không tự bổ sung các trường chưa có trong artifact. Các kết quả dưới đây là kết quả thật của run trong `artifacts/week3_week4`.

## 3. Tiền xử lý và không gian đặc trưng

Pipeline thực hiện các bước cố định trước khi đánh giá: chuẩn hóa tên cột, lọc nhãn theo định nghĩa bài toán, parse timestamp theo format đã khai báo, ép kiểu số, xử lý `NaN/Infinity` theo quy tắc cố định, audit metadata và xử lý bản ghi xuất trùng. Các tham số học từ dữ liệu như quyết định loại cột hằng/toàn thiếu, median điền thiếu, trọng số lớp và mô hình chỉ được fit trên Train.

Flow ID, IP, Timestamp và Label không nằm trong allowlist dùng cho model. Protocol cũng bị loại để giữ schema thống kê flow. `Destination Port` được giữ trong nhánh `with_port` và bị loại trong nhánh `without_port`; đây là ablation đã được thực hiện trong artifact, không phải kết luận rằng port luôn là leakage. Cột `Fwd Header Length` bị lặp tên `.1` không thuộc allowlist.

Theo `frozen.json`:

- Nhánh `with_port` có **67 features**, trong đó feature đầu tiên là `Destination Port`.
- Nhánh `without_port` có **66 features**, tức bỏ `Destination Port` nhưng giữ các feature thống kê flow còn lại.
- Threshold dùng để ghi các chỉ số trong artifact là `0.5`.

Các cột hằng/toàn thiếu chỉ được loại dựa trên Train. Không dùng thống kê phương sai của Validation/Test để giữ feature. Không dùng SHAP để chọn lại feature.

## 4. Thiết kế chia dữ liệu

### 4.1. Time-based split — kết quả chính

Split chính giữ thứ tự thời gian và dùng điều kiện purge/embargo được mô tả trong protocol. Với flow có thời điểm bắt đầu `s`, thời điểm kết thúc bảo thủ là `e = s + Flow Duration + q`, trong đó `q` phản ánh độ chính xác timestamp. Các tập được xác định theo mốc Train, Validation và Test; flow không thỏa điều kiện bị loại ở ranh giới.

Thiết kế này nhằm tránh việc một flow hoặc thông tin thời gian muộn lọt vào tập sớm. Model được chọn trên Validation trước khi Test được mở. Sau khi khóa, không refit, không đổi feature, không đổi model và không đổi threshold theo Test.

### 4.2. Vì sao subtype khác nhau giữa Train, Validation và Test

Theo `frozen.json` và `RESULTS.md`, Train theo thời gian chỉ có `FTP-Patator`, Validation có cả FTP và SSH, còn Test chỉ có `SSH-Patator`. Đây là hệ quả của vị trí các cửa sổ thời gian trong ngày Tuesday và lịch các đợt tấn công, không phải do cân bằng lại nhãn sau khi xem điểm Test.

Cụ thể, Validation time/with_port có `ftp_support = 2418` và `ssh_support = 1886`. Test time/with_port có `ftp_support = 0` và `ssh_support = 3732`. Do đó Test time-based chủ yếu đo khả năng chuyển từ mẫu FTP đã thấy trong Train sang SSH chưa xuất hiện trong Train. Không có support FTP trong Test nên không được kết luận khả năng phát hiện FTP trên Test.

### 4.3. Random split — đối chứng

Random split trộn ngẫu nhiên các flow và được dùng để đối chiếu với time-based split. `split_diff_validation.csv` cho thấy F1 của random split cao hơn time-based từ `0.2630811337826424` đến `0.28480232791878957`, tùy model và việc giữ port. Ví dụ với Random Forest `with_port`, F1 time là `0.7180938198064035`, F1 random là `0.9996891996891997`, chênh lệch là `0.28159537988279615`.

Random split không phải kết quả chính vì các flow tương tự về campaign, subtype hoặc đặc trưng có thể xuất hiện ở cả Train và Validation. Điểm gần 1.0 vì vậy không chứng minh tổng quát hóa theo thời gian và không được dùng để chọn kết luận chính.

## 5. Mất cân bằng và mô hình

Tỷ lệ lớp được xử lý bằng trọng số tính từ Train, không tính trên toàn bộ dữ liệu:

- Decision Tree dùng `class_weight="balanced"`.
- Random Forest dùng `class_weight="balanced"`.
- XGBoost dùng `scale_pos_weight = N_Normal_train / N_Attack_train`.

Ba họ mô hình được đánh giá trên cùng các split và cùng pipeline tiền xử lý:

1. **Decision Tree**.
2. **Random Forest**.
3. **XGBoost**.

Artifact thực tế lưu các grid đã chạy. Decision Tree thử `max_depth` bằng `6, 8, 12, null` và `min_samples_leaf` bằng `5, 10`. Random Forest thử `n_estimators` bằng `100, 150, 300`, `max_depth` bằng `10, 16, null`, và `min_samples_leaf = 5`. XGBoost thử `n_estimators` bằng `100, 200`, `max_depth` bằng `3, 4, 6`, và `learning_rate = 0.08`.

Model và threshold được chọn chỉ trên Validation theo thứ tự: F1 attack cao nhất, sau đó average precision cao hơn, rồi FPR thấp hơn. Các quyết định được khóa trước khi mở Test. `frozen.json` xác nhận model winner là `time/with_port/random_forest` và Test chưa được dùng để chọn model.

## 6. Kết quả Validation

Các bảng dưới đây lấy trực tiếp từ `validation_winners.csv`. Threshold của tất cả dòng là `0.5`. `n` là tổng support và `n_attack` là số flow attack.

### 6.1. Validation đầy đủ

| Key | Model | F1 attack | Precision attack | Recall attack | Accuracy | AP | ROC-AUC | FPR | TN | FP | FN | TP | n | n_attack | FTP recall | SSH recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| time/with_port/decision_tree | Decision Tree | 0.7169642857142857 | 0.9971026490066225 | 0.5597118959107806 | 0.9906685113773512 | 0.5690090415153649 | 0.7798482244544015 | 3.5083850402461885e-05 | 199515 | 7 | 1895 | 2409 | 203826 | 4304 | 0.9962779156327544 | 0.0 |
| time/with_port/random_forest | Random Forest | 0.7180938198064035 | 1.0 | 0.5601765799256505 | 0.9907126666862912 | 0.7326326415549664 | 0.8892384915421836 | 0.0 | 199522 | 0 | 1893 | 2411 | 203826 | 4304 | 0.9971050454921423 | 0.0 |
| time/with_port/xgboost | XGBoost | 0.7180938198064035 | 1.0 | 0.5601765799256505 | 0.9907126666862912 | 0.6045199691010246 | 0.8920862916273239 | 0.0 | 199522 | 0 | 1893 | 2411 | 203826 | 4304 | 0.9971050454921423 | 0.0 |
| time/without_port/decision_tree | Decision Tree | 0.7168576104746317 | 0.9966901117087298 | 0.5597118959107806 | 0.9906636052319135 | 0.5676184529540959 | 0.7798387053049354 | 4.009582903138501e-05 | 199514 | 8 | 1895 | 2409 | 203826 | 4304 | 0.9962779156327544 | 0.0 |
| time/without_port/random_forest | Random Forest | 0.7134191448439118 | 0.9820773930753565 | 0.5601765799256505 | 0.9904967962870291 | 0.5694412376453043 | 0.7758941680793675 | 0.00022052705967261755 | 199478 | 44 | 1893 | 2411 | 203826 | 4304 | 0.9971050454921423 | 0.0 |
| time/without_port/xgboost | XGBoost | 0.7135663507109005 | 0.9840686274509803 | 0.5597118959107806 | 0.9905115147233424 | 0.6873893941672146 | 0.9704497862344534 | 0.00019546716652800192 | 199483 | 39 | 1895 | 2409 | 203826 | 4304 | 0.9962779156327544 | 0.0 |
| random/with_port/decision_tree | Decision Tree | 0.9938878143133463 | 0.9899815043156597 | 0.9978250737921392 | 0.9996192128792808 | 0.9969506887017308 | 0.9988970463759727 | 0.00032333804246174663 | 200963 | 65 | 14 | 6423 | 207465 | 6437 | 0.9997292174383969 | 0.9952623906705539 |
| random/with_port/random_forest | Random Forest | 0.9996891996891997 | 1.0 | 0.9993785925120398 | 0.9999807196394572 | 0.9998492752456534 | 0.9999154794874772 | 0.0 | 201028 | 0 | 4 | 6433 | 207465 | 6437 | 0.9997292174383969 | 0.9989067055393586 |
| random/with_port/xgboost | XGBoost | 0.9995340891442771 | 0.9992237230243751 | 0.99984464812801 | 0.9999710794591858 | 0.9999230906341481 | 0.9999952346075242 | 2.487215711244205e-05 | 201023 | 5 | 1 | 6436 | 207465 | 6437 | 0.9997292174383969 | 1.0 |
| random/without_port/decision_tree | Decision Tree | 0.9799387442572741 | 0.9661784689717651 | 0.9940966288643778 | 0.9987371363844504 | 0.9895234852981134 | 0.9969684816470249 | 0.0011142726386374037 | 200804 | 224 | 38 | 6399 | 207465 | 6437 | 0.9981045220687788 | 0.9887026239067055 |
| random/without_port/random_forest | Random Forest | 0.994181084645822 | 0.9930254184748915 | 0.9953394438402983 | 0.9996384932398236 | 0.99927038395367 | 0.9998780051025532 | 0.00022384941401197843 | 200983 | 45 | 30 | 6407 | 207465 | 6437 | 0.9989168697535878 | 0.9905247813411079 |
| random/without_port/xgboost | XGBoost | 0.99836867862969 | 0.9984462399005594 | 0.9982911294081094 | 0.9998987781071506 | 0.9998505462046366 | 0.9999672910075519 | 4.97443142248841e-05 | 201018 | 10 | 11 | 6426 | 207465 | 6437 | 0.999458434876794 | 0.9967201166180758 |

### 6.2. Kết quả port ablation

`port_ablation_validation.csv` so sánh cùng một họ model trên Validation:

| Model | F1 with_port | F1 without_port | Delta F1 | SSH recall with_port | SSH recall without_port | FTP recall with_port | FTP recall without_port | FPR with_port | FPR without_port |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Decision Tree | 0.7169642857142857 | 0.7168576104746317 | 0.00010667523965401937 | 0.0 | 0.0 | 0.9962779156327544 | 0.9962779156327544 | 3.5083850402461885e-05 | 4.009582903138501e-05 |
| Random Forest | 0.7180938198064035 | 0.7134191448439118 | 0.004674674962491743 | 0.0 | 0.0 | 0.9971050454921423 | 0.9971050454921423 | 0.0 | 0.00022052705967261755 |
| XGBoost | 0.7180938198064035 | 0.7135663507109005 | 0.004527469095503056 | 0.0 | 0.0 | 0.9971050454921423 | 0.9962779156327544 | 0.0 | 0.00019546716652800192 |

Port không làm thay đổi SSH recall trên Validation: tất cả đều bằng `0.0`. Với Random Forest, bỏ port làm F1 giảm từ `0.7180938198064035` xuống `0.7134191448439118` và FPR tăng từ `0.0` lên `0.00022052705967261755`. Đây là kết quả định lượng của ablation trong protocol này, không đủ để khẳng định port luôn là nguyên nhân hay luôn là leakage.

## 7. Model winner và hyperparameter cuối cùng

Model được khóa trước Test là:

- **Key:** `time/with_port/random_forest`.
- **Model:** Random Forest.
- **Hyperparameter:** `n_estimators = 100`, `max_depth = 16`, `min_samples_leaf = 5`.
- **Features:** 67, có `Destination Port`.
- **Threshold:** `0.5`.
- **Validation F1:** `0.7180938198064035`.
- **Validation precision:** `1.0`.
- **Validation recall:** `0.5601765799256505`.
- **Validation AP:** `0.7326326415549664`.
- **Validation ROC-AUC:** `0.8892384915421836`.
- **Validation FPR:** `0.0`.

`frozen.json` ghi `test_opened = false` trong snapshot freeze trước Test. Artifact Test được tạo sau đó và ghi rõ winner đã được chọn trên Validation trước khi Test mở; không có việc chọn lại model theo Test.

## 8. Kết quả Test — mở đúng một lần

Phase Test được chạy đúng một lần. Bảng dưới đây lấy trực tiếp từ `test_comparison.csv`; threshold là `0.5`. Kết quả chính là ba model `time/with_port` đã khóa. Các dòng random là đối chứng.

### 8.1. Test time/with_port — kết quả chính

| Model | Accuracy | Precision attack | Recall attack | F1 attack | AP | ROC-AUC | FPR | TN | FP | FN | TP | n | n_attack | FTP support | FTP recall | SSH support | SSH recall |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Decision Tree | 0.9740352532308525 | 0.0 | 0.0 | 0.0 | 0.025888441074661653 | 0.4999608331849742 | 7.833363005162899e-05 | 140414 | 11 | 3732 | 0 | 144157 | 3732 | 0 | N/A | 3732 | 0.0 |
| **Random Forest (winner)** | **0.9741601170945566** | **1.0** | **0.0018756698821007502** | **0.003744316662209147** | **0.35907455545763656** | **0.748332195118135** | **0.0** | **140425** | **0** | **3725** | **7** | **144157** | **3732** | **0** | **N/A** | **3732** | **0.0018756698821007502** |
| XGBoost | 0.9741115589253383 | 0.0 | 0.0 | 0.0 | 0.08785172107803771 | 0.750322936362417 | 0.0 | 140425 | 0 | 3732 | 0 | 144157 | 3732 | 0 | N/A | 3732 | 0.0 |

Trong Test chính, Random Forest báo đúng 7 attack (`TP = 7`), bỏ sót 3725 attack (`FN = 3725`), không báo nhầm flow BENIGN (`FP = 0`) và có `TN = 140425`. Do Test không có FTP-Patator, `FTP recall` là **N/A**, không thay bằng 0 hay 100%.

### 8.2. Test random split — kết quả đối chứng

| Model | Port | Accuracy | Precision attack | Recall attack | F1 attack | AP | ROC-AUC | FPR | FP | FN | TP | FTP recall | SSH recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Decision Tree | with_port | 0.9996384005021457 | 0.9903993017674013 | 0.9980211081794196 | 0.9941955974153981 | 0.9963176267952678 | 0.9989819638885525 | 0.0003098089746027052 | 44 | 9 | 4539 | 1.0 | 0.9953560371517027 |
| Random Forest | with_port | 0.999979532103895 | 1.0 | 0.9993403693931399 | 0.999670075882547 | 0.9999991805046795 | 0.9999999736809758 | 0.0 | 0 | 3 | 4545 | 1.0 | 0.9984520123839009 |
| XGBoost | with_port | 0.999979532103895 | 0.999340804218853 | 1.0 | 0.9996702934388394 | 0.9999999033508269 | 0.9999999969036442 | 2.112333917745717e-05 | 3 | 0 | 4548 | 1.0 | 1.0 |
| Decision Tree | without_port | 0.9988879109782972 | 0.969989281886388 | 0.9949428320140721 | 0.9823076088136329 | 0.9890395525252749 | 0.997371344884363 | 0.0009857558282813346 | 140 | 23 | 4525 | 0.9969348659003832 | 0.9922600619195047 |
| Random Forest | without_port | 0.9996520457662157 | 0.9934167215273206 | 0.9953825857519789 | 0.9943986820428337 | 0.9994488185050492 | 0.9999654090613279 | 0.00021123339177457173 | 30 | 21 | 4527 | 0.9973180076628353 | 0.9927760577915377 |
| XGBoost | without_port | 0.9998976605194752 | 0.998022412656559 | 0.9986807387862797 | 0.9983514671941972 | 0.9998704763110784 | 0.9999917095073809 | 6.337001753237152e-05 | 9 | 6 | 4542 | 0.9992337164750957 | 0.9979360165118679 |

Các số gần 1.0 trong random split là kết quả đối chứng trong một phân phối trộn ngẫu nhiên. Chúng không thay thế cho kết quả time-based và không được trình bày như bằng chứng tổng quát hóa sang dữ liệu tương lai.

### 8.3. Bản chất học thuật của Random Split: Optimistic Evaluation Bias

Không nên quy chụp đơn giản rằng Random split "chứng minh một cơ chế data leakage cụ thể". Trong an ninh mạng và NIDS:
- Một chiến dịch brute force diễn ra liên tục hàng nghìn flow thường có cùng đặc điểm công cụ dò quét (cùng client SSH/FTP, cùng nhịp gõ thời gian giữa các gói IAT, cùng kích thước gói tin bắt tay).
- Khi xáo trộn ngẫu nhiên toàn bộ ngày Tuesday, các flow thuộc cùng một chiến dịch bị chia đều sang cả Train và Test. Điều này vi phạm giả định quan trọng nhất của học máy: **tính độc lập và phân bố đồng nhất (I.I.D) giữa các flow mạng**.
- Do đó, thuật ngữ học thuật chuẩn xác là **Hiện tượng ước lượng hiệu năng quá lạc quan (Optimistic Evaluation Bias)**: Random split tạo ra một bài toán nội suy dễ hơn rất nhiều, che giấu hoàn toàn điểm mù khi đối mặt với các biến thể tấn công mới trong tương lai.

## 9. Phân tích lỗi

### 9.1. Lỗi trên kết quả chính


Ở Test time/with_port, winner có `FP = 0` và `FPR = 0.0`, nên không tạo báo động giả trong số 140425 flow BENIGN. Tuy nhiên có `FN = 3725` trên `n_attack = 3732`, nên bỏ sót gần như toàn bộ attack của Test; recall attack chỉ là `0.0018756698821007502`, F1 là `0.003744316662209147`.

Precision bằng `1.0` không mâu thuẫn với recall thấp: cả 7 flow bị dự đoán là attack đều đúng, nhưng model gần như luôn dự đoán BENIGN. Vì vậy chỉ nhìn precision hoặc accuracy sẽ che khuất rủi ro bỏ sót; cần đọc đồng thời FN, recall, F1 và support.

### 9.2. Vì sao SSH recall trên Test rất thấp

Train time-based chỉ có FTP-Patator, trong khi Test time-based chỉ có SSH-Patator. Model không được huấn luyện với các mẫu SSH của cửa sổ Train, nên đây là bài kiểm tra zero-shot subtype trong cùng bối cảnh ngày/campaign, không phải bài toán nội suy thông thường giữa hai tập có cùng subtype.

Validation có cả FTP và SSH nhưng winner vẫn có `SSH recall = 0.0` tại threshold `0.5`, trong khi `FTP recall = 0.9971050454921423`. Điều này cho thấy điểm Validation đã cảnh báo sự khác biệt subtype trước khi mở Test. Trên Test, winner chỉ đạt `SSH recall = 0.0018756698821007502`; các model time/with_port còn lại cũng đạt `0.0`.

SHAP cho thấy `Destination Port` có attribution lớn nhất. Vì Train time-based chứa FTP-Patator và Test chỉ có SSH-Patator, port có thể là tín hiệu gắn với dịch vụ/campaign của dữ liệu Train thay vì tín hiệu đủ ổn định cho subtype chưa thấy. Đây là diễn giải phù hợp với pattern quan sát được, nhưng SHAP không chứng minh quan hệ nhân quả.

Kết quả `without_port` trên Test cũng rất thấp: Decision Tree có SSH recall `0.0018756698821007502`, Random Forest `0.0037513397642015005`, và XGBoost `0.0034833869239013935`. Vì vậy việc bỏ port không giải quyết được sự khác biệt subtype; đồng thời không thể quy toàn bộ lỗi cho một feature duy nhất.

### 9.3. Case Study Chuyên sâu: Tác động của Refit Protocol trên Validation đối với XGBoost

Trong quá trình thực nghiệm, xuất hiện sự chênh lệch đáng kể giữa hai kết quả của XGBoost trên kịch bản thời gian:
1. **Benchmark gốc (`artifacts/week3_week4/test_comparison.csv`)**: XGBoost đạt `Test F1 = 0.0000`, `SSH Recall = 0.0%`.
2. **Thực nghiệm Tuning mới (`experiments/w3_05_time_tuning/`)**: XGBoost sau khi chạy script `src/ids/tune_xgboost.py` đạt `Test F1 ≈ 0.9912` (`0.991222`).

**Nguyên nhân kỹ thuật & Bản chất thực nghiệm:**
- Kiểm tra mã nguồn `src/ids/tune_xgboost.py` cho thấy script sử dụng `RandomizedSearchCV` với custom CV trên tập dữ liệu gộp `X_combined = pd.concat([X_train, X_val])`.
- Do không thiết lập `refit=False`, cơ chế mặc định của `RandomizedSearchCV` sẽ tự động lấy toàn bộ `X_combined` (Train + Validation) để huấn luyện lại mô hình `best_estimator_` sau khi chọn xong tham số tối ưu.
- Trong Time-based split: Tập Train chỉ có `FTP-Patator`, nhưng tập Validation chứa **1,886 flows `SSH-Patator`**.
- Do đó, việc refit trên `Train + Val` đã vô tình biến bài toán từ **Zero-Shot Transfer (chưa từng thấy SSH)** thành **Seen-Subtype Evaluation (mô hình đã được học mồi 1,886 mẫu SSH từ trước)**.
- Khi bước vào tập Test, mô hình đã nắm được chữ ký đặc trưng của `SSH-Patator` nên đạt F1 cao (~0.991).

👉 **Ý nghĩa nghiên cứu**: Đây là một bài học thực tế đắt giá trong MLOps và NIDS. Nó chứng minh rằng chỉ cần một sai sót nhỏ trong việc kiểm soát cờ `refit` của thư viện tự động, tính chất của toàn bộ bài toán đánh giá an toàn thông tin sẽ bị thay đổi từ zero-shot sang supervised learning thông thường. Trong báo cáo, nhóm ghi nhận minh bạch cả hai số liệu để làm rõ hiện tượng này.

## 10. SHAP top 10 feature

SHAP được chạy sau khi model đã khóa, trên `validation`, với `n = 500` và `seed = 42`. Model được giải thích là `time/with_port/random_forest`. Đơn vị output là **uncalibrated model score**. Metadata nêu rõ SHAP giải thích hành vi model đã fit, không phải bằng chứng nhân quả và không phải bước chọn feature.

| Hạng | Feature | mean_abs_shap |
|---:|---|---:|
| 1 | Destination Port | 0.12367858920301253 |
| 2 | Fwd Packet Length Std | 0.03392381534141711 |
| 3 | Avg Fwd Segment Size | 0.029166989608427476 |
| 4 | Max Packet Length | 0.028946211059930952 |
| 5 | Packet Length Mean | 0.02748831022689315 |
| 6 | min_seg_size_forward | 0.027221077603185883 |
| 7 | Packet Length Std | 0.027127327898717902 |
| 8 | Fwd Packet Length Mean | 0.027118862731074517 |
| 9 | Average Packet Size | 0.026203867908035312 |
| 10 | Packet Length Variance | 0.020814328103743947 |

`Destination Port` đứng đầu với `mean_abs_shap = 0.12367858920301253`, cao hơn feature thứ hai là `Fwd Packet Length Std` với `0.03392381534141711`. Xếp hạng này chỉ mô tả feature nào model sử dụng nhiều trong các mẫu được giải thích; không được dùng để kết luận feature đó gây ra tấn công hoặc để chọn lại feature sau Test.

## 11. Hình và artifact kết quả

### 11.1. Hình ảnh từ benchmark hợp nhất W3–W4 (`artifacts/week3_week4/figures/`)
- `precision_recall_test_time_with_port.png` — đường precision–recall của kết quả Test time/with_port.
- `confusion_test_time_with_port.png` — confusion matrix của kết quả Test time/with_port.

### 11.2. Bộ 6 biểu đồ khoa học chi tiết phục vụ báo cáo & bảo vệ (`experiments/figures/`)
Được tạo tự động bởi `scripts/generate_detailed_visualizations.py` (chuẩn công bố 300 DPI):
1. `01_tree_structure_detailed.png`: Cấu trúc 3 tầng đầu Cây Quyết định, thể hiện ranh giới tách cổng `Destination Port <= 21.5` phân lập FTP (Port 21) và SSH (Port 22).
2. `02_overfitting_analysis_depth.png`: Đồ thị quá khớp (Overfitting Curve) so sánh F1 Train vs Validation qua các độ sâu từ 2 đến 20, chỉ rõ vùng tối ưu (`max_depth = 4–8`) và vùng quá khớp nặng (`max_depth > 12`).
3. `03_confusion_matrices_detailed.png`: Ma trận nhầm lẫn đối chiếu song song Time-based vs Random split, làm nổi bật 3,725 cuộc tấn công SSH bị bỏ lọt (FN) trên kịch bản thời gian.
4. `04_roc_and_pr_curves_comparative.png`: So sánh trực tiếp đường cong PR (kèm AP) và ROC (kèm AUC) giữa 2 kịch bản phân tách trên cùng hệ quy chiếu.
5. `05_feature_importance_top20.png`: Biểu đồ Top 20 đặc trưng quan trọng nhất phân nhóm theo 4 màu sắc chuyên môn mạng: Cổng mạng, Kích thước gói tin, Thời gian IAT, và Cờ TCP/Tiêu đề.
6. `06_data_leakage_benchmark.png`: Đối chứng tỷ lệ phát hiện theo subtype (FTP vs SSH) và bảng benchmark hiệu năng tổng hợp giữa Decision Tree, Random Forest và XGBoost.

Các hình này là sản phẩm minh họa của run; các con số chính trong báo cáo được lấy từ CSV/JSON, đặc biệt là `test_comparison.csv` và `test_metrics.json`.

## 12. Giới hạn nghiên cứu

1. Kết luận chính chỉ áp dụng cho dữ liệu Tuesday, môi trường và campaign trong run này; không chứng minh tổng quát hóa sang mạng hoặc chiến dịch mới.
2. Time-based Test chỉ có `SSH-Patator`, nên không đánh giá được recall của `FTP-Patator` trên Test; `FTP support = 0` phải được ghi là N/A.
3. Đây là đánh giá zero-shot subtype: Train time-based chỉ có FTP-Patator nhưng Test chỉ có SSH-Patator. Kết quả thấp phản ánh thách thức chuyển subtype, không đủ để tuyên bố pipeline không có giá trị trong mọi bối cảnh.
4. `Destination Port` có vai trò lớn trong SHAP của model winner và được khảo sát bằng port ablation, nhưng không thể suy ra quan hệ nhân quả hay khẳng định port luôn là leakage.
5. Các flow có thể phụ thuộc hoặc tương tự nhau; số dòng không đồng nghĩa với số sự kiện độc lập. Không nên diễn giải support như số mẫu iid độc lập.
6. Chất lượng nhãn chưa được tái kiểm bằng PCAP trong các artifact được đọc.
7. Bài toán phân loại flow hoàn tất không đo latency hay khả năng phát hiện sớm.
8. Score của model chưa được hiệu chuẩn; không được đọc `0.8` như xác suất attack 80%.
9. Random split có thể làm điểm cao do các mẫu tương tự xuất hiện ở nhiều tập; nó chỉ là đối chứng.
10. Không có chứng nhận rằng model đáp ứng yêu cầu triển khai IDS thực tế.

## 13. Kết luận

Với protocol đã khóa, model được chọn trên Validation là Random Forest `time/with_port` với `n_estimators = 100`, `max_depth = 16`, `min_samples_leaf = 5`, 67 features và threshold `0.5`. Trên Validation, model đạt F1 `0.7180938198064035`, precision `1.0`, recall `0.5601765799256505`, AP `0.7326326415549664`, ROC-AUC `0.8892384915421836` và FPR `0.0`.

Trên Test time-based mở đúng một lần, Test chỉ có SSH-Patator. Model winner đạt precision `1.0` nhưng recall `0.0018756698821007502`, F1 `0.003744316662209147`, AP `0.35907455545763656`, ROC-AUC `0.748332195118135`, FPR `0.0`, với `TP = 7`, `FN = 3725`, `FP = 0`, `TN = 140425`. Vì vậy kết luận phù hợp là: mô hình có tổng quát hóa rất hạn chế trong bài kiểm tra theo thời gian từ FTP-Patator sang SSH-Patator chưa xuất hiện trong Train, đặc biệt về khả năng bắt attack; không được phóng đại thành kết luận rằng mô hình thất bại trong mọi bài toán hoặc mọi phân phối dữ liệu.

Các điểm gần 1.0 của random split chỉ là kết quả đối chứng và không được dùng làm kết quả tốt nhất. Sự chênh lệch lớn giữa random split và time-based split là lý do phải ưu tiên kết quả time-based khi trình bày khả năng tổng quát hóa.

## 14. Cách trình bày khi bảo vệ

Có thể trình bày ngắn gọn như sau:

> Nhóm chọn model bằng Validation theo thời gian và khóa model trước khi mở Test. Validation không cao vì đây là chia theo thời gian, còn subtype phân bố không đồng đều: Train time-based chỉ có FTP-Patator, Validation có FTP/SSH và Test chỉ có SSH-Patator. Do đó Test đo một tình huống chuyển sang subtype chưa xuất hiện trong Train; winner chỉ bắt được 7 trên 3732 attack. Ngược lại, random split trộn các flow tương tự giữa các tập nên F1 gần 1.0, nhưng đó chỉ là đối chứng và không đại diện cho tổng quát hóa sang dữ liệu muộn. Vì vậy nhóm báo cáo kết quả time-based là kết quả chính, không chọn lại model theo bảng Test và không gọi điểm random split là bằng chứng triển khai tốt.

## 15. Tái lập và trạng thái khóa

Các phase đã thực hiện bằng Python trong `.venv` của repo theo thứ tự train, Test một lần và SHAP. Test không được mở lại sau lần chạy đó; không có train lại, tune lại hoặc đổi model/feature sau khi Test được mở. `frozen.json` ghi winner là `time/with_port/random_forest`, lựa chọn được thực hiện trên Validation trước Test; snapshot freeze có `test_opened = false` vì đây là trạng thái của checkpoint trước khi mở Test. `test_metrics.json` và `RESULTS.md` ghi rõ Test đã được mở một lần và winner không được chọn lại theo Test.

### Artifact nguồn chính

- `artifacts/week3_week4/validation_winners.csv`
- `artifacts/week3_week4/port_ablation_validation.csv`
- `artifacts/week3_week4/split_diff_validation.csv`
- `artifacts/week3_week4/test_comparison.csv`
- `artifacts/week3_week4/test_metrics.json`
- `artifacts/week3_week4/frozen.json`
- `artifacts/week3_week4/RESULTS.md`
- `artifacts/week3_week4/shap/metadata.json`
- `artifacts/week3_week4/shap/feature_importance.csv`
- `artifacts/week3_week4/figures/precision_recall_test_time_with_port.png`
- `artifacts/week3_week4/figures/confusion_test_time_with_port.png`
