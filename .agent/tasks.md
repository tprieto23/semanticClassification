# Tareas

## Objetivo 1: Ingesta de documentos ✅

- [x] `src/config.py` — settings sin credenciales
- [x] `src/models/database.py` — conexión DB
- [x] `src/models/documents.py` — ORM Document
- [x] `src/models/documents_repo.py` — CRUD + actualizar_status
- [x] `src/models/storage.py` — guardar/eliminar en s3/archivosCrudos
- [x] `src/services/documents.py` — DocumentService + excepciones
- [x] `src/api/routers/ingesta.py` — POST, GET, GET/{id}, DELETE, POST /batch
- [x] `src/api/schemas/ingesta.py` — DocumentRead, DocumentListResponse
- [x] `src/api/main.py` — FastAPI + exception handler

## Objetivo 2: Conversión a Markdown ✅

- [x] Reemplazo PyMuPDF + python-docx → `markitdown[pdf,docx]`
- [x] `s3/archivosConvertidos/` — destino de archivos .md
- [x] `config.py` — STORAGE_CONVERTED
- [x] `models/storage.py` — guardar_convertido()
- [x] `models/documents_repo.py` — actualizar_status()
- [x] `services/conversion.py` — ConversionService.convertir()
- [x] `api/routers/conversion.py` — POST /documents/{id}/process
- [x] Probado: 200, 404, 409

## Objetivo 3: Limpieza de textos ⏳

- [ ] Servicio de limpieza por capas
- [ ] Endpoint `POST /documents/{id}/clean`

## Objetivo 4: Extracción de entidades ⏳

- [ ] Modelo XLM-RoBERTa fine-tuned (ya existe en models/)
- [ ] Servicio NER
- [ ] Endpoint `POST /documents/{id}/extract-entities`

## Objetivos 5–8: Vectores, matrices, grafos, métricas ⏳

- [ ] Sin definir
