import os
import re
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from docx import Document
import pytesseract
from pdf2image import convert_from_bytes
from io import BytesIO

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
    """
    Clean text to ensure it is a single line with symbols spaced out properly.
    Jo aapne bola — left to right reading, 1 line me.
    """
    # Replace newlines and multiple spaces by single space
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)
    
    # Add spaces around certain symbols (optional, can customize)
    symbols = ['/', '|', '-', '•']
    for sym in symbols:
        text = re.sub(rf'\s*{re.escape(sym)}\s*', f' {sym} ', text)
    
    return text.strip()

async def extract_text_from_docx(file: UploadFile) -> str:
    """
    Extracts text from Word file (.docx), reading paragraphs and tables
    but concatenating all text into a single line (left-to-right).
    """
    content = await file.read()
    file_stream = BytesIO(content)
    doc = Document(file_stream)

    full_text = []

    # Extract paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())

    # Extract tables row-wise, concatenate cell texts row-wise with space
    for table in doc.tables:
        for row in table.rows:
            row_text = ' '.join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                full_text.append(row_text)

    # Join all text pieces with space (single line)
    text_single_line = ' '.join(full_text)
    return clean_text_single_line(text_single_line)

async def extract_text_from_pdf(file: UploadFile) -> str:
    """
    Extract text from PDF using OCR always.
    Converts each PDF page to image and applies Tesseract OCR.
    """
    content = await file.read()
    images = convert_from_bytes(content)

    extracted_text = []
    for image in images:
        # You can customize Tesseract config as needed
        custom_config = r'--psm 4'
        page_text = pytesseract.image_to_string(image, config=custom_config)
        if page_text.strip():
            extracted_text.append(page_text.strip())

    # Join extracted text from all pages into single line text
    text_single_line = ' '.join(extracted_text)
    return clean_text_single_line(text_single_line)

@app.post("/upload/")
async def upload_cv(file: UploadFile = File(...)):
    filename = file.filename.lower()
    if filename.endswith(".docx"):
        text = await extract_text_from_docx(file)
    elif filename.endswith(".pdf"):
        text = await extract_text_from_pdf(file)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload .docx or .pdf")

    # Return the extracted cleaned text as JSON response
    return JSONResponse({"extracted_text": text})

@app.get("/")
async def root():
    return {"message": "Welcome to CVFormatic AI Backend"}

