from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import io, base64, re, json
from PIL import Image, ImageOps
import numpy as np
import cv2
from docx import Document
from docx.shared import Inches, Pt
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

def pil_from_upload(f):
    return ImageOps.exif_transpose(Image.open(f.stream).convert('RGB'))

def order_points(pts):
    rect=np.zeros((4,2),dtype='float32')
    s=pts.sum(axis=1); d=np.diff(pts,axis=1).ravel()
    rect[0]=pts[np.argmin(s)]; rect[2]=pts[np.argmax(s)]
    rect[1]=pts[np.argmin(d)]; rect[3]=pts[np.argmax(d)]
    return rect

def four_point_transform(img, pts):
    rect=order_points(pts); tl,tr,br,bl=rect
    w1=np.linalg.norm(br-bl); w2=np.linalg.norm(tr-tl); h1=np.linalg.norm(tr-br); h2=np.linalg.norm(tl-bl)
    W=max(int(max(w1,w2)), 100); H=max(int(max(h1,h2)),100)
    dst=np.array([[0,0],[W-1,0],[W-1,H-1],[0,H-1]],dtype='float32')
    M=cv2.getPerspectiveTransform(rect,dst)
    return cv2.warpPerspective(img,M,(W,H))

def auto_crop(img):
    h,w=img.shape[:2]
    scale=900/max(h,w) if max(h,w)>900 else 1
    small=cv2.resize(img,None,fx=scale,fy=scale) if scale!=1 else img.copy()
    gray=cv2.cvtColor(small,cv2.COLOR_BGR2GRAY)
    blur=cv2.GaussianBlur(gray,(5,5),0)
    edges=cv2.Canny(blur,50,150)
    contours,_=cv2.findContours(edges,cv2.RETR_LIST,cv2.CHAIN_APPROX_SIMPLE)
    best=None; best_area=0
    area0=small.shape[0]*small.shape[1]
    for c in sorted(contours,key=cv2.contourArea,reverse=True)[:30]:
        peri=cv2.arcLength(c,True); approx=cv2.approxPolyDP(c,.02*peri,True); area=cv2.contourArea(c)
        if len(approx)==4 and area>area0*.25 and area>best_area:
            best=approx.reshape(4,2).astype('float32')/scale; best_area=area
    return four_point_transform(img,best) if best is not None else img

def deskew(img):
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    bw=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    coords=np.column_stack(np.where(bw>0))
    if len(coords)<100: return img
    angle=cv2.minAreaRect(coords)[-1]
    angle=-(90+angle) if angle < -45 else -angle
    if abs(angle)<0.25: return img
    h,w=img.shape[:2]; M=cv2.getRotationMatrix2D((w/2,h/2),angle,1.0)
    return cv2.warpAffine(img,M,(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)

def perspective_from_points(img, pts):
    pts=np.asarray(pts,dtype='float32').reshape(4,2)
    return four_point_transform(img, pts)

def remove_shadows(gray):
    # Estimate the page's uneven lighting and divide it out. This is much better
    # for phone photos than a simple global threshold.
    kernel=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(51,51))
    background=cv2.morphologyEx(gray,cv2.MORPH_CLOSE,kernel)
    background=cv2.GaussianBlur(background,(0,0),15)
    normalized=cv2.divide(gray,background,scale=255)
    return cv2.normalize(normalized,None,0,255,cv2.NORM_MINMAX)

def enhance(img, pts=None):
    if pts is not None:
        img=perspective_from_points(img,pts)
    else:
        img=auto_crop(img)
    img=deskew(img)
    gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)
    gray=remove_shadows(gray)
    clahe=cv2.createCLAHE(clipLimit=2.0,tileGridSize=(8,8)); gray=clahe.apply(gray)
    gray=cv2.fastNlMeansDenoising(gray,None,7,7,21)
    sharp=cv2.addWeighted(gray,1.45,cv2.GaussianBlur(gray,(0,0),1.1),-0.45,0)
    bw=cv2.adaptiveThreshold(sharp,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,41,13)
    # Remove tiny specks while preserving characters.
    bw=cv2.medianBlur(bw,3)
    return sharp,bw

def data_url(img, quality=92):
    b=io.BytesIO(); Image.fromarray(cv2.cvtColor(img,cv2.COLOR_BGR2RGB)).save(b,'JPEG',quality=quality)
    return 'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode()

@app.route('/')
def index(): return render_template('index.html')

@app.post('/api/process-image')
def process_image():
    f=request.files.get('file')
    if not f: return jsonify({'error':'No file'}),400
    try:
        img=np.array(pil_from_upload(f))[:,:,::-1].copy()
        pts=None
        raw=request.form.get('points')
        if raw:
            pts=json.loads(raw)
        enhanced,bw=enhance(img,pts)
        return jsonify({'enhanced':data_url(enhanced),'threshold':data_url(cv2.cvtColor(bw,cv2.COLOR_GRAY2BGR))})
    except Exception as e:
        return jsonify({'error':str(e)}),500

@app.post('/api/export')
def export_doc():
    payload=request.get_json(force=True); fmt=payload.get('format','docx'); title=(payload.get('title') or 'Converted Document').strip(); pages=payload.get('pages',[])
    if fmt=='docx':
        doc=Document(); sec=doc.sections[0]; sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.65); sec.left_margin=Inches(.75); sec.right_margin=Inches(.75)
        styles=doc.styles; styles['Normal'].font.name='Arial'; styles['Normal'].font.size=Pt(10.5)
        doc.add_heading(title,1)
        for i,p in enumerate(pages):
            text=(p.get('text') or '').strip()
            if text:
                lines=[x.rstrip() for x in text.splitlines()]
                # simple table detection: 2+ consecutive rows containing 2+ whitespace-separated cells
                j=0
                while j<len(lines):
                    line=lines[j].strip()
                    if not line: j+=1; continue
                    if j+1<len(lines) and len(re.split(r'\s{2,}|\t',line))>=2:
                        rows=[]; k=j
                        while k<len(lines) and lines[k].strip() and len(re.split(r'\s{2,}|\t',lines[k].strip()))>=2:
                            rows.append([c.strip() for c in re.split(r'\s{2,}|\t',lines[k].strip())]); k+=1
                        if len(rows)>=2:
                            cols=max(map(len,rows)); rows=[r+['']*(cols-len(r)) for r in rows]
                            t=doc.add_table(rows=0,cols=cols); t.style='Table Grid'
                            for r in rows:
                                cells=t.add_row().cells
                                for c,v in zip(cells,r): c.text=v
                            j=k; continue
                    if len(line)<90 and (line.isupper() or line.endswith(':')): doc.add_heading(line,2)
                    else: doc.add_paragraph(line)
                    j+=1
            if i<len(pages)-1: doc.add_page_break()
        bio=io.BytesIO(); doc.save(bio); bio.seek(0)
        return send_file(bio,as_attachment=True,download_name=secure_filename(title)+'.docx',mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    bio=io.BytesIO(); styles=getSampleStyleSheet(); body=ParagraphStyle('Body',parent=styles['BodyText'],fontSize=10.5,leading=14,spaceAfter=7); heading=ParagraphStyle('H',parent=styles['Heading2'],fontSize=14,leading=17,spaceBefore=5,spaceAfter=7)
    pdf=SimpleDocTemplate(bio,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=45,bottomMargin=45); story=[Paragraph(title,styles['Title']),Spacer(1,12)]
    for i,p in enumerate(pages):
        text=(p.get('text') or '').strip()
        for para in re.split(r'\n\s*\n',text):
            para=para.strip()
            if not para: continue
            safe=para.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('\n','<br/>')
            story.append(Paragraph(safe,heading if len(para)<90 and (para.isupper() or para.endswith(':')) else body))
        if i<len(pages)-1: story.append(PageBreak())
    pdf.build(story); bio.seek(0); return send_file(bio,as_attachment=True,download_name=secure_filename(title)+'.pdf',mimetype='application/pdf')

if __name__=='__main__': app.run(host='0.0.0.0',port=5000,debug=True)
