# Báo Cáo Học Thuật LaTeX Modular: Đề Tài Brute Force CICIDS2017

Thư mục này chứa toàn bộ mã nguồn báo cáo khoa học / đồ án môn học An toàn Thông tin theo chuẩn Đại học Xây dựng Hà Nội (HUCE), được thiết kế theo kiến trúc **Modular Architecture** và tuân thủ nguyên tắc **Zero-Hallucination** (toàn bộ số liệu thực nghiệm được sinh tự động từ các artifact đã kiểm chứng).

---

## 1. Cấu Trúc Thư Mục

```text
reports/
├── main.tex                       # File gốc điều phối toàn bộ tài liệu
├── Makefile                       # Tự động hóa build và sinh số liệu
├── latexmkrc                      # Cấu hình compiler XeLaTeX
├── LogoHUCE.jpg                   # Logo trường Đại học Xây dựng Hà Nội
│
├── config/                        # Cấu hình và macro số liệu
│   ├── packages.tex               # Khai báo các gói lệnh
│   ├── typography.tex             # Căn lề khổ A4, font Times New Roman tiếng Việt
│   ├── metadata.tex               # Tên đề tài, sinh viên, người hướng dẫn
│   ├── commands.tex               # Macro tiện ích và ký hiệu toán học
│   └── generated_metrics.tex      # TỰ ĐỘNG: Sổ đăng ký macro số liệu từ artifact
│
├── frontmatter/                   # Các trang thủ tục đầu báo cáo
│   ├── titlepage.tex              # Trang bìa chuẩn HUCE
│   ├── acknowledgement.tex        # Lời cảm ơn
│   ├── abstract_vi.tex            # Tóm tắt báo cáo tiếng Việt (vừa vặn 1 trang)
│   └── abbreviations.tex          # Bảng danh mục chữ viết tắt
│
├── chapters/                      # Các chương báo cáo (Chương 1 đến 6)
│   ├── 01_gioi_thieu.tex          # Chương 1: Giới thiệu & Đặt vấn đề
│   ├── 02_co_so_ly_thuyet.tex     # Chương 2: Cơ sở lý thuyết Flow-NIDS & ML cây
│   ├── 03_du_lieu_va_bai_toan.tex # Chương 3: Dữ liệu CICIDS2017 & Làm sạch
│   ├── 04_phuong_phap_de_xuat.tex # Chương 4: Kiến trúc hệ thống & Purge/Embargo
│   ├── 05_thiet_ke_thuc_nghiem.tex# Chương 5: Thiết kế thực nghiệm & Không gian siêu tham số
│   └── 06_ket_qua.tex             # Chương 6: Kết quả thực nghiệm đối chuẩn & Tổng kết RQ1-RQ4
│
├── sections/                      # Module nội dung chi tiết
│   └── results/                   # 8 module kết quả định lượng và tổng kết diễn giải (06_01 đến 06_08)
│
├── tables/                        # Bảng biểu
│   ├── generated/                 # TỰ ĐỘNG SINH: 6 bảng booktabs từ artifact
│   └── manual/                    # 3 bảng mô tả đặc trưng và phương pháp
│
├── appendices/                    # Phụ lục kỹ thuật
│   ├── appendix_a_reproducibility.tex # Hướng dẫn tái lập
│   ├── appendix_b_hyperparameters.tex # Bảng siêu tham số tối ưu
│   ├── appendix_c_feature_list.tex    # Danh mục 67 đặc trưng mạng
│   └── appendix_d_tree_rules.tex      # Quy tắc rẽ nhánh cây quyết định
│
└── bibliography/
    └── references.bib             # Trích dẫn học thuật chuẩn IEEE
```

---

## 2. Hướng Dẫn Biên Dịch PDF

### Yêu cầu tiên quyết:
- Bản phân phối TeX: TeX Live $\ge 2023$ hoặc MiKTeX (hỗ trợ `xelatex` và font `Times New Roman`).
- Trình quản lý trích dẫn: `biber`.
- Python $\ge 3.11$ (để chạy script sinh macro tự động).

### Các lệnh biên dịch:
```bash
# Di chuyển vào thư mục reports
cd reports

# 1. Sinh lại toàn bộ macro và bảng từ artifact (nếu có thay đổi thực nghiệm)
make metrics
# hoặc chạy trực tiếp: python ../scripts/report/generate_latex_registry.py

# 2. Biên dịch toàn bộ tài liệu thành PDF
make pdf
# hoặc: latexmk -xelatex main.tex

# 3. Dọn dẹp các tệp trung gian sau khi biên dịch
make clean
```
