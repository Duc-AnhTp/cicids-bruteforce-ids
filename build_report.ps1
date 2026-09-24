Write-Host "==> Sinh so lieu macro va bang LaTeX..." -ForegroundColor Cyan
python scripts/report/generate_latex_registry.py

Write-Host "==> Bien dich bao cao bang latexmk..." -ForegroundColor Cyan
Set-Location reports
latexmk -xelatex -synctex=1 -interaction=nonstopmode -file-line-error main.tex
Set-Location ..

Write-Host "==> Hoan tat! File PDF tai: reports/main.pdf" -ForegroundColor Green
