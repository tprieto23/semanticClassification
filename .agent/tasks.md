# Tareas

## Objetivo 1: Ingesta de documentos ✅

- [x] `src/config.py` — settings sin credenciales
- [x] `src/models/database.py` — conexión DB
- [x] `src/models/documents.py` — ORM Document
- [x] `src/models/documents_repo.py` — CRUD + actualizar_status + leer_por_status
- [x] `src/models/storage.py` — guardar, leer, eliminar en s3/archivosCrudos
- [x] `src/services/documents.py` — DocumentService + excepciones
- [x] `src/api/routers/documents.py` — POST, GET, GET/{id}, DELETE, POST /batch
- [x] `src/api/schemas/documents.py` — DocumentRead, DocumentListResponse, BatchProcess*
- [x] `src/api/main.py` — FastAPI + exception handler

## Objetivo 2: Conversión a Markdown ✅

- [x] `markitdown[pdf,docx]` en requirements.txt
- [x] `s3/archivosConvertidos/` — destino de archivos .md
- [x] `config.py` — STORAGE_CONVERTED
- [x] `models/documents.py` — columna converted_path
- [x] `services/documents.py` — DocumentService.convertir() + convertir_varios()
- [x] `api/routers/documents.py` — POST /documents/{id}/process + /process-batch
- [x] Probado: 200, 404, 409

### Refactors del objetivo 2
- [x] `models/storage.py` — unificado `guardar(content, filename, target_dir)`, eliminado `guardar_convertido`
- [x] `services/documents.py` — absorbido `ConversionService.convertir()` → `DocumentService.convertir()`
- [x] `api/routers/documents.py` — absorbido `conversion.py`, renombrado `ingesta.py` → `documents.py`
- [x] `api/schemas/documents.py` — renombrado de `ingesta.py`
- [x] Eliminados `services/conversion.py`, `api/routers/conversion.py`, `api/routers/ingesta.py`, `api/schemas/ingesta.py`

## Objetivo 3: Limpieza de textos ✅

- [x] `src/services/cleaning.py` — CleaningService.limpiar()
  - [x] ftfy.fix_text() → reparación de encoding
  - [x] markdown_it.MarkdownIt() → parseo MD → extracción texto plano
  - [x] regex → eliminación de URLs, emails, teléfonos
  - [x] normalización whitespace + .lower()
- [x] `models/documents.py` — columna cleaned_path
- [x] `models/storage.py` — método leer()
- [x] `services/documents.py` — DocumentService.limpiar() + limpiar_varios() + DocumentoNoConvertido
- [x] `api/routers/documents.py` — POST /documents/{id}/clean + /clean-batch
- [x] `config.py` — DATA_CLEANED = s3/archivosLimpiados (borrado DATA_TXT)
- [x] Probado: 200, 404, 409, 500 (archivo no encontrado)
- [x] `POST /documents/{id}/revert-clean` — revierte limpieza, borra .txt, status → converted

## Objetivo 4: Extracción de entidades ⏳

- [ ] Modelo XLM-RoBERTa fine-tuned (ya existe en models/)
- [ ] Servicio NER
- [ ] Endpoint `POST /documents/{id}/extract-entities`

## Objetivos 5–8: Vectores, matrices, grafos, métricas ⏳

- [ ] Sin definir
