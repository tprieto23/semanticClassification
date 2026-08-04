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
| GOV | Instrumentos de gobernanza, políticas, normas, acuerdos |

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
- [x] `POST /documents/{id}/extract-entities` — endpoint que extrae y persiste entidades en DB
- [x] `.env` — variable `ANTHROPIC_API_KEY` (completada por el usuario)
- [x] `requirements.txt` — dependencia `anthropic` (removido spacy/langdetect)
- [x] `src/services/documents.py` — `extraer_entidades_de_documento()` persiste entidades en DB (opción C)
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

### Línea base histórica probada

- [x] La versión anterior extrajo 133 entidades en un documento de prueba.
- [x] Persistencia y respuesta HTTP funcionaron con el esquema anterior.
- [ ] Repetir el piloto con el esquema vigente de cinco etiquetas y sin catálogos.

## Objetivos 5–8: Vectores, matrices, grafos, métricas ⏳

- [ ] Sin definir

## Status de sesión — Jul 27 2026

**Stack actual:**
- Conversión: PyMuPDF (fast path) + Docling OCR (fallback)
- Limpieza estructural: regex + ftfy + markdown-it-py
- Limpieza lingüística: Anthropic Claude
- NER: Anthropic Claude few-shot con prompt externo, ejemplos curados y tool schema (sin catálogos)
- Prompts NER: `data/prompts/ner_prompt.md` (system) y `data/prompts/ner_user_prompt.md` (user template)
- Cliente LLM compartido: `src/services/llm_client.py`
- DB: PostgreSQL 16 + pgvector
- 31 documentos en DB (varios en cleaned)

**Etiquetas NER:** 5 — CHAR, LOC, INFRA, GOV, PRAC

**Cambios recientes:**
- Catálogos eliminados: la extracción NER ahora es en dos fases (fase 1: prompt puro, fase 2: filtro futuro sin catálogos tradicionales).
- ACT eliminado: objetivos, visiones e intenciones no son entidades por sí mismos; las entidades nominales autónomas contenidas en ellos conservan una de las cinco etiquetas válidas.
- `src/services/ner.py`: sin carga de catálogos, JSON de entrada simplificado (`document_id`, `title`, `text`), salida parseada con `label`, `text`, `context`, `ambiguity`.
- `src/models/entities.py`: sin FKs a catálogos; conserva `category`, `text`, offsets, `context` y `ambiguity`.
- Offsets restaurados: el backend calcula posiciones absolutas, las persiste como `position_start`/`position_end` y las expone como `start`/`end`.
- `src/api/schemas/entities.py`: simplificado a `text`, `category`, `context`, `ambiguity`.
- Migración de eliminación de tablas y FKs de catálogos aplicada.
- Instrucción de exhaustividad agregada al prompt ("recorre de principio a fin, ante duda anota").
- `max_tokens` en 16384.

**Problema activo:**
- El endpoint `extract-entities` responde 200 pero con `entities: []`. El parseo de la respuesta del LLM falla (`json.JSONDecodeError`). Se agregó logging detallado para diagnosticar. Pendiente de debug.

**Siguiente objetivo:**
- Diagnosticar y corregir el parseo de la respuesta JSON del LLM.
- Probar extracción exitosa con el prompt de cinco etiquetas y sin catálogos.
- Objetivo 5: Vectores, matrices, grafos, métricas ⏳
