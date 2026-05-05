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

### 2026-05-04 - Limpieza de textos: enfoque determinista por capas (1ra iteración Capa 1)

**Contexto:**
Para el Objetivo 3 (limpieza/depuración de textos `.txt` salidos de la conversión) había que decidir entre un enfoque determinista (regex + librerías de fix) o usar IA (LLM). Además, había que decidir qué se considera "ruido" y qué se preserva, dado que después del Objetivo 4 hace NER sobre estos textos.

**Decisiones acordadas con la usuaria:**
- **NO eliminar** stopwords, conectores, ni palabras cortas como "con", "de", "en". Son señal relacional para el NER posterior (entidad X "trabaja con" entidad Y).
- **NO hacer lowercase** ni quitar acentos. Mayúsculas y tildes son señal de entidad ("Río Magdalena" ≠ "rio magdalena").
- **SÍ eliminar** ruido editorial: actores que aparecen en créditos/colofón pero no en el discurso del documento, headers/footers repetidos, números de página, encoding roto, espacios sobrantes.
- **Corpus es bilingüe** español + inglés → priorizar herramientas multilingües.

**Opciones consideradas:**
1. **Determinista** (regex + ftfy + unicodedata): controlable, reproducible, gratis.
2. **IA (LLM con prompt de limpieza):** detecta ruido sin reglas pero no es determinista, riesgo de alucinación reformulando frases — problemático para análisis crítico de discurso.
3. **`clean-text`** (librería): hace lowercase y remueve puntuación por defecto — exactamente lo que NO queremos.

**Decisión:**
- Enfoque **determinista por capas**.
- **Capa 1 (universal, implementada):** ftfy (encoding) + unicodedata NFC + remover caracteres de control + colapsar espacios + colapsar 3+ saltos de línea a 2 + strip por línea.
- **Capa 2 (estructural, implementada — sub-iteraciones 2a + 2b + 2c):** eliminar líneas tipo número de página + detectar y eliminar headers/footers repetidos + re-unir oraciones partidas por columnas de PDF.
- **Capa 3 (editorial, primera iteración 3a + 3b implementada):**
  - **3a (dot leaders):** eliminar líneas con 5+ puntos consecutivos (`\.{5,}`) — típico de TOCs como "Introducción .................. 5"
  - **3b (bloques TOC numerados al inicio):** detectar y eliminar bloques en los primeros 15% del documento donde ≥5 líneas consecutivas, ≥70% empiezan con patrón numerado (`1.`, `1.1.`, `a.`, `I.`, `•`), y todas tienen ≤100 caracteres. Si hay un header `CONTENIDO`/`ÍNDICE`/`TABLE OF CONTENTS` justo antes del bloque, también se elimina.
- **Capa 3 (pendientes para próximas iteraciones):** eliminar bloques de créditos restantes (Autores, Diseño, ISBN, Primera Edición), portadas con palabras en MAYÚSCULAS partidas en líneas, URLs/emails sueltos.
- Estrategia iterativa: implementar Capa 1, correr sobre corpus real, evaluar, sumar Capa 2, repetir.

**Heurística de Capa 2b (header):** una línea es header si CUMPLE TODAS estas condiciones:
- Repetida ≥ 3 veces en el documento
- Longitud entre 15 y 150 caracteres
- No contiene `.`, `?`, `!` excepto al final
- No empieza con minúscula
- No es ítem de lista (`a)`, `1.`, `1)`, etc.)

**Heurística de Capa 2c (re-unión de oraciones):** unir línea N con N+1 si CUMPLE TODAS:
- Línea N **NO termina** en `.`, `?`, `!`, `:`, `;`
- Línea N+1 **empieza con minúscula**
- Línea N+1 **NO es ítem de lista** (`a)`, `1.`, `b)`, etc.)
- Ambas líneas son no vacías (no hay separación de párrafo entre ellas)

**Skip de documentos cortos:** Capa 2 (incluyendo 2a, 2b y 2c) y Capa 3b (bloques TOC) se saltan si el doc tiene < 200 líneas no vacías. Capa 3a (dot leaders) se aplica siempre porque es inequívoca.

**Protección contra falsos positivos en Capa 3b:** la heurística requiere que el bloque esté en los primeros 15% del documento Y tenga ≥5 líneas consecutivas con ≥70% numeradas. Esto correctamente NO eliminó casos donde la palabra "ÍNDICE/CONTENIDO" aparece como título de sección suelto seguido de texto narrativo (ej. `050c2005`, `9383e086`, `7d596b01`).

**Casos discutibles aceptados (riesgos asumidos):**
- Atribuciones `'Fuente: ...'` repetidas se eliminan en Capa 2 (originalmente se planeaban para Capa 3).
- Subtítulos de sección recurrentes (`'ALIMENTACIÓN DEL ANIMAL'`, `'Estiércol de vaca'`) se eliminan: aunque aporten información, no es fácil relacionarlos con las demás palabras del párrafo.
- Entidades territoriales con menciones tipo header (`'WWF Madre de Dios'`) se eliminan en este doc específico. Si en NER se detectan vacíos, se itera.

**Validación:** se implementó `?dry_run=true` en `POST /documents/{id}/clean` que devuelve métricas y headers detectados sin escribir archivos ni actualizar DB. Útil para auditar antes de aplicar.

**Librerías:**
- `ftfy==6.2.3` (encoding)
- `unicodedata` (stdlib)
- `re` (stdlib)

**Consecuencias:**
- ✅ Reproducible y debuggeable: las reglas son explícitas y se versionan en código.
- ✅ Sin riesgo de "alucinación" sobre el discurso original.
- ✅ Capa 1 sobre 28 docs: avg 1.57% reducción.
- ✅ Capa 1 + 2 (2a+2b) sobre 28 docs: avg 4.92% reducción (max 9.93%). 1,540 líneas de página + 899 líneas-header eliminadas.
- ✅ Capa 1 + 2 (2a+2b+2c) sobre 28 docs: **7,121 oraciones re-unidas** adicionalmente. La 2c no reduce caracteres (un `\n` se vuelve ` `), pero mejora estructura del texto para NER posterior — oraciones completas en vez de fragmentos por columnas.
- ✅ Capa 1 + 2 + 3 sobre 28 docs: **avg 5.54% reducción** (max 14.04%). Capa 3 agregó: 21 dot leaders + 5 bloques TOC + 122 líneas TOC eliminadas en 6/28 archivos que tenían TOC detectable. 0 falsos positivos en docs donde "ÍNDICE/CONTENIDO" era solo título de sección.
- ✅ Métricas por documento guardadas en DB (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB con detalle por capa: `layer1.rules_applied`, `layer2.headers_detected`, `layer2.pages_removed`, `layer2c.sentences_rejoined`, `layer3.dot_leader_lines_removed`, `layer3.toc_blocks_removed`, etc.).
- ✅ Endpoint con `?dry_run=true` para auditar sin efectos colaterales.
- ⚠️ Reglas hechas a mano: no detecta ruido nuevo automáticamente, hay que iterar mirando casos.
- ⚠️ Capa 2c no une títulos de portada con palabras en MAYÚSCULAS partidas en líneas (cada palabra empieza con mayúscula → no cumple el filtro). Esos casos son ruido editorial pendiente para próximas iteraciones de Capa 3.
- ⚠️ Capa 3 primera iteración (3a + 3b) implementada. Pendientes: bloques de créditos editoriales (Autores, Diseño, ISBN), portadas en MAYÚSCULAS, URLs/emails sueltos.

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
