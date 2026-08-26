# PaperConvert Pro v6

OCR-focused document scanner. Uses manual page corners, perspective correction, lighting normalization, multiple OCR-friendly image variants, and multiple Tesseract.js page segmentation passes.

## Run
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py

Open http://localhost:5000

## v6.1 fix
Preserves full-resolution source during perspective correction and handles empty OCR results safely.
