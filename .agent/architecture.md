# Arquitectura

## Estructura

```
src/
├── config.py
├── api/
│   ├── main.py                ← FastAPI + CORS + /health + routers
│   ├── routers/
│   │   ├── ingesta.py         ← POST/GET/GET-id/DELETE /documents + /batch
│   │   └── conversion.py      ← POST /documents/{id}/process
│   └── schemas/
│       └── ingesta.py         ← DocumentRead, DocumentListResponse
├── models/
│   ├── database.py            ← engine, SessionLocal, Base, get_db
│   ├── documents.py           ← ORM Document (8 columnas)
│   ├── documents_repo.py      ← crear, leer_todos, leer_uno, eliminar, actualizar_status
│   └── storage.py             ← guardar, eliminar, guardar_convertido, preparar_nombre
└── services/
    ├── database.py            ← re-exporta get_db (pasamanos para api)
    ├── documents.py           ← DocumentService + excepciones
    └── conversion.py          ← ConversionService.convertir()
```

## Capas

```
api/routers → services → models/{repo, storage}
   ↓            ↓              ↓
  HTTP       orquesta       DB + archivos
```

## Flujo Objetivo 1: Upload

```
POST /documents
  → DocumentService.cargar_documento()
    → Storage.preparar_nombre() → nombre seguro, ext, UUID
    → Storage.guardar()         → s3/archivosCrudos/{uuid}.{ext}
    → DocumentRepo.crear()      → INSERT
  ← 201 + DocumentRead
```

## Flujo Objetivo 2: Conversión

```
POST /documents/{id}/process
  → ConversionService.convertir()
    → DocumentRepo.leer_uno()            → SELECT
    → MarkItDown().convert(file_path)    → PDF/DOCX → MD
    → Storage.guardar_convertido()       → s3/archivosConvertidos/{id}.md
    → DocumentRepo.actualizar_status()   → status = 'converted'
  ← 200 OK
```

## Storage

```
s3/
├── archivosCrudos/           ← upload (POST /documents)
└── archivosConvertidos/      ← conversión (POST /documents/{id}/process)
```

## Endpoints activos

| Método | Ruta | Router | Objetivo |
|---|---|---|---|
| POST | `/documents` | ingesta | Subir archivo |
| POST | `/documents/batch` | ingesta | Subir múltiples |
| GET | `/documents` | ingesta | Listar + filtros |
| GET | `/documents/{id}` | ingesta | Ver uno |
| DELETE | `/documents/{id}` | ingesta | Eliminar |
| POST | `/documents/{id}/process` | conversion | Convertir a MD |
| GET | `/health` | main | Health check |
