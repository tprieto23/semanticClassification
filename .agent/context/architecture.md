# Arquitectura

## Estructura

```
src/
├── config.py
├── api/
│   ├── main.py                ← FastAPI + CORS + /health + exception handler + router
│   ├── routers/
│   │   ├── documents.py       ← endpoints bajo /documents
│   │   └── analysis_networks.py ← build/latest de la red de corpus
│   └── schemas/
│       ├── documents.py       ← DocumentRead, DocumentListResponse, BatchProcess*
│       ├── entities.py        ← EntityOut, ExtractEntitiesResponse
│       └── network.py         ← respuesta tipada de red, cobertura y artefactos
data/
├── codebooks/codebook_en_construccion_en.md ← especificación completa de NER
├── ner/annotations/a251048a.json  ← anotaciones históricas reservadas para evaluación futura
└── prompts/
    └── ner_prompt.md              ← plantilla única: codebook + bloque objetivo del anotador semántico
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
│   ├── sentences.py               ← ORM Sentence (evidencia oración–entidad)
│   ├── sentences_repo.py          ← reemplazo/elimina oraciones por documento
│   └── storage.py                 ← guardar, leer, eliminar, preparar_nombre
 └── services/
      ├── cleaning.py            ← CleaningService: structuralCleaning(regex) + linguisticCleaning(Anthropic)
      ├── documents.py           ← DocumentService + todas las excepciones
      ├── llm_client.py          ← Cliente Anthropic compartido
      ├── ner.py                 ← Extracción few-shot (Anthropic + ejemplos curados + tool schema)
      ├── fuzzy_matching.py      ← resolución determinista de entidades v2
      ├── network.py             ← orquestación por corpus/incubadora/documento
      └── pdf_converter.py       ← PdfConverter: PyMuPDF fast path + Docling OCR fallback

src/analysis/
├── backbone.py                   ← construcción de backbone analítico y exportación canónica
├── cooccurrence.py               ← incidencia y matrices de coocurrencia por oración
├── entity_resolution_audit.py    ← simulación reversible antes/después
├── graph_export.py               ← exportación mínima GraphML + CSV + metadata JSON
├── graph_paths.py                ← rutas y nombres estables de artefactos en s3/graphs/
├── leiden.py                     ← clustering reproducible con atributos para Gephi
└── network_visualization.py      ← red plana estática, JSON, HTML y GraphML
```

La capa de meta-red añade `src/models/semantic_nodes.py`,
`src/services/semantic_nodes.py`, `src/api/schemas/semantic_nodes.py` y
`src/api/routers/semantic_nodes.py`. Su primera entrega registra comunidades
Leiden aceptadas como nodos titulables. Las relaciones entre nodos se construyen
determinísticamente con `src/models/semantic_relationships.py`,
`src/services/semantic_relationships.py` y `src/api/routers/semantic_relationships.py`.

Flujo de nodos semánticos:

```text
GET  /semantic-nodes/leiden-source?language=es&artifact_source=accepted-2026-08-25
  → partición vigente, SHA-256 del GraphML y comunidades disponibles
POST /semantic-nodes/from-leiden
  → registra una comunidad aceptada con fuente, community_id y expected_clustering_sha256
GET  /semantic-nodes
GET  /semantic-nodes/{node_id}
POST /semantic-nodes/{node_id}/generate-description
  → usa el prompt editorial y evidencia interna; genera título/descripcion draft
PATCH /semantic-nodes/{node_id}
  → permite corregir título, descripción o aceptar el nodo
```

Ejemplo de promoción:

```json
{
  "projection_id": "prac-infra-rul-v2",
  "community_id": "C001",
  "artifact_source": "accepted-2026-08-25",
  "incubator_number": "all",
  "language": "es",
  "expected_clustering_sha256": "<SHA-256 recibido en leiden-source>"
}
```

La promoción conserva por incubadora los documentos y miembros que aportan
soporte en el alcance elegido. La generación no modifica nodos `accepted` ni
`retired`; para regenerar uno aceptado, primero se devuelve a `draft`.

## Capas

```
api/routers → services → models/{repo, storage}
   ↓            ↓              ↓
  HTTP       orquesta       DB + archivos
```

## Flujo Objetivo 1: Upload

```
POST /documents
  multipart:
    file
    incubator_number (1..8)
    year opcional (1000..9999)
    productive_sector opcional (Agroforestry)
    document_type opcional (vocabulario controlado)
    metadata opcional
    language opcional
  → FastAPI/OpenAPI valida que la incubadora esté entre 1 y 8
  → DocumentService.cargar_documento()
    → Storage.preparar_nombre() → nombre seguro, ext, UUID
    → Storage.guardar()         → s3/archivosCrudos/{uuid}.{ext}
    → DocumentRepo.crear()      → INSERT con status=raw y atributos de ingesta
  ← 201 + DocumentRead (incluye incubadora, idioma, año, sector y tipo documental)

POST /documents/batch
  multipart: files[] + incubadora; año, sector y tipo documental opcionales comunes al lote
  → cada documento conserva sus propios campos en PostgreSQL

PATCH /documents/{document_id}/classification
  multipart form-data: uno o más de year, productive_sector, document_type
  → solo modifica los campos enviados
  → no cambia status ni repite conversión, limpieza o NER

PATCH /documents/{id}/language
  → registra el idioma de un documento ya cargado

POST /documents/set-language-batch
  → registra el idioma para varios documentos a la vez

GET /documents?incubator_number={1..8}&language=es
  → filtra el corpus documental por incubadora y/o idioma
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
         → _cargar_prompt()                 → lee ner_prompt.md y codebook completo (caché)
           → NER_CODEBOOK_PATH              → data/codebooks/codebook_en_construccion_en.md
         → _partir_por_parrafos()           → chunks de máximo 3 párrafos / 12K caracteres
         → _segmentar_oraciones()           → asigna sentence_id estable y offset absoluto
         → _construir_json_entrada()        → arma JSON con document_id, title y sentences
         → _build_prompt()                  → inserta codebook y JSON objetivo en la plantilla única
         → Anthropic API (claude-sonnet)    → un mensaje de usuario con codebook + fragmento objetivo
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
para CHAR/LOC y 96 para INFRA/RUL/PRAC, con margen mínimo de 5 puntos. La forma
minúscula/singular se aplica a actores genéricos controlados; los nombres propios
conservan una etiqueta legible. Los UUID no se transforman.

La categoría activa `RUL` representa reglas, normas e instrumentos
institucionales concretos. La gobernanza puede describirse en el análisis, pero
no se etiqueta por sí sola. Al leer JSON o particiones históricas, el servicio
normaliza `GOV` a `RUL` en memoria; no reescribe esos artefactos. La migración
`b5c6d7e8f9a0` actualiza las categorías persistidas y cambia la proyección activa
de `prac-infra-gov-v1` a `prac-infra-rul-v2`.

Antes de reprocesar un documento puede ejecutarse una auditoría transaccional que
siempre hace rollback y compara también la red G₁/G₃:

```bash
python -m src.analysis.entity_resolution_audit \
  --ner-json s3/archivosNER/{document_id}.json \
  --output-dir data/output/entity_resolution/{document_id}
```

## Flujo Objetivo 5: Red plana de coocurrencia

```
POST /analysis/network
POST /documents/{id}/network

  → solo incluye documentos con status = 'fuzzyMatching'
  → el POST de corpus recibe incubator_number y language en JSON
  → cada filtro admite un valor concreto o "all"; ambos se combinan con AND
  → consulta entities + canonical_entities sin modificar PostgreSQL
  → nodo = canonical_id, con categoría CHAR/LOC/PRAC/INFRA/RUL
  → arista no dirigida = dos canónicos presentes en la misma
    (document_id, sentence_id), incluso CHAR–CHAR y LOC–LOC
  → peso = número de oraciones distintas donde coocurre el par
  → una sola red: no hay layers, macrocapa L2 ni bloques separados
  → el contexto de evidencia se compone a partir de las menciones del par
  → exportación atómica por incubadora + idioma + minimum_weight + include_isolates
  → archivos CSV, Matrix Market, GraphML, JSON, PNG/SVG y HTML interactivo
  → respuesta con cobertura, conteos, 15 pares de categorías, top nodos y URLs

GET /analysis/network/latest
  → recibe incubadora/idioma como query params y lee la combinación exacta
  → no recalcula la red
```

El layout usa fuerzas para componentes pequeños y una disposición determinista
lineal para componentes de más de 500 nodos. Así la configuración predeterminada
del corpus completo sigue siendo operable con miles de nodos.

## Proyección analítica tipada PRAC + INFRA + RUL

La red histórica de cinco categorías continúa disponible. La proyección analítica
principal se registra por separado como `prac-infra-rul-v2`:

```
entities + canonical_entities
  → agrupar todas las menciones por (document_id, sentence_id)
  → conservar todas las entidades de la oración como evidencia contextual
  → proyectar únicamente nodos PRAC, INFRA y RUL
  → permitir los seis category_pair, incluidas relaciones intratipo
  → calcular las nueve vistas como resúmenes en memoria
  → publicar únicamente la vista canónica main-component/all
```

La publicación oficial se organiza primero por formato y luego por alcance:

```
s3/graphs/
├── graphml/<scope>/{main_network,backbone_<projection>,leiden_<projection>}.graphml
├── json/<scope>/{main_network,backbone_<projection>,leiden_<projection>}.json
└── csv/<scope>/
    ├── {main_network,backbone_<projection>}_{nodes,edges}.csv
    └── leiden_<projection>_{communities,members}.csv
```

`<scope>` es `corpus/{language|all}`, `incubators/{number}/{language|all}` o
`documents/{document_id}`. Los nombres son estables y cada ejecución reemplaza
atómicamente los archivos oficiales. Los parámetros exactos quedan en el JSON.

`CHAR` y `LOC` no son nodos de esta proyección, pero siguen disponibles en
PostgreSQL. La tabla `sentences` almacena el texto normalizado de cada oración;
las entidades proyectadas y contextuales se consultan en `entities`. El endpoint
de evidencia combina ambas fuentes bajo demanda para reconstruir la arista, sus
oraciones y entidades contextuales.

### Construcción analítica parametrizada

El POST de la proyección acepta opcionalmente un objeto `construction` discriminado
por `method`. `document-recurrent-core-v1` siempre vuelve a producir la evidencia W1
del scope y después deriva una red analítica sin modificar PostgreSQL:

```
evidencia W1
  → nodo elegible si node.document_count >= minimum_node_document_count
  → arista incluida si ambos extremos son elegibles
  → métricas: sentence_count, document_count, independent_support_count
  → fractional_weight = Σ 1/(N_s - 1)
  → fractional_document_weight = Σ_doc min(1, Σ contribuciones)
  → Weight de GraphML = analysis_weight seleccionado
  → resúmenes de nueve vistas para all-components y main-component
  → GraphML canónico de main-component/all
```

La configuración completa se registra en el JSON, pero no se codifica en carpetas.
La construcción publica únicamente:

```
graphml/<scope>/backbone_<projection>.graphml
json/<scope>/backbone_<projection>.json
csv/<scope>/backbone_<projection>_nodes.csv
csv/<scope>/backbone_<projection>_edges.csv
```

Sin `construction`, la proyección usa los mismos nombres oficiales y registra el
método `raw-threshold-v1` en sus metadatos. La construcción no ejecuta Leiden.

### Clustering Leiden desacoplado

`POST /analysis/network/projections/{projection_id}/clusterings/leiden` recibe la
misma selección de construcción y una configuración reproducible. La publicación
simplificada acepta la vista canónica `main-component/all`; el cliente nunca envía
rutas de filesystem.

```
GraphML existente
  → hash SHA-256 de la fuente
  → conversión estable a igraph
  → Leiden ponderado (seed + resolution + iterations)
  → IDs estables por tamaño/nombre
  → GraphML derivado + CSV de comunidades/miembros + resumen JSON
```

El artefacto fuente no se modifica. El GraphML derivado conserva `weight` y añade
`modularity_class` entero para la partición de Gephi, además de `community_id`,
`community_size` y `community_color`. Los identificadores son estables únicamente
dentro de la partición exacta; no deben compararse entre filtros o resoluciones.
El JSON registra objetivo, resolución, semilla, iteraciones y atributo de peso. Si
la fuente y la configuración coinciden, el POST devuelve el resultado existente
con `cached=true`; otra configuración reemplaza atómicamente los nombres oficiales.

La configuración `objective_function=modularity` usa la partición generalizada de
modularidad con parámetro de resolución; `cpm` queda disponible para análisis de
sensibilidad. Las comunidades resultantes no se presentan automáticamente como
configuraciones semánticas: la validación de tamaño, evidencia y composición sigue
siendo una fase posterior.

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
├── archivosNER/              ← extracción NER (POST /documents/{id}/extract-entities)
└── graphs/                   ← GraphML, JSON y CSV oficiales por formato y scope
```

## Endpoints activos

| Método | Ruta | Objetivo |
|---|---|---|
| POST | `/documents` | Subir archivo; clasificación documental opcional |
| POST | `/documents/batch` | Subir múltiples con clasificación opcional común |
| PATCH | `/documents/{id}/classification` | Completar o corregir clasificación mediante form-data |
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
| POST | `/documents/{id}/network` | Construir red plana por documento |
| POST | `/analysis/network` | Construir red de corpus/incubadora |
| GET | `/analysis/network/latest` | Leer resumen/URLs sin recalcular |
| POST | `/analysis/network/projections/{projection_id}` | Construir proyección tipada o construcción analítica parametrizada |
| GET | `/files/graphs/{path}` | Servir solo artefactos oficiales de grafos |
| GET | `/health` | Health check |
| POST | `/semantic-network/relationships/build` | Construir relaciones deterministas entre nodos semánticos |
| GET | `/semantic-network/relationships` | Listar relaciones semánticas persistidas |
| POST | `/semantic-network/export/graphml` | Exportar la meta-red persistida a GraphML descargable |
