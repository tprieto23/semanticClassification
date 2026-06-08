from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from src.api.schemas.documents import BatchProcessResponse, DocumentListResponse, DocumentRead
from src.services.documents import DocumentService, get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload(
    file: Annotated[UploadFile, File()],
    metadata: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    return DocumentService.cargar_documento(db, file, metadata)


@router.post("/batch", response_model=list[DocumentRead], status_code=status.HTTP_201_CREATED)
def upload_batch(
    files: Annotated[list[UploadFile], File()],
    metadata: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
):
    return DocumentService.cargar_documentos(db, files, metadata)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    file_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
):
    filas, total = DocumentService.leer_todos(db, skip, limit, file_type, status)
    return DocumentListResponse(
        items=[DocumentRead.model_validate(r) for r in filas],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = DocumentService.leer_uno(db, str(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")
    return doc


@router.post("/{document_id}/process", status_code=status.HTTP_200_OK)
def process(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    DocumentService.convertir(db, str(document_id))


@router.post("/process-batch", response_model=BatchProcessResponse)
def process_batch(
    db: Session = Depends(get_db),
):
    resultado = DocumentService.convertir_varios(db)
    return BatchProcessResponse(**resultado)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = DocumentService.leer_uno(db, str(document_id))
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento {document_id} no encontrado")
    DocumentService.eliminar(db, doc)
