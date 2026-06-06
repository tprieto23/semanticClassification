# Semantic Classification

API de clasificación semántica para análisis de documentos no estructurados.

## Objetivo

Procesar documentos (PDF, DOCX), extraer entidades relevantes y mapear relaciones para análisis territorial socioambiental.

## Cómo correr

```bash
# Levantar todo
docker compose up -d

# Migraciones
docker exec sc_api alembic upgrade head

# Si hay cambios en modelos
docker exec sc_api alembic revision --autogenerate -m "descripcion"
docker exec sc_api alembic upgrade head

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
| Almacenamiento | s3/archivosCrudos (local, montado en Docker) |
| Contenedores | Docker + docker-compose |

## Convenciones

- **Python:** snake_case para archivos, variables y funciones. PascalCase para clases.
- **Endpoints:** router fino (3 líneas máximo), lógica en services, DB en models.
- **Naming de archivos:** mismo dominio, misma carpeta. Ej: `ingesta.py` en api/routers/, services/ y models/.
- **Commits:** solo cuando se pida explícitamente.
- **Variables de entorno:** `.env` (gitignored). `DATABASE_URL` es la única obligatoria.
