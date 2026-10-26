"""Piloto NER sobre un .txt real; conserva evidencia sin escribir en la DB.

Uso: .venv/bin/python scripts/validate_ner_document.py texto.txt --output data/output/ner_pilot/run
Añadir --prepare-only genera la entrada y el manifiesto sin llamar al proveedor.
"""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from anthropic.types import Message

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Settings exige la URL aunque este piloto no crea conexiones a bases de datos.
os.environ.setdefault("DATABASE_URL", "sqlite://")

from src.categories import ACTIVE_CATEGORIES
from src.config import settings
from src.services import ner


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document-title", default="")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--resume-from", type=Path, help="Reutiliza respuestas reales guardadas de una ejecución compatible")
    args = parser.parse_args()
    if args.source.suffix.lower() != ".txt":
        parser.error("La fuente debe ser un .txt limpio")
    source_bytes = args.source.read_bytes()
    text = source_bytes.decode("utf-8")
    if not text.strip():
        parser.error("El texto está vacío")
    # Cada ejecución tiene un destino propio para conservar los resultados anteriores.
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "source.txt").write_bytes(source_bytes)
    inputs = [json.loads(ner._construir_json_entrada(
        ner._segmentar_oraciones(chunk, offset), args.source.stem, args.document_title
    )) for chunk, offset in ner._partir_por_parrafos(text, settings.NER_MAX_CHUNK_LEN)]
    write_json(args.output / "inputs.json", inputs)
    files = [str(settings.NER_CODEBOOK_PATH), "src/categories.py", "src/services/ner.py",
             str(settings.NER_PROMPT_PATH),
             "scripts/validate_ner_document.py"]
    manifest = {
        "status": "prepared", "created_at": datetime.now(timezone.utc).isoformat(),
        "source": str(args.source), "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "document_id": args.source.stem, "characters": len(text),
        "model": settings.ANTHROPIC_MODEL, "prompt_strategy": "codebook-single-prompt", "chunks": len(inputs),
        "sentences": sum(len(i["sentences"]) for i in inputs),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "file_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files},
    }
    write_json(args.output / "manifest.json", manifest)
    if args.prepare_only:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("Falta configurar ANTHROPIC_API_KEY")

    records = []
    warnings = []
    saved = {}
    if args.resume_from:
        previous = json.loads((args.resume_from / "manifest.json").read_text())
        assert previous["source_sha256"] == manifest["source_sha256"]
        assert previous["model"] == manifest["model"]
        assert previous.get("prompt_strategy") == manifest["prompt_strategy"], "No se pueden reutilizar respuestas de otra estrategia de prompt"
        assert json.loads((args.resume_from / "inputs.json").read_text()) == inputs
        for name in files:
            if name.startswith("data/") or name in {"src/categories.py", str(settings.NER_CODEBOOK_PATH), str(settings.NER_PROMPT_PATH)}:
                assert previous["file_sha256"][name] == manifest["file_sha256"][name]
        for record in json.loads((args.resume_from / "provider_responses.json").read_text()):
            saved[tuple(record["sentence_ids"])] = record["response"]
        manifest["resumed_from"] = str(args.resume_from)

    class CaptureWarnings(logging.Handler):
        def emit(self, record):
            warnings.append(record.getMessage())

    client = ner.get_anthropic_client().with_options(timeout=90, max_retries=0)

    def create(**request):
        target = json.loads(request["messages"][0]["content"].split("<target_input>")[1].split("</target_input>")[0])
        ids = [s["sentence_id"] for s in target["sentences"]]
        previous_response = saved.pop(tuple(ids), None)
        reused = previous_response is not None
        response = Message.model_validate(previous_response) if reused else client.messages.create(**request)
        records.append({"sentence_ids": ids, "reused": reused, "response": response.model_dump(mode="json")})
        # Guarda cada respuesta antes de parsearla, incluso si una posterior falla.
        write_json(args.output / "provider_responses.json", records)
        print(f"Respuesta {len(records)} {'reutilizada' if reused else 'recibida'} ({ids[0]})", flush=True)
        return response

    handler = CaptureWarnings(level=logging.WARNING)
    ner.logger.addHandler(handler)
    try:
        with patch.object(ner, "get_anthropic_client", return_value=SimpleNamespace(
            messages=SimpleNamespace(create=create)
        )):
            entities = ner.extraer_entidades(text, args.source.stem, args.document_title)
        sentence_map = {s["sentence_id"]: s["text"] for i in inputs for s in i["sentences"]}
        for entity in entities:
            assert entity["category"] in ACTIVE_CATEGORIES
            assert text[entity["start"]:entity["end"]] == entity["text"]
            assert entity["context"] == sentence_map[entity["sentence_id"]]
        write_json(args.output / "entities.json", {"document_id": args.source.stem, "entities": entities})
        final_records = list({tuple(record["sentence_ids"]): record for record in records}.values())
        received = sum(len(block["input"].get("annotations", []))
                       for record in final_records for block in record["response"]["content"]
                       if block.get("type") == "tool_use" and block.get("name") == ner.NER_TOOL_NAME)
        assert all(block["input"].get("document_id") == args.source.stem
                   for record in final_records for block in record["response"]["content"]
                   if block.get("type") == "tool_use" and block.get("name") == ner.NER_TOOL_NAME)
        manifest.update(status="extracted_requires_review", annotations_received=received,
                        mentions_retained=len(entities), warnings=warnings,
                        correction_retries=len(records) - len(final_records),
                        real_provider_calls=sum(not record["reused"] for record in records),
                        usage={key: sum(record["response"]["usage"].get(key, 0) for record in records)
                               for key in ("input_tokens", "output_tokens")},
                        category_counts={label: sum(e["category"] == label for e in entities)
                                         for label in sorted(ACTIVE_CATEGORIES)})
        lines = ["# Revisión del piloto NER", "", "La extracción requiere revisión de todas las oraciones.", ""]
        for sentence_id, sentence_text in sentence_map.items():
            lines.extend([f"## {sentence_id}", "", sentence_text, ""])
            lines.extend(f"- `{e['category']}`: {e['text']} ({e['ambiguity']}; {e['start']}:{e['end']})"
                         for e in entities if e["sentence_id"] == sentence_id)
            lines.extend(["", "Revisión: pendiente.", ""])
        (args.output / "review.md").write_text("\n".join(lines), encoding="utf-8")
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, warnings=warnings)
        if isinstance(exc, (RuntimeError, AssertionError)):
            manifest["error"] = str(exc)
        # No incluir configuraciones ni credenciales en mensajes de error.
        print(f"Piloto fallido: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    finally:
        ner.logger.removeHandler(handler)
        write_json(args.output / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
