# PaperConvert Pro v5

OCR-focused document scanner for photographed paper.

### v5 changes
- No risky automatic quadrilateral crop before OCR.
- User-controlled 4-corner perspective correction.
- Conservative Hough-based deskew.
- Upscaling for small printed text.
- Shadow normalization, CLAHE, denoising and sharpening.
- OCR runs on two cleaned variants and keeps the higher-confidence result.
- OCR is blocked until the page has been cleaned, preventing raw photos from being sent directly to Tesseract.

Run with `pip install -r requirements.txt` and `gunicorn app:app`.
