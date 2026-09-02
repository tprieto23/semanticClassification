# Semantic Classification

API de clasificación semántica para análisis de documentos no estructurados.

## Objetivo

Procesar documentos (PDF, DOCX), extraer entidades relevantes y mapear relaciones para análisis territorial socioambiental.

## Cómo correr

```bash
# Levantar todo
docker compose up -d

# Migraciones
docker compose exec api alembic upgrade head

# Si hay cambios en modelos
docker compose exec api alembic revision --autogenerate -m "descripcion"
docker compose exec api alembic upgrade head

# API
http://localhost:8000/docs
```

## Stack

| Capa | Tecnología |
|------|-----------|
| API | FastAPI + Uvicorn |
| DB | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy 2.0 |
| Migraciones | Alembic |
| Conversión PDF | **PyMuPDF** (fast path) + Docling OCR (fallback) |
| Conversión DOCX | Docling |
| Parseo MD | markdown-it-py |
| Reparación encoding | ftfy |
| NER | Anthropic Claude (API) + extracción few-shot estructurada |
| Almacenamiento | s3/ (local, montado en Docker) |
| Contenedores | Docker + docker-compose |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/documents` | Subir archivo; exige `incubator_number` entre 1 y 8; `language` opcional |
| POST | `/documents/batch` | Subir múltiples archivos bajo una incubadora común; `language` opcional |
| GET | `/documents` | Listar con filtros (`status`, `file_type`, `incubator_number`, `language`) |
| GET | `/documents/{id}` | Ver documento |
| DELETE | `/documents/{id}` | Eliminar documento |
| PATCH | `/documents/{id}/language` | Registrar idioma después de la carga |
| POST | `/documents/set-language-batch` | Registrar idioma para varios documentos |
| POST | `/documents/{id}/process` | Convertir a Markdown |
| POST | `/documents/process-batch` | Convertir todos en raw |
| POST | `/documents/{id}/clean` | Limpiar texto |
| POST | `/documents/clean-batch` | Limpiar todos en converted |
| POST | `/documents/{id}/revert` | Revertir al estado anterior |
| POST | `/documents/{id}/extract-entities` | Extraer entidades NER (Anthropic) |
| POST | `/documents/{id}/fuzzy-matching` | Resolver menciones v2, registrar evidencia y asociar canónicos |
| POST | `/documents/{id}/network` | Construir la red plana de un documento en `fuzzyMatching` |
| POST | `/documents/{id}/network/projections/prac-infra-gov-v1` | Construir la proyección tipada por documento |
| POST | `/analysis/network` | Construir red filtrada por incubadora e idioma desde el body |
| GET | `/analysis/network/latest` | Leer la última red ya generada para los mismos parámetros |
| POST | `/analysis/network/projections/prac-infra-gov-v1` | Construir la red semántica tipada y sus nueve vistas |
| POST | `/analysis/network/projections/{projection_id}/clusterings/leiden` | Calcular comunidades Leiden sobre una vista ya construida |
| GET | `/analysis/network/projections/prac-infra-gov-v1/latest` | Leer la última proyección sin recalcular |
| GET | `/analysis/network/projections/prac-infra-gov-v1/views` | Enumerar vistas completa, cruzada, intratipo y por par |
| GET | `/analysis/network/projections/prac-infra-gov-v1/edges/{source}/{target}/evidence` | Recuperar oraciones, documentos y entidades de una arista |

El POST de corpus acepta este body opcional:

```json
{
  "incubator_number": 4,
  "language": "es",
  "minimum_weight": 1,
  "include_isolates": true
}
```

`incubator_number` admite `1..8` o `"all"`; `language` admite un idioma o
`"all"`. Los filtros se combinan con AND. Sin body se usa `all/all`, peso 1 y
aislados incluidos. Los artefactos se sirven únicamente bajo `/files/networks/`.

La proyección analítica principal se construye aparte de la red histórica de cinco
categorías y no la sobrescribe. Incluye nodos `PRAC`, `INFRA` y `GOV` y los seis
pares no dirigidos posibles, incluidas las relaciones intratipo. Una sola llamada
genera las vistas `all`, `cross`, `intra`, `prac-prac`, `infra-infra`, `gov-gov`,
`prac-infra`, `prac-gov` e `infra-gov`. La evidencia maestra se conserva en
`sentences.csv`, `sentence_entities.csv` y `edge_observations.csv`.

El mismo POST admite una construcción analítica discriminada y retrocompatible:

```json
{
  "incubator_number": "all",
  "language": "es",
  "construction": {
    "method": "document-recurrent-core-v1",
    "minimum_node_document_count": 2,
    "edge_weighting": "fractional-document",
    "include_minor_components": true
  }
}
```

El método selecciona entidades que aparecen en el mínimo de documentos dentro del
scope solicitado, conserva las aristas entre ellas y exporta `sentence_count`,
`document_count`, soporte independiente, pesos fraccionales y `analysis_weight`.
Genera las nueve vistas para todos los componentes y para la componente principal.
Sin `construction`, el endpoint mantiene el contrato histórico por umbral W1/W2/W3.

El clustering se ejecuta por separado sobre una vista GraphML existente. La
solicitud recibe la misma selección de construcción, además de `view`,
`component_scope` y una configuración reproducible de Leiden. La respuesta publica
`network_clustered.graphml`, `communities.csv`, `community_members.csv` y
`clustering_summary.json`. El GraphML conserva la red fuente y añade
`modularity_class`, `community_id`, `community_size` y `community_color`; en Gephi
se puede usar `modularity_class` en Appearance → Partition. La misma combinación de
GraphML, configuración y semilla se reutiliza desde caché mientras no cambie el
hash SHA-256 de la red fuente.

## Estados del documento

| Estado | Significado |
|---|---|
| `raw` | Recién subido, sin convertir |
| `converted` | Convertido a .md |
| `cleaned` | Texto limpiado, listo para NER |
| `ner` | Entidades extraídas |
| `fuzzyMatching` | Menciones normalizadas y asociadas a entidades canónicas |

## Convenciones

- **Python:** snake_case para archivos, variables y funciones. PascalCase para clases.
- **Endpoints:** router fino, lógica en services, DB en models.
- **Storage:** `Storage.guardar(content, filename, target_dir)` recibe el directorio desde la capa de servicio.
- **Excepciones:** heredan de `DocumentoError(codigo_http)`, capturadas por handler global en `main.py`.
- **Commits:** solo cuando se pida explícitamente.
- **Variables de entorno:** `.env` (gitignored). `DATABASE_URL` es la única obligatoria.

## Dependencias del sistema (Dockerfile)

La imagen base `python:3.11-slim` requiere estos paquetes adicionales para Docling/OpenCV/PyMuPDF:

- `gcc` — compilación
- `libgl1` — OpenGL
- `libglib2.0-0` — GLib
- `libxcb1` — X11 protocol (requerido por OpenCV)
- `libxcb-shm0` — shared memory (X11)
- `libxcb-xfixes0` — X11 fixes extension
- `libxcb-xinerama0` — X11 multi-head extension
- `libglx-mesa0` — Mesa GLX (OpenGL)

## Reglas de trabajo

- **Autorización previa:** antes de cualquier edición de código, presentar el cambio propuesto y esperar autorización explícita. No modificar archivos sin visto bueno.

- **Python:** snake_case para archivos, variables y funciones. PascalCase para clases.
- **Endpoints:** router fino, lógica en services, DB en models.
- **Storage:** `Storage.guardar(content, filename, target_dir)` recibe el directorio desde la capa de servicio.
- **Excepciones:** heredan de `DocumentoError(codigo_http)`, capturadas por handler global en `main.py`.
- **Commits:** solo cuando se pida explícitamente.
- **Variables de entorno:** `.env` (gitignored). `DATABASE_URL` es la única obligatoria.
