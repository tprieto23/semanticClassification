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

### Objetivo 3: Filtrar, limpiar y depurar textos ✅ CAPAS 1 + 2 + 3 (3a + 3b) COMPLETADAS
- [x] Definir tipos de ruido a eliminar (encoding, espacios, saltos de línea, headers/footers, créditos editoriales)
- [x] Definir qué conservar sí o sí (mayúsculas, acentos, stopwords, conectores, palabras cortas)
- [x] Decidir enfoque determinista (no IA) — ver `decisions.md` 2026-05-04
- [x] **Capa 1 (universal):** ftfy + unicodedata NFC + remover control chars + colapsar espacios + colapsar 3+ saltos de línea + strip por línea
- [x] **Capa 2a (números de página):** detectar y eliminar líneas tipo "23", "Página 5", "- 12 -"
- [x] **Capa 2b (headers/footers repetidos):** heurística combinada (frecuencia ≥ 3 + longitud 15-150 + sin puntuación interna + no empieza minúscula + no es ítem de lista)
- [x] **Capa 2c (re-unión de oraciones partidas por columnas):** une línea N con N+1 si N no termina en `.?!:;` + N+1 empieza con minúscula + N+1 no es ítem de lista + ambas dentro del mismo párrafo
- [x] **Skip de Capa 2** (2a, 2b y 2c) si documento tiene < 200 líneas no vacías (no estadísticamente confiable en docs cortos)
- [x] Servicio `src/services/cleaning.py` con `clean_text_layer1()`, `clean_text_layer2()` y `clean_text_layer2c()`
- [x] Endpoint `POST /documents/{id}/clean` con parámetro `?dry_run=true` (auditar sin efectos colaterales)
- [x] Migración Alembic con 4 columnas nuevas en `documents` (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB con detalle por capa)
- [x] 28 documentos limpiados con Capa 1+2+2c (avg reducción **4.92%**, max 9.93%; 1,540 páginas + 899 headers eliminados; **7,121 oraciones re-unidas**; 3 docs cortos saltaron Capa 2)
- [x] **Capa 3a (dot leaders):** eliminar líneas con 5+ puntos consecutivos (TOCs tipo "Título ........... 5")
- [x] **Capa 3b (bloques TOC numerados):** detectar y eliminar bloques en los primeros 15% del doc con ≥5 líneas consecutivas y ≥70% numeradas, incluido header `CONTENIDO/ÍNDICE` previo
- [x] 28 documentos re-limpiados con Capa 1+2+3 (avg reducción **5.54%**, max 14.04%; 21 dot leaders + 5 bloques TOC + 122 líneas TOC eliminadas en 6/28 archivos; 0 falsos positivos)
- [ ] **Capa 3 — iteraciones siguientes (pendiente):** eliminar bloques de créditos editoriales (Autor:, Diseño:, ISBN, Primera Edición), títulos de portada con palabras en MAYÚSCULAS partidas en líneas, URLs/emails sueltos

### Objetivo 4: Clasificar entidades relevantes ⏳ TBD
- [ ] Definir lista completa de categorías
- [ ] Decidir si entidad puede tener múltiples categorías
- [ ] Decidir si clasificación es por documento o global
- [ ] Implementar clasificación (IA/reglas)
- [ ] Definir metadata de cada entidad

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

- Validación manual de los 28 archivos limpiados con Capa 1+2+3 (especialmente los 6 con TOC eliminado)
- Decisión sobre próximas iteraciones de Capa 3 (créditos editoriales, portadas en MAYÚSCULAS, URLs/emails)

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
- [x] Servicio `src/services/cleaning.py` (Capa 1 + 2 + 2c + 3a + 3b)
- [x] Endpoint `POST /documents/{id}/clean` con métricas en DB y soporte `?dry_run=true`
- [x] Migración Alembic `1e6e4c60daa8` aplicada (4 columnas nuevas en `documents`)
- [x] 28 documentos del corpus limpiados con Capa 1 (avg 1.57%)
- [x] 28 documentos re-limpiados con Capa 1+2 (avg 4.92%, 1,540 páginas + 899 headers eliminados)
- [x] 28 documentos re-limpiados con Capa 1+2+2c (mismo % reducción + **7,121 oraciones re-unidas**)
- [x] 28 documentos re-limpiados con Capa 1+2+2c+3 (avg 5.54%, max 14.04%; +21 dot leaders + 122 líneas TOC eliminadas)

## Próximos pasos

1. **Validar manualmente** 2-3 archivos limpios con Capa 1+2+3 (sobre todo los que tuvieron TOC eliminado: `Análisis Instrumentos Financieros` 34 líneas TOC, `DIPTICO-CPS-EARTHWORM` 33 líneas, `Proforest Reporte` 21 dot leaders).
2. **Capa 3 — iteraciones siguientes:**
   - Detección de bloques de créditos al inicio/final que no fueron capturados por Capa 2 (heurísticas de "Autor:", "Diseño:", "ISBN", "Primera Edición")
   - Eliminación de URLs y emails sueltos
4. **Objetivo 4 (NER):** decidir librería (spaCy multilingüe? modelo dedicado?) y empezar clasificación de entidades. Considerar que el corpus es bilingüe (español + inglés).
5. **Objetivo 2 - 2da iteración (cuando aparezcan documentos que lo necesiten):**
   - OCR para PDFs escaneados / imágenes
   - Transcripción de audio
   - Extracción de audio + transcripción para video
