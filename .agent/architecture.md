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
│   ├── documents.py               ← ORM Document + incubator_number controlado (1..8)
│   ├── documents_repo.py          ← CRUD, filtros y acceso por status/incubadora
│   ├── canonical_entities.py      ← ORM CanonicalEntity
│   ├── canonical_entities_repo.py ← acceso a entidades canónicas
│   ├── canonical_entity_aliases.py ← alias observados por canónico
│   ├── canonical_entity_aliases_repo.py ← consulta y registro idempotente de alias
│   ├── entities.py                ← mención + identidad + trazabilidad de resolución
│   ├── entities_repo.py           ← eliminar_por_documento, reemplazar_entidades
│   └── storage.py                 ← guardar, leer, eliminar, preparar_nombre
 └── services/
      ├── cleaning.py            ← CleaningService: structuralCleaning(regex) + linguisticCleaning(Anthropic)
      ├── documents.py           ← DocumentService + todas las excepciones
      ├── llm_client.py          ← Cliente Anthropic compartido
      ├── ner.py                 ← Extracción few-shot (Anthropic + ejemplos curados + tool schema)
      ├── fuzzy_matching.py      ← resolución determinista de entidades v2
      └── pdf_converter.py       ← PdfConverter: PyMuPDF fast path + Docling OCR fallback

src/analysis/
├── cooccurrence.py               ← incidencia y matrices de coocurrencia por oración
├── entity_resolution_audit.py    ← simulación reversible antes/después
└── network_visualization.py      ← red G₃ estática, HTML y GraphML
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
  multipart: file + incubator_number (1..8) + metadata opcional
  → FastAPI/OpenAPI valida que la incubadora esté entre 1 y 8
  → DocumentService.cargar_documento()
    → Storage.preparar_nombre() → nombre seguro, ext, UUID
    → Storage.guardar()         → s3/archivosCrudos/{uuid}.{ext}
    → DocumentRepo.crear()      → INSERT con status=raw e incubator_number
  ← 201 + DocumentRead (incluye incubator_number)

POST /documents/batch
  multipart: files[] + una incubator_number común al lote

GET /documents?incubator_number={1..8}
  → filtra el corpus documental por incubadora
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
         → _segmentar_oraciones()           → asigna sentence_id estable y offset absoluto
         → _construir_json_entrada()        → arma JSON con document_id, title y sentences
         → _cargar_few_shot_examples()      → valida y formatea 25 ejemplos curados
         → Anthropic API (claude-sonnet)    → system + ejemplos + fragmento objetivo
         → tool submit_entity_annotations   → salida validada por JSON Schema
         → _parsear_datos()                 → localiza cada span dentro de su sentence_id
         → fallo explícito                  → no persiste resultados truncados o sin tool use
         → _buscar_offset()                 → calcula start/end absolutos buscando text literal
         → _fusionar_entidades()            → conserva apariciones y deduplica solo la misma posición
     → Guardar JSON en s3/archivosNER/{id}.json
     → doc.ner_path = path                   → guarda la ruta del JSON en documents
     → DocumentRepo.actualizar_status()      → status = 'ner'
   ← 200 + ExtractEntitiesResponse {document_id, entities: [{text, category, start, end, sentence_id, context, ambiguity}]}
```

Este endpoint no escribe, reemplaza ni elimina menciones en la tabla `entities`.
La persistencia y normalización de menciones se delega a un endpoint posterior.

## Flujo de resolución canónica (endpoint histórico Fuzzy Matching)

```
POST /documents/{id}/fuzzy-matching

   → comprueba que el documento exista y tenga status = 'ner'
   → comprueba que ner_path esté registrado
   → lee y valida s3/archivosNER/{id}.json
   → valida primero todas las menciones y analiza el documento completo
   → conserva text/start/end/context; solo normaliza claves de comparación
   → agrupa actores genéricos CHAR mediante singularización controlada
      (mineros → minero; mineras → minera; conserva género y calificadores)
   → detecta familias nominales CHAR por prefijos compatibles dentro del documento
      (Griselda ↔ Griselda Zubizarreta ↔ Griselda Zubizarreta Vargas)
   → rechaza el nombre corto si hay dos familias compatibles en el documento
   → bloquea marcadores institucionales/corporativos en la regla de personas
   → busca candidatos exclusivamente dentro de la misma categoría
   → aplica exacto, alias persistido, nombre personal seguro o fuzzy conservador
   → crea canonical_entity si no existe una coincidencia segura
   → registra los textos observados en canonical_entity_aliases
   → reemplaza las menciones previas del documento en entities
   → persiste method, score, version y details para auditar cada decisión
   → commit único → menciones + canónicos + alias + status
   → status = 'fuzzyMatching'
   ← 200 + menciones con canonical_id y metadatos de la decisión
```

La tabla `canonical_entities` contiene `id`, `canonical_name` y `category`; cada fila
de `entities` referencia una entidad canónica mediante `canonical_id` no nulo. La
versión `deterministic-v2` usa los métodos `exact`, `morphology`, `person_alias`,
`stored_alias`, `person_name`, `fuzzy` y `new`. Los umbrales fuzzy siguen siendo 93
para CHAR/LOC y 96 para INFRA/GOV/PRAC, con margen mínimo de 5 puntos. La forma
minúscula/singular se aplica a actores genéricos controlados; los nombres propios
conservan una etiqueta legible. Los UUID no se transforman.

Antes de reprocesar un documento puede ejecutarse una auditoría transaccional que
siempre hace rollback y compara también la red G₁/G₃:

```bash
python -m src.analysis.entity_resolution_audit \
  --ner-json s3/archivosNER/{document_id}.json \
  --output-dir data/output/entity_resolution/{document_id}
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
| POST | `/documents` | Subir archivo con incubadora obligatoria 1..8 |
| POST | `/documents/batch` | Subir múltiples bajo una incubadora común |
| GET | `/documents` | Listar + filtros, incluido `incubator_number` |
| GET | `/documents/{id}` | Ver uno |
| DELETE | `/documents/{id}` | Eliminar |
| POST | `/documents/{id}/process` | Convertir a MD |
| POST | `/documents/process-batch` | Convertir todos en raw |
| POST | `/documents/{id}/clean` | Limpiar texto |
| POST | `/documents/clean-batch` | Limpiar todos en converted |
| POST | `/documents/{id}/revert` | Revertir al estado anterior |
| POST | `/documents/{id}/extract-entities` | Extraer entidades NER (Anthropic LLM) |
| POST | `/documents/{id}/fuzzy-matching` | Normalizar y persistir menciones con canonical_id |
| GET | `/health` | Health check |
