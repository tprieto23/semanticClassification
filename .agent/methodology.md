# Metodología Técnica

## Visión general del pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│  DOCUMENTOS NO ESTRUCTURADOS → INFORMACIÓN ESTRUCTURADA → ANÁLISIS     │
└─────────────────────────────────────────────────────────────────────────┘

Etapa 1: Ingesta      → raw/ (archivos originales)
Etapa 2: Conversión   → processed/txt/ (.txt planos)
Etapa 3: Limpieza     → processed/cleaned/ (textos depurados)
Etapa 4: Clasificación→ processed/entities/ (entidades JSON)
Etapa 5: Vectorización→ output/vectors/ (embeddings .npy)
Etapa 6: Relaciones   → output/matrices/ (matrices .parquet)
Etapa 7: Grafos       → output/graphs/ (grafos .graphml)
Etapa 8: Métricas     → output/metrics/ (resultados JSON)
```

---

## Etapa 1: Ingesta y almacenamiento

### Proceso
1. Usuario sube archivo vía `POST /documents`
2. Archivo se guarda en `data/raw/{original_filename}`
3. Metadata se registra en PostgreSQL

### Schema
```sql
documents (
  id UUID PRIMARY KEY,
  original_filename TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_type TEXT NOT NULL,  -- pdf, docx, jpg, mp3, mp4, etc.
  file_size_bytes BIGINT,
  status TEXT NOT NULL,     -- raw, converted, cleaned, processed, failed
  uploaded_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB            -- autor, fecha, fuente, descripción
)
```

### Métricas de ingesta
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Total documentos | `COUNT(*)` | Volumen del corpus |
| Por tipo | `COUNT(*) GROUP BY file_type` | Distribución de formatos |
| Tamaño promedio | `AVG(file_size_bytes)` | Complejidad de procesamiento |
| Tasa de falla | `COUNT(status='failed') / COUNT(*)` | Calidad de archivos de entrada |

### Interpretación territorial
- **Más documentos** = Más fuentes para análisis crítico
- **Diversidad de formatos** = Múltiples voces (escritas, orales, visuales)
- **Metadata completa** = Contexto situado de cada documento

---

## Etapa 2: Conversión a texto plano

### Proceso
1. Leer archivo desde `data/raw/`
2. Extraer texto según formato:
   - **PDF:** `PyMuPDF` o `pdfplumber`
   - **Word:** `python-docx`
   - **Imágenes:** OCR con `EasyOCR` o `Tesseract`
   - **Audio:** Whisper (transcripción)
   - **Video:** Extraer audio + Whisper
3. Guardar en `data/processed/txt/{document_id}.txt`
4. Actualizar `documents.status = 'converted'`

### Métricas de conversión
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Tasa de conversión | `COUNT(converted) / COUNT(raw)` | Efectividad del proceso |
| Word count promedio | `AVG(LENGTH(txt_content))` | Cantidad de texto extraído |
| Tiempo por documento | `AVG(conversion_time)` | Eficiencia del pipeline |
| Fallos por formato | `COUNT(failed) GROUP BY file_type` | Formatos problemáticos |

### Interpretación territorial
- **Texto extraído** = Voz del documento preservada
- **Fallos en OCR/audio** = Posibles pérdida de narrativas orales/visuales
- **Word count bajo** = Documento puede ser imagen escaneada sin texto

---

## Etapa 3: Limpieza y depuración

### Proceso
1. Leer texto desde `data/processed/txt/`
2. Aplicar limpieza:
   - Eliminar números de página, headers, footers
   - Normalizar whitespace
   - Eliminar caracteres especiales no informativos
   - Preservar nombres propios, lugares, fechas
3. Guardar en `data/processed/cleaned/{document_id}.txt`
4. Actualizar `documents.status = 'cleaned'`

### Técnicas de limpieza
```python
# Ejemplo de pipeline de limpieza
def clean_text(text: str) -> str:
    text = remove_page_numbers(text)      # "Página 1 de 10" → ""
    text = normalize_whitespace(text)     # Multiple spaces → single
    text = remove_urls_emails(text)       # URLs, emails → ""
    text = fix_encoding(text)             # Codificación → UTF-8
    return text
```

### Métricas de limpieza
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Reducción de texto | `(len(original) - len(cleaned)) / len(original)` | % de ruido eliminado |
| Tokens preservados | `COUNT(tokens_cleaned)` | Información útil retenida |
| Entidades detectadas | `COUNT(named_entities)` | Elementos relevantes identificados |

### Interpretación territorial
- **Alta reducción** = Mucho ruido editorial/formato
- **Baja reducción** = Texto ya limpio o formato simple
- **Entidades preservadas** = Nombres de comunidades, lugares, actores mantenidos

---

## Etapa 4: Clasificación de entidades

### Categorías de entidades

| Categoría | Descripción | Ejemplos |
|-----------|-------------|----------|
| **COMUNIDAD** | Grupos humanos organizados | "Comunidad de Pescadores de X", "Asamblea de Mujeres" |
| **INSTITUCIÓN** | Organizaciones formales | "Ministerio de Ambiente", "Alcaldía de Y" |
| **LUGAR** | Ubicaciones geográficas | "Río Z", "Montaña A", "Vereda B" |
| **PRACTICA** | Acciones repetidas, saberes | "Pesca artesanal", "Trueque", "Ritual de siembra" |
| **INFRAESTRUCTURA** | Construcciones físicas | "Puente", "Escuela", "Represa" |
| **VALOR_ECOLÓGICO** | Elementos naturales significativos | "Bosque nativo", "Especie endémica", "Fuente de agua" |
| **NARRATIVA** | Discursos, relatos, marcos | "Desarrollo sostenible", "Justicia ambiental", "Despojo" |
| **ACTOR** | Individuos con agencia | "Líder comunitario", "Funcionario", "Investigador" |
| **ACCION** | Eventos, procesos | "Consulta previa", "Protesta", "Mesa de negociación" |

### Proceso
1. Leer texto desde `data/processed/cleaned/`
2. Aplicar NER (Named Entity Recognition) con IA
3. Clasificar cada entidad en categoría
4. Guardar en `data/processed/entities/{document_id}.json`
5. Insertar en PostgreSQL tabla `entities`

### Schema
```sql
entities (
  id UUID PRIMARY KEY,
  document_id UUID REFERENCES documents(id),
  category TEXT NOT NULL,        -- COMUNIDAD, INSTITUCIÓN, etc.
  text TEXT NOT NULL,            -- Texto de la entidad
  normalized_text TEXT,          -- Nombre normalizado
  context TEXT,                  -- Párrafo/frase donde aparece
  position_start INT,            -- Posición en el texto
  position_end INT,
  confidence FLOAT,              -- Confianza de la clasificación
  metadata JSONB,                -- Información adicional
  created_at TIMESTAMP DEFAULT NOW()
)
```

### Métricas de clasificación
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Entidades por doc | `COUNT(entities) / COUNT(documents)` | Densidad de información |
| Por categoría | `COUNT(*) GROUP BY category` | Perfil temático del corpus |
| Entidades únicas | `COUNT(DISTINCT normalized_text)` | Diversidad de elementos |
| Entidades repetidas | `COUNT(*) - COUNT(DISTINCT normalized_text)` | Patrones recurrentes |

### Interpretación territorial (PERSPECTIVA CRÍTICA)

#### Por categoría:
- **COMUNIDAD ↑** = Fuerte presencia de organización comunitaria
- **INSTITUCIÓN ↑** = Alta presencia estatal/empresarial
- **LUGAR ↑** = Territorio bien delimitado geográficamente
- **PRACTICA ↑** = Saberes locales, economías propias
- **INFRAESTRUCTURA ↑** = Intervención física en el territorio
- **VALOR_ECOLÓGICO ↑** = Riqueza natural, posible conflicto extractivo
- **NARRATIVA ↑** = Disputa de sentidos, marcos interpretativos
- **ACTOR ↑** = Individuos clave, liderazgos
- **ACCION ↑** = Dinamismo, conflicto, movilización

#### Análisis feminista y de género:
- **Buscar:** Entidades de mujeres, colectivos feministas, prácticas de cuidado
- **Preguntar:** ¿Quiénes son las actoras mencionadas? ¿Qué roles se les asignan?
- **Visibilizar:** Trabajo reproductivo, economías del cuidado, liderazgo de mujeres

---

## Etapa 5: Vectorización (Embeddings)

### Proceso
1. Para cada entidad, generar embedding del texto + contexto
2. Modelo: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (o similar)
3. Dimensión: 384 dimensiones
4. Guardar vector en PostgreSQL (pgvector) y crudo en `output/vectors/`

### Schema con pgvector
```sql
CREATE EXTENSION vector;

entities (
  -- ... campos anteriores ...
  embedding vector(384)  -- pgvector
)

CREATE INDEX ON entities USING ivfflat (embedding vector_cosine_ops);
```

### Métricas de vectorización
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Similaridad promedio | `AVG(cosine_similarity)` | Cohesión semántica del corpus |
| Entidades cercanas | `COUNT(similarity > 0.8)` | Posibles duplicados/variaciones |
| Coverage del modelo | `COUNT(embedding IS NOT NULL) / COUNT(*)` | Entidades vectorizables |

### Interpretación territorial
- **Alta similitud** = Mismos conceptos repetidos (hegemonía discursiva)
- **Baja similitud** = Diversidad de narrativas
- **Clusters naturales** = Comunidades semánticas (temas que emergen)

---

## Etapa 6: Matrices de adyacencia

### Definición de relación

Dos entidades están **relacionadas** si:
1. **Co-ocurrencia:** Aparecen en mismo párrafo o ventana de N tokens
2. **Similitud semántica:** `cosine_similarity(embedding_a, embedding_b) > threshold`
3. **Relación explícita:** IA detecta relación sintáctica (sujeto-verbo-objeto)

### Tipos de matriz

| Tipo | Descripción | Uso |
|------|-------------|-----|
| **Binaria** | 0 = sin relación, 1 = con relación | Estructura básica |
| **Ponderada** | Peso = fuerza de relación (0.0-1.0) | Análisis de intensidad |
| **Dirigida** | A→B ≠ B→A (relación tiene dirección) | Relaciones asimétricas |
| **Por documento** | Una matriz por documento | Análisis individual |
| **Global** | Todas las entidades de todos los docs | Visión del corpus |

### Proceso
1. Para cada par de entidades (A, B):
   - Calcular co-ocurrencia en documentos
   - Calcular similitud semántica
   - Asignar peso: `weight = alpha * coocurrencia + beta * similitud`
2. Guardar matriz en `output/matrices/{scope}_adjacency.parquet`
3. Insertar relaciones en PostgreSQL

### Schema
```sql
relationships (
  id UUID PRIMARY KEY,
  entity_source_id UUID REFERENCES entities(id),
  entity_target_id UUID REFERENCES entities(id),
  weight FLOAT NOT NULL,       -- Fuerza de la relación
  relationship_type TEXT,      -- COOCURRENCIA, SIMILITUD, EXPLICITA
  document_id UUID,            -- Documento donde se detectó
  metadata JSONB,
  created_at TIMESTAMP DEFAULT NOW()
)
```

### Métricas de relaciones
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Densidad de relaciones | `COUNT(relations) / (N * (N-1))` | Conectividad del sistema |
| Peso promedio | `AVG(weight)` | Fuerza de conexiones |
| Relaciones por entidad | `COUNT(*) GROUP BY entity_id` | Centralidad de grado |

### Interpretación territorial
- **Alta densidad** = Sistema altamente interconectado
- **Peso alto** = Relaciones fuertes, estables
- **Entidades con muchas relaciones** = Actores centrales, nodos clave

---

## Etapa 7: Grafos de conocimiento

### Construcción del grafo

```
Nodos = Entidades (con categoría como atributo)
Aristas = Relaciones (con peso como atributo)
```

### Proceso
1. Leer relaciones desde PostgreSQL o matriz
2. Construir grafo con `networkx`
3. Asignar atributos a nodos (categoría, documento, etc.)
4. Guardar en `output/graphs/{graph_id}.graphml`

### Tipos de grafo

| Tipo | Descripción | Cuándo usar |
|------|-------------|-------------|
| **No dirigido** | A—B (simétrico) | Co-ocurrencia, similitud |
| **Dirigido** | A→B (asimétrico) | Relaciones causales, influencia |
| **Ponderado** | Aristas con peso | Intensidad de relación |
| **Multiplex** | Múltiples tipos de arista | Relaciones heterogéneas |

### Métricas de grafo (ver Etapa 8)

### Interpretación territorial (ANÁLISIS CRÍTICO)

#### Estructura del grafo:
- **Grafo denso** = Territorio con múltiples interacciones
- **Grafo disperso** = Territorio fragmentado, poco conectado
- **Componentes conexos** = Sub-territorios, comunidades separadas
- **Nodos puente** = Actores que conectan grupos (posibles mediadores)

#### Perspectiva feminista:
- **¿Dónde están las mujeres?** = Posición de nodos de mujeres/colectivos
- **¿Qué conexiones tienen?** = Redes de cuidado, economía solidaria
- **¿Son centrales o periféricas?** = Visibilidad en el sistema

---

## Etapa 8: Métricas de análisis de redes

### Métricas a calcular

#### A nivel de nodo (por entidad)

| Métrica | Fórmula | Interpretación territorial |
|---------|---------|---------------------------|
| **Grado** | `degree(v) = |conexiones(v)|` | Cantidad de relaciones directas. Actor muy conectado. |
| **Grado ponderado** | `weighted_degree(v) = Σ peso(conexiones)` | Intensidad de relaciones. Actor con vínculos fuertes. |
| **Centralidad de intermediación** | `betweenness(v) = Σ (caminos que pasan por v / total caminos)` | Actor puente, mediador, gatekeeper. Controla flujo de información. |
| **Centralidad de cercanía** | `closeness(v) = 1 / Σ distancia(v, otros)` | Actor que alcanza rápido a todos. Difunde información eficientemente. |
| **Centralidad de vector propio** | `eigenvector(v) ∝ Σ centralidad(vecinos)` | Conectado con otros importantes. Prestigio, influencia. |
| **PageRank** | `PR(v) = (1-d)/N + d * Σ (PR(u)/out_degree(u))` | Importancia recursiva. Actor influyente en el sistema. |

#### A nivel de grafo (global)

| Métrica | Fórmula | Interpretación territorial |
|---------|---------|---------------------------|
| **Densidad** | `density = 2*|E| / (|V| * (|V|-1))` | Qué tan conectado está el territorio. 1 = totalmente conectado. |
| **Diámetro** | `diameter = max(distancia(u, v))` | Máxima distancia entre actores. Territorio fragmentado si es alto. |
| **Distancia promedio** | `avg_path_length = AVG(distancia(u, v))` | Qué tan cerca están los actores entre sí. |
| **Coeficiente de clustering** | `clustering(v) = triángulos(v) / triángulos_posibles` | Qué tan agrupados están los vecinos de un actor. Comunidades locales. |
| **Modularidad** | `Q = (fracción aristas intra-comunidad) - (valor esperado)` | Fuerza de la estructura comunitaria. 1 = comunidades muy definidas. |
| **Número de comunidades** | `communities = detect_communities()` | Cuántos grupos distintos hay en el territorio. |

### Schema de métricas
```sql
metrics (
  id UUID PRIMARY KEY,
  graph_id UUID,
  entity_id UUID,              -- NULL si es métrica global
  metric_name TEXT NOT NULL,   -- degree, betweenness, etc.
  metric_value FLOAT NOT NULL,
  calculated_at TIMESTAMP DEFAULT NOW()
)
```

### Interpretación crítica de métricas

#### Actores centrales (alto degree, betweenness, eigenvector):
- **Instituciones con alta centralidad** = Poder concentrado, posible dominación
- **Comunidades con baja centralidad** = Marginalización, exclusión de decisiones
- **Actores puente (high betweenness)** = Mediadores, posibles cooptados o facilitadores

#### Comunidades detectadas (modularidad):
- **Comunidades por categoría** = Actores similares se relacionan más (homofilia)
- **Comunidades transversales** = Alianzas entre tipos distintos (solidaridad)
- **Comunidades aisladas** = Grupos excluidos del sistema

#### Perspectiva feminista y de género:
- **Mujeres con alta centralidad** = Liderazgo femenino visible
- **Mujeres periféricas** = Invisibilización, roles subordinados
- **Redes de cuidado** = Comunidades de prácticas reproductivas, economía feminista
- **Brecha de género en centralidad** = Desigualdad en acceso a poder/decisiones

---

## Etapa 9: API para gestión del flujo

### Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/documents` | Subir archivo |
| `GET` | `/documents` | Listar documentos |
| `GET` | `/documents/{id}` | Ver detalle + estado |
| `POST` | `/documents/{id}/process` | Procesar documento |
| `GET` | `/entities` | Listar entidades (con filtros) |
| `GET` | `/entities/{id}` | Ver entidad + vector |
| `GET` | `/relationships` | Listar relaciones |
| `GET` | `/graphs` | Listar grafos |
| `GET` | `/graphs/{id}` | Ver grafo (nodos, aristas) |
| `GET` | `/metrics` | Métricas globales |
| `GET` | `/metrics/{entity_id}` | Métricas de entidad |

### Métricas de API
| Métrica | Fórmula | Interpretación |
|---------|---------|----------------|
| Tiempo de respuesta | `AVG(response_time)` | Performance del sistema |
| Requests por minuto | `COUNT(requests) / tiempo` | Uso de la API |
| Tasa de error | `COUNT(status>=400) / COUNT(*)` | Estabilidad |

---

## Etapa 10: Base de datos

### Schema completo (resumen)

```sql
-- Documentos
documents (id, original_filename, file_path, file_type, status, metadata, uploaded_at)

-- Entidades
entities (id, document_id, category, text, normalized_text, context, embedding, confidence, metadata)

-- Relaciones
relationships (id, entity_source_id, entity_target_id, weight, relationship_type, document_id)

-- Grafos
graphs (id, name, description, file_path, created_at)

-- Métricas
metrics (id, graph_id, entity_id, metric_name, metric_value, calculated_at)
```

---

## Dashboard: Visualización e interpretación

### Vistas recomendadas

1. **Vista de documentos**
   - Lista con estado de procesamiento
   - Filtros por tipo, fecha, estado

2. **Vista de entidades**
   - Tabla filtrable por categoría
   - Mapa de lugares (si hay coordenadas)
   - Nube de tags por categoría

3. **Vista de grafo**
   - Visualización interactiva (D3.js, Cytoscape)
   - Colores por categoría
   - Tamaño por centralidad
   - Filtros por categoría, peso de arista

4. **Vista de métricas**
   - Top 10 entidades por centralidad
   - Distribución de categorías
   - Evolución temporal (si hay múltiples versiones)

### Interpretación guiada para el usuario

**Preguntas para el análisis crítico:**

1. **¿Quiénes son los actores centrales?**
   - ¿Instituciones o comunidades?
   - ¿Hombres o mujeres?

2. **¿Qué narrativas dominan?**
   - ¿Qué categorías son más frecuentes?
   - ¿Qué valores ecológicos se mencionan?

3. **¿Cómo está estructurado el territorio?**
   - ¿Comunidades bien definidas o fluido?
   - ¿Actores puente o fragmentación?

4. **¿Qué relaciones de poder se observan?**
   - ¿Instituciones conectadas entre sí?
   - ¿Comunidades periféricas?

5. **¿Dónde está el cuidado, lo reproductivo?**
   - ¿Prácticas de cuidado visibles?
   - ¿Redes de mujeres identificadas?

---

## Resumen de métricas e interpretación

| Etapa | Métricas clave | Interpretación crítica |
|-------|---------------|----------------------|
| Ingesta | Total docs, por tipo | Volumen y diversidad del corpus |
| Conversión | Tasa de conversión, word count | Calidad de extracción |
| Limpieza | % reducción, entidades preservadas | Ruido vs. información útil |
| Clasificación | Entidades por categoría | Perfil temático, sesgos |
| Vectorización | Similaridad promedio | Cohesión semántica |
| Relaciones | Densidad, peso promedio | Conectividad del sistema |
| Grafos | Componentes, nodos puente | Estructura territorial |
| Métricas | Centralidad, modularidad | Poder, influencia, comunidades |

---

## Notas metodológicas finales

### Perspectiva crítica
- Los datos **no son neutrales**: reflejan relaciones de poder
- Las categorías **no son fijas**: pueden reproducir o cuestionar estructuras
- El grafo **es una representación**: simplifica la complejidad territorial

### Perspectiva feminista
- Visibilizar **trabajo de cuidado** y economías propias
- Cuestionar **jerarquías** en la red (¿quiénes son centrales?)
- Buscar **narrativas silenciadas** (¿qué no aparece en el grafo?)

### Perspectiva situada
- El análisis **es desde un lugar**: explicitar posición política
- Las comunidades **no son homogéneas**: hay conflictos internos
- El territorio **es dinámico**: el grafo es una foto en el tiempo

### Ética
- **Consentimiento:** Documentos pueden contener información sensible
- **Anonimización:** Considerar para actores en situaciones de riesgo
- **Devolución:** Resultados deben retornar a las comunidades
