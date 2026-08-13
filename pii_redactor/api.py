import os
import tempfile
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from detectors import RegexDetector, NERDetector, ContextDetector
from core.resolver import EntityResolver
from core.replacement import DeterministicReplacer
from document.processor import DocumentProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PII Redactor API",
    description="API for detecting and redacting PII from DOCX documents.",
    version="1.0.0"
)

# Minimal CORS: only allow if necessary, currently wildcard for broad API access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup_temp_dir(tmpdir: tempfile.TemporaryDirectory):
    """Cleanup the temporary directory after the response is sent."""
    try:
        tmpdir.cleanup()
        logger.info(f"Cleaned up temporary directory: {tmpdir.name}")
    except Exception as e:
        logger.error(f"Failed to clean up temporary directory {tmpdir.name}: {e}")

@app.get("/health", summary="Health Check")
async def health_check():
    return {"status": "ok", "service": "PII Redactor"}

@app.post(
    "/redact",
    summary="Redact PII from a DOCX file",
    description="""
    Upload a DOCX file to be redacted.
    The system detects configured PII categories (e.g., PERSON, COMPANY, PHONE, EMAIL, etc.) 
    and replaces them with deterministic synthetic values while preserving document structure.
    Returns the redacted DOCX file.
    """
)
async def redact_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
        
    if not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=415, detail="Unsupported file type. Only .docx files are allowed.")
        
    # Read the file content into memory to avoid relying on the filename
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(status_code=500, detail="Failed to read the uploaded file.")
        
    # Create a secure temporary directory
    tmpdir = tempfile.TemporaryDirectory()
    
    input_path = os.path.join(tmpdir.name, "upload.docx")
    output_path = os.path.join(tmpdir.name, "Redacted_Prospectus.docx")
    
    try:
        with open(input_path, "wb") as f:
            f.write(content)
            
        logger.info("Initializing redaction pipeline...")
        detectors = [RegexDetector(), NERDetector(), ContextDetector()]
        resolver = EntityResolver()
        replacer = DeterministicReplacer()
        processor = DocumentProcessor(detectors, resolver, replacer)
        
        logger.info("Processing document...")
        stats = processor.process(input_path, output_path)
        logger.info(f"Processing completed. Stats: {stats}")
        
    except Exception as e:
        logger.error(f"Error during document processing: {e}")
        tmpdir.cleanup()
        raise HTTPException(status_code=500, detail="An error occurred while processing the document.")

    # Enqueue cleanup task to run after the response is sent
    background_tasks.add_task(cleanup_temp_dir, tmpdir)
    
    return FileResponse(
        path=output_path,
        filename="Redacted_Prospectus.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
