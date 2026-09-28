# Tareas

## Objetivo 1: Ingesta de documentos ✅

- [x] `src/config.py` — settings sin credenciales
- [x] `src/models/database.py` — conexión DB
- [x] `src/models/documents.py` — ORM Document
- [x] `src/models/documents_repo.py` — CRUD + actualizar_status + leer_por_status
- [x] `src/models/storage.py` — guardar, leer, eliminar en s3/archivosCrudos
- [x] `src/services/documents.py` — DocumentService + excepciones
- [x] `src/api/routers/documents.py` — POST, GET, GET/{id}, DELETE, POST /batch
- [x] `src/api/schemas/documents.py` — DocumentRead, DocumentListResponse, BatchProcess*
- [x] `src/api/main.py` — FastAPI + exception handler
- [x] `documents.incubator_number` — dimensión controlada `1..8`, indexada y validada en PostgreSQL
- [x] `POST /documents` y `POST /documents/batch` — incubadora obligatoria y seleccionable en OpenAPI
- [x] `GET /documents?incubator_number=1..8` — filtro de documentos por incubadora
- [x] Migración `c4d5e6f7a8b9` aplicada; el esquema admite temporalmente incubadora `NULL` para legado
- [x] Eliminados 29 documentos de prueba que permanecían en estado `raw` y sus archivos físicos
- [x] Seguimiento: eliminado `1770a776-d813-47c0-8738-b7f23e06f230` tras revertirlo a `raw`
- [x] `61b5cf8e-8109-408c-a571-cdf5b31512ca` asignado a `incubator_number = 1`
- [x] `documents.language` — idioma del documento (`es`, `en`, `pt`, etc.), nullable, indexado
- [x] `PATCH /documents/{id}/language` — registrar idioma después de la carga
- [x] `POST /documents/set-language-batch` — registrar idioma en lote
- [x] `GET /documents?language=...` — filtrar documentos por idioma
- [x] Migración `d5e6f7a8b9c0` aplicada; todos los documentos existentes quedan con `language = NULL`
- [x] Atributos opcionales en cargas nuevas: `year`, `productive_sector` y `document_type`
- [x] `year` validado como entero de cuatro dígitos (`1000..9999`)
- [x] `productive_sector` usa vocabulario controlado; opción vigente: `Agroforestry`
- [x] `document_type` usa las opciones `academic`, `technical_report`, `project_report`,
  `policy_document`, `manual_or_guide`, `institutional_document` y `other`
- [x] Migración `a4b5c6d7e8f9` aplicada; las columnas son nullable únicamente para compatibilidad histórica
- [x] Colección de Postman actualizada para ingesta individual y por lote
- [x] `PATCH /documents/{id}/classification` con `form-data` para completar o corregir parcialmente esos atributos

## Objetivo 2: Conversión a Markdown ✅

- [x] ~~`markitdown[pdf,docx]` en requirements.txt~~ → reemplazado por `docling`
- [x] `s3/archivosConvertidos/` — destino de archivos .md
- [x] `config.py` — STORAGE_CONVERTED
- [x] `models/documents.py` — columna converted_path
- [x] `services/documents.py` — DocumentService.convertir() con Docling + convertir_varios()
- [x] `api/routers/documents.py` — POST /documents/{id}/process + /process-batch
- [x] Dockerfile — `libgl1`, `libglib2.0-0`, `libxcb1` para OpenCV/Docling
- [x] Probado: 200, 404, 409

### Refactors del objetivo 2
- [x] `models/storage.py` — unificado `guardar(content, filename, target_dir)`, eliminado `guardar_convertido`
- [x] `services/documents.py` — absorbido `ConversionService.convertir()` → `DocumentService.convertir()`
- [x] `api/routers/documents.py` — absorbido `conversion.py`, renombrado `ingesta.py` → `documents.py`
- [x] `api/schemas/documents.py` — renombrado de `ingesta.py`
- [x] Eliminados `services/conversion.py`, `api/routers/conversion.py`, `api/routers/ingesta.py`, `api/schemas/ingesta.py`

### Mejora de rendimiento PDF — Jun 12 2026
- [x] `requirements.txt` — agregado `PyMuPDF`
- [x] `Dockerfile` — agregados `libxcb-shm0`, `libxcb-xfixes0`, `libxcb-xinerama0`, `libglx-mesa0`
- [x] `src/services/pdf_converter.py` — **nuevo** convertidor híbrido:
  - Fast path: PyMuPDF para PDFs nativos (~0.1-1s por documento)
  - Fallback: Docling OCR para PDFs escaneados (~60-90s por documento)
- [x] `src/services/documents.py` — `convertir()` reutiliza `PdfConverter` (lazy)
- [x] Batch de 27 PDFs convertidos en **28 segundos** (vs ~2-3 horas con Docling puro)

### Refactor de simplificación — feat/reedireccion2
- [x] `src/services/pdf_converter.py` — API simplificada: `convertir(file_path: str) -> str`
- [x] `src/services/pdf_converter.py` — código muerto eliminado (`_extraer_imagenes_pymupdf`, bloques comentados, imports no usados)
- [x] `src/services/pdf_converter.py` — TODO documentado para extracción futura de texto en imágenes `.png` dentro de PDFs nativos
- [x] `src/services/documents.py` — adaptado a la nueva firma del convertidor
- [ ] Extracción de imágenes como archivos separados — **postergado** (se mantiene la columna `images_path` en DB/schema por si se retoma)

## Objetivo 3: Limpieza de textos 🔧

- [x] `src/services/cleaning.py` — CleaningService.structuralCleaning()
  - [x] ftfy.fix_text() → reparación de encoding
  - [x] markdown_it.MarkdownIt("commonmark") → parseo MD → extracción texto plano
  - [x] regex → eliminación de URLs, emails, teléfonos
  - [x] eliminación de placeholders de imágenes (`<!-- Start/End of picture text -->`)
  - [x] eliminación conservadora de metadata de autoria (autores, facilitadores, revisores, directores, etc.)
  - [x] eliminación de direcciones postales, correos y teléfonos
  - [x] eliminación de notas legales, copyright y créditos de fotografía/diagramación
  - [x] eliminación de índices/tablas de contenido
  - [x] eliminación de tablas Markdown (agenda, anexos tabulados)
  - [x] eliminación de headers de anexos
  - [x] eliminación de prefijos de numeración de secciones y subsecciones
  - [x] eliminación de items/viñetas sueltos
  - [x] eliminación de números de página y líneas muy cortas
  - [x] deduplicación de párrafos consecutivos
  - [x] normalización whitespace (_MULTISPACE + _SPACES) **sin** `.lower()`
- [x] `linguisticCleaning()` — ~~regex~~ → **migrado a Anthropic Claude** (Jul 2026):
  - [x] Elimina referencias bibliográficas, citas entre paréntesis y notas al pie
  - [x] Preserva párrafos separados por `\n\n`
  - [x] Chunking por párrafos para textos largos
  - [x] Prompt específico alineado con el dominio territorial amazónico
  - [x] Métodos regex obsoletos eliminados (`_CITA_PARENTESIS`, `_REF_BIB_*`, `_NOTA_PIE`, `_HEADERS_REFERENCIAS`)
- [x] `models/documents.py` — columna cleaned_path
- [x] `models/storage.py` — método leer()
- [x] `services/documents.py` — DocumentService.limpiar() + limpiar_varios() + DocumentoNoConvertido
- [x] `api/routers/documents.py` — POST /documents/{id}/clean + /clean-batch
- [x] `config.py` — DATA_CLEANED = s3/archivosLimpiados (borrado DATA_TXT)
- [x] Probado: 200, 404, 409, 500 (archivo no encontrado)
- [x] `POST /documents/{id}/revert` — revierte al estado anterior (cleaned→converted, converted→raw)

### Refactor de limpieza — Jul 02 2026

- [x] Renombrado `_eliminar_lineas_repetidas` → `_eliminar_headers_footers_y_numeros`:
  - Solo elimina números de página y headers/footers cortos recurrentes.
  - Conserva lemas y frases identitarias repetidas para el futuro conteo de `NARRATIVA`.
- [x] `_es_direccion` separa direcciones postales de topónimos:
  - Nunca elimina ciudades/países aislados (Lima, Perú, Bogotá, Puerto Maldonado).
  - Solo elimina líneas que son predominantemente direcciones postales.
- [x] Nuevo `_es_titulo_estructural` para eliminar headers de sección explícitamente
  (`Introducción`, `Resumen`, `Conclusiones`, `Referencias`, etc.) sin confundir con contenido.
- [x] `_eliminar_citas_parentesis` refinado:
  - Elimina citas académicas `(Apellido, 2020)`.
  - Preserva decretos, leyes, resoluciones y rangos institucionales.
- [x] Nueva `_eliminar_seccion_referencias`:
  - Detecta el header `Referencias` / `Bibliografía` y elimina todo desde ese punto.
- [x] `_URL_PATTERN` mejorado para capturar dominios sin `www`.
- [x] `_PHONE_PATTERN` más conservador:
  - Evita borrar años, fechas, coordenadas y rangos de páginas.
- [x] `_SECCION_PREFIX` corregido:
  - Quita numeración romana de 2+ letras (`II.`, `III.`) pero preserva iniciales (`V.`, `A.`).
- [x] `_NOTA_PIE` corregido para no eliminar listas numeradas legítimas.
- [x] `_REF_BIB_AUTOR` ajustado para no confundir topónimos con autores
  (`Maldonado, Lima` vs `García, A.`).
- [x] Logging de trazabilidad agregado en cada paso de limpieza.
- [x] Verificación manual de que las 9 categorías semánticas se conservan.
- [x] Fix post-refactor: `_es_referencia_bibliografica` ya no usa rangos de años
  (`2001-2018`) como único criterio, evitando que párrafos con datos y
  estadísticas sean eliminados incorrectamente (caso documento
  `e33950f0-0e69-41a8-9f37-50ab93f2a0df`).
- [x] Fix post-refactor: `_eliminar_headers_footers_y_numeros` ahora también
  elimina footers largos en MAYÚSCULAS repetidos, típicos de presentaciones
  tipo PowerPoint convertidas a PDF (caso documento
  `9c6c4d34-34f2-4ecf-a229-71809682cef8`).

## Objetivo 4: Extracción de entidades 🔧

**Nuevo enfoque:** Se reemplazó el modelo BERT/XLM-RoBERTa por extracción few-shot mediante Anthropic Claude. El esquema vigente contiene 5 etiquetas, usa 25 demostraciones curadas, no usa catálogos y fuerza una salida estructurada mediante tool use.

### Etiquetas finales

| Etiqueta | Descripción |
|----------|-------------|
| CHAR | Actores individuales o colectivos con un rol contextual concreto |
| LOC | Lugares geográficos, territorios, regiones, países, ciudades |
| INFRA | Infraestructura física, técnica o soportes estables |
| PRAC | Prácticas, actividades productivas, cadenas de valor |
| RUL | Reglas, normas e instrumentos institucionales concretos |

Los objetivos, visiones e intenciones no son entidades por sí mismos. Una entidad nominal autónoma contenida en ellos conserva la etiqueta que le corresponda.

### Implementado

- [x] `data/ner/annotations/a251048a.json` — anotaciones históricas retiradas del request; reservadas para trazabilidad
- [x] `data/ner/few_shot_examples.json` — 25 ejemplos activos, cinco por categoría
- [x] `src/models/entities.py` — ORM Entity (tabla `entities` recreada vía migración)
- [x] `src/services/llm_client.py` — cliente Anthropic compartido (reutilizado por cleaning.py y ner.py)
- [x] `src/services/ner.py` — servicio de extracción con:
  - Prompts externos en `data/prompts/`: system prompt + user prompt template
  - Definiciones de las 5 etiquetas + ejemplos + reglas de frontera en `data/prompts/ner_prompt.md`
  - Few-shot curado: 25 demostraciones validadas antes de enviar cada fragmento
  - Chunking de máximo 3 párrafos o 12K caracteres con offsets absolutos
  - Salida estructurada forzada con `submit_entity_annotations` y JSON Schema
  - Salida semántica: `{"annotations": [{label, text, ambiguity}]}`
  - Fallo explícito si Anthropic trunca la respuesta o no usa la herramienta requerida
  - Oraciones con `sentence_id` estable para localizar menciones aunque Claude responda fuera de orden
  - Repeticiones conservadas por aparición, incluso dentro de una misma oración
  - Cálculo backend de `start`/`end` absolutos buscando el span literal en el chunk
  - Campo `context` (texto circundante 80 chars antes/después)
  - Fusión de resultados de chunks conservando cada aparición por posición
  - Parseo robusto (strip markdown wrappers)
- [x] `src/services/cleaning.py` — `linguisticCleaning()` migrado a Anthropic (ver Objetivo 3)
- [x] `src/api/schemas/entities.py` — EntityOut con text, category, start, end, context y ambiguity
- [x] `POST /documents/{id}/extract-entities` — endpoint que extrae entidades y guarda el resultado en JSON
- [x] `.env` — variable `ANTHROPIC_API_KEY` (completada por el usuario)
- [x] `requirements.txt` — dependencia `anthropic` (removido spacy/langdetect)
- [x] `src/services/documents.py` — `extraer_entidades_de_documento()` no modifica la tabla `entities`; esa persistencia queda para un endpoint posterior
- [x] `migrations/versions/b8e3f2a1c4d5_recreate_entities_table.py` — recrea tabla entities
- [x] `src/config.py` — `STORAGE_NER = s3/archivosNER`, `NER_PROMPT_PATH = data/prompts/ner_prompt.md`, `NER_USER_PROMPT_PATH = data/prompts/ner_user_prompt.md`
- [x] `src/models/documents.py` — columna `ner_path`
- [x] `migrations/versions/5ea1bb7e236a_add_ner_path_to_documents.py` — migración para `ner_path`
- [x] `src/services/documents.py` — `extraer_entidades_de_documento()` guarda JSON en `s3/archivosNER/{id}.json`, devuelve el array de entidades y actualiza status a `ner`
- [x] `src/api/schemas/documents.py` — `DocumentRead` incluye `ner_path`
- [x] `src/services/documents.py` — `revertir()` soporta revertir desde status `ner` → `cleaned` → `raw`
- [x] `src/services/documents.py` — `eliminar()` borra todos los archivos generados (raw, converted, cleaned, NER)
- [x] `src/services/documents.py` — `extraer_entidades_de_varios()` para batch NER
- [x] `src/api/routers/documents.py` — `POST /documents/extract-entities-batch`
- [x] `POST /documents/{id}/fuzzy-matching` — normaliza, crea/reutiliza canónicos, persiste menciones y avanza a `fuzzyMatching`
- [x] `canonical_entities` — modelo, repositorio y migración inicial
- [x] `entities.canonical_id` — FK obligatoria hacia `canonical_entities`
- [x] Matching conservador por categoría — exact normalizado, fuzzy con umbral y margen, y protección para términos cortos
- [x] Persistencia transaccional — rollback completo ante errores y reemplazo idempotente de menciones por documento

### Rediseño de resolución canónica v2 — Ago 12 2026

- [x] Planificación por documento antes de comparar menciones aisladas
- [x] Singularización controlada de actores genéricos CHAR, en minúscula y conservando género/calificadores
- [x] Familias de nombres personales por prefijo compatible y ancla más completa
- [x] Protección contra nombres de pila ambiguos y sufijos corporativos (`SA`, `SAC`, `EIRL`, etc.)
- [x] Tabla `canonical_entity_aliases` para conservar formas observadas
- [x] Trazabilidad en `entities`: método, puntaje, versión y evidencia JSON
- [x] Migración `b3c4d5e6f7a8` aplicada y verificada
- [x] Auditoría reversible PostgreSQL + JSON + red antes/después
- [x] Simulación de `Relatos mineros.docx`: 1.111 menciones, DB sin cambios, 13 convergencias y 0 separaciones
- [x] 33 pruebas unitarias/integración local y health check de API
- [ ] Revisar cualitativamente los 48 nuevos canónicos propuestos y las 27 decisiones `person_alias`
- [ ] Reprocesar el documento real solo después de aprobar la auditoría

### Línea base histórica probada

- [x] La versión anterior extrajo 133 entidades en un documento de prueba.
- [x] Persistencia y respuesta HTTP funcionaron con el esquema anterior.
- [ ] Repetir el piloto con el esquema vigente de cinco etiquetas y sin catálogos.

## Objetivos 5–8: Vectores, matrices, grafos, métricas 🔧

### Punto de control de validación Postman — 23 septiembre 2026

- El endpoint `GET /semantic-nodes/leiden-source?language=es&artifact_source=official` fue validado correctamente.
- Clustering validado: `5b0fbd7a7b89c9a00bd6876afce066016195135764ecf66e7f984ef6694ea7f6`.
- Grafo fuente validado: `704bf158c3138a42733a5c466d45055534626d79a5b7521776431955129ac0f7`.
- Se promovió correctamente `C001` a nodo semántico.
- UUID del nodo `C001`: `2e73cadf-6799-46f8-9ba2-ac0a1a5dd40c`.
- El endpoint `GET /semantic-nodes` confirmó `total: 1`.
- El siguiente endpoint en el checklist es el número 4: `GET /semantic-nodes/{node_id}`; su respuesta detallada fue revisada.
- El 24 Sep se verificaron dos credenciales obsoletas cargadas en Docker y se recreó el servicio `api` con la llave vigente.
- `POST /semantic-nodes/{node_id}/generate-description` quedó validado con `HTTP 200`; Anthropic generó y persistió el título y la descripción de `C001` con estado `draft`.
- La generación usa ahora un tool schema forzado en lugar de depender de JSON como texto libre; conserva el fallback de texto para compatibilidad y registra errores del proveedor sin exponer credenciales al cliente HTTP.
- El cliente compartido y Docker Compose admiten además `ANTHROPIC_WORKSPACE_ID` para llaves organizacionales que requieran seleccionar workspace.
- Siguiente paso: revisión humana del título y la descripción generados; después corregir mediante `PATCH /semantic-nodes/{node_id}` o aceptar el nodo con `status: accepted`.
- `POST /semantic-network/relationships/build` validado con 40 nodos registrados: 96 relaciones calculadas a partir de 836 aristas fuente; migración `f3c4d5e6f7a8` aplicada.
- `POST /semantic-network/export/graphml` exporta la meta-red persistida con atributos auditables y aislados a `s3/graphs/graphml/<scope>/semantic_network_<projection>.graphml`.
- Validación real del GraphML: 40 nodos, 96 relaciones, 20 aislados y descarga pública `HTTP 200`.

- [x] Primer experimento de coocurrencia por `(document_id, sentence_id)`
- [x] Nodos definidos por `canonical_id`; menciones repetidas en una oración cuentan una sola presencia
- [x] Matriz de incidencia oración–nodo y adyacencia sparse simétrica
- [x] Red plana única de CHAR, LOC, PRAC, INFRA y RUL; eliminadas capas/bloques L2
- [x] Exportaciones CSV/Matrix Market con observaciones auditables
- [x] Visualización de G₃ (`peso >= 3`) en PNG, HTML interactivo y GraphML
- [x] Matrices regeneradas después de aplicar resolución v2: 523 nodos y 1.216 aristas
- [x] Visualización G₁ completa: peso mínimo 1, 523 nodos, 1.216 aristas y 28 aislados
- [x] Visualizador: aislados preservados, etiquetas bajo demanda en HTML y top 25 en figuras estáticas
- [x] Contexto de cada arista compuesto desde sus menciones, compatible con contextos distintos dentro de una oración
- [x] Relaciones intra-categoría explícitas (incluidas CHAR–CHAR y LOC–LOC)
- [x] `POST /analysis/network` para corpus completo o incubadora
- [x] Body de red con `incubator_number` y `language`, ambos con valor concreto o `"all"`
- [x] Intersección AND de incubadora/idioma y artefactos separados por combinación
- [x] `GET /analysis/network/latest` para lectura sin recálculo
- [x] `POST /documents/{id}/network` para inspección puntual
- [x] Artefactos oficiales por formato y scope; publicación restringida a `/files/graphs`
- [x] Persistencia simplificada a GraphML, JSON de metadatos y CSV canónicos
- [x] Escritura atómica y bloqueo por destino para evitar resultados parciales/concurrentes
- [x] Validación real: 78 documentos, 41.148 menciones, red G₁ de 16.527 nodos y 45.866 aristas
- [x] Suite automatizada: 47 pruebas exitosas
- [x] Proyección versionada `prac-infra-rul-v2` centrada en PRAC, INFRA y RUL
- [x] Seis relaciones: PRAC–PRAC, PRAC–INFRA, PRAC–RUL, INFRA–INFRA, INFRA–RUL y RUL–RUL
- [x] Nueve vistas derivadas sin recalcular la coocurrencia maestra
- [x] Evidencia normalizada oración–entidad con CHAR/LOC contextuales preservados en PostgreSQL
- [x] Endpoint paginado de evidencia por arista consultado bajo demanda en PostgreSQL
- [x] Validación real: 9.518 nodos, 13.196 aristas, 10.310 oraciones y 14.657 observaciones
- [x] Suite automatizada ampliada: 57 pruebas exitosas
- [x] Contrato `construction` discriminado y retrocompatible en la proyección tipada
- [x] Método `document-recurrent-core-v1` por recurrencia documental de nodos
- [x] Pesos `sentence-count`, `document-count`, `fractional` y `fractional-document`
- [x] Auditoría calculada de nodos/aristas excluidos y soporte contextual independiente
- [x] Resúmenes all/main component × nueve vistas; GraphML canónico main-component/all
- [x] Suite automatizada ampliada: 63 pruebas exitosas
- [x] Ejecutar Leiden sobre el GraphML del backbone validado
- [x] Endpoint desacoplado de Leiden con semilla, resolución, pesos y caché
- [x] Exportación GraphML/CSV de comunidades compatible con Gephi

## Objetivo 9: Migración de almacenamiento de grafos a `s3/graphs/` ✅

**Fecha:** 03 Sep 2026

- [x] Nueva tabla `sentences` con `(document_id, sentence_id, text)`
- [x] `src/models/sentences.py` y `src/models/sentences_repo.py`
- [x] Persistir oraciones durante `POST /documents/{id}/fuzzy-matching` y eliminarlas al revertir
- [x] Endpoint de evidencia por arista consulta PostgreSQL en lugar de CSV
- [x] Migración Alembic `d7e8f9a0b1c2_add_sentences_table.py`
- [x] `src/analysis/graph_paths.py` con nombres oficiales estables y parámetros en JSON
- [x] `src/analysis/graph_export.py` para exportación mínima GraphML + CSV + JSON
- [x] `src/analysis/backbone.py` con `export_backbone_to_files`
- [x] `src/analysis/leiden.py` acepta `base_name` y exporta `_communities.csv` y `_members.csv`
- [x] `src/services/network.py` reescrito para `s3/graphs/`, escritura atómica y rutas relativas
- [x] `src/config.py` con `STORAGE_GRAPHS` y alias legado `STORAGE_NETWORK`
- [x] `src/api/main.py` monta `/files/graphs` y conserva `/files/networks` como legado
- [x] `src/api/schemas/network.py` conserva campos adicionales de metadatos
- [x] Suite ampliada a 81 pruebas: 79 pasan y 2 se omiten sin dependencias Leiden

## Objetivo 10: Nodos semánticos para la meta-red 🔧

- [x] Prompt experto para título y descripción internos: `data/prompts/semantic_node_prompt.md`
- [x] Modelo y migración para nodos, miembros, procedencia y soporte por incubadora
- [x] Consulta de partición Leiden y hash del GraphML exacto
- [x] Promoción explícita e idempotente de una comunidad a nodo semántico
- [x] Consulta, listado, edición y generación LLM de título y descripción
- [x] Aplicar las migraciones y validar los endpoints contra PostgreSQL y Claude en Docker
- [x] Limitar la meta-red a meta-nodes aceptados y registrados; las comunidades no promovidas quedan fuera
- [x] Definir e implementar conexiones intercluster deterministas: basta una arista fuente positiva entre miembros de dos meta-nodes distintos; el peso es la suma de los pesos fuente
- [x] Definición matemática `data/prompts/meta_network_relationships_math.md`
- [x] Instantánea de aristas fuente y agregación SQL de relaciones intercluster
- [x] `POST /semantic-network/relationships/build` y consulta de relaciones
- [x] Exportación GraphML de la meta-red
- [ ] Regenerar backbone y Leiden oficiales para `prac-infra-rul-v2`; volver a
  vincular los meta-nodes con el nuevo `clustering_sha256`
- [ ] Revisión humana y aceptación de los títulos/descripciones de los meta-nodes
- [ ] Prompt editorial separado para describir conexiones ya calculadas
