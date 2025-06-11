import os
import re
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import pytesseract
from pdf2image import convert_from_bytes
from io import BytesIO
from docxtpl import DocxTemplate

app = FastAPI()

# CORS middleware add karna yahin, app banate hi
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development ke liye sabko allow, production me apne domain ka URL daal dena
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set your Tesseract executable path here (adjust if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def clean_text_single_line(text: str) -> str:
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    symbols = ['/', '|', '-', '•']
    for sym in symbols:
        text = re.sub(rf'\s*{re.escape(sym)}\s*', f' {sym} ', text)
    return text.strip()

async def extract_text_from_docx(file: UploadFile) -> str:
    content = await file.read()
    file_stream = BytesIO(content)
    doc = Document(file_stream)
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    for table in doc.tables:
        for row in table.rows:
            row_text = ' '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                full_text.append(row_text)
    text_single_line = ' '.join(full_text)
    return clean_text_single_line(text_single_line)

async def extract_text_from_pdf(file: UploadFile) -> str:
    content = await file.read()
    images = convert_from_bytes(content)
    extracted_text = []
    for image in images:
        custom_config = r'--psm 4'
        page_text = pytesseract.image_to_string(image, config=custom_config)
        if page_text.strip():
            extracted_text.append(page_text.strip())
    text_single_line = ' '.join(extracted_text)
    return clean_text_single_line(text_single_line)

def parse_extracted_text(text: str) -> dict:
    """
    Basic parser to extract name, nationality, and location from text.
    """
    result = {
        "FULL_NAME": "Candidate",
        "NATIONALITY": "N/A",
        "LOCATION": "N/A"
    }

    match_nationality = re.search(r'Nationality[:\-]?\s*(\w+)', text, re.IGNORECASE)
    if match_nationality:
        result["NATIONALITY"] = match_nationality.group(1)

    match_location = re.search(r'Location[:\-]?\s*([\w\s]+)', text, re.IGNORECASE)
    if match_location:
        result["LOCATION"] = match_location.group(1).strip()

    words = text.strip().split()
    if len(words) >= 2:
        result["FULL_NAME"] = f"{words[0]} {words[1]}"
    elif words:
        result["FULL_NAME"] = words[0]

    return result

def generate_cv(context: dict) -> str:
    try:
        template_path = os.path.join("templates", "uk_danos_compliance.docx")
        doc = DocxTemplate(template_path)
        doc.render(context)
        full_name = context.get("FULL_NAME", "Candidate").strip()
        safe_name = re.sub(r'[^\w\s-]', '', full_name).replace(' ', '_')
        output_filename = f"{safe_name}.docx"
        output_path = os.path.join("generated_cvs", output_filename)
        os.makedirs("generated_cvs", exist_ok=True)
        doc.save(output_path)
        return output_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV generation failed: {str(e)}")

@app.post("/upload/")
async def upload_cv(file: UploadFile = File(...)):
    try:
        filename = file.filename.lower()
        if filename.endswith(".docx"):
            text = await extract_text_from_docx(file)
        elif filename.endswith(".pdf"):
            text = await extract_text_from_pdf(file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .docx or .pdf")
        return JSONResponse({"extracted_text": text})
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/generate-cv/")
async def generate_cv_endpoint(context: dict):
    extracted_text = context.get("extracted_text", "")
    parsed_fields = parse_extracted_text(extracted_text)
    context.update(parsed_fields)
    output_path = generate_cv(context)
    return JSONResponse({
        "message": "CV generated successfully!",
        "output_file": output_path
    })

@app.get("/download-cv/")
async def download_cv(filename: str):
    file_path = os.path.join("generated_cvs", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )

@app.get("/")
async def root():
    return {"message": "Welcome to CVFormatic AI Backend"}
