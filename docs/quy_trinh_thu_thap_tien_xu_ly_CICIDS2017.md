# QUY TRÌNH THU THẬP VÀ TIỀN XỬ LÝ DỮ LIỆU CICIDS2017

**Phạm vi:** chuẩn bị dữ liệu Brute Force FTP/SSH cho giai đoạn huấn luyện Decision Tree, Random Forest và XGBoost  
**Dataset:** CICIDS2017 - Tuesday `GeneratedLabelledFlows`  
**Mục tiêu tài liệu:** giúp một thành viên khác có thể hiểu dữ liệu đến từ đâu, đã được kiểm tra/xử lý như thế nào, đầu ra của từng giai đoạn là gì, và phải dùng dữ liệu cuối cùng ra sao khi bắt đầu huấn luyện mô hình.

> **Căn cứ chính:** *Báo cáo thiết kế protocol thực nghiệm - Ứng dụng học máy trong phát hiện tấn công mạng từ dữ liệu lưu lượng mạng*, đặc biệt các mục 2-7 và quy trình cuối cùng ở mục 13. Những quyết định triển khai riêng của project được ghi rõ là “quy tắc triển khai của project”, không được trình bày như yêu cầu mặc định của protocol.

---

## 1. Tóm tắt luồng xử lý

```text
CSV CICIDS2017 Tuesday gốc
        |
        v
[1] Thu thập + provenance
        |
        v
[2] Audit schema / nhãn / Timestamp / Flow Duration
        |
        v
[3] Làm sạch deterministic + EDA
        |
        v
[4] Chốt 2 chiến lược split
        |-----------------------------|
        v                             v
   Time-based                     Random
 + purge/embargo               stratified
        |                             |
        v                             v
   checkpoint                     checkpoint
        |                             |
        +-------------+---------------+
                      |
                      v
[5] Preprocessing FIT trên Train của từng split
    - bỏ metadata/feature không dùng
    - constant/all-missing filter
    - median imputation
                      |
                      v
[6] 2 feature scenarios cho mỗi split
    - WITH Destination Port
    - WITHOUT Destination Port
                      |
                      v
[7] QA model-ready
                      |
                      v
Dữ liệu bàn giao cho DT / RF / XGBoost
```

**Điểm dừng của phần dữ liệu:** sau bước QA model-ready. Từ đây mới bắt đầu train/tune mô hình.

---

## 2. Các thuật ngữ cần hiểu trước khi đọc

### 2.1 Flow
**Flow** là một luồng giao tiếp mạng đã được tổng hợp thành một bản ghi thống kê, thay vì một packet đơn lẻ. Một flow có các đặc trưng như số packet, số byte, thời lượng, độ trễ giữa packet, cờ TCP, v.v. Trong đề tài này, mô hình phân loại ở **mức flow**, không phải ở packet đầu tiên.

### 2.2 Feature
**Feature** là biến đầu vào cho mô hình học máy. Ví dụ: `Flow Duration`, `Flow Bytes/s`, `Packet Length Mean`. Các cột chỉ dùng để định danh/audit như `Flow ID`, IP, Timestamp hoặc Label không được đưa vào model.

### 2.3 Label, Binary Label và Subtype
- **Label**: nhãn gốc của CICIDS2017, ví dụ `BENIGN`, `FTP-Patator`, `SSH-Patator`.
- **Binary Label**: nhãn nhị phân của bài toán: `0 = Normal`, `1 = Attack`.
- **Subtype**: loại tấn công gốc được giữ lại để biết Attack là FTP hay SSH, nhưng không phải feature đầu vào.

### 2.4 Provenance
**Provenance** là thông tin truy xuất nguồn gốc dữ liệu: file nào đã dùng, lấy từ đâu, kích thước, hash, phiên bản, script nào tạo ra dữ liệu xử lý. Provenance giúp người khác tái lập đúng thí nghiệm.

### 2.5 Hash SHA-256
**SHA-256** là dấu vân tay số của file. Nếu file thay đổi dù chỉ một byte, hash thường thay đổi. Project dùng hash để xác nhận đúng file đầu vào.

### 2.6 Audit dữ liệu
**Audit** là bước kiểm tra dữ liệu trước khi train: schema, nhãn, Timestamp, Flow Duration, NaN/Infinity, duplicate, provenance, v.v. Audit không phải huấn luyện mô hình.

### 2.7 EDA
**EDA (Exploratory Data Analysis)** là phân tích khám phá dữ liệu. Ở đây EDA dùng để hiểu phân bố nhãn theo thời gian, missing/Infinity, duplicate và support của từng subtype trước khi chốt split. Không dùng EDA để thử nhiều cutoff rồi chọn cutoff có Test/F1 đẹp nhất.

### 2.8 Data Leakage
**Data Leakage** là việc thông tin không nên có ở thời điểm train/selection vô tình lọt vào pipeline, khiến kết quả đánh giá lạc quan giả tạo. Ví dụ: tính median trên toàn bộ dataset rồi mới chia Train/Test.

### 2.9 Train / Validation / Test
- **Train**: tập duy nhất được phép dùng để học tham số preprocessing và model.
- **Validation**: dùng để chọn model, hyperparameter và threshold.
- **Test**: chỉ dùng đánh giá cuối sau khi mọi quyết định đã khóa.

### 2.10 Fit và Transform
- **Fit**: học tham số từ dữ liệu. Ví dụ `median` của feature hoặc danh sách cột constant.
- **Transform**: áp dụng tham số đã học vào tập khác. Validation/Test chỉ được transform bằng preprocessing đã fit trên Train.

### 2.11 Time-based split
**Time-based split** là chia dữ liệu theo trật tự quá khứ -> tương lai. Đây là split chính của protocol vì gần với tình huống triển khai hơn random split.

### 2.12 Random split
**Random split** là chia ngẫu nhiên dữ liệu thành Train/Validation/Test. Trong protocol này, Random split chỉ là **đối chứng**, không phải kết quả chính.

### 2.13 Purge và Embargo
- **Purge**: loại các flow cắt qua ranh giới thời gian giữa các tập.
- **Embargo**: tạo một khoảng đệm sau ranh giới để giảm tương tác quá gần giữa tập trước và tập sau.

Với một flow:

```text
s = thời gian bắt đầu flow
e = s + Flow Duration + q
```

Trong đó `q` là biên sai số bảo thủ do độ chính xác Timestamp. Gọi `a` là mốc hết Train, `b` là mốc hết Validation, `g` là embargo:

```text
Train      : e < a
Validation : s >= a + g và e < b
Test       : s >= b + g
```

### 2.14 Imputation
**Imputation** là điền giá trị cho dữ liệu thiếu. Project dùng **median imputation**: giá trị thiếu được thay bằng median học từ **Train** tương ứng.

### 2.15 Constant feature / all-missing feature
- **Constant feature**: cột chỉ có một giá trị hữu ích trên Train, không cung cấp khả năng phân biệt mẫu.
- **All-missing feature**: cột toàn missing trên Train.

Hai loại này được xác định từ Train và loại khỏi schema model.

### 2.16 Ablation
**Ablation** là thí nghiệm có chủ đích bỏ một feature/nhóm feature để xem kết quả thay đổi ra sao. Protocol yêu cầu chạy hai kịch bản `WITH Destination Port` và `WITHOUT Destination Port`.

### 2.17 Shortcut feature
**Shortcut feature** là feature có thể cho model một đường tắt rất dễ dự đoán trong dataset nhưng không phản ánh đầy đủ hành vi cần học. `Destination Port` có nguy cơ gắn mạnh với FTP/SSH nên phải làm ablation. Không được kết luận bản thân Port luôn là leakage.

### 2.18 Model-ready
**Model-ready** là dữ liệu đã được đưa về schema số nhất quán, không còn NaN/Infinity, feature giữa Train/Validation/Test giống nhau và có target tách riêng, sẵn sàng đưa cho thuật toán train.

---

## 3. Giai đoạn 1 - Thu thập và xác nhận đúng nguồn dữ liệu

### 3.1 File dữ liệu sử dụng

Project dùng file:

```text
data/raw/cicids2017/GeneratedLabelledFlows/Tuesday-WorkingHours.pcap_ISCX.csv
```

Thông tin đã audit:

| Thuộc tính | Giá trị |
|---|---:|
| Kích thước file | 174,696,560 bytes |
| SHA-256 | `ae9c88e10c41a8eb1ff454ae98bc513454925097d0b0b57180f94e79de445815` |
| Số dòng raw | 445,909 |
| Số cột raw | 85 |

### 3.2 Vì sao không dùng file 79 cột ban đầu?

Bản `MachineLearningCSV` đã kiểm tra trước đó không có `Timestamp`, trong khi protocol yêu cầu phải có trục thời gian thật để thực hiện Time-based split. Vì vậy project chuyển sang `GeneratedLabelledFlows` có `Label`, `Timestamp` và `Flow Duration`.

### 3.3 Đầu ra của giai đoạn thu thập

Đầu ra không phải là dataset mới, mà là **một nguồn dữ liệu raw đã được xác nhận danh tính**:

```text
Input raw CSV + hash + schema + số dòng/cột + thông tin nguồn
```

Script liên quan:

```text
scripts/audit_tuesday.py
scripts/inspect_tuesday_quality.py
```

---

## 4. Giai đoạn 2 - Audit schema, nhãn và chất lượng dữ liệu

### 4.1 Phạm vi nhãn

Theo protocol, chỉ giữ ba nhãn:

| Nhãn gốc | Nhãn nhị phân | Vai trò |
|---|---:|---|
| `BENIGN` | 0 | Normal |
| `FTP-Patator` | 1 | Attack - FTP |
| `SSH-Patator` | 1 | Attack - SSH |

Phân bố raw:

| Label | Số dòng |
|---|---:|
| BENIGN | 432,074 |
| FTP-Patator | 7,938 |
| SSH-Patator | 5,897 |

### 4.2 Kiểm tra các cột bắt buộc

File `GeneratedLabelledFlows` có đủ:

```text
Label
Timestamp
Flow Duration
```

Đây là điều kiện cần để tiếp tục Time-based split.

### 4.3 Missing và Infinity

Trên raw data:

- `Flow Bytes/s`: có 201 NaN gốc.
- Infinity tổng cộng: 327 giá trị.
  - `Flow Packets/s`: 264 Infinity.
  - `Flow Bytes/s`: 63 Infinity.

**Infinity** là giá trị vô cực, thường xuất hiện do phép chia cho 0 hoặc thời lượng rất nhỏ. Protocol cho phép đổi Infinity thành missing theo quy tắc cố định trước split; việc điền missing bằng imputation phải đợi đến Train.

Sau khi đổi Infinity -> NaN:

```text
Flow Bytes/s    : 264 missing
Flow Packets/s  : 264 missing
```

### 4.4 Flow Duration âm

Có **17 dòng** có `Flow Duration < 0`, tất cả thuộc `BENIGN`.

Quy tắc triển khai của project: loại 17 dòng này khỏi dữ liệu dùng để split, vì thời lượng âm không tạo được completion time hợp lệ cho purge/embargo.

### 4.5 Duplicate

Phát hiện 4 duplicate dư, tức 4 cặp bản ghi giống nhau hoàn toàn (8 dòng tạo thành 4 cặp). Tất cả thuộc `BENIGN`.

Quy tắc: **giữ bản xuất hiện sớm nhất, bỏ bản trùng sau và log số lượng**. Nếu cùng bản ghi nhưng nhãn mâu thuẫn thì phải dừng để điều tra provenance; không vote nhãn theo đa số.

### 4.6 Cột lặp `.1`

`Fwd Header Length.1` được kiểm tra và giống `Fwd Header Length` trên toàn bộ 445,909 dòng. Vì vậy cột `.1` được loại để tránh duplication feature.

### 4.7 Đầu ra sau deterministic cleaning

**Deterministic cleaning** nghĩa là các thao tác làm sạch dùng quy tắc cố định, không học tham số từ Validation/Test.

Sau khi bỏ 17 duration âm và 4 duplicate dư:

```text
445,888 rows
```

Phân bố còn lại:

| Label | Số dòng |
|---|---:|
| BENIGN | 432,053 |
| FTP-Patator | 7,938 |
| SSH-Patator | 5,897 |

Đầu ra logic của giai đoạn này là **clean population** gồm 445,888 flow, vẫn giữ missing ở `Flow Bytes/s` và `Flow Packets/s` để imputer học sau từ Train.

---

## 5. Giai đoạn 3 - Xử lý Timestamp và EDA phục vụ thiết kế split

### 5.1 Vấn đề Timestamp thực tế

Timestamp raw không có token AM/PM và chỉ quan sát thấy giờ `1-5` và `8-12`. Protocol yêu cầu phải kiểm tra 12h/24h, AM/PM và không được suy giờ trực tiếp từ Label hoặc Destination Port.

### 5.2 Quy tắc triển khai của project

Project dùng quy tắc tái dựng thời gian độc lập với Label/Port:

```text
raw hour 8-12 : giữ nguyên
raw hour 1-5  : +12 giờ
```

Sau tái dựng:

```text
min Timestamp : 2017-07-04 08:53
max Timestamp : 2017-07-04 17:00
```

Khoảng hoạt động quan sát được:

```text
FTP-Patator : 09:17 - 10:30
SSH-Patator : 14:09 - 15:11
```

> **Lưu ý quan trọng:** quy tắc `1-5 -> +12h` là **quy tắc triển khai của project sau audit**, không phải câu lệnh được protocol mặc định quy định. Phải ghi đây là limitation/reconstruction policy khi báo cáo.

### 5.3 EDA theo thời gian

Project dùng bin thời gian 10 phút (`TimeBin10`) để quan sát support Attack và chọn cutoff khả thi. `TimeBin10` là **cột EDA-only**, tuyệt đối không dùng làm feature model.

EDA được dùng để chọn mốc có support Attack hợp lý, không dùng kết quả model/Test để tối ưu cutoff.

### 5.4 Mốc split đã khóa

Project chốt:

```text
a = 2017-07-04 10:00
b = 2017-07-04 14:30
q = 60 giây
g = 120 giây
```

Trong đó:

- `a`: mốc hết Train.
- `b`: mốc hết Validation.
- `q`: biên sai số cộng vào completion time của flow.
- `g`: khoảng embargo sau mỗi ranh giới.

---

## 6. Giai đoạn 4 - Time-based split chính

### 6.1 Công thức

Mỗi flow có:

```text
s = StartTime
e = s + Flow Duration + q
```

Với cấu hình `q=60s`, `g=120s`:

```text
Train      : e < 10:00
Validation : s >= 10:02 và e < 14:30
Test       : s >= 14:32
```

Những flow rơi vào vùng biên hoặc embargo bị loại khỏi split chính và được log.

### 6.2 Số flow bị loại ở biên

| Loại | Số dòng |
|---|---:|
| Purge tại mốc `a` | 1,102 |
| Embargo sau `a` | 2,863 |
| Purge tại mốc `b` | 1,487 |
| Embargo sau `b` | 2,180 |
| **Tổng** | **7,632** |

### 6.3 Kết quả Time-based split

| Tập | Tổng | BENIGN | FTP | SSH | Attack | Attack % |
|---|---:|---:|---:|---:|---:|---:|
| Train | 90,273 | 85,139 | 5,134 | 0 | 5,134 | 5.687% |
| Validation | 203,826 | 199,522 | 2,418 | 1,886 | 4,304 | 2.112% |
| Test | 144,157 | 140,425 | 0 | 3,732 | 3,732 | 2.589% |

Khoảng thời gian thực tế:

```text
Train      : 08:53 - 09:58
Validation : 10:02 - 14:28
Test       : 14:32 - 17:00
```

### 6.4 Limitation quan trọng của Time-based split

Train Attack chỉ có FTP, trong khi Test Attack chỉ có SSH. Điều này không làm sai bài toán nhị phân Normal/Attack, nhưng khiến Test đồng thời kiểm tra **temporal generalization** và một mức **subtype shift**.

**Subtype shift** nghĩa là phân bố loại tấn công giữa Train và Test thay đổi. Người train phải biết điều này để không diễn giải kết quả như thể Train/Test có cùng subtype distribution.

### 6.5 Checkpoint đầu ra

```text
data/processed/split_v1/
├── train.csv
├── validation.csv
├── test.csv
└── split_metadata.json
```

**Checkpoint** là ảnh chụp dữ liệu đã chốt ở một giai đoạn, giúp các model dùng đúng cùng một split và không tự chia lại.

---

## 7. Giai đoạn 5 - Random split đối chứng

### 7.1 Mục đích

Random split được giữ vì protocol yêu cầu một đối chứng với Time-based split. Random không dùng làm kết quả chính.

### 7.2 Cách tạo

- Nguồn: cùng clean population 445,888 flow trước purge của Time split.
- Seed: `42`.
- Shuffle: có.
- Stratify: theo `Label` gốc để BENIGN/FTP/SSH cùng được phân bố vào ba tập.
- Tỷ lệ mục tiêu: theo tỷ lệ các tập Time-based sau purge.

**Stratify** nghĩa là chia dữ liệu sao cho tỷ lệ các nhãn trong mỗi tập gần với tỷ lệ chung theo biến dùng để stratify.

### 7.3 Kết quả Random split

| Tập | Tổng | BENIGN | FTP | SSH | Attack | Attack % |
|---|---:|---:|---:|---:|---:|---:|
| Train | 91,845 | 88,995 | 1,635 | 1,215 | 2,850 | 3.103% |
| Validation | 207,375 | 200,941 | 3,692 | 2,742 | 6,434 | 3.103% |
| Test | 146,668 | 142,117 | 2,611 | 1,940 | 4,551 | 3.103% |

### 7.4 Checkpoint đầu ra

```text
data/processed/random_split_v1/
├── train.csv
├── validation.csv
├── test.csv
└── split_metadata.json
```

---

## 8. Giai đoạn 6 - Chính sách feature trước preprocessing

### 8.1 Metadata/target không đưa vào model

Các cột sau không phải feature model:

```text
Flow ID
Source IP
Destination IP
Timestamp
Timestamp_fixed
StartTime
EndTime
TimeBin10
Label
Subtype
BinaryLabel
```

Lý do:

- ID/IP/Timestamp có nguy cơ tạo shortcut/leakage và protocol quy định giữ cho audit/split, không làm đầu vào model.
- `Label`, `Subtype`, `BinaryLabel` mô tả target; nếu đưa vào feature thì model sẽ nhìn thấy đáp án.
- `TimeBin10` chỉ được tạo cho EDA.

### 8.2 Source Port và Protocol

Project chọn loại thêm:

```text
Source Port
Protocol
```

Đây là **lựa chọn thiết kế của project**, không phải yêu cầu bắt buộc của protocol. Không được kết luận hai feature này vô ích cho mọi IDS.

### 8.3 Destination Port - hai scenario

Mỗi split tạo hai cấu hình:

```text
WITH_PORT    : giữ Destination Port
WITHOUT_PORT : bỏ Destination Port
```

Mục tiêu là đo mức phụ thuộc của model vào thông tin cổng dịch vụ.

---

## 9. Giai đoạn 7 - Preprocessing fit trên Train

### 9.1 Nguyên tắc fit boundary

Đây là nguyên tắc quan trọng nhất để tránh Data Leakage:

```text
Train      : được FIT preprocessing
Validation : chỉ TRANSFORM
Test       : chỉ TRANSFORM
```

Không được tính median trên toàn dataset. Không được xem Validation/Test để quyết định cột constant.

### 9.2 Feature count trước filter

Ở cả Time và Random:

```text
WITH Destination Port    : 77 features
WITHOUT Destination Port : 76 features
```

### 9.3 Constant features học từ Train

Cả Time Train và Random Train đều phát hiện 10 constant features:

```text
Bwd PSH Flags
Fwd URG Flags
Bwd URG Flags
CWE Flag Count
Fwd Avg Bytes/Bulk
Fwd Avg Packets/Bulk
Fwd Avg Bulk Rate
Bwd Avg Bytes/Bulk
Bwd Avg Packets/Bulk
Bwd Avg Bulk Rate
```

All-missing features: `0`.

Sau constant filter:

```text
WITH_PORT    : 67 features
WITHOUT_PORT : 66 features
```

### 9.4 Median imputation

Chỉ hai feature còn missing:

```text
Flow Bytes/s
Flow Packets/s
```

Median học từ **Time Train**:

| Feature | Median |
|---|---:|
| Flow Bytes/s | 2500.479106 |
| Flow Packets/s | 97.087379 |

Median học từ **Random Train**:

| Feature | Median |
|---|---:|
| Flow Bytes/s | 2501.807126 |
| Flow Packets/s | 120.407580 |

Median khác nhau là bình thường. Điều này minh họa lý do mỗi split phải fit preprocessing riêng trên Train tương ứng.

### 9.5 Script chính thức

```text
scripts/preprocess_data.py
```

Script này:

1. load Train/Validation/Test checkpoint;
2. chọn feature theo policy;
3. phát hiện constant/all-missing từ Train;
4. fit `SimpleImputer(strategy="median")` trên Train;
5. transform Train/Validation/Test;
6. kiểm tra NaN/Infinity;
7. lưu X/y và metadata cho từng scenario.

**Lưu ý:** việc đọc Test để transform bằng transformer đã fit không phải leakage. Leakage xảy ra nếu Test được dùng để học median, chọn cột, chọn model, threshold hoặc hyperparameter.

---

## 10. Giai đoạn 8 - Model-ready output

### 10.1 Cấu trúc thư mục

```text
data/model_ready/
├── time/
│   ├── with_port/
│   │   ├── X_train.csv
│   │   ├── X_validation.csv
│   │   ├── X_test.csv
│   │   ├── y_train.csv
│   │   ├── y_validation.csv
│   │   ├── y_test.csv
│   │   └── preprocessing_metadata.json
│   └── without_port/
│       └── ...
└── random/
    ├── with_port/
    │   └── ...
    └── without_port/
        └── ...
```

### 10.2 Ý nghĩa file

- `X_*.csv`: ma trận feature đã preprocessing.
- `y_*.csv`: target `BinaryLabel` tương ứng.
- `preprocessing_metadata.json`: mô tả feature count, constant feature, median imputer, class support và policy đã dùng.

### 10.3 QA cuối

QA đã xác nhận cho 4 scenario:

```text
Same feature schema : True
NaN                : 0
Infinity           : 0
X/y index aligned  : True
```

Kích thước Time-based:

| Scenario | Train | Validation | Test |
|---|---:|---:|---:|
| WITH_PORT | (90,273, 67) | (203,826, 67) | (144,157, 67) |
| WITHOUT_PORT | (90,273, 66) | (203,826, 66) | (144,157, 66) |

Target Time-based:

```text
Train      : Normal 85,139 | Attack 5,134
Validation : Normal 199,522 | Attack 4,304
Test       : Normal 140,425 | Attack 3,732
```

Kích thước Random:

| Scenario | Train | Validation | Test |
|---|---:|---:|---:|
| WITH_PORT | (91,845, 67) | (207,375, 67) | (146,668, 67) |
| WITHOUT_PORT | (91,845, 66) | (207,375, 66) | (146,668, 66) |

Target Random:

```text
Train      : Normal 88,995 | Attack 2,850
Validation : Normal 200,941 | Attack 6,434
Test       : Normal 142,117 | Attack 4,551
```

---

## 11. Người train phải dùng dữ liệu như thế nào?

### 11.1 Không chia lại dữ liệu

Người train **không được** lấy toàn bộ dữ liệu rồi tự `train_test_split` lại. Các checkpoint đã khóa để mọi thuật toán dùng chung một dữ liệu so sánh công bằng.

### 11.2 Ma trận thí nghiệm

Ba model bắt buộc:

```text
Decision Tree
Random Forest
XGBoost
```

Mỗi model chạy trên:

```text
2 split x 2 feature scenario = 4 cấu hình
```

Do đó toàn bộ thực nghiệm có:

```text
3 model x 2 split x 2 scenario = 12 cấu hình
```

### 11.3 Ví dụ load dữ liệu

Ví dụ train Decision Tree cho Time-based + WITH_PORT:

```python
import pandas as pd

base = "data/model_ready/time/with_port"

X_train = pd.read_csv(f"{base}/X_train.csv", index_col=0)
y_train = pd.read_csv(f"{base}/y_train.csv", index_col=0)["BinaryLabel"]

X_val = pd.read_csv(f"{base}/X_validation.csv", index_col=0)
y_val = pd.read_csv(f"{base}/y_validation.csv", index_col=0)["BinaryLabel"]

# Test chưa dùng trong giai đoạn tuning.
```

### 11.4 Train/Validation/Test được dùng thế nào?

```text
Train
  -> fit model
  -> class_weight / scale_pos_weight phải tính từ Train

Validation
  -> chọn hyperparameter
  -> chọn threshold
  -> so sánh model/scenario

Test
  -> giữ đóng cho đến khi mọi quyết định đã khóa
  -> chỉ đánh giá cuối
```

### 11.5 Không fit lại preprocessing

Dữ liệu trong `data/model_ready` đã được preprocessing bằng thống kê của Train. Nếu train trực tiếp từ model-ready thì **không chạy thêm median imputer trên toàn bộ Train+Validation/Test**.

Nếu nhóm muốn sử dụng pipeline trực tiếp từ checkpoint `data/processed`, preprocessing phải được fit lại **chỉ từ Train của cùng split** với đúng policy và metadata tương ứng.

### 11.6 Không dùng Test để ra quyết định

Không được:

- chọn feature sau khi nhìn Test;
- chọn hyperparameter theo Test;
- chọn threshold theo Test;
- đổi cutoff split sau khi nhìn F1 Test;
- xem SHAP trên Test rồi đổi model/feature nhưng vẫn giữ kết quả Test cũ là độc lập.

---

## 12. Script và trách nhiệm từng file

Các script dữ liệu hiện tại có thể giữ tách riêng:

| Script | Chức năng |
|---|---|
| `audit_tuesday.py` | Audit tổng quan file Tuesday: schema, label, Timestamp, hash, kích thước |
| `inspect_tuesday_quality.py` | Kiểm tra sâu NaN/Infinity, duplicate, Flow Duration, cột lặp |
| `prepare_splits.py` | Cleaning deterministic, Timestamp policy, Time split + purge/embargo, checkpoint |
| `preprocess_data.py` | Preprocessing Train-only, WITH/WITHOUT Port, xuất model-ready |
| `make_demo_data.py` | Tạo dữ liệu synthetic để test phần mềm; không phải pipeline dữ liệu thật |
| `smoke_test.py` | Chạy smoke test trên demo để xác nhận hệ thống chạy; không dùng làm kết quả thực nghiệm |

**Smoke test** là kiểm tra nhanh xem phần mềm/pipeline có chạy end-to-end hay không. Nó không thay thế đánh giá trên CICIDS2017 thật.

---

## 13. Những gì KHÔNG nên commit lên Git

Các file dữ liệu rất lớn không nên đưa vào repository nếu project đã `.gitignore` chúng:

```text
data/raw/
data/processed/
data/model_ready/
*.pcap
*.pcapng
```

Nên commit:

```text
scripts/*.py
docs/*.md
README.md
config/metadata nhỏ
```

Mục tiêu là người khác clone repo, đặt raw CSV đúng vị trí rồi chạy script để tái tạo checkpoint/model-ready.

---

## 14. Giới hạn và lưu ý cần ghi trong báo cáo

### 14.1 Timestamp reconstruction

Timestamp Tuesday cần quy tắc tái dựng `1-5 -> +12h`. Đây là quyết định kỹ thuật của project sau audit, không phải một quy tắc phổ quát của CICIDS2017. Phải công khai trong limitations.

### 14.2 Time-based subtype shift

Time Train có Attack là FTP nhưng Test có Attack là SSH. Do đó kết quả Time-based phản ánh đồng thời khả năng dự đoán tương lai và khả năng tổng quát sang subtype Attack khác.

### 14.3 Embargo không chứng minh độc lập hoàn toàn

`g=120s` là buffer kỹ thuật nhằm giảm tương tác gần ranh giới, không phải bằng chứng toán học rằng các flow giữa các tập hoàn toàn độc lập.

### 14.4 Source Port và Protocol

Hai feature này được project bỏ theo lựa chọn thiết kế. Không được khái quát rằng chúng vô ích trong mọi IDS.

### 14.5 Destination Port

Destination Port có thể là thông tin mạng hợp lệ. Mục đích ablation là đo độ phụ thuộc/shortcut sensitivity, không tự động gắn nhãn leakage.

---

## 15. Checklist bàn giao trước khi train

Người nhận dữ liệu nên kiểm tra các điểm sau trước khi bắt đầu model:

- [ ] Có cả `time/with_port`, `time/without_port`, `random/with_port`, `random/without_port`.
- [ ] WITH_PORT có 67 feature; WITHOUT_PORT có 66 feature.
- [ ] Không còn NaN hoặc Infinity.
- [ ] X và y cùng số dòng, index align.
- [ ] Không tự chia lại Train/Validation/Test.
- [ ] Không fit imputer/constant filter trên Validation/Test.
- [ ] Không đưa Flow ID/IP/Timestamp/Label/metadata vào model.
- [ ] Random split chỉ dùng làm đối chứng; Time-based là kết quả chính.
- [ ] Validation dùng cho tuning và threshold.
- [ ] Test giữ đóng đến khi model/hyperparameter/feature scenario/threshold đã khóa.
- [ ] Khi báo cáo Time-based, nêu rõ subtype support thực tế của FTP/SSH.

---

## 16. Nguồn tham chiếu

1. **Báo cáo thiết kế protocol thực nghiệm - Ứng dụng học máy trong phát hiện tấn công mạng từ dữ liệu lưu lượng mạng**, trọng tâm Brute Force trên CICIDS2017. Các mục sử dụng trực tiếp trong tài liệu này: Mục 2 (phạm vi bài toán), Mục 3 (audit), Mục 4 (EDA/chất lượng), Mục 5 (Time/Random split), Mục 6 (ranh giới fit), Mục 7 (feature policy và Destination Port ablation), Mục 13 (quy trình cuối cùng).
2. **Đề cương đồ án đã cập nhật**, dùng để xác nhận phạm vi nhãn, ba mô hình bắt buộc và định hướng Time-based/Random split.

---

## 17. Kết luận bàn giao

Phần thu thập và tiền xử lý kết thúc tại `data/model_ready`. Tại thời điểm bàn giao, dữ liệu đã:

```text
- xác nhận nguồn và hash;
- audit schema/nhãn/thời gian/chất lượng;
- loại lỗi deterministic đã chốt;
- khóa Time-based split và Random split;
- áp purge/embargo cho Time-based;
- fit constant filter và median imputation chỉ trên Train;
- tạo 2 scenario có/không Destination Port;
- kiểm tra schema, NaN, Infinity và X/y alignment;
- sẵn sàng dùng chung cho Decision Tree, Random Forest và XGBoost.
```

Từ đây, nhóm model bắt đầu ở **Bước 8 của protocol: Train và tuning**, không quay lại chia hoặc fit preprocessing trên toàn dataset.
