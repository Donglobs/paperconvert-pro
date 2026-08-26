# PaperConvert Pro v7

Server-side OCR upgrade focused on photographed paper documents.

## v7 highlights
- Four-corner perspective correction and image cleanup
- Server-side RapidOCR (ONNX Runtime) instead of browser-only Tesseract OCR
- Multiple cleaned image variants are recognized and scored
- Word boxes are grouped into reading-order lines
- Confidence and selected OCR pass are shown in the review screen
- Editable review before Word/PDF export
- Multi-page image/PDF import and page ordering

## Run locally
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://localhost:5000.

## Deployment
This version is configured for Render with Python 3.11 and one Gunicorn worker to keep memory usage lower on the free instance. The first OCR request may take longer while the ONNX model initializes.
