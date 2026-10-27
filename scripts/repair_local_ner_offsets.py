import json
from pathlib import Path

from sqlalchemy import select

from src.models.database import SessionLocal
from src.models.documents import Document

db = SessionLocal()
try:
    repaired = 0
    unresolved = 0
    docs = list(db.scalars(select(Document).where(Document.productive_sector == "Agroforestry", Document.status == "ner")).all())
    for doc in docs:
        path = Path(doc.ner_path) if doc.ner_path else None
        if not path or not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("metadata", {}).get("provider") != "local-spacy-es_core_news_sm":
            continue
        source = Path(doc.cleaned_path).read_text(encoding="utf-8")
        changed = False
        for entity in payload.get("entities", []):
            start, end, text = entity["start"], entity["end"], entity["text"]
            if source[start:end] == text:
                continue
            if source[start:end].strip():
                entity["text"] = source[start:end]
                changed = True
                repaired += 1
                continue
            sentence = entity.get("context", "")
            local = sentence.find(text)
            if local < 0:
                unresolved += 1
                continue
            around = max(0, start - 200)
            candidate = source.find(text, around, min(len(source), start + len(sentence) + 200))
            if candidate < 0:
                unresolved += 1
                continue
            entity["start"] = candidate
            entity["end"] = candidate + len(text)
            changed = True
            repaired += 1
        if changed:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"repaired={repaired} unresolved={unresolved}")
finally:
    db.close()
