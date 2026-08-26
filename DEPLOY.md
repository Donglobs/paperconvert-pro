# PaperConvert Pro v7 deployment

1. Replace the files in `Donglbs/paperconvert-pro` with this package.
2. Commit to `main`.
3. Push to GitHub.
4. Render auto-deploys.

Render settings:
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --workers 1 --threads 2 --timeout 180`
- Python: 3.11.11 (runtime.txt)
- Health check: `/api/health`

If the free Render instance runs out of memory while importing the OCR runtime, upgrade the instance or move OCR to a dedicated worker/API.
