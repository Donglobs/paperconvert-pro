# PaperConvert Pro

A local web app for converting scanned paper documents into editable Word/PDF files.

## Features
- Image and camera import
- Multi-page ordering
- PDF page import
- Browser OCR with Tesseract.js
- English / Filipino / combined language selection
- Image preprocessing
- Editable OCR review
- Word and PDF export
- Responsive UI

## Run
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

Open http://localhost:5000

## Notes
The OCR language data is loaded by Tesseract.js in the browser. An internet connection is needed on first use.
