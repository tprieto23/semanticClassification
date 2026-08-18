from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.api.schemas.documents import (
    BatchProcessResponse,
    DocumentLanguageUpdate,
    DocumentListResponse,
    DocumentRead,
    IncubatorNumber,
    SetLanguageBatchRequest,
    SetLanguageBatchResponse,
)
from src.api.schemas.entities import (
    EntityOut,
    ExtractEntitiesResponse,
    FuzzyMatchingResponse,
    MatchedEntityOut,
)
from src.services.documents import DocumentService, get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload(
    file: Annotated[UploadFile, File()],
    incubator_number: Annotated[IncubatorNumber, Form()],
    metadata: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form(min_length=2, max_length=10)] = None,
    db: Session = Depends(get_db),
):
    language_limpio = language.lower().strip() if language else None
    return DocumentService.cargar_documento(
        db, file, int(incubator_number), metadata, language_limpio
    )


@router.post(
    "/batch", response_model=list[DocumentRead], status_code=status.HTTP_201_CREATED
)
def upload_batch(
    files: Annotated[list[UploadFile], File()],
    incubator_number: Annotated[IncubatorNumber, Form()],
    metadata: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form(min_length=2, max_length=10)] = None,
    db: Session = Depends(get_db),
):
    language_limpio = language.lower().strip() if language else None
    return DocumentService.cargar_documentos(
        db, files, int(incubator_number), metadata, language_limpio
    )


@router.get("", response_model=DocumentListResponse)
def list_documents(
    db: Session = Depends(get_db),
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    file_type: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    incubator_number: Annotated[int | None, Query(ge=1, le=8)] = None,
    language: Annotated[str | None, Query(min_length=2, max_length=10)] = None,
):
    language_limpio = language.lower().strip() if language else None
    filas, total = DocumentService.leer_todos(
        db, skip, limit, file_type, status, incubator_number, language_limpio
    )
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
        raise HTTPException(
            status_code=404, detail=f"Documento {document_id} no encontrado"
        )
    return doc


@router.patch("/{document_id}/language", response_model=DocumentRead)
def update_document_language(
    document_id: UUID,
    body: DocumentLanguageUpdate,
    db: Session = Depends(get_db),
):
    doc = DocumentService.actualizar_language(db, str(document_id), body.language)
    return doc


@router.post("/set-language-batch", response_model=SetLanguageBatchResponse)
def set_language_batch(
    body: SetLanguageBatchRequest,
    db: Session = Depends(get_db),
):
    resultado = DocumentService.actualizar_language_varios(
        db, [str(doc_id) for doc_id in body.document_ids], body.language
    )
    return SetLanguageBatchResponse(
        updated=[UUID(doc_id) for doc_id in resultado["processed"]],
        errors=[BatchProcessError(**e) for e in resultado["errors"]],
    )


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


@router.post("/{document_id}/clean", status_code=status.HTTP_200_OK)
def clean(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    DocumentService.limpiar(db, str(document_id))


@router.post("/clean-batch", response_model=BatchProcessResponse)
def clean_batch(
    db: Session = Depends(get_db),
):
    resultado = DocumentService.limpiar_varios(db)
    return BatchProcessResponse(**resultado)


@router.post("/{document_id}/revert", status_code=status.HTTP_200_OK)
def revert(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    DocumentService.revertir(db, str(document_id))


@router.post("/{document_id}/extract-entities", response_model=ExtractEntitiesResponse)
def extract_entities(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    entidades = DocumentService.extraer_entidades_de_documento(db, str(document_id))
    return ExtractEntitiesResponse(
        document_id=str(document_id),
        entities=[EntityOut(**e) for e in entidades],
    )


@router.post("/extract-entities-batch", response_model=BatchProcessResponse)
def extract_entities_batch(
    db: Session = Depends(get_db),
):
    resultado = DocumentService.extraer_entidades_de_varios(db)
    return BatchProcessResponse(**resultado)


@router.post(
    "/{document_id}/fuzzy-matching",
    response_model=FuzzyMatchingResponse,
    summary="Resolución canónica de entidades",
    description=(
        "Analiza conjuntamente las menciones NER del documento, resuelve variantes "
        "canónicas y persiste la evidencia de cada decisión."
    ),
)
def fuzzy_matching(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    entidades = DocumentService.preparar_fuzzy_matching(db, str(document_id))
    return FuzzyMatchingResponse(
        document_id=str(document_id),
        entities=[MatchedEntityOut(**e) for e in entidades],
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    doc = DocumentService.leer_uno(db, str(document_id))
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Documento {document_id} no encontrado"
        )
    DocumentService.eliminar(db, doc)
