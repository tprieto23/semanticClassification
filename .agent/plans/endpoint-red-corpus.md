# Plan — Endpoint de red de coocurrencia (corpus completo)

## Objetivo

Exponer como endpoint HTTP la generación del grafo de coocurrencia de **todo el
corpus**, calculado al vuelo desde `entities`, sin tablas nuevas. Reemplaza los
dos comandos CLI manuales (`src.analysis.cooccurrence` + `src.analysis.network_visualization`)
por una sola llamada.

## Decisiones ya tomadas

- **Red plana de 5 categorías** (CHAR, LOC, PRAC, INFRA, GOV). **Sin capas /
  sin macrocapa "L2"** — obsoleto, se elimina.
- **Cálculo al vuelo, recompute total** en cada llamada → **idempotente**. No es
  incremental. No hay tabla materializada (eso es v2b).
- Salida = **archivos** (graphml, imágenes, CSV) vía `Storage`/`s3`. La respuesta
  HTTP es un **resumen + rutas de descarga**.
- Nodo = `canonical_id` (identidad global). Arista = dos canónicos en la misma
  `(document_id, sentence_id)`. Peso = nº de oraciones distintas donde coocurren.

## Ruta

```
POST /analysis/network
```

Query params opcionales:
- `minimum_weight: int = 1` — filtra aristas por peso en la exportación (g1, g3, …).
- `include_isolates: bool = true` — incluye nodos sin aristas que alcancen el umbral.
- `incubator_number: int | None` (1..8) — opcional; grafo de una sola incubadora.

## Flujo

1. **Reunir menciones.** Nueva consulta que trae **todas** las menciones de
   documentos con `status = 'fuzzyMatching'` (join `entities` → `canonical_entities`),
   opcionalmente filtradas por `incubator_number`.
2. **Cobertura.** Contar documentos incluidos vs total del corpus.
3. `build_sentence_cooccurrence(menciones)` — **sin cambios**, ya soporta N documentos.
4. **Exportar artefactos (versión plana):** `nodes.csv`, `edges.csv`,
   `sentences.csv`, `edge_observations.csv`, `category_pair_summary.csv`,
   `cooccurrence_adjacency.mtx`, `sentence_node_incidence.mtx`, `summary.json`.
   → **sin** carpeta `blocks/` (decomposición L2 eliminada).
5. **Visualizar (solo layout libre):** `g{w}.graphml`, `g{w}_free.png/svg`,
   `g{w}_interactive.html`, `g{w}_nodes.csv`, `g{w}_edges.csv`, `g{w}_summary.json`.
6. **Guardar** en `s3/archivosRed/corpus/` (o carpeta fechada si se quiere historial).
   Devolver el resumen.

## Respuesta HTTP (schema `NetworkBuildResponse`)

```
generated_at
scope: "corpus" | "incubator:{n}"
coverage: { documents_included, documents_total, excluded_by_status }
counts:   { canonical_nodes, sentences, undirected_edges, max_edge_weight }
nodes_by_category: { CHAR, LOC, PRAC, INFRA, GOV }
category_pair_summary: [ 15 combinaciones con observed_edges, density,
                         total_cooccurrences, mean_weight, max_weight ]   ← LAS CORRELACIONES
top_nodes_by_strength: [ { canonical_name, category, degree, strength } ]
outputs: { graphml, interactive_html, free_png, nodes_csv, edges_csv, summary_json }
```

`category_pair_summary` es la respuesta directa a la pregunta de investigación
("¿qué categorías se asocian con qué?"). Ya lo calcula `_category_pair_rows`.

## Cambios de código

**Nuevos:**
- `src/services/network.py` — servicio orquestador. Recibe un **scope**
  (`corpus` | `incubadora N` | `document_id`) y de ahí en adelante el pipeline
  es idéntico. Reutilizado por el endpoint por-documento.
- `src/api/routers/analysis.py` — router `POST /analysis/network`.
- `src/api/schemas/network.py` — `NetworkBuildResponse` + sub-modelos.
- `src/config.py` — `STORAGE_NETWORK = s3/archivosRed`.

**Modificar:**
- `src/analysis/cooccurrence.py`:
  - Nueva `load_all_db_mentions(status="fuzzyMatching", incubator_number=None)`
    (o generalizar `load_db_mentions` con filtro opcional).
  - **Quitar capas:** `LAYER_BY_CATEGORY`, `GROUP_CATEGORIES`, `BLOCK_SPECS`,
    `_export_blocks`; `layer`/`layer_index` en `NodeRecord` y `NODE_FIELDS`;
    `layer_pair` en `edges.csv`.
- `src/analysis/network_visualization.py`:
  - **Quitar layout por capas:** `build_layered_layout`, `_draw_layer_background`,
    `_interactive_layered_positions`, `LAYER_BY_CATEGORY`, `LAYERED_Y`, bandas; y
    en el HTML el botón "Capas" y `drawBands`.
  - **Conservar:** `build_free_layout`, graphml, CSV, HTML (solo disposición libre).
- `entities_repo.py` (o `documents_repo.py`): consulta de menciones por status /
  incubadora.

> **Mínimo viable:** generar solo lo plano y dejar el código de capas sin usar.
> **Recomendado:** borrar el código de capas en la misma pasada para no confundir.

## Idempotencia

Cada llamada recalcula desde la DB. Correr N veces sobre el mismo estado → el mismo
grafo. Los documentos nuevos aparecen solo cuando llegan a `fuzzyMatching`. Sin
doble conteo posible (ver también nota de idempotencia en las conversaciones).

## Cobertura / transparencia

La respuesta siempre informa "X de Y documentos incluidos", para dejar claro que
los que están a mitad del pipeline (raw/converted/cleaned/ner) **no** cuentan aún.

## Servir archivos + endpoint de URLs

La carpeta `s3/` es una carpeta local en la raíz del proyecto. Para que los
artefactos tengan **URLs abribles en el navegador** (efecto "S3 real"), se montan
como estáticos y se agrega un endpoint de lectura que devuelve esas URLs. Esto
concreta el patrón **generar antes / leer durante** (ideal para demos).

### 1. Montar `s3/` como estático

En `src/api/main.py`:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/files", StaticFiles(directory="s3"), name="files")
```

Con esto, `s3/archivosRed/corpus/g1.graphml` se sirve en
`http://<host>/files/archivosRed/corpus/g1.graphml`. Según el tipo, el navegador:

| Archivo | Comportamiento |
|---|---|
| `g1_interactive.html` | se **renderiza** (explorador en vivo) |
| `g1_free.png` | se muestra la imagen |
| `g1.graphml` | se descarga / se ve como XML → Gephi |
| `g1_nodes.csv` / `g1_edges.csv` | se descargan |

### 2. Endpoint de lectura (instantáneo, no recalcula)

```
GET /analysis/network/latest        (opcional: ?incubator_number=N)
```

Lee el `summary.json` ya generado en disco y devuelve el resumen + las **URLs**
(no rutas de disco). Respuesta instantánea; no dispara ningún build.

```python
from fastapi import Request

@router.get("/analysis/network/latest")
def latest(request: Request):
    base = str(request.base_url).rstrip("/")            # http://localhost:8000
    prefix = f"{base}/files/archivosRed/corpus"
    # leer s3/archivosRed/corpus/summary.json y mapear cada output a su URL
    return { "coverage": ..., "category_pair_summary": ..., "outputs": {
        "graphml":          f"{prefix}/g1.graphml",
        "interactive_html": f"{prefix}/g1_interactive.html",
        "free_png":         f"{prefix}/g1_free.png",
        "nodes_csv":        f"{prefix}/g1_nodes.csv",
    }}
```

URLs absolutas armadas con `request.base_url` para que apunten bien sin importar
host/puerto.

### Flujo de demo resultante

```
(antes)   POST /analysis/network        → hornea archivos en s3/archivosRed/corpus/
(en vivo) GET  /analysis/network/latest → resumen + URLs (instantáneo)
(clic)    URL del .html                 → explorador renderizado en el navegador
(clic)    URL del .graphml              → Gephi
```

### Notas

- `StaticFiles` da URL por archivo pero **no** lista la carpeta (no hay índice
  navegable tipo bucket). No hace falta: el endpoint de lectura ya "lista" los
  archivos de la corrida devolviendo sus URLs.
- **Sin auth:** correcto para uso local. Si algún día sale de local, restringir
  qué se sirve bajo `/files` (fuera de alcance ahora).
- El endpoint `POST` de build también puede devolver ya las URLs (mismo mapeo),
  para no depender de un segundo llamado.

## Fuera de alcance (ver v2)

- Filtrado interactivo servido por API → **v2a**.
- Tabla materializada de coocurrencias → **v2b**.
