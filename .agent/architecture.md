# Arquitectura

## Estructura

```
src/
├── config.py                  ← DATABASE_URL + paths
├── api/
│   ├── main.py                ← FastAPI app, CORS, /health, exception handlers
│   ├── routers/
│   │   └── ingesta.py         ← endpoints (POST/GET/GET-id/DELETE /documents)
│   └── schemas/
│       └── ingesta.py         ← Pydantic: DocumentRead, DocumentListResponse
├── models/
│   ├── database.py            ← engine, SessionLocal, Base, get_db
│   ├── documents.py           ← ORM Document (columnas)
│   ├── documents_repo.py      ← CRUD puro (crear, leer_todos, leer_uno, eliminar)
│   └── storage.py             ← guardar/eliminar archivos en s3/archivosCrudos
└── services/
    └── documents.py           ← DocumentService (orquesta Storage + Repo) + excepciones
```

## Capas y responsabilidades

```
api/routers → services → models/{repo, storage}
   ↓            ↓              ↓
  HTTP       orquesta       DB + archivos
```

| Capa | ¿Qué hace? | ¿Qué NO hace? |
|---|---|---|
| `api/routers/` | Recibir request, llamar service, devolver response | Lógica de negocio, queries, archivos |
| `services/` | Validar, orquestar Storage + Repo, manejar errores de dominio | HTTP, SQL directo, sistema operativo |
| `models/` | ORM, queries SQL, archivos en disco | HTTP, validaciones de negocio |

## Flujo de upload

```
POST /documents
  → router: recibe file + metadata
  → DocumentService.cargar_documento()
    → Storage.preparar_nombre()    → nombre seguro, extensión, UUID
    → Storage.guardar()            → escribe en s3/archivosCrudos/{uuid}.ext
    → DocumentRepo.crear()         → INSERT en PostgreSQL
  ← Document (ORM) → serializado como DocumentRead
```

## DB

```
documents
├── id                 UUID PK
├── original_filename  text
├── file_path          text
├── file_type          text
├── file_size_bytes    bigint
├── status             text      (raw → converted → cleaned → processed)
├── uploaded_at        timestamp
└── metadata           jsonb     (autor, etiquetas, notas, etc.)
```

## Storage

```
s3/archivosCrudos/
└── {uuid}.{ext}       ← archivos subidos (gitignored)
```

Montado como volumen en Docker: `./s3:/app/s3`
