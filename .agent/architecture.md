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
│       ├── documents.py       ← DocumentRead, DocumentListResponse, BatchProcess*
│       └── entities.py        ← EntityOut, ExtractEntitiesResponse
data/
├── ner/annotations/a251048a.json  ← anotaciones históricas reservadas para evaluación futura
└── prompts/
    ├── ner_prompt.md              ← system prompt del anotador semántico
    └── ner_user_prompt.md         ← plantilla del user prompt (inyecta el JSON de entrada)
├── models/
│   ├── database.py                ← engine, SessionLocal, Base, get_db
│   ├── documents.py               ← ORM Document (10 columnas)
│   ├── documents_repo.py          ← crear, leer_todos, leer_uno, eliminar, actualizar_status, leer_por_status
│   ├── entities.py                ← ORM Entity (category, text, offsets, context, ambiguity)
│   ├── entities_repo.py           ← eliminar_por_documento, reemplazar_entidades
│   └── storage.py                 ← guardar, leer, eliminar, preparar_nombre
 └── services/
      ├── cleaning.py            ← CleaningService: structuralCleaning(regex) + linguisticCleaning(Anthropic)
      ├── documents.py           ← DocumentService + todas las excepciones
      ├── llm_client.py          ← Cliente Anthropic compartido
      ├── ner.py                 ← Extracción few-shot (Anthropic + ejemplos curados + tool schema)
      └── pdf_converter.py       ← PdfConverter: PyMuPDF fast path + Docling OCR fallback
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
     → PdfConverter().convertir()       → PyMuPDF (PDF nativo) o Docling OCR (fallback) → MD
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
     → CleaningService.structuralCleaning()
         → ftfy.fix_text()              → repara encoding
         → elimina placeholders de imágenes
         → elimina headers/footers repetidos
         → markdown_it.MarkdownIt()     → parsea MD → extrae texto plano
         → regex URL/email/teléfono     → elimina datos de contacto
         → elimina metadata de autoria (autores, facilitadores, revisores, directores)
         → elimina direcciones postales, notas legales, copyright y créditos
         → elimina índices/tablas de contenido, tablas Markdown y headers de anexos
         → elimina prefijos de numeración de secciones, subsecciones e items
         → elimina números de página y líneas muy cortas
         → deduplica párrafos consecutivos
         → _MULTISPACE + _SPACES + strip → normaliza whitespace (mantiene mayúsculas)
      → CleaningService.linguisticCleaning()
          → Anthropic API (claude-sonnet)      → prompt de limpieza lingüística
          → elimina referencias, citas, notas al pie
          → preserva párrafos (\n\n)
      → Storage.guardar()                → s3/archivosLimpiados/{id}.txt
      → doc.cleaned_path = path          → guarda ruta en DB
      → DocumentRepo.actualizar_status() → status = 'cleaned'
   ← 200 OK

linguisticCleaning() fue migrado de regex a Anthropic Claude (Jul 2026). Recibe el texto post-structuralCleaning, lo chunkifica por párrafos si es largo, lo envía a Claude con un prompt especializado, y devuelve el texto con párrafos preservados.

limpiar_varios: busca todos en status "converted", limpia uno a uno con rollback por documento
```

## Flujo Objetivo 4: Extracción de entidades (NER vía LLM)

```
POST /documents/{id}/extract-entities

   → DocumentService.extraer_entidades_de_documento()
     → DocumentRepo.leer_uno()              → SELECT
     → Storage.leer(cleaned_path)           → lee el .txt limpio
     → extraer_entidades(texto, document_id, document_title):
         → _cargar_system_prompt()          → lee data/prompts/ner_prompt.md (caché)
         → _partir_por_parrafos()           → chunks de máximo 3 párrafos / 12K caracteres
         → _construir_json_entrada()        → arma JSON con document_id, title, text
         → _cargar_few_shot_examples()      → valida y formatea 25 ejemplos curados
         → Anthropic API (claude-sonnet)    → system + ejemplos + fragmento objetivo
         → tool submit_entity_annotations   → salida validada por JSON Schema
         → _parsear_datos()                 → valida annotations [{label, text, ambiguity}]
         → fallo explícito                  → no persiste resultados truncados o sin tool use
         → _buscar_offset()                 → calcula start/end absolutos buscando text literal
         → _fusionar_entidades()            → conserva apariciones y deduplica solo la misma posición
     → Guardar JSON en s3/archivosNER/{id}.json
     → Entity bulk insert en DB             → persiste menciones y offsets sin catálogos
     → db.commit()
   ← 200 + ExtractEntitiesResponse {document_id, entities: [{text, category, start, end, context, ambiguity}]}
```

## Flujo Revertir

```
POST /documents/{id}/revert

  → DocumentService.revertir()
    → DocumentRepo.leer_uno()          → SELECT
    → cleaned  → Storage.eliminar(cleaned_path)  → borra .txt
              → doc.cleaned_path = None
              → status = 'converted'
    → converted → Storage.eliminar(converted_path) → borra .md
               → doc.converted_path = None
               → status = 'raw'
    → raw      → DocumentoNoReversible (409)
  ← 200 OK
```

## Storage

```
s3/
├── archivosCrudos/           ← upload (POST /documents)
├── archivosConvertidos/      ← conversión (POST /documents/{id}/process)
├── archivosLimpiados/        ← limpieza (POST /documents/{id}/clean)
└── archivosNER/              ← extracción NER (POST /documents/{id}/extract-entities)
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
| POST | `/documents/{id}/revert` | Revertir al estado anterior |
| POST | `/documents/{id}/extract-entities` | Extraer entidades NER (Anthropic LLM) |
| GET | `/health` | Health check |
