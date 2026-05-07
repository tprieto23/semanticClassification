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
- **Capa 3 (estructural por patrón — TOCs):**
  - **3a (dot leaders):** eliminar líneas con 5+ puntos consecutivos (`\.{5,}`) — típico de TOCs como "Introducción .................. 5"
  - **3b (bloques TOC numerados al inicio):** detectar y eliminar bloques en los primeros 15% del documento donde ≥5 líneas consecutivas, ≥70% empiezan con patrón numerado (`1.`, `1.1.`, `a.`, `I.`, `•`), y todas tienen ≤100 caracteres. Si hay un header `CONTENIDO`/`ÍNDICE`/`TABLE OF CONTENTS` justo antes del bloque, también se elimina.
- **Capa 4 (editorial por contenido — implementada):**
  - **4a (URLs y emails):** eliminar todas las URLs (`https?://...`, `www....`) y emails (`x@y.z`) en cualquier parte del texto (inline o líneas completas). Aplica siempre.
  - **4b (créditos editoriales con extensión B1):** detectar bloques al inicio (primeros 15%) o final (últimos 5%) donde ≥2 líneas tienen keyword editorial (`Autor:`, `Diseño:`, `ISBN`, `Editor:`, `Coordinación:`, `Revisión técnica:`, `Citar como`, `Editado por ©`, etc.) cercanas (≤3 líneas entre sí). **Extensión B1:** después del último keyword detectado, extender el bloque hacia adelante hasta encontrar 5 líneas consecutivas sin keyword (parar antes de incluir esa 5ª línea), o un párrafo narrativo, o un título de sección. Esto preserva listas de instituciones firmantes que vienen después del bloque editorial.
  - **4c (portadas en MAYÚSCULAS):** detectar bloques de ≥4 líneas consecutivas (con tolerancia a 1 línea vacía) en los primeros 5% del documento donde todas las letras son MAYÚSCULAS.
  - **4d (agradecimientos):** detectar header explícito `AGRADECIMIENTOS`/`ACKNOWLEDGEMENTS`/`RECONOCIMIENTOS` y eliminar el bloque siguiente hasta el próximo título de sección (numerado o MAYÚSCULAS), o hasta 50 líneas máximo.
- **Re-normalización al final de Capa 4:** colapsar espacios y tabs múltiples + strip por línea + colapsar 3+ saltos de línea. Necesario porque eliminar URLs/emails inline puede dejar dobles espacios.
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

**Skip de documentos cortos:** Capa 2 (incluyendo 2a, 2b y 2c), Capa 3b (bloques TOC), y Capa 4 (4b/4c/4d) se saltan si el doc tiene < 200 líneas no vacías. Capa 3a (dot leaders) y Capa 4a (URLs/emails) se aplican siempre porque son inequívocas.

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
- ✅ Capa 1 + 2 + 3 sobre 28 docs: avg 5.54% reducción (max 14.04%). Capa 3 agregó: 21 dot leaders + 5 bloques TOC + 122 líneas TOC eliminadas en 6/28 archivos. 0 falsos positivos.
- ✅ Capa 1 + 2 + 3 + 4 (B1) sobre 28 docs: **avg 7.01% reducción** (max 16.55%). Capa 4 agregó: 305 URLs + 47 emails + 89 líneas portada MAYÚSCULAS + 62 líneas de créditos + 45 líneas agradecimientos en 22/28 archivos. Versión B1 (extensión por threshold de 5 líneas sin keyword) preserva listas de instituciones firmantes que vienen después del bloque editorial puro.
- ✅ Métricas por documento guardadas en DB (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB con detalle por capa: `layer1.rules_applied`, `layer2.headers_detected`, `layer2c.sentences_rejoined`, `layer3.dot_leader_lines_removed`, `layer4.urls_removed`, `layer4.credit_blocks_removed`, etc.).
- ✅ Endpoint con `?dry_run=true` para auditar sin efectos colaterales.
- ⚠️ Reglas hechas a mano: no detecta ruido nuevo automáticamente, hay que iterar mirando casos.
- ⚠️ Capa 4 con B1 deja 4-5 líneas residuales después del bloque editorial puro (típicamente subtítulos como "AGRADECEMOS LA PARTICIPACIÓN DE:" + 3 líneas). Trade-off aceptado para preservar listas de instituciones firmantes que aparecen después.
- ⚠️ Capa 4b NO captura líneas-crédito sueltas que no estén en bloque (1 keyword aislada). Ejemplo: una línea `Editado por:` aislada en medio del cuerpo no se elimina. Comportamiento intencional para no destruir contenido.

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

---

### 2026-05-05 - NER: spaCy con modelos monolingües (Fase 1 del Objetivo 4)

**Contexto:**
Para el Objetivo 4 (clasificación de entidades) necesitábamos empezar por extraer entidades nombradas del corpus. El corpus es bilingüe (español + inglés). Hasta ahora tenemos 28 documentos limpios con Capa 1+2+2c+3+4.

**Opciones consideradas:**
1. **spaCy** (modelos monolingües es_core_news_sm + en_core_web_sm): rápido, local, deterministico, bien documentado.
2. **Transformers (Hugging Face)** con modelo multilingüe (xlm-roberta): más preciso potencialmente pero mucho más lento, requiere GPU para ser práctico, modelos de ~1GB+.
3. **Flair**: bueno para NER pero menos maduro en español.
4. **Stanza (Stanford NLP)**: bueno pero más lento que spaCy.

**Decisión:**
- **Fase 1 (prototipo):** spaCy con `es_core_news_sm` y `en_core_web_sm`.
- **Estrategia bilingüe:** detectar idioma del documento con `langdetect`, procesar con el modelo correspondiente.
- **Fase 1 guarda etiquetas spaCy originales** (PER, ORG, LOC, GPE, MISC) en la columna `category`. El mapeo a las 9 categorías del proyecto (COMUNIDAD, INSTITUCIÓN, LUGAR, etc.) se hará en una fase posterior tras evaluar calidad.
- **Filtros de falsos positivos estructurales:** lista negra de palabras comunes de títulos/secciones ("PLAN", "CRÉDITOS", "PROYECTO", "INTRODUCCIÓN", etc.) para evitar que el Ner etiquete estructura del documento como entidades.
- **Se extrae contexto y oración** para cada entidad, facilitando análisis posterior.

**Librerías:**
- `spacy>=3.7.0`
- `langdetect==1.0.9`
- Modelos: `es_core_news_sm`, `en_core_web_sm`

**Implementación:**
- Servicio: `src/services/ner.py`
- Endpoint: `POST /documents/{document_id}/extract-entities`
- Requiere documento en status `cleaned` o `processed`
- Guarda en tabla `entities` con metadata JSONB (`lang`, `sentence`, `source_ner`)
- Re-extracción idempotente (borra entidades previas del documento)
- Actualiza `documents.status = 'processed'`

**Resultados sobre corpus (prototipo):**

| Documento | Idioma | Total | ORG | LOC | PER | MISC |
|---|---|---:|---:|---:|---:|---:|
| AGRAP Plan de Acción | es | 449 | 134 | 89 | 45 | 181 |
| WWF UK PACT | es | 255 | 50 | 90 | 42 | 73 |
| Coalición Producción Sostenible | es | 418 | 84 | 120 | 36 | 178 |

**Calidad observada:**
- ✅ Entidades correctas: WWF, TFA, Climate Group, Gobierno de Reino Unido, Madre de Dios, Amazonía Peruana, Earthworm Foundation, NDPE, nombres de personas individuales.
- ⚠️ Falsos positivos: palabras estructurales residuales ("Editor", "Diseño" — de créditos no eliminados por Capa 4), conjunciones como "Además" clasificadas como PER.
- ⚠️ Delimitación incorrecta: spaCy agrupa múltiples nombres de personas en listas verticales como una sola entidad PER; incluye texto adyacente ("Amazonía Peruana La presente publicación").
- ⚠️ Clasificación spaCy imperfecta: "Perú" a veces clasificado como PER en vez de LOC/GPE; "Coalición" como LOC.

**Consecuencias:**
- ✅ Pipeline end-to-end funcional: cleaned text → entities en DB.
- ✅ No requiere GPU, corre localmente.
- ✅ Rápido (~1-2 segundos por documento).
- ⚠️ Calidad suficiente para prototipo pero requiere iteración antes de usar para análisis crítico.
- ⚠️ Mejora de limpieza (Capa 4+) podría reducir falsos positivos estructurales significativamente.

---

### 2026-05-05 - Fase 2 del NER: Clasificación en 9 categorías del proyecto

**Contexto:**
Tras completar la Fase 1 (NER genérico con spaCy) y validar el corpus limpio, se necesitaba mapear las etiquetas spaCy (ORG, LOC, PER, MISC, etc.) a las 9 categorías del proyecto: COMUNIDAD, INSTITUCIÓN, LUGAR, PRÁCTICA, INFRAESTRUCTURA, VALOR_ECOLÓGICO, NARRATIVA, ACTOR, ACCIÓN.

**Decisiones del proyecto:**
1. **Una entidad puede tener múltiples categorías** → se guardan como entidades separadas con categorías distintas
2. **MISC no se descartan** → van a una categoría temporal `MISC_Spacy` para revisión manual futura
3. **Enfoque híbrido pragmático** + modelos (BERT, RoBERTa) a futuro
4. **NARRATIVA y PRÁCTICA:** spaCy no las detecta bien, se dejan para método futuro

**Opciones consideradas:**
1. **Reglas deterministas:** rápido, controlable, pero limitado a keywords.
2. **LLM (GPT/Claude):** entiende contexto, pero no determinista y costoso.
3. **Híbrido recomendado:** reglas para casos claros + revisión para ambiguos + MISC_Spacy para revisión manual.

**Decisión:**
- **Servicio `src/services/entity_classifier.py`** con:
  - Mapeo base: ORG→[INSTITUCIÓN, COMUNIDAD], LOC→[LUGAR, INSTITUCIÓN], PER→[ACTOR, COMUNIDAD], MISC→[MISC_Spacy]
  - Reglas de keywords por categoría (40+ patrones regex)
  - Protección contra falsos positivos de spaCy ("Según", "Además", "ganadería" como PER)
  - Exclusiones para evitar sobre-clasificación
- **MISC_Spacy como categoría temporal:** entidades MISC que no coinciden con ninguna keyword se guardan ahí para revisión manual
- **Endpoint actualizado:** `POST /documents/{id}/extract-entities` ahora guarda `project_category` en `entities.category` y la etiqueta spaCy original en `metadata_.spacy_label`

**Resultados de prueba (Documento AGRAP):**

| Categoría | Cantidad |
|---|---|
| MISC_Spacy | 150 |
| INSTITUCIÓN | 148 |
| LUGAR | 93 |
| ACTOR | 39 |
| COMUNIDAD | 8 |
| PRÁCTICA | 7 |
| NARRATIVA | 4 |

**Calidad observada:**
- ✅ Instituciones correctas: WWF, TFA, Climate Group, Gobierno de Reino Unido, Ministerio de Ambiente
- ✅ Lugares correctos: Madre de Dios, Perú, Amazonía Peruana, San Martín
- ✅ Actores correctos: Jorge Sáenz Rabanal, Nelson Gutiérrez
- ✅ Comunidades correctas: Mesa Boliviana de Carne Sostenible, Escuelas de Campo
- ⚠️ Falsos positivos de spaCy ahora protegidos: "Según", "Además", "ganadería" → MISC_Spacy
- ⚠️ ~33% van a MISC_Spacy (esperado: son entidades ambiguas que requieren revisión manual)

**Consecuencias:**
- ✅ Clasificación automática funcional para ~67% de entidades
- ✅ MISC_Spacy permite revisión manual sin pérdida de información
- ⚠️ Reglas de keywords son frágiles: nuevas entidades requieren agregar patrones
- ⚠️ NARRATIVA y PRÁCTICA casi no se detectan (spaCy no las etiqueta)
- 🔄 Próximo paso: revisión manual de MISC_Spacy para entrenar un modelo de clasificación (BERT/RoBERTa)

---

### 2026-05-05 - Corrección crítica en Capa 2b: proteger oraciones narrativas repetidas

**Contexto:**
Durante la validación manual de Capa 4 sobre los 3 documentos de mayor reducción, se descubrió que la heurística de Capa 2b (headers/footers repetidos) estaba eliminando **oraciones narrativas completas** en documentos tipo brochure/díptico. En el Proforest Reporte se eliminó contenido como:
> "Es posible obtener los productos básicos agrarios de una manera que responda a la creciente demanda global..."

Esto pasaba porque el texto aparecía ≥3 veces (formato de brochure con páginas repetidas) y cumplía todas las heurísticas de header: longitud 15-150 chars, no puntuación interna, no empieza con minúscula, no es ítem de lista.

**Diagnóstico:**
La heurística `_is_header_candidate` no distinguía entre un header corto como "Metodología" y una oración narrativa de 15 palabras que se repite en múltiples páginas.

**Decisión:**
Agregar en `_is_header_candidate` una regla: **si la línea tiene más de 10 palabras, NO es header.** Los headers reales rara vez superan las 10 palabras; las oraciones narrativas sí.

**Resultados tras corrección (28 documentos):**

| Métrica | Antes | Después |
|---|---|---|
| Reducción promedio | 7.09% | **5.32%** |
| Proforest Reporte | 16.44% | **16.55%** (contenido restaurado, solo headers reales eliminados) |
| DIPTICO-EARTHWORM | 14.78% | **7.49%** (gran parte era contenido narrativo) |
| Guía AGRAP | 11.91% | **11.73%** (headers más precisos) |

**Consecuencias:**
- ✅ Se preserva contenido narrativo valioso en brochures/dípticos
- ✅ Los headers reales (≤10 palabras) siguen eliminándose correctamente
- ⚠️ Trade-off: headers largos repetidos (>10 palabras) ya no se eliminan. Ej: "ENFOQUE DE ALTOS VALORES DE CONSERVACIÓN (AVC) Y ALTAS RESERVAS DE CARBONO (ARC)" en el DIPTICO. Aceptado como trade-off conservador.
- ⚠️ Los números de página y TOCs siguen eliminándose por otras capas (2a, 3a, 3b)

---

### 2026-05-05 - Capa 4: sub-reglas 4e (contactos) y 4f (placeholders)

**Contexto:**
Durante la validación manual del Proforest Reporte, se identificaron tres tipos de ruido residual que las capas 1-4 no eliminaban:
1. **Footers de contacto:** `Proforest Latinoamérica S.A.S.| +57 (602) 3966477 | latinoamerica@proforest.net | www.proforest.net` (11 veces en el mismo documento)
2. **Líneas de contacto sueltas:** `T: +57 (602) 3966477`, `Oficina Regional Latinoamérica`, direcciones postales (`Calle. 11 # 100-121 Of 203`)
3. **Placeholders de MS Word:** `Error! Bookmark not defined`, `Error! Reference source not found`, `Main Title Subtitle Description`

**Opciones consideradas:**
1. **Agregar a Capa 2b:** los footers con pipe se repiten ≥3 veces, pero no cumplen la heurística de header (contienen caracteres especiales, emails, etc.).
2. **Nuevas sub-reglas en Capa 4:** crear 4e (contactos) y 4f (placeholders) como reglas dedicadas.
3. **Capa separada (Capa 5):** innecesario, son pocos casos y son ruido editorial.

**Decisión:**
Agregar sub-reglas **4e** y **4f** dentro de `clean_text_layer4`:

- **4e (contactos):** eliminar líneas que sean predominantemente información de contacto:
  - Líneas con prefijo explícito (`T:`, `Tel:`, `E:`, `Email:`, `Contacto:`) + teléfono/email
  - Líneas con `Oficina Regional` / `Oficina Central` como header standalone
  - Líneas con dirección postal (`Calle.`, `Av.`, `Avenida`, `Jr.` + `#` + `Of.`)
  - Líneas cortas con pipe `|` + teléfono (footer típico)
  - Líneas cortas (<40 chars) que son solo un número de teléfono
  - **Protección:** solo líneas ≤150 caracteres (evitar eliminar texto narrativo que mencione un teléfono).

- **4f (placeholders):**
  - Eliminar líneas exactas: `Main Title Subtitle Description`
  - Eliminar inline: `Error! Bookmark not defined`, `Error! Reference source not found`
  - **Manejo multi-línea:** cuando "Error!" está en línea N y "Reference source not found" en línea N+1, eliminar ambas partes.

**Resultados sobre corpus (28 documentos):**

| Métrica | Valor |
|---|---|
| Líneas de contacto eliminadas | 23 |
| Placeholders eliminados | 5 |
| Documentos afectados | 6/28 |
| Documento top (Proforest) | 19 contactos + 5 placeholders |

**Consecuencias:**
- ✅ Footers de contacto repetidos eliminados correctamente
- ✅ Placeholders de MS Word eliminados (incluyendo multi-línea)
- ✅ Líneas de dirección postal eliminadas
- ⚠️ Líneas como `E:` (prefijo de email sin dirección) pueden quedar residuales si el email fue eliminado por 4a

---

### 2026-05-06 - Aplicación de correcciones manuales al dataset de entidades

**Contexto:**
La usuaria revisó manualmente 200 entidades MISC_Spacy en un CSV. Era necesario aplicar esas correcciones al dataset completo de 14,812 entidades de forma sistemática.

**Opciones consideradas:**
1. **Editar archivos JSON individuales:** muy laborioso y propenso a errores.
2. **Script de correcciones centralizado:** leer el CSV revisado, construir un mapping, aplicar al `_all_entities.json`.
3. **Corrección directa en DB:** requeriría conexión a PostgreSQL y sería menos reproducible.

**Decisión:**
Script `apply_corrections.py` con lógica de 3 pasos:
1. **Descartar:** textos con `proposed_category == "No es entidad"` se eliminan del dataset.
2. **Corregir manual:** textos con categoría asignada y/o `full_entity_name` diferente se actualizan.
3. **Normalizar global:** reglas basadas en las notas del CSV (ej: "cada vez que diga 'Solidaridad' → 'Solidaridad Network'") se aplican a TODO el dataset, no solo a las entidades del CSV.

**Mapeo de categorías del usuario:**
- "ORGANIZACION/ACTOR/AGENTE" → "INSTITUCIÓN"

**Resultados:**
- 170 textos únicos descartados (1,131 ocurrencias eliminadas)
- 354 entidades corregidas manualmente
- 4 entidades normalizadas automáticamente por reglas globales
- Dataset final: 13,681 entidades

**Consecuencias:**
- ✅ Dataset corregido reproducible desde el CSV fuente
- ✅ Normalizaciones globales evitan inconsistencias
- ⚠️ Algunas entidades del CSV tenían `proposed_category` vacío pero `notes == "No es entidad"` → se tuvo que considerar ambas columnas para el descarte

---

### 2026-05-06 - Entrenamiento de embeddings con sentence-transformers

**Contexto:**
Con el dataset corregido (6,510 entidades únicas, 4,125 con categoría válida), se quería entrenar un modelo de embeddings para que entidades de la misma categoría tengan vectores similares.

**Opciones consideradas:**
1. **Fine-tuning de BERT/RoBERTa con clasificación:** requiere más datos y es más complejo.
2. **sentence-transformers con BatchHardTripletLoss:** entrena embeddings directamente, no requiere clasificación explícita, funciona bien con pocos ejemplos por clase.
3. **Zero-shot con modelo pre-entrenado:** no aprovecha las correcciones manuales.

**Decisión:**
sentence-transformers con `BatchHardTripletLoss` sobre `paraphrase-multilingual-MiniLM-L12-v2`.
- Loss: en cada batch, selecciona el positive más difícil y el negative más difícil para cada anchor.
- Entrada: texto de la entidad (sin categoría explícita, para evitar data leakage en inference).
- Label: ID de categoría.

**Hiperparámetros (iteración 1):**
- Base model: `paraphrase-multilingual-MiniLM-L12-v2`
- Loss: `BatchHardTripletLoss`
- Epochs: 1 (conservador para primera prueba)
- Batch size: 8 (reducido por OOM en MPS)
- Learning rate: 2e-5
- Warmup: 100 steps

**Resultados:**
- Loss final: 4.811 (bajó de 5.375)
- Tiempo: ~2.5 minutos en CPU
- Similitud intra-categoría (INSTITUCIÓN): 0.161
- Similitud intra-categoría (LUGAR): 0.259

**Consecuencias:**
- ✅ Modelo entrenado y guardado localmente
- ✅ 1 época no es suficiente para convergencia → se necesitan 3-5 épocas
- ⚠️ MPS en Mac tiene límite de memoria de 9GB → se entrenó en CPU (lento)
- ⚠️ Modelo pesa 1.8GB → no se commitea a git
- ⚠️ BatchHardTripletLoss requiere batches con múltiples ejemplos por categoría; con batch size 8 y 9 categorías, algunos batches pueden tener poca variedad
- ⚠️ Direcciones parciales sin patrón postal explícito (ej. `Campestre Towers |Cali| Colombia`) no se eliminan — aceptado como trade-off
