# Session Context

## Sesión actual

**Fecha:** 2026-06-03 (sesión 18)

**Propósito:** Reset completo de `src/` y reorganización arquitectónica.

---

## Última sesión

**Fecha:** 2026-06-03 (sesión 18)

**Trabajado en:**
- Reset completo del código fuente (`src/`) preservando documentación, datos e infraestructura
- Reorganización de la API con arquitectura limpia (routers, schemas, deps)
- Centralización de configuración en `src/core/config.py`
- Refactor de `src/core/database.py` con lazy engine
- Reescritura de modelos SQLAlchemy compatibles con DB existente
- Servicios como stubs documentados listos para implementar

**Resumen de la sesión:**

### Motivación
La usuaria identificó que los endpoints y la configuración de la API estaban desorganizados y mal estructurados. Se decidió resetear `src/` completamente y reescribir con una arquitectura limpia.

### Qué se preservó
- `.agent/` — documentación del proyecto
- `data/` — archivos raw, processed (txt, cleaned, entities)
- `docker-compose.yml`, `Dockerfile`, `.dockerignore`
- `.env`, `requirements.txt`
- `migrations/`, `alembic.ini`
- `.gitignore`

### Nueva arquitectura

```
src/
├── api/
│   ├── main.py              # App factory + middleware + include routers
│   ├── deps.py              # Dependencias reutilizables (get_document_or_404, require_status)
│   ├── routers/
│   │   ├── documents.py     # CRUD documentos, upload, batch, process, clean
│   │   └── entities.py      # Listar/extraer entidades
│   └── schemas/
│       ├── common.py        # HealthResponse
│       ├── document.py      # DocumentResponse, ProcessResponse, CleanResponse, BatchUploadResponse
│       └── entity.py        # EntityResponse, ExtractEntitiesSummary
├── core/
│   ├── config.py            # Settings centralizado (DB, paths) con pydantic-settings
│   └── database.py          # Lazy engine, session, Base (DeclarativeBase), get_db
├── models/
│   └── models.py            # SQLAlchemy: Document, Entity, Relationship, Graph, Metric
├── services/
│   ├── conversion.py        # Stub: convert_document (PDF/DOCX), ConversionError, etc.
│   ├── cleaning.py          # Stub: clean_text_layer1..4 con métricas, save_cleaned_text
│   └── ner.py               # Stub: extract_entities, ExtractedEntity, normalize_entity_name
├── training/                # Vacío (scripts se reescribirán)
├── utils/                   # Vacío
└── visualization/           # Vacío
```

### Principios de diseño
1. **Routers por recurso** — separación clara de responsabilidades HTTP
2. **Endpoints delgados** — solo HTTP, delegan a servicios
3. **Schemas dedicados** — Pydantic models en archivos separados
4. **Dependencias reutilizables** — `get_document_or_404`, `require_status`
5. **Config centralizado** — `src/core/config.py` con paths y DB settings
6. **Lazy engine** — no intenta conectar a DB en tiempo de importación
7. **Stubs documentados** — cada servicio tiene sus TODOs explícitos

### Endpoints (todos funcionales)

| Método | Ruta | Router |
|--------|------|--------|
| GET | `/` | main |
| GET | `/health` | main |
| POST | `/documents` | documents |
| GET | `/documents` | documents |
| POST | `/documents/batch` | documents |
| GET | `/documents/{id}` | documents |
| POST | `/documents/{id}/process` | documents |
| POST | `/documents/{id}/clean?dry_run=` | documents |
| GET | `/entities` | entities |
| POST | `/entities/extract/{id}` | entities |

### Verificación
- ✅ Todas las importaciones compilan
- ✅ API arranca con uvicorn
- ✅ OpenAPI docs generados correctamente
- ✅ Migraciones Alembic compatibles (`env.py` importa `Base` y `settings`)
- ✅ DB schema compatible con migraciones existentes

### Próximos pasos
1. Implementar `src/services/cleaning.py` Capa 1 (ftfy + normalización)
2. Implementar `src/services/ner.py` con modelo XLM-RoBERTa fine-tuned
3. Iterar capa por capa de limpieza (2, 2c, 3, 4)
4. Re-implementar scripts de training (`prepare_ner_dataset.py`, `train_ner_xlm.py`)
