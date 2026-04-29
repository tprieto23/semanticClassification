from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid

from src.core.database import get_db
from src.models.models import Document, Entity, Relationship, Graph, Metric

app = FastAPI(
    title="Semantic Classification API",
    description="API para procesamiento documental y análisis territorial",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DocumentCreate(BaseModel):
    original_filename: str
    file_type: str
    file_size_bytes: Optional[int] = None
    metadata: Optional[dict] = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str
    file_type: str
    file_size_bytes: Optional[int]
    status: str
    uploaded_at: datetime
    metadata: Optional[dict]

    class Config:
        from_attributes = True


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


@app.get("/")
def root():
    return {"message": "Semantic Classification API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(document: DocumentCreate, db: Session = Depends(get_db)):
    db_document = Document(
        original_filename=document.original_filename,
        file_path=f"data/raw/{document.original_filename}",
        file_type=document.file_type,
        file_size_bytes=document.file_size_bytes,
        status="raw",
        metadata_=document.metadata
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document


@app.get("/documents", response_model=List[DocumentResponse])
def list_documents(status_filter: Optional[str] = None, db: Session = Depends(get_db)):
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


@app.get("/entities", response_model=List[EntityResponse])
def list_entities(
    category_filter: Optional[str] = None,
    document_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Entity)
    if category_filter:
        query = query.filter(Entity.category == category_filter)
    if document_id:
        query = query.filter(Entity.document_id == document_id)
    return query.all()
