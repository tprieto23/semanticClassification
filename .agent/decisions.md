# Technical Decisions (ADRs)

## Decisiones registradas

### 2026-04-27 - Base de datos: PostgreSQL + pgvector

**Contexto:**
Necesitábamos una base de datos que soportara:
- Metadata de documentos y entidades
- Búsqueda por similitud semántica (vectores)
- Relaciones entre entidades (grafos)
- Queries para dashboard

**Opciones consideradas:**
1. MongoDB (NoSQL) - Flexible pero sin búsqueda vectorial nativa
2. Bases vectoriales (Pinecone, Milvus, Qdrant) - Buenas para vectores pero no para grafos
3. Neo4j - Excelente para grafos, curva de aprendizaje
4. PostgreSQL + pgvector - Balance entre vectores, relaciones y SQL

**Decisión:**
PostgreSQL + pgvector

**Consecuencias:**
- ✅ Vectores + relaciones en la misma DB
- ✅ Búsqueda por similitud nativa
- ✅ SQL para queries complejas
- ✅ Open source, local, maduro
- ⚠️ Queries de grafos más lentas que Neo4j
- ⚠️ Escalar horizontalmente es más complejo

---

### 2026-04-27 - API: FastAPI

**Contexto:**
Necesitábamos un framework para exponer endpoints que el dashboard pueda consumir.

**Opciones consideradas:**
1. Flask - Simple pero menos moderno
2. FastAPI - Moderno, auto-documentado, asíncrono
3. Express (Node.js) - Requeriría cambiar de lenguaje

**Decisión:**
FastAPI

**Consecuencias:**
- ✅ Documentación OpenAPI automática
- ✅ Type hints nativos
- ✅ Asíncrono
- ✅ Popular en Python
- ⚠️ Curva de aprendizaje si el equipo no conoce

---

### 2026-04-27 - ORM: SQLAlchemy + Alembic

**Contexto:**
Necesitábamos un ORM para manejar la DB desde Python y un sistema de migraciones.

**Decisión:**
- SQLAlchemy como ORM
- Alembic para migraciones

**Consecuencias:**
- ✅ Ampliamente usado en ecosistema Python
- ✅ Compatible con FastAPI
- ✅ Alembic es el estándar para migraciones
- ⚠️ Configurar bien las relaciones

---

### 2026-04-27 - Arquitectura híbrida: DB + Archivos

**Contexto:**
No sabíamos si guardar vectores, matrices y grafos en DB o en archivos.

**Decisión:**
- **DB (PostgreSQL):** Metadata, entidades, relaciones, métricas, estados
- **Archivos:** Vectores crudos (.npy), matrices grandes (.parquet), grafos completos (.graphml)

**Consecuencias:**
- ✅ DB liviana para queries frecuentes
- ✅ Archivos para análisis pesado
- ✅ Dashboard consulta DB rápido
- ⚠️ Necesita coordinar DB ↔ archivos
- ⚠️ Backup debe incluir ambos

---

### 2026-04-27 - Docker para desarrollo local

**Contexto:**
Necesitábamos un entorno reproducible para desarrollar con PostgreSQL + pgvector y FastAPI.

**Opciones consideradas:**
1. Instalar todo local (Python, PostgreSQL, pgvector)
2. Docker con docker-compose
3. Máquinas virtuales

**Decisión:**
- PostgreSQL en Docker (imagen `pgvector/pgvector:pg16`)
- API en Docker (imagen custom desde Dockerfile)
- docker-compose para orquestar
- Volúmenes para persistencia de datos y hot-reload

**Consecuencias:**
- ✅ Entorno consistente entre desarrolladores
- ✅ Fácil de levantar/bajar (`docker-compose up/down`)
- ✅ Aislado del sistema local
- ✅ pgvector preinstalado (sin compilar)
- ✅ Hot-reload con volúmenes
- ⚠️ Curva de aprendizaje Docker
- ⚠️ Overhead de recursos

---

### 2026-04-29 - Conversión de documentos: PyMuPDF + python-docx (1ra iteración)

**Contexto:**
Para el Objetivo 2 (conversión de documentos no estructurados a texto plano) hay que decidir librerías por formato. El corpus puede incluir PDF, Word, imágenes, audio y video, pero conviene priorizar lo más común para no sobre-diseñar.

**Opciones consideradas (PDF):**
1. **PyMuPDF (`fitz`)** - Rápido, robusto con layouts complejos. Licencia AGPL.
2. **pdfplumber** - Mejor para tablas. Más lento. Licencia MIT.
3. **PyPDF2/pypdf** - Pure Python. Limitado en PDFs complejos.

**Opciones consideradas (Word):**
1. **python-docx** - Estándar, simple, solo `.docx`.
2. **antiword / LibreOffice headless** - Necesarios para `.doc` legacy. Diferido si aparecen.

**Opciones consideradas (OCR/audio/video):**
1. Tesseract / EasyOCR / PaddleOCR para imágenes
2. OpenAI Whisper / faster-whisper para audio
3. ffmpeg-python / moviepy para extraer audio de video

**Decisión:**
- **1ra iteración:** PyMuPDF (PDF) + python-docx (Word).
- **2da iteración (diferida):** OCR (sugerido: `pytesseract` con paquete de español), audio (sugerido: `faster-whisper`), video (sugerido: `ffmpeg-python` + `faster-whisper`).

**Razones:**
- PDF y Word cubren la mayoría del corpus documental típico.
- Permite tener pipeline funcional rápido sin instalar dependencias pesadas (Tesseract a nivel sistema, modelos de Whisper de varios GB).
- La licencia AGPL de PyMuPDF es aceptable para uso académico/investigación de este proyecto.
- OCR/audio/video se incorporan cuando aparezcan documentos que los necesiten.

**Consecuencias:**
- ✅ Pipeline funcional para la mayoría de documentos rápido
- ✅ Sin dependencias del sistema operativo en el Dockerfile
- ✅ Imagen Docker liviana
- ⚠️ Documentos escaneados (PDFs sin texto seleccionable) no se procesan hasta 2da iteración
- ⚠️ Audio/video no se procesan hasta 2da iteración
- ⚠️ Si el proyecto se vuelve cerrado/comercial, revisar licencia AGPL de PyMuPDF

---

### 2026-04-27 - Sin autenticación inicial

**Contexto:**
El proyecto inicia en local, sin necesidad de autenticación.

**Decisión:**
No implementar autenticación en la fase inicial. Registrar como deuda técnica.

**Consecuencias:**
- ✅ Desarrollo más rápido inicial
- ✅ Menos complejidad
- ⚠️ Necesitará refactor para agregar auth después
- ⚠️ No se puede exponer a internet sin auth
