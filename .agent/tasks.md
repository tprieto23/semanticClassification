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

### Objetivo 3: Filtrar, limpiar y depurar textos ⏳ TBD
- [ ] Definir tipos de ruido a eliminar
- [ ] Definir qué conservar sí o sí
- [ ] Decidir si hay revisión humana
- [ ] Implementar limpieza con IA

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

- Procesamiento del corpus inicial (~30 archivos) — pendiente de implementar batch script

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

## Próximos pasos

1. **Procesar los ~25 archivos restantes del corpus** vía script bash + curl (Opción A definida en sesión 4)
   - Pendiente: confirmar ruta de la carpeta y formatos a filtrar
2. **Objetivo 3:** Limpieza/depuración de textos. Definir:
   - Tipos de ruido a eliminar (números de página, headers, URLs, etc.)
   - Si es 100% determinista (regex) o usa IA
   - Crear endpoint `POST /documents/{id}/clean`
3. **Objetivo 2 - 2da iteración (cuando aparezcan documentos que lo necesiten):**
   - OCR para PDFs escaneados / imágenes
   - Transcripción de audio
   - Extracción de audio + transcripción para video
