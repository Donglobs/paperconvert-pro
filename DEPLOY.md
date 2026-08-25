# Deploy PaperConvert Pro

## Easiest: Render

1. Create a GitHub repository and upload this project.
2. Go to Render and create a new Web Service.
3. Connect the GitHub repository.
4. Render will use `render.yaml`, or set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`
5. Deploy.
6. Open the generated `onrender.com` URL.

## Docker

Build:
`docker build -t paperconvert-pro .`

Run:
`docker run -p 5000:5000 paperconvert-pro`

## Important production notes

This build is suitable as an MVP deployment. For a public production service, add authentication, persistent object storage, rate limiting, CSRF protection, job queues, usage limits, and a server-side OCR provider if you want stronger OCR and layout reconstruction.
