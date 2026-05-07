# Session Context

## Última sesión

**Fecha:** 2026-05-06 (sesión 15)

**Trabajado en:**
- Aplicar correcciones manuales del CSV revisado por la usuaria al dataset completo
- Mejorar clasificador con nuevas reglas y protecciones contra falsos positivos
- Entrenar modelo de embeddings (iteración 1) con sentence-transformers
- Actualización de `.agent/`

**Resumen de la sesión:**

### Dataset corregido

1. **Revisión manual completada:** La usuaria revisó el CSV `_misc_spacy_for_review - _misc_spacy_for_review.csv` con 200 entidades.
2. **Script `apply_corrections.py`:**
   - Carga correcciones manuales del CSV
   - Descarta 170 textos únicos marcados como "No es entidad" (1,131 ocurrencias eliminadas)
   - Aplica 354 correcciones manuales (cambio de nombre + categoría)
   - Aplica normalizaciones globales automáticas (Solidaridad → Solidaridad Network, Alianza Ganadería → AGRAP, etc.)
   - Genera `_all_entities_corrected.json` (13,681 entidades) y `_entities_for_embeddings.json` (6,510 únicas)

3. **Distribución después de correcciones:**

| Categoría | Cantidad | % |
|---|---|---|
| LUGAR | 4,639 | 33.9% |
| MISC_Spacy | 3,516 | 25.7% |
| INSTITUCIÓN | 2,879 | 21.0% |
| ACTOR | 1,570 | 11.5% |
| NARRATIVA | 454 | 3.3% |
| PRÁCTICA | 210 | 1.5% |
| COMUNIDAD | 188 | 1.4% |
| ACCIÓN | 176 | 1.3% |
| INFRAESTRUCTURA | 41 | 0.3% |
| VALOR_ECOLÓGICO | 8 | 0.1% |

### Mejoras al clasificador

1. **`entity_classifier.py`:**
   - Protección ampliada contra falsos positivos comunes: "Madre", "Dios", "Además", "Uso", "Potencial", "Bovina", conectores y frases preposicionales
   - Nuevas keywords INSTITUCIÓN: Tropical Forest Alliance, The Nature Conservancy, TNC, MINAM, Solidaridad Network, Cooperativa Agraria CP Cacao, LandScale
   - Nuevas keywords NARRATIVA: Plan Nacional para el Desarrollo de la Cadena de Valor de Cacao, Política Nacional Forestal, Ley Forestal, Revolución Productiva, Bosques conservados y restaurados, Fomento de la ganadería, Ganadería Sostenible, AgroPerú y Agroideas

2. **`ner.py`:**
   - Ampliación de `STRUCTURAL_WORDS` con falsos positivos frecuentes que spaCy corta mal

### Entrenamiento de embeddings (iteración 1)

1. **Dataset para entrenamiento:** 4,125 entidades únicas con categoría válida (excluyendo MISC_Spacy), 9 categorías
2. **Modelo base:** `paraphrase-multilingual-MiniLM-L12-v2`
3. **Loss:** `BatchHardTripletLoss`
4. **Hiperparámetros:** 1 época, batch size 8, lr 2e-5, warmup 100
5. **Resultados:** Loss final 4.811 (bajó de 5.375)
6. **Problemas:** MPS OOM en Mac → se entrenó en CPU (muy lento, ~2.5 min por época)
7. **Modelo guardado:** `models/entity_embeddings/` (1.8GB, no commiteado)

### Decisiones

1. **Normalización de nombres:** Cuando una entidad tiene nombre completo conocido, siempre guardar el nombre completo (ej: "AGRAP" en vez de "Alianza por una Ganadería Regenerativa en la Amazonía Peruana")
2. **Descarte de entidades:** Las marcadas "No es entidad" en el CSV se descartan del dataset completo
3. **Categorías compuestas del usuario:** "ORGANIZACION/ACTOR/AGENTE" se mapea a "INSTITUCIÓN"
4. **No commitear modelos:** Los modelos entrenados son muy grandes (1.8GB), se ignoran en `.gitignore`

### Aprendizajes

- **Las correcciones manuales son fundamentales:** El clasificador rule-based clasifica bien lo obvio pero necesita supervisión humana para los casos difíciles
- **Normalización global es poderosa:** Una regla como "Solidaridad → Solidaridad Network" corrige docenas de instancias
- **sentence-transformers v5 cambió la API:** `SentenceTransformerTrainer` requiere `accelerate` y `datasets`, y `Trainer.train()` no acepta kwargs directos
- **MPS en Mac tiene límite de memoria:** `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` desactiva el límite pero puede causar inestabilidad del sistema
- **1 época no es suficiente:** Las similitudes intra-categoría son muy bajas (0.16-0.26), se necesitan 3-5 épocas mínimo

---

**Fecha:** 2026-05-05 (sesión 14)

**Trabajado en:**
- Implementación de Fase 2 del NER: clasificación de entidades en 9 categorías del proyecto
- Diseño de mapeo spaCy → categorías con reglas deterministas + heurísticas
- Creación de servicio `src/services/entity_classifier.py`
- Actualización del endpoint `/extract-entities` para usar clasificación
- Pruebas de calidad sobre documento AGRAP
- Actualización de `.agent/`

**Resumen de la sesión:**

### Decisiones del proyecto (definidas por la usuaria)

1. **Entidades con múltiples categorías:** se guardan como entidades separadas con categorías distintas (Opción 1)
2. **MISC no se descartan:** van a categoría temporal `MISC_Spacy` para revisión manual futura (Opción 3)
3. **NARRATIVA y PRÁCTICA:** se dejan para método futuro (no NER)
4. **Enfoque híbrido + modelos** (BERT, RoBERTa) a futuro

### Implementación

1. **`src/services/entity_classifier.py`:**
   - 9 categorías del proyecto + `MISC_Spacy` temporal
   - Mapeo base: ORG→[INSTITUCIÓN, COMUNIDAD], LOC→[LUGAR, INSTITUCIÓN], PER→[ACTOR, COMUNIDAD]
   - 40+ patrones regex de keywords por categoría
   - Protección contra falsos positivos de spaCy ("Según", "Además", "ganadería" como PER → MISC_Spacy)
   - Exclusiones para evitar sobre-clasificación

2. **`src/services/ner.py`:**
   - `ExtractedEntity` ahora incluye `project_category`
   - `extract_entities()` clasifica cada entidad tras extraerla

3. **`src/api/main.py`:**
   - Endpoint `/extract-entities` guarda `project_category` en `entities.category`
   - Etiqueta spaCy original guardada en `metadata_.spacy_label`
   - `by_label` en respuesta ahora muestra distribución por categorías del proyecto

### Resultados de prueba (Documento AGRAP)

| Categoría | Cantidad | % del total |
|---|---|---|
| MISC_Spacy | 150 | 33% |
| INSTITUCIÓN | 148 | 33% |
| LUGAR | 93 | 21% |
| ACTOR | 39 | 9% |
| COMUNIDAD | 8 | 2% |
| PRÁCTICA | 7 | 2% |
| NARRATIVA | 4 | 1% |

**Calidad:**
- ✅ Instituciones: WWF, TFA, Climate Group, Ministerio de Ambiente, ACOPAGRO (COMUNIDAD)
- ✅ Lugares: Madre de Dios, Perú, Amazonía Peruana, San Martín
- ✅ Actores: Jorge Sáenz Rabanal, Nelson Gutiérrez
- ✅ Falsos positivos protegidos: "Según", "Además", "ganadería" → MISC_Spacy
- ⚠️ ~33% a MISC_Spacy (esperado, requieren revisión manual)

### Aprendizajes

- **Las reglas de keywords funcionan para casos claros** (80% de ORG, LOC, PER) pero fallan con MISC
- **MISC_Spacy es una categoría valiosa:** no es "basura", es "pendiente de clasificar"
- **Nombres de personas como "Nelson Gutiérrez Carpio" funcionan bien con keywords explícitos**
- **El contexto sigue siendo clave:** la misma entidad puede cambiar de categoría según el párrafo

### Dataset completo generado

Corpus completo (28 documentos): **14,812 entidades**

| Categoría | Cantidad | % |
|---|---|---|
| LUGAR | 4,862 | 32.8% |
| MISC_Spacy | 4,654 | 31.4% |
| INSTITUCIÓN | 2,830 | 19.1% |
| ACTOR | 1,621 | 10.9% |
| NARRATIVA | 222 | 1.5% |
| PRÁCTICA | 210 | 1.4% |
| COMUNIDAD | 188 | 1.3% |
| ACCIÓN | 176 | 1.2% |
| INFRAESTRUCTURA | 41 | 0.3% |
| VALOR_ECOLÓGICO | 8 | 0.1% |

### Archivos generados para revisión manual

- `data/processed/entities/_misc_spacy_FOR_REVIEW.csv` (200 entidades)
- `data/processed/entities/_misc_spacy_filtered.json` (2,285 entidades únicas)
- `data/processed/entities/_all_entities.json` (14,812 entidades)
- `data/processed/entities/<doc_id>.json` (28 archivos por documento)

### Discusiones clave con la usuaria

1. **Entidades incompletas (spaCy corta nombres):**
   - Ej: "Global Forest Watch" en vez de "Global Forest Watch Pro"
   - Solución: columna `full_entity_name` en CSV para correcciones manuales
   - Futuro: post-procesamiento automático o modelo custom

2. **Stopwords/listas de filtrado:**
   - Las listas SOLO sirven para evitar que spaCy etiquete palabras comunes como entidades
   - Las palabras (conectores, adverbios) NUNCA se eliminan del texto ni del contexto
   - Son CRÍTICAS para construir relaciones entre entidades ("WWF trabaja CON comunidades")

### Pendiente para próxima sesión

1. **Revisión manual de MISC_Spacy:** usuario revisa `_misc_spacy_FOR_REVIEW.csv` (200 entidades)
   - Llenar `full_entity_name` si spaCy cortó la entidad
   - Llenar `proposed_category` para entidades válidas
   - Dejar vacío si no es entidad real
2. **Entrenar modelo BERT/RoBERTa** con las clasificaciones manuales
3. **Extracción de NARRATIVA y PRÁCTICA:** método alternativo (keyphrase extraction, topic modeling)
4. **Aplicar correcciones manuales** al dataset completo

---

**Fecha:** 2026-05-05 (sesión 13)

**Trabajado en:**
- Refinamiento de Capa 4: implementación de sub-reglas 4e (contactos/footers) y 4f (placeholders)
- Análisis programático del corpus para identificar patrones de contacto, direcciones y placeholders
- Corrección de regex para placeholders multi-línea ("Error!\nReference source not found")
- Re-procesamiento del corpus completo con las nuevas sub-reglas
- Validación visual del Proforest Reporte
- Actualización de `.agent/`

**Resumen de la sesión:**

### Problemas identificados en validación

El Proforest Reporte (16.55% reducción) contenía ruido residual no capturado por Capas 1-4:
1. **Footer repetido:** `Proforest Latinoamérica S.A.S.| +57 (602) 3966477 | latinoamerica@proforest.net | www.proforest.net` aparecía 11 veces
2. **Líneas de contacto:** `T: +57 (602) 3966477`, `Oficina Regional Latinoamérica`, `Calle. 11 # 100-121 Of 203`
3. **Placeholders de MS Word:** `Main Title Subtitle Description` (2 veces), `Error! Bookmark not defined` (inline), `Error! Reference source not found` (multi-línea)

### Implementación

1. **`src/services/cleaning.py`:**
   - Nuevas regex: `PHONE_RE`, `CONTACT_PREFIX_RE`, `ADDRESS_RE`, `OFFICE_HEADER_RE`, `TEMPLATE_PLACEHOLDER_RE`, `TEMPLATE_LINE_RE`
   - Nueva función `_is_contact_line()`: detecta 5 tipos de líneas de contacto con protección ≤150 chars
   - Sub-regla 4e: elimina líneas de contacto/footers
   - Sub-regla 4f: elimina placeholders inline, exactos, y multi-línea
   - Métricas nuevas en `clean_text_layer4`: `contact_lines_removed`, `template_placeholders_removed`
2. **`src/api/main.py`:** campos `contact_lines_removed` y `template_placeholders_removed` agregados a `CleanResponse` y endpoint `/clean`

### Resultados del re-procesamiento (28 docs)

| Métrica | Valor |
|---|---|
| Reducción promedio | 5.49% |
| Líneas de contacto eliminadas | 23 |
| Placeholders eliminados | 5 |
| Documentos afectados por 4e/4f | 6/28 |

**Documento top:** Proforest Reporte — 19 contactos + 5 placeholders eliminados.

### Validación visual (Proforest Reporte)

**✅ Antes del refinamiento:** footers de contacto aparecían en múltiples páginas, placeholders rompían oraciones.

**✅ Después del refinamiento:**
- Footers eliminados completamente
- Placeholders eliminados (incluyendo multi-línea)
- Contenido narrativo preservado ("Acerca de Proforest", "Introducción", "Cooperativa Agraria ACOPAGRO")
- Línea que antes decía:
  > "Resultados del análisis de riesgos usando Global Forest Watch ProError! Bookmark not defined."
  
  Ahora dice:
  > "Resultados del análisis de riesgos usando Global Forest Watch Pro."

### Problemas menores residuales

- `E:` (línea con solo prefijo de email) queda residual cuando el email fue eliminado por 4a
- `Campestre Towers |Cali| Colombia` — dirección parcial sin patrón postal explícito, se preserva
- TOC roto en Proforest sigue presente (no es prioridad)

### Pendiente para próxima sesión

1. **Decidir si la limpieza está lista** para pasar al NER, o si hay más refinamientos que valga la pena
2. **Correr NER sobre el corpus re-limpiado** (ahora con menos ruido residual)
3. **Continuar con Fase 2 del NER:** mapeo a las 9 categorías del proyecto

---

**Fecha:** 2026-05-05 (sesión 12)

**Trabajado en:**
- Revisión manual de Capa 4 sobre los 3 documentos con mayor reducción del corpus
- Identificación de bug crítico en Capa 2b: eliminaba contenido narrativo repetido en brochures/dípticos
- Corrección de la heurística `_is_header_candidate` (proteger líneas con >10 palabras)
- Re-procesamiento del corpus completo (28 documentos) con la corrección
- Validación visual de los documentos corregidos
- Actualización de `.agent/`

**Resumen de la sesión:**

### Bug crítico encontrado

La validación manual mostró que el **Proforest Reporte** y el **DIPTICO-CPS-EARTHWORM** habían perdido párrafos enteros de contenido narrativo. Ejemplo del Proforest (antes de la corrección):

```
L18: Es posible obtener los productos básicos agrarios de una manera que responda a la creciente
L21: Nos enfocamos en la base de producción y las cadenas de suministro de productos agropecuarios
L27: Apoyamos a las empresas para que tomen medidas para abordar los riesgos ambientales y
```

Todas estas líneas se eliminaban porque:
1. Aparecían ≥3 veces en el documento (formato brochure con páginas repetidas)
2. Cumplían `_is_header_candidate`: longitud 15-150, sin puntuación interna, no empiezan minúscula

### Corrección aplicada

En `src/services/cleaning.py`, función `_is_header_candidate`:

```python
# Must not be a long sentence (>10 words) — likely narrative content
# repeated across pages in brochures, not a structural header.
if len(stripped.split()) > 10:
    return False
```

### Resultados del re-procesamiento (28 docs)

| Métrica | Antes | Después |
|---|---|---|
| Reducción promedio | 7.09% | **5.32%** |
| Proforest Reporte | 16.44% | 16.55% (solo headers reales) |
| DIPTICO-EARTHWORM | 14.78% | **7.49%** |
| Guía AGRAP | 11.91% | 11.73% |

El DIPTICO mejoró drásticamente porque casi la mitad de su reducción era contenido narrativo eliminado erróneamente.

### Validación visual

**DIPTICO (después):** ahora conserva los párrafos introductorios completos sobre la Coalición y Earthworm Foundation.

**Proforest Reporte (después):** conserva las secciones "Acerca de Proforest", "Introducción", "Cooperativa Agraria ACOPAGRO LTDA" completas.

### Trade-off aceptado

Headers largos repetidos (>10 palabras) ya no se eliminan. Ejemplo en el DIPTICO:
> "ENFOQUE DE ALTOS VALORES DE CONSERVACIÓN (AVC) Y ALTAS RESERVAS DE CARBONO (ARC)"

Este título aparece en cada página del díptico y antes se eliminaba; ahora se preserva. Aceptado como trade-off conservador para no perder contenido narrativo.

### Problemas residuales menores

1. **Footers de contacto en Proforest:** "Proforest Latinoamérica S.A.S.| +57 (602) 3966477 | |" aparece varias veces y no se elimina (no cumple heurística de header por caracteres especiales).
2. **TOC roto en Proforest:** la "Tabla de contenido" tiene formato atípico (números sueltos en líneas separadas) y Capa 3b no lo capturó completamente.
3. **Placeholder en Proforest:** "Main Title Subtitle Description" — texto de template.

### Aprendizajes

- **La validación manual es indispensable.** Las métricas de reducción (%) no revelan si se eliminó ruido o contenido valioso. Solo la lectura visual lo detecta.
- **Los documentos tipo brochure/díptico son un caso límite** para la heurística de frecuencia: el mismo texto narrativo aparece intencionalmente en múltiples páginas.
- **La regla de ">10 palabras" es un buen proxy** para distinguir headers de contenido narrativo, pero no perfecta.

### Pendiente para próxima sesión

1. **Decidir si refinamos más Capa 4:** ¿vale la pena eliminar footers de contacto, placeholders, y TOC rotos? ¿O avanzamos al NER con la limpieza actual?
2. **Correr NER sobre los 28 documentos re-limpiados** para ver si la calidad mejoró (menos falsos positivos de créditos editoriales).
3. **Continuar con Fase 2 del NER:** mapeo a las 9 categorías del proyecto.

---

**Fecha:** 2026-05-05 (sesión 11)

**Trabajado en:**
- Inicio del Objetivo 4 (NER / Extracción de entidades)
- Decisión de librería: spaCy con modelos monolingües (es_core_news_sm + en_core_web_sm) + langdetect
- Implementación de servicio `src/services/ner.py` con detección de idioma, filtros de falsos positivos estructurales, extracción de contexto y oración
- Creación de endpoint `POST /documents/{id}/extract-entities`
- Pruebas con 3 documentos reales del corpus
- Actualización de Dockerfile para descargar modelos spaCy
- Actualización de `.agent/` (decisions.md, tasks.md, session.md)

**Resumen de la sesión:**

### Decisiones tomadas

- **Fase 1 del NER:** extraer entidades con spaCy y guardar etiquetas originales (PER, ORG, LOC, GPE, MISC). El mapeo a las 9 categorías del proyecto se hará en Fase 2 tras evaluar calidad.
- **Estrategia bilingüe:** `langdetect` para detectar idioma del documento, luego procesar con modelo spaCy correspondiente.
- **Filtros de falsos positivos:** lista negra case-insensitive de palabras/frases estructurales (títulos de sección, encabezados) para no etiquetar estructura del documento como entidades.

### Implementación

1. **`requirements.txt`:** agregadas `spacy>=3.7.0` y `langdetect==1.0.9`.
2. **`src/services/ner.py`:**
   - `_ensure_model()`: carga modelo spaCy, descarga automáticamente si no existe.
   - `detect_language()`: detecta idioma con fallback a 'es'.
   - `extract_entities()`: procesa texto, extrae entidades de TARGET_LABELS, filtra falsos positivos estructurales, extrae contexto (±300 chars) y oración completa.
   - `normalize_entity_name()`: normaliza para deduplicación (elimina artículos iniciales).
3. **`src/api/main.py`:**
   - Nuevo schema `ExtractEntityResponse`
   - Nuevo schema `ExtractEntitiesSummary`
   - Nuevo endpoint `POST /documents/{document_id}/extract-entities`
   - Requiere status `cleaned` o `processed`
   - Borra entidades previas del documento (idempotente)
   - Actualiza `documents.status = 'processed'`
   - Guarda en tabla `entities` con metadata JSONB
4. **`Dockerfile`:** agregados `RUN python -m spacy download es_core_news_sm` y `en_core_web_sm`.

### Resultados de prueba (3 documentos)

| Documento | Idioma | Total | ORG | LOC | PER | MISC |
|---|---|---:|---:|---:|---:|---:|
| AGRAP Plan de Acción | es | 449 | 134 | 89 | 45 | 181 |
| WWF UK PACT | es | 255 | 50 | 90 | 42 | 73 |
| Coalición Producción Sostenible | es | 418 | 84 | 120 | 36 | 178 |

### Calidad observada

**✅ Correctas:**
- Organizaciones: WWF, TFA, Climate Group, Earthworm Foundation, Gobierno de Reino Unido, NDPE
- Lugares: Madre de Dios, Amazonía Peruana, América Latina, Perú
- Personas: Nelson Gutiérrez Carpio, Maricarmen Brenis, David Parra, Carlos Roque

**⚠️ Problemas:**
- Falsos positivos de créditos editoriales residuales: "Editor", "Diseño" — Capa 4 no eliminó completamente todos los créditos.
- Delimitación incorrecta en listas verticales: spaCy une múltiples nombres de personas como una sola entidad PER.
- Texto adyacente incluido: "Amazonía Peruana La presente publicación" (LOC que incluye texto narrativo).
- "Perú" clasificado como PER en algunos casos (error de spaCy).
- "Además" clasificado como PER (error de spaCy).

### Aprendizajes

- **spaCy es rápido y funciona localmente**, pero el modelo `es_core_news_sm` tiene limitaciones con documentos estructurados (saltos de línea, listas).
- **La calidad del NER depende fuertemente de la calidad de la limpieza**: los créditos editoriales residuales generan falsos positivos. Mejorar Capa 4 reduciría ruido en el NER.
- **Filtrar falsos positivos estructurales ayuda**: la lista negra eliminó ~50 entidades inválidas (PLAN, CRÉDITOS, INTRODUCCIÓN, etc.) en el AGRAP.
- **No forzar mapeo a categorías del proyecto en Fase 1 fue la decisión correcta**: las etiquetas spaCy son imperfectas; mapearlas ahora propagaría errores.

### Pendiente para próxima sesión

1. **Evaluar si refinamos la limpieza Capa 4** antes de seguir con NER (los créditos residuales generan ruido).
2. **Fase 2 del NER:** diseñar mapeo spaCy → 9 categorías del proyecto (¿heurísticas? ¿clasificador?).
3. **Post-procesamiento de entidades:** dividir entidades PER que contengan múltiples nombres; corregir "Perú"→LOC.
4. **Probar con documento en inglés** del corpus para verificar modelo en_core_web_sm.
5. **Correr NER sobre los 28 documentos** y hacer análisis agregado (top entidades, frecuencias).

---

**Fecha:** 2026-05-05 (sesión 10)

**Trabajado en:**
- Decisión arquitectónica: separar Capa 4 dedicada a "ruido editorial por contenido" (URLs/emails, créditos, portadas MAYÚSCULAS, agradecimientos)
- Análisis programático del corpus para diseñar las 4 sub-reglas (4a, 4b, 4c, 4d) con datos
- Implementación de Capa 4 con extensión B1 (refinada después de detectar agresividad excesiva en B inicial)
- Validación con dry_run y comparación visual antes/después
- Aplicación de Capa 1+2+2c+3+4 al corpus completo (28 documentos)
- Actualización de la documentación `.agent/`

**Resumen de la sesión:**

### Estructura final del pipeline de limpieza

- **Capa 1**: universal (encoding/espacios)
- **Capa 2**: estructural por estadística (headers, páginas, oraciones)
- **Capa 3**: estructural por patrón (TOCs)
- **Capa 4**: editorial por contenido (URLs/emails, créditos, portadas, agradecimientos)

### Análisis previo a codear

Antes de implementar, análisis programático sobre los 28 archivos:
- **4a:** 55 líneas-solo-URL en 13 archivos + 5 líneas-solo-email en 3 archivos + 250 URLs inline + 42 emails inline. Decisión: eliminar todos (Tania confirmó "en ningún momento las vamos a etiquetar").
- **4b:** 149 líneas con keywords de crédito en 26/28 archivos, **PERO con falsos positivos** (la palabra "Producción" sola pesca contenido normal). Decisión: keyword debe ir seguida de `:` o `©`, eliminar bloques (no líneas individuales).
- **4c:** 10/28 archivos tienen portadas con palabras MAYÚSCULAS partidas en líneas (`ACUERDO DE / ACCIÓN COLECTIVA / ...`).
- **4d:** Solo 2/28 archivos con header `AGRADECIMIENTOS` explícito.

### Iteración crítica: B → B1

**B inicial fue demasiado agresivo.** En el Plan AGRAP eliminó 40 líneas, incluyendo:
- ✅ Bloque puro de créditos (15 líneas: Autor:, Diseño:, etc.)
- ❌ Lista de instituciones firmantes (`Ministerio de Ambiente`, `Mancomunidad Regional Amazónica`, `Proforest`, `Universidad Nacional Agraria...`) — son **actores territoriales reales** del análisis.

**B1 refinada:** después del último keyword detectado, parar la extensión cuando aparezcan 5 líneas consecutivas sin nuevo keyword (no incluir esa 5ª línea). En el Plan AGRAP, B1 elimina 13 líneas (vs 40 con B), preservando las instituciones firmantes.

**Trade-off aceptado:** quedan 4-5 líneas residuales después del bloque editorial puro (típicamente subtítulos como `AGRADECEMOS LA PARTICIPACIÓN DE:` + 3 líneas), antes del threshold de 5.

### Implementación

1. **`src/services/cleaning.py`:**
   - Función `clean_text_layer4(text)` con 4 sub-reglas en orden: 4a → 4c → 4b → 4d
   - Función `_renormalize()` al final: re-aplicar normalización de espacios y saltos (porque eliminar URLs inline puede dejar dobles espacios)
   - Constantes explícitas (`CREDIT_FIRST_FRACTION=0.15`, `CREDIT_LAST_FRACTION=0.05`, `CREDIT_MIN_KEYWORDS_IN_BLOCK=2`, `CREDIT_MAX_NONKEYWORD_LINES=5`, etc.) para tuneo
2. **`src/api/main.py`:** endpoint `/clean` ahora aplica Capa 1+2+2c+3+4 en cascada. `CleanResponse` ampliado con 9 nuevos campos (`urls_removed`, `emails_removed`, `credit_blocks_removed`, etc.).

### Resultados sobre el corpus

| Métrica | Capa 1+2+2c+3 | Capa 1+2+2c+3+4 (B1) |
|---|---:|---:|
| Reducción avg | 5.54% | **7.01%** |
| Reducción max | 14.04% | **16.55%** |
| URLs eliminadas | 0 | 305 |
| Emails eliminados | 0 | 47 |
| Líneas portada MAYÚSCULAS | 0 | 89 |
| Líneas créditos | 0 | 62 |
| Líneas agradecimientos | 0 | 45 |
| Archivos donde la capa actuó | 6/28 (Capa 3) | 22/28 (Capa 4) |

### Aprendizajes

- **Validación visual antes/después es crítica para detectar agresividad excesiva**: B inicial pasó las heurísticas pero comió contenido valioso. Solo se vio al inspeccionar el resultado en el Plan AGRAP.
- **El threshold "líneas sin keyword" es un control fino**: cambiar de "2 párrafos narrativos seguidos" a "5 líneas sin keyword" produjo el cambio de 40→13 líneas eliminadas en el Plan AGRAP.
- **Dato del corpus > intuición**: encontrar 250 URLs inline + 7 archivos donde "ÍNDICE" no era TOC + falsos positivos en regex de créditos cambió las decisiones de diseño en cada caso.
- **Re-normalización post-eliminación**: cuando se elimina contenido inline (URL/email), hay que re-aplicar normalización de espacios. Sin esto quedaba `consultar  más info` con doble espacio.

### Pendiente para próxima sesión

1. **Validación manual** de los 22 archivos donde Capa 4 actuó, especialmente los de mayor reducción (`Proforest Reporte` 16.55%, `DIPTICO-CPS-EARTHWORM` 14.34%, `Año de Referencia` 11.80%).
2. **Decidir:** ¿avanzar al **Objetivo 4 (NER)** con la limpieza actual, o seguir refinando Capa 4 (los 4-5 líneas residuales tipo "AGRADECEMOS LA PARTICIPACIÓN DE:")?
3. **Empezar a planear Objetivo 4 (NER)**: elección de librería (spaCy multilingüe?), categorías concretas para clasificación de entidades.

---

**Fecha:** 2026-05-04 (sesión 9)

**Trabajado en:**
- Diagnóstico de tipos de TOC presentes en el corpus (análisis programático)
- Diseño de heurística para Capa 3a (dot leaders) y Capa 3b (bloques TOC numerados al inicio)
- Implementación de **Capa 3** (primera iteración: 3a + 3b)
- Validación con dry_run sobre 6 archivos representativos (incluyendo casos que NO debían ser eliminados)
- Aplicación de Capa 1+2+2c+3 al corpus completo (28 documentos)
- Actualización de la documentación `.agent/`

**Resumen de la sesión:**

### Análisis previo a codear

Antes de inventar reglas de "borrar TOCs", corrimos análisis programático sobre los 28 archivos limpios. Hallazgos:

- **Tipo A — TOC con dot leaders** (`.................` patron típico): 1 archivo (`1d93b172` ACOPAGRO).
- **Tipo B — TOC con numeración pero sin dot leaders**: ~5 archivos (`cf1fde65`, `5d5f7118`, etc.). El header dice `CONTENIDO`/`ÍNDICE` y siguen líneas tipo `1.`, `1.1.`, `2.`, etc.
- **Tipo C — Trampa: palabra `ÍNDICE`/`CONTENIDO` aislada SIN TOC real**: 7 archivos (`050c2005`, `9383e086`, `7d596b01`, etc.) donde la palabra es solo título de sección y después viene texto narrativo.

**Conclusión crítica:** una regla naïve tipo "borrar todo después de `ÍNDICE`" destruiría contenido legítimo en 7 docs. Necesitamos heurística más fina.

### Decisiones acordadas

- **Capa 3a — dot leaders:** eliminar líneas con `\.{5,}` (5+ puntos consecutivos). Aplicar SIEMPRE (es inequívoco). Captura el Tipo A.
- **Capa 3b — bloques TOC al inicio:** detectar bloques contiguos donde:
  - Están en los **primeros 15% del documento**
  - Tienen **≥5 líneas no vacías** consecutivas (con tolerancia a 1 línea vacía)
  - **≥70% empiezan con patrón numerado** (`1.`, `1.1.`, `a.`, `I.`, `•`)
  - **Todas son ≤100 caracteres**
  - Si hay header `CONTENIDO/ÍNDICE/TABLE OF CONTENTS` justo antes, también se elimina.
  Captura el Tipo B y NO toca el Tipo C.
- **Skip Capa 3b** si doc < 200 líneas no vacías (consistente con Capa 2). Capa 3a aplica a todos los docs.

### Implementación

1. **`src/services/cleaning.py`:** función `clean_text_layer3(text)` agregada con 3a y 3b. Constantes explícitas (`TOC_FIRST_FRACTION=0.15`, `TOC_MIN_BLOCK_LINES=5`, `TOC_MIN_NUMBERED_RATIO=0.7`, `TOC_MAX_LINE_LENGTH=100`) para tuneo.
2. **`src/api/main.py`:** endpoint `/clean` ahora aplica Capa 1 + 2 + 2c + 3 en cascada. `CleanResponse` ampliado con `dot_leader_lines_removed`, `toc_blocks_removed`, `toc_lines_removed`, `skipped_layer3b_short_doc`.

### Validación con dry_run

Probamos sobre 6 archivos representativos:

| Caso | Esperado | Resultado |
|---|---|---|
| `cf1fde65` — TOC tipo B con `CONTENIDO` | Detectar | ✅ 1 bloque, 34 líneas |
| `1d93b172` — TOC tipo A con dot leaders | Detectar | ✅ 21 dot leaders |
| `5d5f7118` — TOC tipo B simple | Detectar | ✅ 1 bloque, 33 líneas |
| `050c2005` — palabra "Contenido" SIN TOC real | NO tocar | ✅ 0 bloques |
| `9383e086` — "Índice" + autores (NO es TOC) | NO tocar | ✅ 0 bloques |
| `5db822ad` — Acuerdo Café corto | Skip 3b | ✅ skipped |

**Las protecciones funcionaron**: 0 falsos positivos en docs donde "Contenido/Índice" era solo un título de sección.

### Resultados sobre el corpus

- 28/28 documentos re-procesados con Capa 1+2+2c+3 (sin fallos)
- **5 bloques TOC + 122 líneas TOC eliminadas** (en 4 archivos distintos — algunos tienen 2 TOCs)
- **21 dot leaders eliminados** (en 1 archivo principal: ACOPAGRO)
- 6/28 archivos tenían TOC detectable
- **Reducción avg subió de 4.92% a 5.54%** (max ahora 14.04%)
- 3 docs cortos saltaron Capa 3b correctamente

### Verificación visual antes/después (cf1fde65)

Las líneas 26-44 (header `CONTENIDO` + bloque numerado completo `1. CONTEXTO PERUANO` + `1.1. LA GANADERÍA BOVINA...` + ... + `3.4. INSTRUMENTO...`) fueron eliminadas. El cuerpo del documento ahora arranca directamente con `"En el Perú, la ganadería genera empleo..."`.

### Aprendizajes

- **El "primeros 15% del documento" es una protección clave**: distingue TOCs (siempre al inicio) de listas legítimas en el cuerpo.
- **La combinación `≥5 líneas + ≥70% numeradas` es robusta**: una lista de 3 ítems en el cuerpo no se elimina; solo bloques sustanciales típicos de TOC.
- **Heurísticas data-driven >> heurísticas a priori**: el análisis programático del corpus mostró que la trampa "Índice/Contenido sin TOC real" era frecuente (7 docs). Sin haberlo identificado, la regla naïve habría destruido contenido legítimo.

### Pendiente para próxima sesión

1. **Validación manual** de los 6 archivos donde Capa 3 actuó (verificar que los TOCs eliminados eran realmente TOCs y no contenido).
2. **Capa 3 — iteraciones siguientes:**
   - Eliminar bloques de créditos editoriales (Autores, Diseño, ISBN, Primera Edición) que la 2b/3b no capturó
   - Detectar títulos de portada con palabras MAYÚSCULAS partidas en líneas
   - Eliminar URLs y emails sueltos
3. **Empezar Objetivo 4 (NER):** elección de librería (spaCy multilingüe? modelo dedicado?), categorías concretas.

---

**Fecha:** 2026-05-04 (sesión 8)

**Trabajado en:**
- Verificación en disco de que Capa 2 (sesión 7) sí se aplicó correctamente — usuaria pensaba que los archivos seguían en Capa 1
- Implementación de **Capa 2c** (re-unión de oraciones partidas por columnas de PDF)
- Comparación visual antes/después en archivo representativo
- Aplicación de Capa 1+2+2c al corpus completo (28 documentos)
- Actualización de la documentación `.agent/`

**Resumen de la sesión:**

### Verificación inicial (falsa alarma)

Usuaria reportó que los archivos limpios "seguían en Capa 1". Verificamos en disco:
- Headers detectados (`'ANÁLISIS DE INSTRUMENTOS FINANCIEROS PÚBLICOS'` × 63) → 0 ocurrencias en cleaned ✓
- Líneas-página → 0 ocurrencias ✓
- Tamaños correctos (cf1fde65 bajó de 112 KB a 103 KB) ✓
- Fechas de modificación recientes ✓

**Conclusión:** Capa 2 sí estaba aplicada. La confusión venía de:
- La portada del Análisis de Instrumentos Financieros tiene un título cuyas palabras están partidas en líneas (`"ANÁLISIS DE"`, `"INSTRUMENTOS"`, etc.). Eso parece "ruido sin limpiar" pero NO es un header repetido — aparece una sola vez. La Capa 2 no lo toca porque no es un header repetido. La Capa 2c tampoco lo une porque cada palabra empieza con MAYÚSCULA.
- Esos títulos de portada quedan para Capa 3 (créditos editoriales).

### Implementación Capa 2c

**Heurística:** unir línea N con N+1 si CUMPLE TODAS:
- Línea N **NO termina** en `.`, `?`, `!`, `:`, `;`
- Línea N+1 **empieza con minúscula**
- Línea N+1 **NO es ítem de lista** (`a)`, `1.`, `b)`, etc.)
- Ambas son no vacías (no hay `\n\n` entre ellas — preservamos límites de párrafo)

**Skip** si documento < 200 líneas no vacías (consistente con 2a/2b).

### Implementación

1. **`src/services/cleaning.py`:** función `clean_text_layer2c(text)` agregada
2. **`src/api/main.py`:** endpoint `/clean` ahora aplica Capa 1 + 2 + 2c en cascada; `CleanResponse` ampliado con `sentences_rejoined` y `skipped_layer2c_short_doc`; `cleaning_metadata` JSONB ahora estructurado como `{layer1, layer2, layer2c}`

### Validación con dry_run

Comparación visual antes/después sobre Análisis Instrumentos Financieros:

**ANTES (Capa 1+2):** oración partida en 3 líneas
```
Documento elaborado por Earth Innovation Institute por encargo del Foro Económico
Mundial, mediante su programa Tropical Forest Alliance – TFA –, como parte de las
acciones de la Alianza por una Ganadería Regenerativa en la Amazonía Peruana (AGRAP),
```

**DESPUÉS (Capa 1+2+2c):** oraciones reunidas
```
Documento elaborado por Earth Innovation Institute por encargo del Foro Económico
Mundial, mediante su programa Tropical Forest Alliance – TFA –, como parte de las acciones de la Alianza por una Ganadería Regenerativa en la Amazonía Peruana (AGRAP),
```

**Listas verticales preservadas correctamente:** los ítems de "Autores:" (cada nombre en su línea) NO se unieron — la heurística las protege porque empiezan con mayúscula.

### Resultados sobre el corpus

- 28/28 documentos re-procesados con Capa 1+2+2c
- **7,121 oraciones re-unidas en total** (top: `4.1 Análisis Experiencias Promisoras Tocache` con 1,109 reuniones)
- Reducción avg/max: igual que con solo Capa 1+2 (4.92% / 9.93%) — la 2c no reduce caracteres
- 3 docs cortos saltaron Capa 2/2c correctamente
- 0 fallos

### Aprendizajes

- **La 2c no reduce caracteres pero mejora estructura del texto** (un `\n` se vuelve ` `). El % de reducción no captura el beneficio — la métrica relevante es `sentences_rejoined`. Para el NER posterior, oraciones completas son mucho más útiles que fragmentos por columnas.
- **Caso límite no resuelto: títulos de portada en MAYÚSCULAS partidos en líneas** (`"ANÁLISIS DE"\n"INSTRUMENTOS"\n"FINANCIEROS"`). La heurística de 2c no los une porque cada palabra empieza con mayúscula. Decisión: dejarlos así, son ruido editorial pendiente para Capa 3.
- **Listas verticales preservadas**: la regla "siguiente empieza con minúscula" + "no es ítem de lista" funciona bien para distinguir oraciones partidas de listas de nombres/items.
- **Verificación en disco vs percepción**: cuando una usuaria reporta "no veo cambios", verificar siempre con `grep` o tamaños antes de re-correr el proceso. La confusión puede venir de mirar la parte del texto que NO debe limpiarse aún (portada → Capa 3).

### Pendiente para próxima sesión

1. **Validación manual** de archivos top-reuniones (`Análisis Experiencias Promisoras Tocache` con 1,109 reuniones) para confirmar que ninguna unión rompe la estructura.
2. **Capa 3 (editorial):**
   - Eliminar bloques de créditos al inicio/final (Autores, Diseño, ISBN, Primera Edición, URLs)
   - Detectar y eliminar títulos de portada con palabras MAYÚSCULAS partidas en líneas
   - Eliminar URLs y emails sueltos
3. **Empezar Objetivo 4 (NER):** elección de librería (spaCy multilingüe? modelo dedicado?), categorías concretas.

---

**Fecha:** 2026-05-04 (sesión 7)

**Trabajado en:**
- Diseño y datos: análisis programático sobre los 28 archivos limpios (Capa 1) para identificar patrones reales de headers, footers y números de página antes de codear las reglas
- Diseño de heurística combinada para Capa 2b (no solo "línea repetida N veces" — múltiples criterios para evitar borrar entidades legítimas)
- Implementación de **Capa 2** de limpieza: 2a (números de página) + 2b (headers/footers repetidos)
- Implementación de modo **`?dry_run=true`** para auditar antes de aplicar
- Validación con dry_run sobre 5 archivos representativos
- Aplicación de Capa 1 + 2 al corpus completo (28 documentos)
- Decisión explícita de NO implementar Capa 2c (re-unión de oraciones) — diferida por riesgo

**Resumen de la sesión:**

### Análisis previo a codear (data-driven)

Antes de inventar reglas, corrimos un análisis sobre los 28 archivos `cleaned/` para ver:
- Qué líneas se repiten 3+ veces (candidatas a header)
- Qué líneas son solo números o "Página N" (candidatas a 2a)
- Total: 27,004 líneas no vacías; 7.39% se repiten 3+ veces; 5.71% son solo números de página.

**Hallazgo crítico:** la heurística simple "línea repetida 3+ veces" pesca falsos positivos: palabras sueltas (`'jurisdiccional'`), valores de tabla (`'5 kilos'`, `'Cantidad'`), nombres de columnas. Por eso definimos **heurística combinada**.

### Decisiones acordadas (ver `decisions.md` 2026-05-04)

- **Heurística de Capa 2b** (línea es header si CUMPLE TODAS):
  - Repetida ≥ 3 veces
  - Longitud entre 15 y 150 caracteres
  - No contiene `.`, `?`, `!` excepto al final
  - No empieza con minúscula
  - No es ítem de lista (`a)`, `1.`, `1)`, etc.)
- **Skip Capa 2** si documento < 200 líneas no vacías (3 docs cortos saltaron correctamente).
- **Capa 2c (re-unión oraciones) NO implementada**: la más riesgosa, diferida.
- **Casos discutibles aceptados:**
  - Atribuciones `'Fuente: ...'`: que se eliminen ahora (originalmente Capa 3).
  - Subtítulos recurrentes (`'ALIMENTACIÓN DEL ANIMAL'`, `'Estiércol de vaca'`): eliminar — "aunque aporten información, no es fácil relacionarlos con las demás palabras del párrafo" (cita usuaria).
  - Entidades como `'WWF Madre de Dios'` en headers: dejarlas eliminarse en este doc; iterar después en NER si aparecen vacíos.

### Implementación

1. **`src/services/cleaning.py`:** función `clean_text_layer2(text) -> tuple[str, dict]` con:
   - `_is_header_candidate(line)`: implementa la heurística combinada
   - 2a: regex `PAGE_NUMBER_RE` para números de página solos
   - 2b: `Counter` para frecuencia + filtro por heurística
   - Constants explícitas (`SHORT_DOC_LINE_THRESHOLD=200`, `HEADER_REPETITION_MIN=3`, etc.) para tuneo posterior
2. **`src/api/main.py`:**
   - `CleanResponse` ampliado con `dry_run`, `pages_removed`, `headers_removed_count`, `headers_detected`, `skipped_layer2_short_doc`
   - Endpoint `POST /documents/{id}/clean` ahora aplica Capa 1 + Capa 2 en cascada
   - Parámetro `?dry_run=true`: corre la limpieza, devuelve métricas y headers detectados, **NO escribe archivo ni actualiza DB**
   - `cleaning_metadata` JSONB ahora estructurado como `{layer1: {...}, layer2: {...}}`

### Resultados sobre el corpus real

- **28/28 documentos limpiados** (Capa 1 + 2)
- **Reducción avg 4.92%** (vs 1.57% con Capa 1 sola — ~3x más limpio)
- **Max reducción 9.93%** (GUIA-TECNICA-GLOBAL FOREST WATCH)
- **1,540 líneas-página + 899 líneas-header eliminadas** en total
- **3 documentos cortos saltaron Capa 2 correctamente** (Acuerdo Café, MOU Cacao, MOU AGRAP)

### Aprendizajes para futuras sesiones

- **Diseñar reglas con datos reales, no a priori**: el análisis programático previo nos mostró falsos positivos que la heurística simple habría capturado (palabras sueltas, valores de tabla). Sin esto, habríamos borrado contenido legítimo.
- **`dry_run` debería ser estándar** para cualquier operación destructiva sobre datos del corpus. Le dio a la usuaria el control de auditar antes de aplicar.
- **Reglas idempotentes**: el endpoint `/clean` se puede correr sobre un doc en estado `cleaned` y produce el mismo resultado. Permitió re-procesar los 28 docs con la nueva Capa 2 sin reset de DB.
- **La taxonomía Capa 2 vs Capa 3 es porosa en la práctica**: muchos créditos y atribuciones que se planeaban para Capa 3 fueron capturados por la heurística de 2b. Bonus accidental.

### Pendiente para próxima sesión

1. **Validación manual** de 2-3 archivos top-reducción (GUIA Forest Watch 9.93%, AGRAP Guía 9.79%) para confirmar que no se perdió contenido importante.
2. **Capa 2c (re-unión de oraciones partidas)**: evaluar si vale la pena, definir reglas seguras.
3. **Capa 3 (créditos restantes + URLs/emails)**: lo que la heurística de 2b no pescó.
4. **Empezar Objetivo 4 (NER)**: elección de librería (spaCy multilingüe?), categorías concretas, primer prototipo.

---

**Fecha:** 2026-05-04 (sesión 6)

**Trabajado en:**
- Decisiones de fondo para el Objetivo 3 (limpieza/depuración de textos)
- Inspección manual de 2 archivos `.txt` reales del corpus para identificar tipos de ruido
- Implementación completa de la **Capa 1** de limpieza (universal, determinista)
- Migración de DB para guardar métricas de limpieza
- Aplicación de la limpieza Capa 1 sobre 28 documentos del corpus
- Actualización de la documentación `.agent/`

**Resumen de la sesión:**

### Decisiones acordadas (ver `decisions.md` 2026-05-04)

- **Enfoque determinista por capas** (no IA): controlable, reproducible, sin riesgo de "alucinación" sobre el discurso original — esto último es importante para un análisis crítico/feminista.
- **NO eliminar** stopwords, conectores ni palabras cortas ("con", "de", "en"): son señal relacional para el NER (Objetivo 4) y los grafos.
- **NO hacer lowercase ni quitar acentos**: "Río Magdalena" debe seguir siéndolo.
- **SÍ eliminar ruido editorial**: lo que está en créditos/colofón pero no en el discurso (autores, diseñadores, ISBN, etc.).
- **Corpus bilingüe** (español + inglés): librerías deben ser multilingües.
- **Tres capas** definidas: Capa 1 universal (encoding/espacios), Capa 2 estructural (headers/páginas/columnas), Capa 3 editorial (créditos/URLs).

### Inspección de archivos reales

Abrimos 2 `.txt` con perfiles distintos:
- **Perfil A — PDF maquetado** (Plan AGRAP 2024-2026): headers repetidos cada página, créditos editoriales al inicio, oraciones partidas por columnas, números de página sueltos.
- **Perfil B — Documento simple** (Acuerdo Café y Bosques): saltos de línea espurios, indentación con espacios largos, espacios al final de líneas, sin headers/créditos visibles.

Conclusión: **no sirve una sola receta de regex** — la limpieza debe ir por capas adaptables.

### Implementación

1. **`requirements.txt`:** agregada `ftfy==6.2.3`. Imagen Docker reconstruida.
2. **`src/services/cleaning.py`** (nuevo): función `clean_text_layer1(text) -> tuple[str, dict]` con 6 reglas universales (ftfy → NFC → control chars → espacios múltiples → 3+ saltos de línea → strip por línea), devuelve métricas detalladas por regla. También `save_cleaned_text()`.
3. **Modelo `Document`:** agregadas 4 columnas (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB).
4. **Migración Alembic `1e6e4c60daa8`:** ⚠️ autogenerate quería borrar 8 índices de `entities`/`metrics`/`relationships` (porque los modelos no los declaran pero la DB sí los tiene desde la migración 001). **Editamos manualmente** la migración para dejar SOLO los `add_column` y eliminar los `drop_index`. Aprendizaje importante para futuras migraciones.
5. **Endpoint `POST /documents/{id}/clean`** en `src/api/main.py`: lee `data/processed/txt/{id}.txt`, aplica Capa 1, guarda en `data/processed/cleaned/{id}.txt`, actualiza `status='cleaned'` y métricas. Devuelve `CleanResponse`. Idempotente (acepta status `converted` o `cleaned`). 404 si el `.txt` no existe en disco.

### Resultados sobre el corpus real

- **28/30 documentos limpiados** (2 fallaron correctamente con 404 — eran `test_doc.docx`/`test_doc.pdf` viejos sin `.txt` en disco).
- **Reducción avg 1.57%**, max 7.30% (Acuerdo Café y Bosques), min 0.05%.
- Reducción baja **es lo esperado**: la Capa 1 es deliberadamente conservadora. Las Capas 2 y 3 son las que reducirán más.

### Aprendizajes para futuras sesiones

- **Alembic autogenerate no es 100% confiable**: siempre revisar la migración generada antes de aplicar. En este caso quería borrar índices que no debíamos perder. Lección: si un modelo SQLAlchemy no declara los índices que la DB ya tiene, declararlos en el modelo o editar la migración a mano antes del `upgrade`.
- **Métricas en columnas dedicadas vs JSONB:** elegimos columnas para `original_char_count`, `cleaned_char_count`, `reduction_percentage` (filtrables/ordenables) y JSONB para el detalle por regla (`cleaning_metadata`) que es info menos consultable.
- **Idempotencia en endpoints de pipeline:** el endpoint `/clean` permite re-correr aunque el documento ya esté en `cleaned`. Útil para iterar reglas sin tener que volver a procesar.

### Pendiente para próxima sesión

1. **Validación manual** de 2-3 archivos limpiados (sobre todo los de mayor reducción) para confirmar que no se perdió información.
2. **Diseñar Capa 2 (estructural):** las reglas concretas para detectar headers/footers repetidos por frecuencia, números de página sueltos, y re-unión de oraciones partidas por columnas.
3. **Capa 3 (editorial):** créditos y URLs.
4. **Empezar a planear Objetivo 4 (NER):** elección de librería (spaCy multilingüe?), categorías concretas, etc.

---

**Fecha:** 2026-05-04 (sesión 5)

**Trabajado en:**
- Implementación de endpoint `POST /documents/batch` para subida y procesamiento múltiple de archivos
- Usuario puede ahora subir una carpeta completa de archivos (PDF + DOCX) en un solo request
- El endpoint hace upload + process automáticamente para cada archivo
- Documentación actualizada en session.md, tasks.md

**Resumen de la sesión:**

### Nuevo endpoint: `POST /documents/batch`

**Propósito:** Permitir subir múltiples archivos en un solo request HTTP y procesarlos automáticamente (upload + conversión a TXT).

**Request:**
- Método: POST
- URL: `http://localhost:8000/documents/batch`
- Content-Type: `multipart/form-data`
- Body: `form-data` con KEY=`files` (múltiples archivos, todos con el mismo key)

**Cómo usar desde Postman:**
1. Crear nuevo request POST a `http://localhost:8000/documents/batch`
2. Ir a Body → seleccionar "form-data"
3. En KEY escribir: `files`
4. Cambiar dropdown de "Text" a **"File"**
5. Click en "Select Files" y seleccionar múltiples archivos (Cmd+A para seleccionar todos)
6. O arrastrar todos los archivos desde Finder al Body de Postman
7. Click en "Send"

**Response:**
```json
[
  {
    "document_id": "abc123...",
    "original_filename": "documento1.pdf",
    "file_type": "pdf",
    "upload_status": "success",
    "process_status": "converted",
    "txt_path": "data/processed/txt/abc123...txt",
    "char_count": 12345,
    "error": null
  },
  {
    "document_id": "def456...",
    "original_filename": "documento2.docx",
    "file_type": "docx",
    "upload_status": "success",
    "process_status": "converted",
    "txt_path": "data/processed/txt/def456...txt",
    "char_count": 6789,
    "error": null
  },
  {
    "document_id": "ghi789...",
    "original_filename": "archivo.txt",
    "file_type": "txt",
    "upload_status": "success",
    "process_status": "failed",
    "txt_path": null,
    "char_count": null,
    "error": "Unsupported file type: File type 'txt' not supported..."
  }
]
```

**Campos de respuesta:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `document_id` | UUID | ID único del documento en DB |
| `original_filename` | string | Nombre original del archivo |
| `file_type` | string | Extensión inferida (pdf, docx, etc.) |
| `upload_status` | "success" / "failed" | Si se guardó en data/raw/ |
| `process_status` | "converted" / "failed" / null | Si se convirtió a TXT |
| `txt_path` | string o null | Ruta del archivo .txt generado |
| `char_count` | int o null | Cantidad de caracteres extraídos |
| `error` | string o null | Mensaje de error si ocurrió |

**Manejo de errores por archivo:**
- Cada archivo tiene su propio `upload_status`, `process_status` y `error`
- Si un archivo falla, los demás continúan procesándose
- Errores comunes:
  - Formato no soportado (415): `process_status: "failed"`, `error: "Unsupported file type..."`
  - Archivo sin extensión: `upload_status: "failed"`, `error: "File must have an extension..."`
  - Fallo de conversión: `process_status: "failed"`, `error: "Conversion error: ..."`
  - Archivo corrupto: `process_status: "failed"`, `error: "Failed to convert..."`

**Ventajas:**
- ✅ Un solo request para toda una carpeta (30 archivos = 1 request)
- ✅ No requiere scripts externos ni terminal
- ✅ Accesible desde Postman, curl, o cualquier cliente HTTP
- ✅ Feedback individual por archivo en la respuesta
- ✅ Auto-procesamiento: upload + process en un solo paso
- ✅ Ideal para usuarios no técnicos (humanos, no programadores)

**Comparación con enfoque individual:**

| Característica | Individual (`POST /documents`) | Batch (`POST /documents/batch`) |
|----------------|-------------------------------|---------------------------------|
| Archivos por request | 1 | Múltiples (ilimitados) |
| Requests para 30 archivos | 30 uploads + 30 process = 60 | 1 request |
| Tiempo estimado (30 archivos) | ~15-20 min manual | ~30-60 segundos |
| Auto-procesamiento | No (requiere 2do paso) | Sí (upload + process) |
| Feedback | Por archivo (cada request) | Todos en una respuesta |
| Complejidad para usuario | Media (2 pasos) | Baja (1 paso) |

**Implementación técnica:**
- Nuevo schema Pydantic: `BatchUploadResponse`
- Endpoint en `src/api/main.py:132-224`
- Itera sobre cada archivo en `files: List[UploadFile]`
- Para cada archivo:
  1. Valida extensión
  2. Guarda en `data/raw/{document_id}/`
  3. Inserta en DB con status="raw"
  4. Intenta convertir (llama a `convert_document()`)
  5. Guarda TXT en `data/processed/txt/`
  6. Actualiza status a "converted" o "failed"
  7. Agrega resultado a la lista de respuesta
- Transaccional: cada archivo se commitea individualmente (si uno falla, los demás continúan)

**Archivos modificados:**
- `src/api/main.py`: agregado `BatchUploadResponse`, nuevo endpoint `POST /documents/batch`
- `.agent/session.md`: documentación de la sesión
- `.agent/tasks.md`: marcado endpoint batch como completado

**Estado actual del pipeline:**

```
┌─────────────────────────────────────────────────────────────┐
│  POST /documents/batch (1 request, múltiples archivos)     │
│  → Upload + Process automático                              │
│  → Response: array con resultado por archivo               │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  Para cada archivo:                                         │
│  1. data/raw/{id}/{filename} ← guardado                    │
│  2. DB: documents.insert(status="raw")                     │
│  3. Conversión (PDF→PyMuPDF, DOCX→python-docx)            │
│  4. data/processed/txt/{id}.txt ← guardado                 │
│  5. DB: documents.update(status="converted")               │
└─────────────────────────────────────────────────────────────┘
```

**Próximo paso inmediato:**
- Usuaria puede ahora subir los ~25-30 archivos restantes del corpus desde Postman en un solo request
- Verificar que todos los archivos se procesen correctamente
- Revisar los .txt generados en `data/processed/txt/`

---

**Fecha:** 2026-04-29 (sesión 4)

**Trabajado en:**
- Pruebas manuales end-to-end del pipeline de conversión (Objetivo 1 + 2) con archivos reales
- Aclaración conceptual sobre cómo funciona una API HTTP, qué hace Postman, y cómo se suben archivos (multipart/form-data)
- Definición del plan para procesar el resto del corpus (script bash vs. endpoint batch)

**Resumen de la sesión:**

### Conceptos aclarados (importante para futuras sesiones)
La usuaria está aprendiendo APIs/HTTP, no había usado Postman para subir archivos antes. Los conceptos que se documentaron explícitamente:

- **La API HTTP vive corriendo todo el tiempo** dentro de Docker. No se "ejecuta" cada vez. Se le mandan mensajes (requests) y reacciona.
- **Postman es solo un cliente HTTP** — empaca y manda mensajes; no ejecuta código del servidor. Curl, navegador o cualquier cliente sirven igual.
- **El flujo es de 2 pasos separados, no uno:**
  - `POST /documents` → upload (sube y guarda)
  - `POST /documents/{id}/process` → conversión a `.txt`
  
  Razón: permite re-procesar sin re-subir, o subir en lote y procesar después.
- **Los archivos no se pre-colocan en una carpeta especial del proyecto antes de probar.** Pueden estar en cualquier ruta del Mac. Postman/curl los lee de donde sea y los empaca dentro del request HTTP. La API los guarda automáticamente en `data/raw/{id}/`.
- **Para subir un archivo en Postman:** Body → `form-data` → KEY=`file` con el dropdown cambiado de "Text" a **"File"** → Select Files. **Sin el cambio a "File" no hay manera de mandar el archivo** — es la trampa más común para quien arranca.
- **La arquitectura ya es portable a S3:** la API es la abstracción entre "el cliente tiene un archivo" y "el archivo queda almacenado en algún lado". Hoy guarda en disco, mañana puede guardar en S3 cambiando solo la línea de almacenamiento, sin afectar a los clientes (Postman/script/dashboard futuro).

### Pruebas manuales realizadas
- ✅ 5 archivos (PDF + DOCX) subidos y procesados manualmente desde Postman
- ✅ Usuaria familiarizada con el flujo de Postman (form-data, File field, copiar id, llamar a process)
- ⏳ Pendiente verificar: que los 5 hayan terminado con `status: "converted"`, que los `.txt` resultantes se vean correctos, y si alguno era PDF escaneado (PyMuPDF no hace OCR — saldría vacío)

### Decisión pendiente para próxima sesión

Para procesar los ~25 archivos restantes del corpus, dos opciones evaluadas:

| Opción | Qué hace | Tiempo | Cuándo conviene |
|---|---|---|---|
| **A. Script bash + curl** | Recorre una carpeta local y sube + procesa cada archivo. Se corre una vez con `./batch_upload.sh /ruta/carpeta` | ~10 min | Resolver tanda específica sin tocar la API |
| **B. Endpoint `POST /documents/batch`** | Múltiples archivos en un solo request HTTP. Reutilizable. | ~30-40 min | Si batch se vuelve capacidad permanente |

**Recomendación elegida (pendiente de ejecutar):** Opción A primero. Si más adelante el patrón batch es recurrente, agregamos B sin haber perdido nada.

Para implementar la A, falta saber:
- Ruta de la carpeta donde estarán los 30 archivos
- Si es mezcla de PDF/DOCX (para que el script filtre y no falle con `.DS_Store` u otros)

---

**Fecha:** 2026-04-29 (sesión 3)

**Trabajado en:**
- Definición de librerías para Objetivo 2 (conversión de documentos)
- Implementación completa de la 1ra iteración del Objetivo 2 (PDF + DOCX)
- Mejora de `POST /documents` para recibir archivos reales (multipart)
- Implementación del endpoint `POST /documents/{id}/process`
- Pruebas end-to-end con DOCX y PDF

**Resumen de la sesión:**

### Decisiones (ver `decisions.md`)
- **1ra iteración Objetivo 2:** PyMuPDF (PDF) + python-docx (DOCX)
- **2da iteración (diferida):** OCR (pytesseract), audio (faster-whisper), video (ffmpeg + faster-whisper)
- Razón: cubre la mayoría del corpus típico sin instalar dependencias pesadas; OCR/audio/video se agregan cuando se necesiten

### Implementación

1. **`requirements.txt`:** agregadas `PyMuPDF==1.24.0` y `python-docx==1.1.0`. Imagen Docker reconstruida.

2. **`src/services/conversion.py`** (nuevo): servicio puro con
   - `convert_pdf(file_path) -> str`
   - `convert_docx(file_path) -> str`
   - `convert_document(file_path, file_type) -> str` (dispatcher)
   - `save_converted_text(text, output_path)`
   - Excepciones: `UnsupportedFileTypeError`, `ConversionError`

3. **`src/api/main.py`** actualizado:
   - **`POST /documents`** ahora recibe `multipart/form-data` con `file` (UploadFile) y `metadata` (string JSON opcional). Guarda en `data/raw/{document_id}/{original_filename}` (folder por documento para evitar colisiones de nombre). El `file_type` se infiere automáticamente del sufijo del archivo.
   - **`POST /documents/{id}/process`** (nuevo): lee el documento de DB, llama al converter según `file_type`, guarda `.txt` en `data/processed/txt/{document_id}.txt`, actualiza `status` a `'converted'` (o `'failed'` si hay error). Devuelve `ProcessResponse` con `txt_path` y `char_count`.
   - Manejo de errores: 404 si el archivo no está en disco, 415 si el formato no es soportado, 500 si falla la conversión.

4. **Fix Pydantic v2 + SQLAlchemy:** SQLAlchemy reserva el atributo `metadata` en `Base`, así que el modelo usa la columna como `metadata_` (con `name="metadata"` en el SQL). Pydantic v2 estaba leyendo `MetaData()` en vez del JSONB. Solucionado con `validation_alias="metadata_"` en `DocumentResponse.metadata`.

### Verificación end-to-end
- ✅ DOCX: subido, procesado, texto extraído correctamente
- ✅ PDF: subido, procesado, texto extraído correctamente
- ✅ Listado `GET /documents` muestra status `converted` después de procesar
- ✅ Error 415 al intentar procesar `.txt` (formato no soportado)
- ✅ Validación de metadata como JSON válido (400 si está malformado)

### Aprendizajes

- **Pydantic v2 + SQLAlchemy con campo `metadata`:** siempre usar `metadata_` en el modelo SQLAlchemy (con `name="metadata"`) y `validation_alias="metadata_"` en el schema Pydantic. Si no, Pydantic toma el `Base.metadata` registry de SQLAlchemy.
- **`UploadFile` de FastAPI** requiere `python-multipart` (ya estaba en requirements). Para combinar archivo + metadata JSON en multipart, se manda un `file` (UploadFile) y un `metadata` (Form, string que parseamos como JSON).
- **Convención de almacenamiento:** `data/raw/{document_id}/{original_filename}` da folder por documento (sin colisiones de nombre, preserva nombre original).

### Estado actual del corpus
En la DB hay 4 documentos de prueba (1 raw orphan de un test fallido + 2 DOCX/PDF convertidos correctamente + 1 .txt que falló por formato no soportado). No hay valor real en estos datos — son solo de prueba. Si se quiere DB limpia para empezar Objetivo 3: `docker-compose down -v && docker-compose up -d db` y aplicar migración.

---

**Fecha:** 2026-04-29 (sesión 2)

**Trabajado en:**
- Levantar Docker por primera vez con DB + API + migraciones
- Diagnóstico y corrección de errores en la migración inicial de Alembic
- Ajuste de `docker-compose.yml` para montar `migrations/` y `alembic.ini` como volúmenes

**Resumen de la sesión:**

### Problema encontrado
Al ejecutar `docker-compose run api alembic upgrade head`, la migración fallaba con:
```
AttributeError: module 'alembic.op' has no attribute 'create_extension'
```

**Causa raíz:** dos cosas combinadas:
1. La migración `001_initial.py` había sido escrita usando `op.create_extension('vector')` y `op.drop_extension('vector')`, métodos que **no existen** en Alembic. La forma correcta es `op.execute('CREATE EXTENSION IF NOT EXISTS vector')` y `op.execute('DROP EXTENSION IF EXISTS vector')`.
2. La carpeta `migrations/` no estaba montada como volumen en `docker-compose.yml`, sino que se copiaba a la imagen con `COPY . .` en el `Dockerfile`. Por eso, aunque se editara el archivo local, el contenedor seguía corriendo la versión vieja hasta hacer `docker-compose build`.

### Cambios aplicados

1. **`migrations/versions/001_initial.py` línea 114:** corregido `op.drop_extension('vector')` → `op.execute('DROP EXTENSION IF EXISTS vector')`. (La línea 20 del `upgrade` ya estaba correcta con `op.execute(...)` localmente, pero el contenedor tenía la versión vieja).

2. **`docker-compose.yml`:** agregados dos volúmenes al servicio `api` para que los cambios futuros en migraciones no requieran reconstruir la imagen:
   ```yaml
   volumes:
     - ./src:/app/src
     - ./data:/app/data
     - ./migrations:/app/migrations
     - ./alembic.ini:/app/alembic.ini
   ```

3. **Imagen reconstruida** con `docker-compose build api` y migración aplicada con `docker-compose run --rm api alembic upgrade head`.

### Verificación

- ✅ Extensión `vector` instalada en PostgreSQL
- ✅ 6 tablas creadas: `alembic_version`, `documents`, `entities`, `graphs`, `metrics`, `relationships`
- ✅ API respondiendo en `http://localhost:8000`:
  - `GET /` → `{"message":"Semantic Classification API","status":"running"}`
  - `GET /health` → `{"status":"healthy"}`
  - Swagger UI disponible en `http://localhost:8000/docs`

### Aprendizajes para futuras sesiones

- **Alembic no tiene `op.create_extension` ni `op.drop_extension`** — usar `op.execute('CREATE EXTENSION ...')` y `op.execute('DROP EXTENSION ...')`.
- **Si se edita un archivo local pero los cambios no se reflejan en el contenedor**, verificar si la carpeta está montada como volumen en `docker-compose.yml`. Si no, hay que hacer `docker-compose build` para reconstruir la imagen.
- **Comando para migraciones nuevas:**
  ```bash
  docker-compose run --rm api alembic revision --autogenerate -m "descripción"
  docker-compose run --rm api alembic upgrade head
  ```

---

**Fecha:** 2026-04-29 (sesión 1)

**Trabajado en:**
- Definición del schema de la base de datos (5 modelos SQLAlchemy)
- Creación de migraciones iniciales con Alembic
- Integración de la API con la base de datos
- Endpoints básicos para documentos y entidades

**Resumen de la sesión:**
- Se crearon los modelos `Document`, `Entity`, `Relationship`, `Graph`, `Metric` en `src/models/models.py`
- Se configuró `src/core/database.py` con SQLAlchemy + pgvector
- Se creó la migración inicial `migrations/versions/001_initial.py` con las 5 tablas e índices
- Se actualizaron los endpoints de la API: `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /entities`
- La API ahora inicializa la DB automáticamente al arrancar

---

**Fecha:** 2026-04-27

**Trabajado en:**
- Creación de estructura de documentación (.agent/)
- Definición de objetivos del proyecto (1-10)
- Decisiones tecnológicas principales
- Configuración de Docker
- Redacción de metodología técnica completa

## Resumen de la sesión

### Completado:
1. ✅ Estructura de carpetas `.agent/` creada con 9 archivos
2. ✅ README en raíz apuntando a `.agent/` para agentes
3. ✅ `project-overview.md` con contexto del proyecto
4. ✅ `architecture.md` con flujo y estructura
5. ✅ `tech-stack.md` con tecnologías decididas
6. ✅ `conventions.md` con convenciones de código
7. ✅ `tasks.md` con los 10 objetivos como roadmap
8. ✅ `decisions.md` con 5 ADRs registrados
9. ✅ `tech-debt.md` con deuda técnica conocida
10. ✅ Docker configurado (docker-compose.yml + Dockerfile)
11. ✅ Estructura de carpetas `src/` y `data/`
12. ✅ API básica con 2 endpoints probada con Postman
13. ✅ `methodology.md` con las 10 etapas, métricas e interpretación crítica

### Decisiones tomadas:
- PostgreSQL + pgvector como DB
- FastAPI para API
- SQLAlchemy + Alembic para ORM y migraciones
- Arquitectura híbrida (DB + Archivos)
- Docker para desarrollo local
- Sin autenticación inicial

### Pendientes de decisión:
- Librerías de conversión (Obj 2)
- Limpieza de textos (Obj 3)
- Clasificación de entidades (Obj 4)
- Modelo de embeddings (Obj 5)
- Matrices y relaciones (Obj 6)
- Grafos (Obj 7)
- Métricas (Obj 8)

## Pendientes para próxima sesión

1. Definir schema de la base de datos (modelos SQLAlchemy)
2. Crear migraciones iniciales con Alembic
3. Implementar endpoint POST /documents
4. Empezar con Objetivo 2 (conversión)

## Notas

- El proyecto es para análisis territorial con perspectiva crítica, feminista y de género
- El dashboard es el consumidor principal de la API (tenerlo en mente)
- La documentación debe leerse completa al iniciar cada sesión nueva

---

## Historial de sesiones

| Fecha | Trabajado en |
|-------|--------------|
| 2026-04-27 | Creación de documentación, definición de objetivos, decisiones tecnológicas, configuración de Docker, metodología técnica |
| 2026-04-29 (s1) | Schema de DB (5 modelos SQLAlchemy), migración inicial con Alembic, integración API ↔ DB, endpoints `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /entities` |
| 2026-04-29 (s2) | Levantar Docker por primera vez; corrección de errores en migración (`op.create_extension`/`op.drop_extension` no existen); ajuste de volúmenes en `docker-compose.yml` para `migrations/` y `alembic.ini`; verificación de tablas creadas y API respondiendo |
| 2026-04-29 (s3) | Definición de librerías Objetivo 2 (PyMuPDF + python-docx, 1ra iteración); creación de `src/services/conversion.py`; mejora de `POST /documents` para recibir archivos reales (multipart); nuevo endpoint `POST /documents/{id}/process`; fix Pydantic v2 + SQLAlchemy `metadata`; pruebas end-to-end con PDF y DOCX |
| 2026-04-29 (s4) | Pruebas manuales del pipeline con 5 archivos reales desde Postman; aclaración conceptual de APIs HTTP / Postman / multipart uploads / arquitectura portable a S3; plan definido para procesar los ~25 restantes (Opción A: script bash + curl) |
| 2026-05-04 (s5) | Implementación de endpoint `POST /documents/batch` para subida y procesamiento múltiple en un solo request; documentación actualizada; API reiniciada y endpoint probado; usuaria puede ahora subir carpeta completa desde Postman sin scripts |
| 2026-05-04 (s6) | Decisiones de fondo Objetivo 3 (limpieza determinista por capas, no IA, preservar conectores/mayúsculas/acentos, descartar ruido editorial); inspección de 2 .txt reales con perfiles distintos; implementación completa Capa 1 (`ftfy` + servicio + endpoint `POST /documents/{id}/clean` + migración Alembic con 4 columnas de métricas); 28 documentos del corpus limpiados (avg 1.57% reducción, max 7.30%) |
| 2026-05-04 (s7) | Análisis programático de patrones reales en el corpus (frecuencia de líneas, longitudes); diseño de heurística combinada para headers; implementación Capa 2 (2a páginas + 2b headers, NO 2c); modo `?dry_run=true` en endpoint `/clean`; validación dry-run sobre 5 archivos; aplicación Capa 1+2 al corpus (28 docs, avg 4.92% reducción, max 9.93%, 1,540 páginas + 899 headers eliminados) |
| 2026-05-04 (s8) | Verificación en disco de que Capa 2 sí se aplicó (falsa alarma de usuaria); implementación Capa 2c (re-unión de oraciones partidas por columnas) con heurística que respeta listas verticales y nuevos párrafos; validación visual antes/después; aplicación Capa 1+2+2c al corpus (28 docs, **7,121 oraciones re-unidas**, mismas métricas de reducción porque 2c no quita caracteres) |
| 2026-05-04 (s9) | Análisis programático de tipos de TOC en el corpus (3 tipos identificados, incluyendo trampa de palabra "Índice/Contenido" sin TOC real en 7 docs); implementación Capa 3 (3a dot leaders + 3b bloques TOC numerados al inicio con protección de "primeros 15%" + ≥5 líneas + ≥70% numeradas); validación dry_run con 0 falsos positivos; aplicación Capa 1+2+2c+3 al corpus (28 docs, avg 5.54% reducción, max 14.04%; +21 dot leaders + 5 bloques TOC + 122 líneas TOC eliminadas en 6/28 archivos) |
| 2026-05-05 (s10) | Decisión arquitectónica: Capa 4 dedicada a ruido editorial por contenido (4a URLs/emails, 4b créditos, 4c portadas MAYÚSCULAS, 4d agradecimientos); análisis programático del corpus identificó falsos positivos en regex de créditos; implementación con extensión B inicial fue agresiva (40 líneas en Plan AGRAP, comió instituciones firmantes); refinamiento a B1 (parar tras 5 líneas sin keyword) bajó a 13 líneas preservando instituciones; aplicación Capa 1+2+2c+3+4 al corpus (28 docs, **avg 7.01% reducción, max 16.55%**; +305 URLs +47 emails +89 portada +62 créditos +45 agradecimientos en 22/28 archivos) |
| 2026-05-06 (s15) | Correcciones manuales de MISC_Spacy aplicadas al dataset (170 textos descartados, 354 corregidos); mejoras a clasificador (protección contra falsos positivos + nuevas keywords); entrenamiento modelo embeddings iteración 1 (`paraphrase-multilingual-MiniLM-L12-v2` + `BatchHardTripletLoss`, 1 época, loss 4.81); datasets generados: `_all_entities_corrected.json` (13,681 entidades) + `_entities_for_embeddings.json` (6,510 únicas) |
