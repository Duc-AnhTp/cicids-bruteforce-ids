#!/usr/bin/env bash
set -e

echo "==> Sinh so lieu macro va bang LaTeX..."
python scripts/report/generate_latex_registry.py

echo "==> Bien dich bao cao bang latexmk..."
cd reports
latexmk -xelatex -synctex=1 -interaction=nonstopmode -file-line-error main.tex

echo "==> Hoan tat! File PDF da duoc tao tai: reports/main.pdf"
