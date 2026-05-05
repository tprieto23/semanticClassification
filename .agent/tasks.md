# Tasks

## Roadmap - Objetivos del proyecto

### Objetivo 1: Organizar archivos no estructurados ✅ COMPLETADO
- [x] Definir estructura de carpetas (`data/raw/`, `data/processed/`, `data/output/`)
- [x] Decidir DB para metadata (PostgreSQL)
- [x] Implementar sistema de almacenamiento local (`POST /documents` recibe archivo y lo guarda en `data/raw/{document_id}/{filename}`)
- [x] Definir convención de nombres para archivos (UUID por documento como folder, nombre original preservado dentro)

### Objetivo 2: Convertir documentos a archivos planos ✅ COMPLETADO (1ra iteración)
- [x] Decidir enfoque (llamar librerías directamente, sin agente de IA en esta fase)
- [x] Seleccionar librerías/herramientas específicas (1ra iteración: PyMuPDF + python-docx)
- [x] Agregar dependencias a `requirements.txt`
- [x] Implementar conversión para PDF (PyMuPDF) en `src/services/conversion.py`
- [x] Implementar conversión para Word (python-docx) en `src/services/conversion.py`
- [x] Crear endpoint `POST /documents/{id}/process`
- [x] Guardar texto convertido en `data/processed/txt/{document_id}.txt`
- [x] Actualizar `documents.status = 'converted'` al finalizar (o `failed` si hay error)
- [x] Manejo de error 415 para formatos no soportados
- [x] Probado end-to-end con DOCX y PDF
- [ ] **Diferido a 2da iteración:** OCR para imágenes (pytesseract)
- [ ] **Diferido a 2da iteración:** transcripción para audio (faster-whisper)
- [ ] **Diferido a 2da iteración:** procesamiento de video (ffmpeg + faster-whisper)

### Objetivo 3: Filtrar, limpiar y depurar textos ✅ CAPAS 1 + 2 + 3 + 4 COMPLETADAS (con correcciones 2026-05-05)
- [x] Definir tipos de ruido a eliminar (encoding, espacios, saltos de línea, headers/footers, créditos editoriales)
- [x] Definir qué conservar sí o sí (mayúsculas, acentos, stopwords, conectores, palabras cortas)
- [x] Decidir enfoque determinista (no IA) — ver `decisions.md` 2026-05-04
- [x] **Capa 1 (universal):** ftfy + unicodedata NFC + remover control chars + colapsar espacios + colapsar 3+ saltos de línea + strip por línea
- [x] **Capa 2a (números de página):** detectar y eliminar líneas tipo "23", "Página 5", "- 12 -"
- [x] **Capa 2b (headers/footers repetidos):** heurística combinada (frecuencia ≥ 3 + longitud 15-150 + sin puntuación interna + no empieza minúscula + no es ítem de lista)
- [x] **CORRECCIÓN 2026-05-05:** proteger líneas con >10 palabras (eran contenido narrativo en brochures, no headers)
- [x] **Capa 2c (re-unión de oraciones partidas por columnas):** une línea N con N+1 si N no termina en `.?!:;` + N+1 empieza con minúscula + N+1 no es ítem de lista + ambas dentro del mismo párrafo
- [x] **Skip de Capa 2** (2a, 2b y 2c) si documento tiene < 200 líneas no vacías (no estadísticamente confiable en docs cortos)
- [x] Servicio `src/services/cleaning.py` con `clean_text_layer1()`, `clean_text_layer2()` y `clean_text_layer2c()`
- [x] Endpoint `POST /documents/{id}/clean` con parámetro `?dry_run=true` (auditar sin efectos colaterales)
- [x] Migración Alembic con 4 columnas nuevas en `documents` (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB con detalle por capa)
- [x] 28 documentos limpiados con Capa 1+2+2c (avg reducción **4.92%**, max 9.93%; 1,540 páginas + 899 headers eliminados; **7,121 oraciones re-unidas**; 3 docs cortos saltaron Capa 2)
- [x] **Capa 3a (dot leaders):** eliminar líneas con 5+ puntos consecutivos (TOCs tipo "Título ........... 5")
- [x] **Capa 3b (bloques TOC numerados):** detectar y eliminar bloques en los primeros 15% del doc con ≥5 líneas consecutivas y ≥70% numeradas, incluido header `CONTENIDO/ÍNDICE` previo
- [x] 28 documentos re-limpiados con Capa 1+2+3 (avg reducción **5.54%**, max 14.04%; 21 dot leaders + 5 bloques TOC + 122 líneas TOC eliminadas en 6/28 archivos; 0 falsos positivos)
- [x] **Capa 4a (URLs y emails):** eliminar todos los `https?://`, `www....`, `x@y.z` (inline o línea completa)
- [x] **Capa 4b (créditos editoriales con extensión B1):** detectar bloques al inicio/final con ≥2 keywords cercanas (Autor:, Diseño:, ISBN, etc.); extender hasta 5 líneas consecutivas sin keyword o párrafo narrativo
- [x] **Capa 4c (portadas en MAYÚSCULAS):** detectar bloques de ≥4 líneas consecutivas en MAYÚSCULAS en primeros 5% del doc
- [x] **Capa 4d (agradecimientos):** detectar header `AGRADECIMIENTOS`/`ACKNOWLEDGEMENTS`/`RECONOCIMIENTOS` y eliminar hasta el próximo título de sección
- [x] **Capa 4e (contactos/footers):** eliminar líneas de contacto (teléfonos, direcciones, emails, footers con pipe)
- [x] **Capa 4f (placeholders):** eliminar placeholders de MS Word (`Error! Bookmark not defined`, `Main Title Subtitle Description`, etc.) incluyendo multi-línea
- [x] 28 documentos re-limpiados con Capa 1+2+3+4 (avg reducción **5.49%**; 23 líneas de contacto + 5 placeholders + 312 URLs + 48 emails + 89 portada + 62 créditos + 45 agradecimientos eliminados en 22/28 archivos)
- [x] **RE-PROCESAMIENTO 2026-05-05:** corrección de bug crítico en Capa 2b + re-limpieza de todo el corpus
- [x] **Validación manual:** 3 documentos top-reducción revisados, bug crítico encontrado y corregido
- [ ] **Validación manual pendiente:** revisar los otros documentos donde Capa 4 actuó

### Objetivo 4: Clasificar entidades relevantes 🚧 EN PROGRESO (Fase 2 implementada)
- [x] Definir lista completa de categorías (9 categorías en methodology.md)
- [x] **Decisión:** entidad puede tener múltiples categorías → se guardan como entidades separadas
- [x] **Decisión:** clasificación es por aparición (contexto específico)
- [x] **Fase 1:** Implementar extracción NER con spaCy (es_core_news_sm + en_core_web_sm)
- [x] **Fase 1:** Crear endpoint `POST /documents/{id}/extract-entities`
- [x] **Fase 2:** Servicio `src/services/entity_classifier.py` con mapeo spaCy → 9 categorías
- [x] **Fase 2:** Reglas de keywords por categoría (40+ patrones) + protección contra falsos positivos
- [x] **Fase 2:** Categoría temporal `MISC_Spacy` para entidades no clasificables automáticamente
- [x] **Fase 2:** Endpoint actualizado guarda `project_category` en DB, `spacy_label` en metadata
- [x] **Fase 1:** Definir metadata de cada entidad (contexto, oración, posición, idioma, source_ner)
- [ ] **Fase 3:** Revisión manual de MISC_Spacy para entrenar modelo BERT/RoBERTa
- [ ] **Fase 3:** Implementar extracción de NARRATIVA y PRÁCTICA (método alternativo a NER)
- [ ] Evaluar calidad del NER sobre corpus completo (28 docs)
- [ ] Iterar filtros de falsos positivos estructurales

### Objetivo 5: Representar entidades mediante vectores ⏳ TBD
- [ ] Seleccionar modelo de embeddings
- [ ] Definir dimensiones del vector
- [ ] Decidir si embedding es por entidad o por aparición
- [ ] Implementar vectorización
- [ ] Guardar vectores en DB (pgvector)

### Objetivo 6: Construir matrices de adyacencia ⏳ TBD
- [ ] Definir qué es una "relación"
- [ ] Decidir si matriz es binaria o con pesos
- [ ] Decidir si matriz es por documento o global
- [ ] Definir tipos de relaciones
- [ ] Implementar generación de matrices

### Objetivo 7: Generar grafos de conocimiento ⏳ TBD
- [ ] Seleccionar librería (networkx, igraph, etc.)
- [ ] Decidir si grafo es dirigido o no
- [ ] Decidir si un solo grafo o múltiples
- [ ] Definir formato de exportación
- [ ] Implementar generación de grafos

### Objetivo 8: Calcular medidas de análisis de grafos ⏳ TBD
- [ ] Definir métricas a calcular
- [ ] Decidir si métricas son globales o por nodo
- [ ] Decidir frecuencia de cálculo
- [ ] Decidir si guardar historial
- [ ] Implementar cálculo de métricas

### Objetivo 9: Diseñar API ✅ COMPLETADO
- [x] Seleccionar framework (FastAPI)
- [x] Definir endpoints iniciales (/documents)
- [x] Decidir sin autenticación por ahora
- [x] Decidir Docker para local
- [x] OpenAPI para documentación
- [x] docker-compose.yml configurado
- [x] Dockerfile creado
- [x] API básica con endpoints `/` y `/health`
- [x] Implementar endpoint POST /documents
- [x] Implementar endpoint GET /documents
- [x] Implementar endpoint GET /documents/{id}
- [x] Implementar endpoint GET /entities
- [x] Implementar endpoint POST /documents/{id}/process
- [x] Implementar endpoint POST /documents/batch (upload + process múltiple)
- [ ] Implementar endpoints de graphs (futuro)
- [ ] Implementar endpoints de metrics (futuro)

### Objetivo 10: Base de datos ✅ COMPLETADO
- [x] PostgreSQL + pgvector
- [x] SQLAlchemy como ORM
- [x] Alembic para migraciones
- [x] Docker para DB
- [x] Backup manual
- [x] docker-compose.yml con servicio db
- [x] Definir schema completo
- [x] Crear migraciones iniciales
- [x] Configurar conexión desde API

## En progreso

- Validación manual de los 28 archivos limpiados con Capa 1+2+3+4 (especialmente los 22 donde Capa 4 actuó)
  - ✅ 3 documentos top-reducción validados (Proforest, DIPTICO, Guía AGRAP)
  - ✅ Bug crítico en Capa 2b encontrado y corregido (contenido narrativo eliminado)
  - ✅ Corpus re-procesado con corrección (avg reducción ahora 5.32%)
  - ⏳ 19 documentos restantes por validar
- Decidir si avanzar a Objetivo 4 (NER) o seguir refinando limpieza

## Completadas

- [x] Definir estructura de documentación (.agent/)
- [x] Documentar objetivos del proyecto
- [x] Decidir stack tecnológico principal
- [x] Configurar Docker (docker-compose.yml + Dockerfile)
- [x] Crear estructura de carpetas src/ y data/
- [x] API básica con 2 endpoints probada con Postman
- [x] Schema de DB con 5 modelos SQLAlchemy
- [x] Migración inicial Alembic aplicada (extensión `vector` + 5 tablas + índices)
- [x] Volúmenes de `migrations/` y `alembic.ini` agregados a docker-compose
- [x] Stack completo (DB + API) levantado y verificado en Docker
- [x] `POST /documents` recibe archivo real (multipart) y lo guarda en `data/raw/{id}/`
- [x] Servicio de conversión `src/services/conversion.py` (PDF + DOCX)
- [x] Endpoint `POST /documents/{id}/process` funcional
- [x] Pipeline upload → procesar probado end-to-end con PDF y DOCX
- [x] Pruebas manuales desde Postman con 5 archivos reales del corpus
- [x] Endpoint `POST /documents/batch` para subida y procesamiento múltiple
- [x] Servicio `src/services/cleaning.py` (Capa 1 + 2 + 2c + 3a + 3b + 4a + 4b + 4c + 4d)
- [x] Endpoint `POST /documents/{id}/clean` con métricas en DB y soporte `?dry_run=true`
- [x] Migración Alembic `1e6e4c60daa8` aplicada (4 columnas nuevas en `documents`)
- [x] 28 documentos del corpus limpiados con Capa 1 (avg 1.57%)
- [x] 28 documentos re-limpiados con Capa 1+2 (avg 4.92%, 1,540 páginas + 899 headers eliminados)
- [x] 28 documentos re-limpiados con Capa 1+2+2c (mismo % reducción + **7,121 oraciones re-unidas**)
- [x] 28 documentos re-limpiados con Capa 1+2+2c+3 (avg 5.54%, max 14.04%; +21 dot leaders + 122 líneas TOC eliminadas)
- [x] 28 documentos re-limpiados con Capa 1+2+3+4 (avg 7.01%, max 16.55%; +305 URLs + 47 emails + 89 portada + 62 créditos + 45 agradecimientos)

## Próximos pasos

1. **Validar manualmente** 2-3 archivos limpios con Capa 1+2+3+4 (sobre todo los de mayor reducción: `Proforest Reporte` 16.55%, `DIPTICO-CPS-EARTHWORM` 14.34%, `Año de Referencia` 11.80%).
2. **Iteraciones futuras de Capa 4 (si fuera necesario):**
   - Detección de bloques de créditos al inicio/final que no fueron capturados por Capa 2 (heurísticas de "Autor:", "Diseño:", "ISBN", "Primera Edición")
   - Eliminación de URLs y emails sueltos
4. **Objetivo 4 (NER):** decidir librería (spaCy multilingüe? modelo dedicado?) y empezar clasificación de entidades. Considerar que el corpus es bilingüe (español + inglés).
5. **Objetivo 2 - 2da iteración (cuando aparezcan documentos que lo necesiten):**
   - OCR para PDFs escaneados / imágenes
   - Transcripción de audio
   - Extracción de audio + transcripción para video
