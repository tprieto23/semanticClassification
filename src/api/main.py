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


RAW_DIR = Path("data/raw")
TXT_DIR = Path("data/processed/txt")


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
