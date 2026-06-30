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
- [x] `src/config.py` — agregado `STORAGE_IMAGES = s3/imagenesExtraidas`
- [x] `src/models/documents.py` — agregada columna `images_path`
- [x] `src/models/storage.py` — agregado `eliminar_directorio()`
- [x] `src/api/schemas/documents.py` — agregado `images_path`
- [x] `src/services/documents.py` — `convertir()` reutiliza `PdfConverter` (lazy), `revertir()` elimina directorio de imágenes
- [x] Migración alembic: `cfe959221fc7` — add images_path to documents
- [x] Batch de 27 PDFs convertidos en **28 segundos** (vs ~2-3 horas con Docling puro)

## Objetivo 3: Limpieza de textos 🔧

- [x] `src/services/cleaning.py` — CleaningService.structuralCleaning()
  - [x] ftfy.fix_text() → reparación de encoding
  - [x] markdown_it.MarkdownIt() (default, no "commonmark") → parseo MD → extracción texto plano
  - [x] regex → eliminación de URLs, emails, teléfonos
  - [x] normalización whitespace (_MULTISPACE + _SPACES) + .lower()
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

## Refactor convertidor — solo texto, sin imágenes — Jun 29 2026

**Motivo:** la extracción de imágenes guardaba archivos innecesarios para el análisis.
El foco es producir Markdown **bien estructurado** (títulos, secciones, párrafos), no imágenes.

**Hallazgos de diagnóstico:**
- Corpus actual: **27 PDFs + 2 DOCX**. Los 27 PDFs son **100% texto nativo** (0 escaneados).
- El camino de OCR de Docling nunca se disparaba con el corpus actual.
- El camino rápido viejo (`page.get_text()`) producía texto **plano** sin estructura → raíz de la queja de "desorden".
- 24 de 29 documentos en DB ya tenían `images_path` (convertidos con el código viejo).

**Decisiones de diseño:**
- PDF nativo → **`pymupdf4llm`** (Markdown estructurado, `write_images=False`).
- PDF escaneado → **Docling + OCR conservado** para documentos futuros (hoy no hay ninguno, queda "dormido").
- DOCX → Docling.
- Imágenes: se eliminan por completo (extracción, `images_path`, `STORAGE_IMAGES`).
- Ruido editorial (créditos, números de página) → se filtra en la **etapa de limpieza**, no en la conversión.

**Plan por pasos:**
- [x] **Paso 1** — convertidor + dependencias
  - [x] `src/services/pdf_converter.py` reescrito (158 → ~70 líneas, sin imágenes, usa `pymupdf4llm`)
  - [x] `src/services/documents.py` — `convertir()` y `revertir()` sin manejo de `images_dir`
  - [x] `requirements.txt` — agregado `pymupdf4llm==0.0.17` (versión liviana, sin `onnxruntime`)
  - [x] Probado: smoke test convierte PDF nativo → MD estructurado OK
- [ ] **Paso 2** — sacar `images_path` del modelo de datos
  - [ ] `models/documents.py` — quitar columna `images_path`
  - [ ] `config.py` — quitar `STORAGE_IMAGES`
  - [ ] `api/schemas/documents.py` — quitar `images_path`
  - [ ] `models/storage.py` — quitar `eliminar_directorio()`
  - [ ] migración Alembic — `DROP COLUMN images_path`
- [ ] **Paso 3** — borrar `s3/imagenesExtraidas/` y `s3/test_images/`
- [ ] **Paso 4** — rebuild de la imagen + revertir los 24 docs viejos a `raw` y reconvertir con el nuevo convertidor (iterar calidad del MD)
- [ ] **Paso 5** — actualizar `.agent/` (README, architecture)

**Pendiente posterior (Objetivo 3):**
- Implementar `linguisticCleaning()` con spaCy + langdetect (actualmente es `pass`)
- Definir si `limpiar()` guarda un solo `.txt` o múltiples chunks
- Conflicto a resolver: `structuralCleaning()` hace `.lower()` al final, pero el criterio del proyecto es **no** bajar a minúsculas (las mayúsculas son señal para NER)

**Siguiente objetivo:**
- Objetivo 4: Extracción de entidades (NER con XLM-RoBERTa)
