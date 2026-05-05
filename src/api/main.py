import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.models.models import Document, Entity, Graph, Metric, Relationship
from src.services.conversion import (
    ConversionError,
    UnsupportedFileTypeError,
    convert_document,
    save_converted_text,
)
from src.services.cleaning import (
    clean_text_layer1,
    clean_text_layer2,
    clean_text_layer2c,
    clean_text_layer3,
    save_cleaned_text,
)


RAW_DIR = Path("data/raw")
TXT_DIR = Path("data/processed/txt")
CLEANED_DIR = Path("data/processed/cleaned")


app = FastAPI(
    title="Semantic Classification API",
    description="API para procesamiento documental y análisis territorial",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    file_path: str
    file_type: str
    file_size_bytes: Optional[int]
    status: str
    uploaded_at: datetime
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")


class EntityResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    category: str
    text: str
    normalized_text: Optional[str]
    confidence: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    txt_path: str
    char_count: int


class CleanResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    cleaned_path: str
    original_char_count: int
    cleaned_char_count: int
    reduction_percentage: float
    dry_run: bool = False
    pages_removed: int = 0
    headers_removed_count: int = 0
    headers_detected: List[str] = []
    skipped_layer2_short_doc: bool = False
    sentences_rejoined: int = 0
    skipped_layer2c_short_doc: bool = False
    dot_leader_lines_removed: int = 0
    toc_blocks_removed: int = 0
    toc_lines_removed: int = 0
    skipped_layer3b_short_doc: bool = False


class BatchUploadResponse(BaseModel):
    document_id: uuid.UUID
    original_filename: str
    file_type: str
    upload_status: str
    process_status: Optional[str] = None
    txt_path: Optional[str] = None
    char_count: Optional[int] = None
    error: Optional[str] = None


@app.get("/")
def root():
    return {"message": "Semantic Classification API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    original_filename = file.filename or "unnamed"
    extension = Path(original_filename).suffix.lstrip(".").lower()
    if not extension:
        raise HTTPException(
            status_code=400, detail="File must have an extension to infer file_type"
        )

    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json.loads(metadata)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400, detail=f"metadata must be valid JSON: {e}"
            )

    document_id = uuid.uuid4()
    document_dir = RAW_DIR / str(document_id)
    document_dir.mkdir(parents=True, exist_ok=True)
    target_path = document_dir / original_filename

    contents = file.file.read()
    target_path.write_bytes(contents)

    db_document = Document(
        id=document_id,
        original_filename=original_filename,
        file_path=str(target_path),
        file_type=extension,
        file_size_bytes=len(contents),
        status="raw",
        metadata_=parsed_metadata,
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


@app.post(
    "/documents/batch",
    response_model=List[BatchUploadResponse],
    status_code=status.HTTP_201_CREATED,
)
def upload_documents_batch(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    results = []
    
    for file in files:
        original_filename = file.filename or "unnamed"
        extension = Path(original_filename).suffix.lstrip(".").lower()
        
        if not extension:
            results.append(
                BatchUploadResponse(
                    document_id=uuid.uuid4(),
                    original_filename=original_filename,
                    file_type="unknown",
                    upload_status="failed",
                    process_status=None,
                    error="File must have an extension to infer file_type",
                )
            )
            continue
        
        try:
            document_id = uuid.uuid4()
            document_dir = RAW_DIR / str(document_id)
            document_dir.mkdir(parents=True, exist_ok=True)
            target_path = document_dir / original_filename
            
            contents = file.file.read()
            target_path.write_bytes(contents)
            
            db_document = Document(
                id=document_id,
                original_filename=original_filename,
                file_path=str(target_path),
                file_type=extension,
                file_size_bytes=len(contents),
                status="raw",
                metadata_=None,
            )
            db.add(db_document)
            db.commit()
            
            source_path = Path(db_document.file_path)
            
            try:
                text = convert_document(str(source_path), db_document.file_type)
            except UnsupportedFileTypeError as e:
                db_document.status = "failed"
                db.commit()
                results.append(
                    BatchUploadResponse(
                        document_id=document_id,
                        original_filename=original_filename,
                        file_type=extension,
                        upload_status="success",
                        process_status="failed",
                        error=f"Unsupported file type: {e}",
                    )
                )
                continue
            except ConversionError as e:
                db_document.status = "failed"
                db.commit()
                results.append(
                    BatchUploadResponse(
                        document_id=document_id,
                        original_filename=original_filename,
                        file_type=extension,
                        upload_status="success",
                        process_status="failed",
                        error=f"Conversion error: {e}",
                    )
                )
                continue
            
            txt_path = TXT_DIR / f"{document_id}.txt"
            save_converted_text(text, str(txt_path))
            
            db_document.status = "converted"
            db.commit()
            
            results.append(
                BatchUploadResponse(
                    document_id=document_id,
                    original_filename=original_filename,
                    file_type=extension,
                    upload_status="success",
                    process_status="converted",
                    txt_path=str(txt_path),
                    char_count=len(text),
                )
            )
            
        except Exception as e:
            results.append(
                BatchUploadResponse(
                    document_id=uuid.uuid4(),
                    original_filename=original_filename,
                    file_type=extension if extension else "unknown",
                    upload_status="failed",
                    process_status=None,
                    error=str(e),
                )
            )
    
    return results


@app.get("/documents", response_model=List[DocumentResponse])
def list_documents(
    status_filter: Optional[str] = None, db: Session = Depends(get_db)
):
    query = db.query(Document)
    if status_filter:
        query = query.filter(Document.status == status_filter)
    return query.all()


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@app.post("/documents/{document_id}/process", response_model=ProcessResponse)
def process_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    source_path = Path(document.file_path)
    if not source_path.exists():
        document.status = "failed"
        db.commit()
        raise HTTPException(
            status_code=404, detail=f"Source file missing on disk: {source_path}"
        )

    try:
        text = convert_document(str(source_path), document.file_type)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except ConversionError as e:
        document.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

    txt_path = TXT_DIR / f"{document_id}.txt"
    save_converted_text(text, str(txt_path))

    document.status = "converted"
    db.commit()
    db.refresh(document)

    return ProcessResponse(
        document_id=document_id,
        status=document.status,
        txt_path=str(txt_path),
        char_count=len(text),
    )


@app.post("/documents/{document_id}/clean", response_model=CleanResponse)
def clean_document(
    document_id: uuid.UUID,
    dry_run: bool = False,
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    txt_path = TXT_DIR / f"{document_id}.txt"
    if not txt_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Converted text not found at {txt_path}. Run /process first.",
        )

    if document.status not in ("converted", "cleaned"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Document must be in 'converted' or 'cleaned' status to clean, "
                f"current: '{document.status}'"
            ),
        )

    try:
        original_text = txt_path.read_text(encoding="utf-8")
        text_after_l1, l1_metrics = clean_text_layer1(original_text)
        text_after_l2, l2_metrics = clean_text_layer2(text_after_l1)
        text_after_l2c, l2c_metrics = clean_text_layer2c(text_after_l2)
        final_text, l3_metrics = clean_text_layer3(text_after_l2c)
    except Exception as e:
        if not dry_run:
            document.status = "failed"
            db.commit()
        raise HTTPException(status_code=500, detail=f"Cleaning failed: {e}")

    original_count = l1_metrics["original_char_count"]
    cleaned_count = len(final_text)
    reduction = (
        (original_count - cleaned_count) / original_count if original_count > 0 else 0.0
    )
    rules_applied = {
        "layer1": l1_metrics["rules_applied"],
        "layer2": l2_metrics,
        "layer2c": l2c_metrics,
        "layer3": l3_metrics,
    }

    cleaned_path = CLEANED_DIR / f"{document_id}.txt"

    if dry_run:
        return CleanResponse(
            document_id=document_id,
            status=document.status,
            cleaned_path=str(cleaned_path),
            original_char_count=original_count,
            cleaned_char_count=cleaned_count,
            reduction_percentage=reduction,
            dry_run=True,
            pages_removed=l2_metrics["pages_removed"],
            headers_removed_count=l2_metrics["headers_removed_count"],
            headers_detected=l2_metrics["headers_detected"],
            skipped_layer2_short_doc=l2_metrics["skipped_layer2_short_doc"],
            sentences_rejoined=l2c_metrics["sentences_rejoined"],
            skipped_layer2c_short_doc=l2c_metrics["skipped_layer2c_short_doc"],
            dot_leader_lines_removed=l3_metrics["dot_leader_lines_removed"],
            toc_blocks_removed=l3_metrics["toc_blocks_removed"],
            toc_lines_removed=l3_metrics["toc_lines_removed"],
            skipped_layer3b_short_doc=l3_metrics["skipped_layer3b_short_doc"],
        )

    save_cleaned_text(final_text, str(cleaned_path))

    document.status = "cleaned"
    document.original_char_count = original_count
    document.cleaned_char_count = cleaned_count
    document.reduction_percentage = reduction
    document.cleaning_metadata = rules_applied
    db.commit()
    db.refresh(document)

    return CleanResponse(
        document_id=document_id,
        status=document.status,
        cleaned_path=str(cleaned_path),
        original_char_count=original_count,
        cleaned_char_count=cleaned_count,
        reduction_percentage=reduction,
        dry_run=False,
        pages_removed=l2_metrics["pages_removed"],
        headers_removed_count=l2_metrics["headers_removed_count"],
        headers_detected=l2_metrics["headers_detected"],
        skipped_layer2_short_doc=l2_metrics["skipped_layer2_short_doc"],
        sentences_rejoined=l2c_metrics["sentences_rejoined"],
        skipped_layer2c_short_doc=l2c_metrics["skipped_layer2c_short_doc"],
        dot_leader_lines_removed=l3_metrics["dot_leader_lines_removed"],
        toc_blocks_removed=l3_metrics["toc_blocks_removed"],
        toc_lines_removed=l3_metrics["toc_lines_removed"],
        skipped_layer3b_short_doc=l3_metrics["skipped_layer3b_short_doc"],
    )


@app.get("/entities", response_model=List[EntityResponse])
def list_entities(
    category_filter: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Entity)
    if category_filter:
        query = query.filter(Entity.category == category_filter)
    if document_id:
        query = query.filter(Entity.document_id == document_id)
    return query.all()
