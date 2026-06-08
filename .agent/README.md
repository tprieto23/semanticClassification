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
| Conversión | markitdown (PDF, DOCX → MD) |
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
| POST | `/documents/{id}/revert-clean` | Revertir limpieza → converted |

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
