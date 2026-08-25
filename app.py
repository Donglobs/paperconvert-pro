from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from pathlib import Path
import io, os, uuid, base64, re, json
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

try:
    import fitz
except ImportError:
    fitz = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
UPLOAD = Path("uploads")
UPLOAD.mkdir(exist_ok=True)

def preprocess(img):
    img = ImageOps.exif_transpose(img).convert("RGB")
    # normalize size for OCR without exploding memory
    max_side = 2600
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize((int(img.width*scale), int(img.height*scale)), Image.Resampling.LANCZOS)
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = gray.filter(ImageFilter.MedianFilter(size=3))
    return gray

def pdf_pages(data):
    if not fitz: return []
    doc = fitz.open(stream=data, filetype="pdf")
    out=[]
    for p in doc:
        pix=p.get_pixmap(matrix=fitz.Matrix(1.8,1.8), alpha=False)
        out.append(Image.frombytes("RGB",[pix.width,pix.height],pix.samples))
    return out

@app.route("/")
def index():
    return render_template("index.html")

@app.post("/api/export")
def export_doc():
    payload=request.get_json(force=True)
    fmt=payload.get("format","docx")
    title=(payload.get("title") or "Converted Document").strip()
    pages=payload.get("pages",[])
    if fmt=="docx":
        doc=Document()
        sec=doc.sections[0]
        sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.65)
        sec.left_margin=Inches(.75); sec.right_margin=Inches(.75)
        doc.add_heading(title, level=1)
        for i,p in enumerate(pages):
            text=p.get("text","").strip()
            if text:
                for para in re.split(r"\n\s*\n", text):
                    para=para.strip()
                    if not para: continue
                    lines=para.splitlines()
                    if len(lines)==1 and len(para)<90 and (para.isupper() or para.endswith(":")):
                        doc.add_heading(para, level=2)
                    else:
                        doc.add_paragraph(para)
            if i < len(pages)-1: doc.add_page_break()
        bio=io.BytesIO(); doc.save(bio); bio.seek(0)
        return send_file(bio, as_attachment=True, download_name=secure_filename(title)+".docx",
                         mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    # PDF
    bio=io.BytesIO()
    styles=getSampleStyleSheet()
    body=ParagraphStyle("Body", parent=styles["BodyText"], fontSize=10.5, leading=14, spaceAfter=8)
    heading=ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=14, leading=17, spaceBefore=6, spaceAfter=8)
    pdf=SimpleDocTemplate(bio,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=45,bottomMargin=45)
    story=[Paragraph(title, styles["Title"]), Spacer(1,12)]
    for i,p in enumerate(pages):
        text=p.get("text","").strip()
        for para in re.split(r"\n\s*\n", text):
            para=para.strip()
            if not para: continue
            safe=para.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br/>")
            if len(para)<90 and (para.isupper() or para.endswith(":")):
                story.append(Paragraph(safe,heading))
            else: story.append(Paragraph(safe,body))
        if i<len(pages)-1: story.append(PageBreak())
    pdf.build(story); bio.seek(0)
    return send_file(bio,as_attachment=True,download_name=secure_filename(title)+".pdf",mimetype="application/pdf")

@app.post("/api/pdf-info")
def pdf_info():
    f=request.files.get("file")
    if not f: return jsonify({"error":"No file"}),400
    data=f.read()
    if not fitz: return jsonify({"error":"PyMuPDF is not installed"}),500
    pages=pdf_pages(data)
    result=[]
    for img in pages:
        b=io.BytesIO(); img.save(b,"JPEG",quality=88)
        result.append("data:image/jpeg;base64,"+base64.b64encode(b.getvalue()).decode())
    return jsonify({"pages":result})

@app.post("/api/preprocess")
def api_preprocess():
    f=request.files.get("file")
    if not f: return jsonify({"error":"No file"}),400
    img=preprocess(Image.open(f.stream))
    b=io.BytesIO(); img.save(b,"JPEG",quality=90)
    return send_file(io.BytesIO(b.getvalue()),mimetype="image/jpeg")

if __name__=="__main__":
    app.run(host="0.0.0.0",port=5000,debug=True)
