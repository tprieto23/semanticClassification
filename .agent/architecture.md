# Architecture

## Arquitectura general

Sistema de procesamiento documental para análisis territorial socioambiental con perspectiva crítica, feminista y de género.

**Flujo principal:**
```
Documentos no estructurados → Conversión → Limpieza → Clasificación → Vectores → Grafos → Métricas → API → Dashboard
```

## Estructura del proyecto

```
.
├── .agent/                 # Documentación del proyecto
├── data/
│   ├── raw/                # Archivos originales (no modificar)
│   ├── processed/
│   │   ├── txt/            # Archivos convertidos a texto plano
│   │   ├── cleaned/        # Textos depurados
│   │   └── entities/       # Entidades extraídas (JSON)
│   ├── output/
│   │   ├── vectors/        # Representaciones vectoriales (.npy)
│   │   ├── matrices/       # Matrices de adyacencia (.parquet)
│   │   ├── graphs/         # Grafos de conocimiento (.graphml)
│   │   └── metrics/        # Métricas calculadas
│   └── temp/               # Archivos temporales
├── src/
│   ├── api/                # FastAPI — routers, schemas, deps
│   │   ├── main.py         # App factory, middleware, router includes
│   │   ├── deps.py         # Dependencias reutilizables
│   │   ├── routers/        # Endpoints por recurso
│   │   │   ├── documents.py
│   │   │   └── entities.py
│   │   └── schemas/        # Pydantic models
│   │       ├── common.py
│   │       ├── document.py
│   │       └── entity.py
│   ├── core/               # Configuración y DB
│   │   ├── config.py       # Settings (paths, DB creds)
│   │   └── database.py     # Engine, session, Base, get_db
│   ├── models/             # ORM SQLAlchemy
│   │   └── models.py       # Document, Entity, Relationship, Graph, Metric
│   ├── services/           # Lógica de negocio del pipeline
│   │   ├── conversion.py   # PDF/DOCX → texto plano
│   │   ├── cleaning.py     # Pipeline de limpieza (4 capas)
│   │   └── ner.py          # Extracción de entidades
│   ├── training/           # Scripts de entrenamiento de modelos
│   └── utils/              # Utilidades
├── migrations/             # Alembic migrations
├── docker-compose.yml      # Servicios Docker
└── Dockerfile
```

## Componentes

### 1. API (`src/api/`)

**Patrón:** Routers por recurso con endpoints delgados.

- **`main.py`:** `create_app()` factory. Middleware CORS. Incluye routers.
- **`deps.py`:** `get_document_or_404`, `require_status(*allowed)`. Dependencias FastAPI reutilizables que encapsulan lógica común (lookup + validación de estado).
- **`routers/documents.py`:** Upload simple y batch, list/get, process, clean con dry_run.
- **`routers/entities.py`:** Listar con filtros, extraer entidades de documento.
- **`schemas/`:** Pydantic models separados por dominio.

**Principios:**
- Endpoints solo manejan HTTP (parsing, status codes, responses)
- Lógica de negocio delegada a `src/services/`
- Validación de estado vía dependencias (`require_status`)
- Configuración de paths vía `src/core/config.py`

### 2. Core (`src/core/`)

- **`config.py`:** `Settings` con pydantic-settings. DB creds, paths de datos. Lee `.env`. `extra="ignore"` para variables de entorno no declaradas.
- **`database.py`:** Lazy engine creation (no conecta en import time). `Base` (DeclarativeBase). `get_db()` generator para FastAPI dependency injection.

### 3. Modelos (`src/models/`)

Cinco tablas mapeadas con SQLAlchemy ORM:

| Modelo | Tabla | Propósito |
|--------|-------|-----------|
| Document | documents | Metadata de archivos subidos |
| Entity | entities | Entidades extraídas + embeddings (pgvector) |
| Relationship | relationships | Relaciones entre entidades |
| Graph | graphs | Grafos generados |
| Metric | metrics | Métricas de análisis de redes |

### 4. Servicios (`src/services/`)

Implementan la lógica del pipeline:

- **`conversion.py`:** PDF (PyMuPDF) y DOCX (python-docx) → texto plano. Errores tipados: `UnsupportedFileTypeError`, `ConversionError`.
- **`cleaning.py`:** Pipeline de 4 capas deterministas. Cada capa retorna `(texto, métricas)`. Capa 1 universal, Capa 2 estructural, Capa 3 TOCs, Capa 4 editorial.
- **`ner.py`:** Extracción de entidades. `ExtractedEntity` dataclass. Interfaz `extract_entities(text, doc_id) → (entities, lang)`.

### 5. Infraestructura Docker

| Servicio | Imagen | Puerto |
|----------|--------|--------|
| db | pgvector/pgvector:pg16 | 5432 |
| api | Python 3.11-slim custom | 8000 |

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check |
| GET | `/health` | Health check |
| POST | `/documents` | Subir un archivo |
| GET | `/documents` | Listar documentos |
| POST | `/documents/batch` | Subir + procesar múltiples archivos |
| GET | `/documents/{id}` | Ver documento |
| POST | `/documents/{id}/process` | Convertir a TXT |
| POST | `/documents/{id}/clean` | Limpiar (4 capas), soporta `?dry_run=true` |
| GET | `/entities` | Listar entidades (filtros: category, document_id) |
| POST | `/entities/extract/{id}` | Extraer entidades de un documento |

## Decisiones arquitectónicas (vigentes)

- **DB:** PostgreSQL + pgvector
- **API:** FastAPI con routers modulares
- **ORM:** SQLAlchemy 2.0 con DeclarativeBase
- **Migraciones:** Alembic (compatible con `src.models.models.Base`)
- **Config:** pydantic-settings con `.env`
- **Limpieza:** Determinista por capas (no IA)
- **NER:** XLM-RoBERTa fine-tuned (pendiente integrar)
- **Infraestructura:** Docker Compose (db + api)
