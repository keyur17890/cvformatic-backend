from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to CVFormatic!"}

@app.post("/upload/")
async def upload_cv(file: UploadFile = File(...)):
    content = await file.read()
    # Abhi basic placeholder logic rakha hai.
    return JSONResponse({"filename": file.filename, "size": len(content)})
