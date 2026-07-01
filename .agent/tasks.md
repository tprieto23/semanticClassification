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

- [x] ~~`markitdown[pdf,docx]` en requirements.txt~~ → reemplazado por `docling`
- [x] `s3/archivosConvertidos/` — destino de archivos .md
- [x] `config.py` — STORAGE_CONVERTED
- [x] `models/documents.py` — columna converted_path
- [x] `services/documents.py` — DocumentService.convertir() con Docling + convertir_varios()
- [x] `api/routers/documents.py` — POST /documents/{id}/process + /process-batch
- [x] Dockerfile — `libgl1`, `libglib2.0-0`, `libxcb1` para OpenCV/Docling
- [x] Probado: 200, 404, 409

### Refactors del objetivo 2
- [x] `models/storage.py` — unificado `guardar(content, filename, target_dir)`, eliminado `guardar_convertido`
- [x] `services/documents.py` — absorbido `ConversionService.convertir()` → `DocumentService.convertir()`
- [x] `api/routers/documents.py` — absorbido `conversion.py`, renombrado `ingesta.py` → `documents.py`
- [x] `api/schemas/documents.py` — renombrado de `ingesta.py`
- [x] Eliminados `services/conversion.py`, `api/routers/conversion.py`, `api/routers/ingesta.py`, `api/schemas/ingesta.py`

### Mejora de rendimiento PDF — Jun 12 2026
- [x] `requirements.txt` — agregado `PyMuPDF`
- [x] `Dockerfile` — agregados `libxcb-shm0`, `libxcb-xfixes0`, `libxcb-xinerama0`, `libglx-mesa0`
- [x] `src/services/pdf_converter.py` — **nuevo** convertidor híbrido:
  - Fast path: PyMuPDF para PDFs nativos (~0.1-1s por documento)
  - Fallback: Docling OCR para PDFs escaneados (~60-90s por documento)
- [x] `src/services/documents.py` — `convertir()` reutiliza `PdfConverter` (lazy)
- [x] Batch de 27 PDFs convertidos en **28 segundos** (vs ~2-3 horas con Docling puro)

### Refactor de simplificación — feat/reedireccion2
- [x] `src/services/pdf_converter.py` — API simplificada: `convertir(file_path: str) -> str`
- [x] `src/services/pdf_converter.py` — código muerto eliminado (`_extraer_imagenes_pymupdf`, bloques comentados, imports no usados)
- [x] `src/services/pdf_converter.py` — TODO documentado para extracción futura de texto en imágenes `.png` dentro de PDFs nativos
- [x] `src/services/documents.py` — adaptado a la nueva firma del convertidor
- [ ] Extracción de imágenes como archivos separados — **postergado** (se mantiene la columna `images_path` en DB/schema por si se retoma)

## Objetivo 3: Limpieza de textos 🔧

- [x] `src/services/cleaning.py` — CleaningService.structuralCleaning()
  - [x] ftfy.fix_text() → reparación de encoding
  - [x] markdown_it.MarkdownIt("commonmark") → parseo MD → extracción texto plano
  - [x] regex → eliminación de URLs, emails, teléfonos
  - [x] eliminación de placeholders de imágenes (`<!-- Start/End of picture text -->`)
  - [x] eliminación conservadora de metadata de autoria (autores, facilitadores, revisores, directores, etc.)
  - [x] eliminación de direcciones postales, correos y teléfonos
  - [x] eliminación de notas legales, copyright y créditos de fotografía/diagramación
  - [x] eliminación de índices/tablas de contenido
  - [x] eliminación de tablas Markdown (agenda, anexos tabulados)
  - [x] eliminación de headers de anexos
  - [x] eliminación de prefijos de numeración de secciones y subsecciones
  - [x] eliminación de items/viñetas sueltos
  - [x] eliminación de números de página y líneas muy cortas
  - [x] deduplicación de párrafos consecutivos
  - [x] normalización whitespace (_MULTISPACE + _SPACES) **sin** `.lower()`
- [ ] `linguisticCleaning()` — **stub (pass)**. Plan: spaCy + langdetect para tokenización por oraciones y filtrado de ruido (portadas, referencias)
- [x] `models/documents.py` — columna cleaned_path
- [x] `models/storage.py` — método leer()
- [x] `services/documents.py` — DocumentService.limpiar() + limpiar_varios() + DocumentoNoConvertido
- [x] `api/routers/documents.py` — POST /documents/{id}/clean + /clean-batch
- [x] `config.py` — DATA_CLEANED = s3/archivosLimpiados (borrado DATA_TXT)
- [x] Probado: 200, 404, 409, 500 (archivo no encontrado)
- [x] `POST /documents/{id}/revert` — revierte al estado anterior (cleaned→converted, converted→raw)

## Objetivo 4: Extracción de entidades ⏳

- [ ] Modelo XLM-RoBERTa fine-tuned (ya existe en models/)
- [ ] Servicio NER
- [ ] Endpoint `POST /documents/{id}/extract-entities`

## Objetivos 5–8: Vectores, matrices, grafos, métricas ⏳

- [ ] Sin definir

## Status de sesión — Jun 11 2026

**Stack actual:**
- Conversión: Docling (DocumentConverter sin opciones de pipeline, sin OCR)
- Dockerfile: `libgl1`, `libglib2.0-0`, `libxcb1` para OpenCV
- 29 documentos en DB, todos en `raw` (salvo 1 en `converted`)

**Pendiente inmediato:**
- Implementar `linguisticCleaning()` con spaCy + langdetect (actualmente es `pass`)
- Definir si `limpiar()` guarda un solo `.txt` o múltiples chunks

**Siguiente objetivo:**
- Objetivo 4: Extracción de entidades (NER con XLM-RoBERTa)
