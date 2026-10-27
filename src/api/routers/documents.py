from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.api.schemas.documents import (
    BatchProcessError,
    BatchProcessResponse,
    DocumentLanguageUpdate,
    DocumentListResponse,
    DocumentRead,
    DocumentType,
    IncubatorNumber,
    ProductiveSector,
    SetLanguageBatchRequest,
    SetLanguageBatchResponse,
)
from src.api.schemas.entities import (
    EntityOut,
    ExtractEntitiesResponse,
    FuzzyMatchingResponse,
    MatchedEntityOut,
)
from src.api.schemas.network import NetworkBuildResponse, TypedNetworkBuildResponse
from src.services.documents import DocumentService, get_db
from src.services.network import NetworkService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def upload(
    file: Annotated[UploadFile, File()],
    incubator_number: Annotated[IncubatorNumber, Form()],
    year: Annotated[int | None, Form(ge=1990, le=2030)] = None,
    productive_sector: Annotated[ProductiveSector | None, Form()] = None,
    document_type: Annotated[str | None, Form(max_length=50)] = None,
    metadata: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form(min_length=2, max_length=10)] = None,
    db: Session = Depends(get_db),
):
    language_limpio = language.lower().strip() if language else None
    return DocumentService.cargar_documento(
        db,
        file,
        int(incubator_number),
        year,
        productive_sector.value if productive_sector else None,
        document_type,
        metadata,
        language_limpio,
    )


@router.post(
    "/batch", response_model=list[DocumentRead], status_code=status.HTTP_201_CREATED
)
def upload_batch(
    files: Annotated[list[UploadFile], File()],
    incubator_number: Annotated[IncubatorNumber, Form()],
    year: Annotated[int | None, Form(ge=1990, le=2030)] = None,
    productive_sector: Annotated[ProductiveSector | None, Form()] = None,
    document_type: Annotated[str | None, Form(max_length=50)] = None,
    metadata: Annotated[str | None, Form()] = None,
    language: Annotated[str | None, Form(min_length=2, max_length=10)] = None,
    db: Session = Depends(get_db),
):
    language_limpio = language.lower().strip() if language else None
    return DocumentService.cargar_documentos(
        db,
        files,
        int(incubator_number),
        year,
        productive_sector.value if productive_sector else None,
        document_type,
        metadata,
        language_limpio,
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


@router.patch(
    "/{document_id}/classification",
    response_model=DocumentRead,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "year": {
                                "type": "integer",
                                "minimum": 1990,
                                "maximum": 2030,
                            },
                            "productive_sector": {
                                "type": "string",
                                "enum": ["Agroforestry"],
                            },
                            "document_type": {
                                "type": "string",
                                "maxLength": 50,
                                "description": "Tipo, fuente, autor o revista según el catálogo del corpus.",
                            },
                        },
                    }
                }
            }
        }
    },
)
def update_document_classification(
    document_id: UUID,
    year: Annotated[int | None, Form(ge=1990, le=2030)] = None,
    productive_sector: Annotated[ProductiveSector | None, Form()] = None,
    document_type: Annotated[str | None, Form(max_length=50)] = None,
    db: Session = Depends(get_db),
):
    return DocumentService.actualizar_clasificacion(
        db,
        str(document_id),
        year,
        productive_sector.value if productive_sector else None,
        document_type,
    )


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


@router.post("/{document_id}/network", response_model=NetworkBuildResponse)
def build_document_network(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    minimum_weight: Annotated[int, Query(ge=1)] = 1,
    include_isolates: bool = True,
):
    payload = NetworkService.build(
        db,
        document_id=str(document_id),
        minimum_weight=minimum_weight,
        include_isolates=include_isolates,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


@router.post(
    "/{document_id}/network/projections/{projection_id}",
    response_model=TypedNetworkBuildResponse,
)
def build_document_typed_projection(
    document_id: UUID,
    projection_id: str,
    request: Request,
    db: Session = Depends(get_db),
    minimum_weight: Annotated[int, Query(ge=1)] = 1,
    include_isolates: bool = True,
):
    payload = NetworkService.build_projection(
        db,
        projection_id,
        document_id=str(document_id),
        minimum_weight=minimum_weight,
        include_isolates=include_isolates,
    )
    return NetworkService.with_public_urls(payload, str(request.base_url))


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
