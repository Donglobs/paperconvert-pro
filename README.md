# PaperConvert Pro v3

Smart paper-to-document web app with automatic image enhancement before OCR.

## New in v3
- Automatic document edge detection and perspective crop
- Deskew/rotation correction
- Contrast enhancement, denoising and sharpening
- Adaptive threshold OCR image
- Per-page Enhance control
- OCR confidence display
- Improved Word table reconstruction for tab/space-separated rows
- Production Gunicorn/Render configuration

## Run
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python app.py

Open http://localhost:5000
