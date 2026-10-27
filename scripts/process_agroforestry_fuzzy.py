import json
from pathlib import Path

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.documents import Document
from src.services.documents import DocumentService

db = SessionLocal()
try:
    docs = list(db.scalars(select(Document).where(Document.productive_sector == "Agroforestry", Document.status == "ner").order_by(Document.uploaded_at, Document.id)).all())
    targets = []
    for doc in docs:
        path = Path(doc.ner_path) if doc.ner_path else None
        if not path or not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("metadata", {}).get("provider") == "local-spacy-es_core_news_sm":
            targets.append(doc)
    print(f"targets={len(targets)}", flush=True)
    completed = 0
    errors = []
    for index, doc in enumerate(targets, 1):
        try:
            entities = DocumentService.preparar_fuzzy_matching(db, str(doc.id))
            methods = {}
            for entity in entities:
                methods[entity["match_type"]] = methods.get(entity["match_type"], 0) + 1
            completed += 1
            print(f"{index}/{len(targets)} OK {doc.id} mentions={len(entities)} methods={methods}", flush=True)
        except Exception as exc:
            db.rollback()
            errors.append((str(doc.id), type(exc).__name__, str(exc)))
            print(f"{index}/{len(targets)} ERROR {doc.id} {type(exc).__name__}: {str(exc)[:250]}", flush=True)
    print(f"completed={completed} errors={len(errors)}", flush=True)
    for doc_id, error_type, message in errors:
        print(f"FAILED {doc_id} {error_type}: {message[:300]}", flush=True)
finally:
    db.close()
