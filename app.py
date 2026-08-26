from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image
from io import BytesIO
import base64, re
import cv2
import numpy as np
from docx import Document
from docx.shared import Inches
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=50*1024*1024

def b64img(img, quality=94):
    ok, enc=cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok: raise RuntimeError('Could not encode image')
    return 'data:image/jpeg;base64,'+base64.b64encode(enc.tobytes()).decode()

def decode_data_url(data):
    if ',' in data: data=data.split(',',1)[1]
    raw=base64.b64decode(data)
    arr=np.frombuffer(raw,np.uint8)
    img=cv2.imdecode(arr,cv2.IMREAD_COLOR)
    if img is None: raise ValueError('Invalid image')
    return img

def order_points(pts):
    pts=np.asarray(pts,dtype=np.float32).reshape(4,2)
    s=pts.sum(axis=1); d=np.diff(pts,axis=1).reshape(-1)
    return np.array([pts[np.argmin(s)],pts[np.argmin(d)],pts[np.argmax(s)],pts[np.argmax(d)]],dtype=np.float32)

def clean_page(img, points):
    h,w=img.shape[:2]
    pts=order_points(points)
    tl,tr,br,bl=pts
    widthA=np.linalg.norm(br-bl); widthB=np.linalg.norm(tr-tl)
    heightA=np.linalg.norm(tr-br); heightB=np.linalg.norm(tl-bl)
    W=max(800,int(max(widthA,widthB)))
    H=max(1100,int(max(heightA,heightB)))
    W=min(W,3200); H=min(H,4200)
    dst=np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]],dtype=np.float32)
    M=cv2.getPerspectiveTransform(pts,dst)
    warped=cv2.warpPerspective(img,M,(W,H),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    gray=cv2.cvtColor(warped,cv2.COLOR_BGR2GRAY)
    # Upscale modestly for small print.
    if gray.shape[0] < 1800:
        scale=1800/gray.shape[0]
        gray=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    # Normalize uneven lighting using a large background estimate.
    bg=cv2.GaussianBlur(gray,(0,0),31)
    norm=cv2.divide(gray,bg,scale=170)
    norm=cv2.normalize(norm,None,0,255,cv2.NORM_MINMAX)
    # Gentle denoise + sharpen.
    den=cv2.fastNlMeansDenoising(norm,None,7,7,21)
    sharp=cv2.addWeighted(den,1.35,cv2.GaussianBlur(den,(0,0),1.2),-0.35,0)
    clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)).apply(sharp)
    # Two OCR-friendly variants.
    adaptive=cv2.adaptiveThreshold(clahe,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,41,11)
    otsu=cv2.threshold(clahe,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    # Remove tiny specks without destroying letters.
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(2,2))
    adaptive=cv2.morphologyEx(adaptive,cv2.MORPH_OPEN,kernel)
    otsu=cv2.morphologyEx(otsu,cv2.MORPH_OPEN,kernel)
    return {
      'preview':b64img(sharp),
      'gray':b64img(sharp),
      'adaptive':b64img(adaptive),
      'otsu':b64img(otsu),
      'width':int(sharp.shape[1]),'height':int(sharp.shape[0])
    }

@app.get('/')
def home(): return render_template('index.html')

@app.post('/api/clean')
def api_clean():
    data=request.get_json(force=True)
    img=decode_data_url(data.get('image',''))
    pts=data.get('points')
    if not isinstance(pts,list) or len(pts)!=4: return jsonify({'error':'Four corner points are required'}),400
    try: result=clean_page(img,pts)
    except Exception as e: return jsonify({'error':str(e)}),400
    return jsonify(result)

@app.post('/api/export')
def export():
    data=request.get_json(force=True); fmt=data.get('format','docx'); title=(data.get('title') or 'Converted Document').strip(); pages=data.get('pages',[])
    if fmt=='docx':
        doc=Document(); sec=doc.sections[0]; sec.top_margin=Inches(.6); sec.bottom_margin=Inches(.6); sec.left_margin=Inches(.7); sec.right_margin=Inches(.7)
        doc.add_heading(title,0)
        for idx,p in enumerate(pages):
            text=(p.get('text') or '').strip()
            lines=[x.strip() for x in text.splitlines() if x.strip()]
            for line in lines:
                if re.match(r'^\d+[.)]\s+',line): doc.add_paragraph(re.sub(r'^\d+[.)]\s+','',line),style='List Number')
                elif len(line)<90 and (line.isupper() or line.endswith(':')): doc.add_heading(line,level=2)
                else: doc.add_paragraph(line)
            if idx<len(pages)-1: doc.add_page_break()
        bio=BytesIO(); doc.save(bio); bio.seek(0)
        return send_file(bio,as_attachment=True,download_name=title+'.docx',mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    styles=getSampleStyleSheet(); body=ParagraphStyle('body',parent=styles['BodyText'],fontSize=10.5,leading=14,spaceAfter=7); head=ParagraphStyle('head',parent=styles['Heading2'],fontSize=14,leading=17,spaceAfter=7)
    bio=BytesIO(); pdf=SimpleDocTemplate(bio,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42); story=[Paragraph(title,styles['Title']),Spacer(1,10)]
    for idx,p in enumerate(pages):
        for line in (p.get('text') or '').splitlines():
            line=line.strip()
            if not line: continue
            safe=line.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            story.append(Paragraph(safe,head if (line.isupper() or line.endswith(':')) and len(line)<90 else body))
        if idx<len(pages)-1: story.append(PageBreak())
    pdf.build(story); bio.seek(0); return send_file(bio,as_attachment=True,download_name=title+'.pdf',mimetype='application/pdf')

if __name__=='__main__': app.run(host='0.0.0.0',port=5000,debug=True)
