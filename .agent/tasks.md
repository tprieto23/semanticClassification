# Tareas

## Objetivo 1: Ingesta de documentos ✅

- [x] `src/config.py` — settings sin credenciales
- [x] `src/models/database.py` — conexión DB
- [x] `src/models/documents.py` — ORM Document
- [x] `src/models/documents_repo.py` — CRUD puro
- [x] `src/models/storage.py` — archivos en s3/archivosCrudos
- [x] `src/services/documents.py` — DocumentService + excepciones
- [x] `src/api/routers/ingesta.py` — 4 endpoints
- [x] `src/api/schemas/ingesta.py` — Pydantic schemas
- [x] `src/api/main.py` — FastAPI app
- [x] Alembic autogenerate funcional
- [x] Docker con s3 montado como volumen

## Objetivo 2: Conversión a texto plano ⏳

- [ ] `src/models/conversion.py` — ORM para seguimiento de conversión (si aplica)
- [ ] `src/services/conversion.py` — PyMuPDF (PDF) + python-docx (DOCX) → TXT
- [ ] Endpoint `POST /documents/{id}/process`
- [ ] Guardar TXT en `data/processed/txt/`
- [ ] Actualizar `documents.status = 'converted'`

## Objetivo 3: Limpieza de textos ⏳

- [ ] Servicio de limpieza por capas
- [ ] Endpoint `POST /documents/{id}/clean`

## Objetivo 4: Extracción de entidades ⏳

- [ ] Modelo XLM-RoBERTa fine-tuned (ya existe en models/)
- [ ] Servicio NER
- [ ] Endpoint `POST /documents/{id}/extract-entities`

## Objetivos 5–8: Vectores, matrices, grafos, métricas ⏳

- [ ] Sin definir
