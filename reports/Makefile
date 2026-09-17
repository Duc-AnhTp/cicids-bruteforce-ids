# ==============================================================================
# reports/Makefile
# Makefile tự động hóa biên dịch báo cáo LaTeX và sinh số liệu
# ==============================================================================

PROJECT = main
BUILD_DIR = build
COMPILER = xelatex
BIB_COMPILER = biber

.PHONY: all pdf clean metrics view help

all: metrics pdf

# 1. Sinh macro so lieu va bang LaTeX tu artifact
metrics:
	@echo "==> Dang sinh macro so lieu va bang tu artifacts..."
	python ../scripts/report/generate_latex_registry.py

# 2. Bien dich PDF bang latexmk (hoac fallback xelatex)
pdf:
	@echo "==> Dang bien dich $(PROJECT).tex bang $(COMPILER)..."
	latexmk -xelatex -synctex=1 -interaction=nonstopmode -file-line-error $(PROJECT).tex || \
	($(COMPILER) -interaction=nonstopmode $(PROJECT).tex && \
	 $(BIB_COMPILER) $(PROJECT) && \
	 $(COMPILER) -interaction=nonstopmode $(PROJECT).tex && \
	 $(COMPILER) -interaction=nonstopmode $(PROJECT).tex)
	@echo "==> Hoan tat! File PDF duoc tao tai: $(PROJECT).pdf"

# 3. Don dep cac file tam
clean:
	@echo "==> Dang don dep cac file trung gian..."
	rm -f *.aux *.bbl *.bcf *.blg *.fdb_latexmk *.fls *.log *.out *.run.xml *.synctex.gz *.toc *.lot *.lof
	rm -f chapters/*.aux frontmatter/*.aux appendices/*.aux config/*.aux sections/results/*.aux sections/discussion/*.aux

help:
	@echo "Cac lenh kha dung:"
	@echo "  make all      - Sinh so lieu va bien dich toan bo PDF"
	@echo "  make metrics  - Chi chay script Python sinh macro va bang"
	@echo "  make pdf      - Bien dich PDF tu ma nguon LaTeX hien tai"
	@echo "  make clean    - Xoa toan bo file tam sinh ra khi bien dich"
