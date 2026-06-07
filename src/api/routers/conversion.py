from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.services.conversion import (
    ConversionService,
    DocumentoNoEncontrado,
    DocumentoYaConvertido,
)
from src.services.documents import get_db

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/{document_id}/process", status_code=status.HTTP_200_OK)
def process(
    document_id: UUID,
    db: Session = Depends(get_db),
):
    try:
        ConversionService.convertir(db, str(document_id))
    except DocumentoNoEncontrado as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DocumentoYaConvertido as e:
        raise HTTPException(status_code=409, detail=str(e))
