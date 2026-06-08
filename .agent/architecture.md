# Arquitectura

## Estructura

```
src/
├── config.py
├── api/
│   ├── main.py                ← FastAPI + CORS + /health + exception handler + router
│   ├── routers/
│   │   └── documents.py       ← todos los endpoints bajo /documents
│   └── schemas/
│       └── documents.py       ← DocumentRead, DocumentListResponse, BatchProcess*
├── models/
│   ├── database.py            ← engine, SessionLocal, Base, get_db
│   ├── documents.py           ← ORM Document (10 columnas)
│   ├── documents_repo.py      ← crear, leer_todos, leer_uno, eliminar, actualizar_status, leer_por_status
│   └── storage.py             ← guardar, leer, eliminar, preparar_nombre
└── services/
    ├── cleaning.py            ← CleaningService.limpiar()
    └── documents.py           ← DocumentService + todas las excepciones
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
POST /documents/process-batch

  → DocumentService.convertir()
    → DocumentRepo.leer_uno()          → SELECT
    → MarkItDown().convert(file_path)  → archivo → MD
    → Storage.guardar()                → s3/archivosConvertidos/{id}.md
    → doc.converted_path = path        → guarda ruta en DB
    → DocumentRepo.actualizar_status() → status = 'converted'
  ← 200 OK

convertir_varios: busca todos en status "raw", convierte uno a uno con rollback por documento
```

## Flujo Objetivo 3: Limpieza

```
POST /documents/{id}/clean
POST /documents/clean-batch

  → DocumentService.limpiar()
    → DocumentRepo.leer_uno()          → SELECT
    → Storage.leer(converted_path)     → lee el .md
    → CleaningService.limpiar()
        → ftfy.fix_text()              → repara encoding
        → markdown_it.MarkdownIt()     → parsea MD → extrae texto plano
        → regex URL/email/teléfono     → elimina datos de contacto
        → re.sub + strip + .lower()   → normaliza whitespace + minúsculas
    → Storage.guardar()                → s3/archivosLimpiados/{id}.txt
    → doc.cleaned_path = path          → guarda ruta en DB
    → DocumentRepo.actualizar_status() → status = 'cleaned'
  ← 200 OK

limpiar_varios: busca todos en status "converted", limpia uno a uno con rollback por documento
```

## Flujo Revertir Limpieza

```
POST /documents/{id}/revert-clean

  → DocumentService.revertir_limpieza()
    → DocumentRepo.leer_uno()          → SELECT
    → Storage.eliminar(cleaned_path)   → borra el .txt
    → doc.cleaned_path = None          → limpia referencia
    → DocumentRepo.actualizar_status() → status = 'converted'
  ← 200 OK
```

## Storage

```
s3/
├── archivosCrudos/           ← upload (POST /documents)
├── archivosConvertidos/      ← conversión (POST /documents/{id}/process)
└── archivosLimpiados/        ← limpieza (POST /documents/{id}/clean)
```

## Endpoints activos

| Método | Ruta | Objetivo |
|---|---|---|
| POST | `/documents` | Subir archivo |
| POST | `/documents/batch` | Subir múltiples |
| GET | `/documents` | Listar + filtros |
| GET | `/documents/{id}` | Ver uno |
| DELETE | `/documents/{id}` | Eliminar |
| POST | `/documents/{id}/process` | Convertir a MD |
| POST | `/documents/process-batch` | Convertir todos en raw |
| POST | `/documents/{id}/clean` | Limpiar texto |
| POST | `/documents/clean-batch` | Limpiar todos en converted |
| POST | `/documents/{id}/revert-clean` | Revertir limpieza → converted |
| GET | `/health` | Health check |
