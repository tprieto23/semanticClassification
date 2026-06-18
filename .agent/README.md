# Semantic Classification

API de clasificación semántica para análisis de documentos no estructurados.

## Objetivo

Procesar documentos (PDF, DOCX), extraer entidades relevantes y mapear relaciones para análisis territorial socioambiental.

## Cómo correr

```bash
# Levantar todo
docker compose up -d

# Migraciones
docker compose exec api alembic upgrade head

# Si hay cambios en modelos
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head

# API
http://localhost:8000/docs
```

## Stack

| Capa | Tecnología |
|------|-----------|
| API | FastAPI + Uvicorn |
| DB | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 |
| Migraciones | Alembic |
| Conversión PDF | **PyMuPDF** (fast path) + Docling OCR (fallback) |
| Conversión DOCX | Docling |
| Parseo MD | markdown-it-py |
| Reparación encoding | ftfy |
| Almacenamiento | s3/ (local, montado en Docker) |
| Contenedores | Docker + docker-compose |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/documents` | Subir archivo |
| POST | `/documents/batch` | Subir múltiples archivos |
| GET | `/documents` | Listar con filtros (status, file_type) |
| GET | `/documents/{id}` | Ver documento |
| DELETE | `/documents/{id}` | Eliminar documento |
| POST | `/documents/{id}/process` | Convertir a Markdown |
| POST | `/documents/process-batch` | Convertir todos en raw |
| POST | `/documents/{id}/clean` | Limpiar texto |
| POST | `/documents/clean-batch` | Limpiar todos en converted |
| POST | `/documents/{id}/revert` | Revertir al estado anterior |

## Estados del documento

| Estado | Significado |
|---|---|
| `raw` | Recién subido, sin convertir |
| `converted` | Convertido a .md |
| `cleaned` | Texto limpiado, listo para NER |

## Convenciones

- **Python:** snake_case para archivos, variables y funciones. PascalCase para clases.
- **Endpoints:** router fino, lógica en services, DB en models.
- **Storage:** `Storage.guardar(content, filename, target_dir)` recibe el directorio desde la capa de servicio.
- **Excepciones:** heredan de `DocumentoError(codigo_http)`, capturadas por handler global en `main.py`.
- **Commits:** solo cuando se pida explícitamente.
- **Variables de entorno:** `.env` (gitignored). `DATABASE_URL` es la única obligatoria.

## Dependencias del sistema (Dockerfile)

La imagen base `python:3.11-slim` requiere estos paquetes adicionales para Docling/OpenCV/PyMuPDF:

- `gcc` — compilación
- `libgl1` — OpenGL
- `libglib2.0-0` — GLib
- `libxcb1` — X11 protocol (requerido por OpenCV)
- `libxcb-shm0` — shared memory (X11)
- `libxcb-xfixes0` — X11 fixes extension
- `libxcb-xinerama0` — X11 multi-head extension
- `libglx-mesa0` — Mesa GLX (OpenGL)

## Reglas de trabajo

- **Autorización previa:** antes de cualquier edición de código, presentar el cambio propuesto y esperar autorización explícita. No modificar archivos sin visto bueno.

- **Python:** snake_case para archivos, variables y funciones. PascalCase para clases.
- **Endpoints:** router fino, lógica en services, DB en models.
- **Storage:** `Storage.guardar(content, filename, target_dir)` recibe el directorio desde la capa de servicio.
- **Excepciones:** heredan de `DocumentoError(codigo_http)`, capturadas por handler global en `main.py`.
- **Commits:** solo cuando se pida explícitamente.
- **Variables de entorno:** `.env` (gitignored). `DATABASE_URL` es la única obligatoria.
