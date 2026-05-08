# Architecture

## Arquitectura general

Sistema de procesamiento documental para análisis territorial socioambiental con perspectiva crítica, feminista y de género.

**Flujo principal:**
```
Documentos no estructurados → Conversión → Limpieza → Clasificación → Vectores → Grafos → Métricas → API → Dashboard
```

## Estructura del proyecto

```
.
├── .agent/                 # Documentación del proyecto
├── data/
│   ├── raw/                # Archivos originales (no modificar)
│   ├── processed/
│   │   ├── txt/            # Archivos convertidos a texto plano
│   │   ├── cleaned/        # Textos depurados
│   │   └── entities/       # Entidades extraídas (JSON)
│   ├── output/
│   │   ├── vectors/        # Representaciones vectoriales (.npy)
│   │   ├── matrices/       # Matrices de adyacencia (.parquet)
│   │   ├── graphs/         # Grafos de conocimiento (.graphml)
│   │   └── metrics/        # Métricas calculadas
│   └── temp/               # Archivos temporales
├── src/
│   ├── api/                # FastAPI endpoints
│   ├── core/               # Lógica principal
│   ├── models/             # Modelos SQLAlchemy
│   ├── services/           # Servicios de procesamiento
│   ├── training/           # Scripts de entrenamiento de modelos
│   └── utils/              # Utilidades
├── migrations/             # Alembic migrations
├── tests/                  # Tests
├── docker-compose.yml      # Servicios Docker
└── Dockerfile
```

## Componentes

### 1. Almacenamiento (Objetivo 1)
- Sistema local de carpetas (`data/`)
- Futuro: migración a S3
- Metadata en PostgreSQL

### 2. Conversión (Objetivo 2)
- PDF, Word, imágenes, audio, video → `.txt`
- Agente de IA para conversión
- Metadata guardada en DB

### 3. Limpieza (Objetivo 3) — Capas 1 + 2 + 3 + 4 implementadas
- Enfoque **determinista por capas** (no IA — ver `decisions.md` 2026-05-04)
- Original (`data/processed/txt/`) se conserva intacto; resultado va a `data/processed/cleaned/`
- **Capa 1 (universal):** ftfy + unicodedata NFC + control chars + colapsar espacios y saltos de línea + strip por línea
- **Capa 2 (estructural por estadística):**
  - 2a: números de página
  - 2b: headers/footers repetidos (con protección de >10 palabras para contenido narrativo)
  - 2c: re-unión de oraciones partidas por columnas
- **Capa 3 (estructural por patrón — TOCs):**
  - 3a: dot leaders (5+ puntos consecutivos)
  - 3b: bloques TOC numerados en primeros 15% del doc (incluye header `CONTENIDO/ÍNDICE`)
- **Capa 4 (editorial por contenido):**
  - 4a: URLs y emails (inline o línea completa)
  - 4b: créditos editoriales (Autor:, Diseño:, ISBN, etc.) con extensión B1 (parar en 5 líneas sin keyword) en primeros 15% / últimos 5% del doc
  - 4c: portadas con ≥4 líneas en MAYÚSCULAS en primeros 5% del doc
  - 4d: secciones de agradecimientos (header explícito → próximo título)
  - 4e: líneas de contacto/footers (teléfonos, direcciones, emails, footers con pipe)
  - 4f: placeholders de MS Word (`Error! Bookmark not defined`, `Main Title Subtitle Description`, etc.) incluyendo multi-línea
- **Skip si doc < 200 líneas:** Capa 2 entera + Capa 3b + Capa 4 (4b/4c/4d). Capa 3a, 4a, 4e, 4f aplican siempre.
- Servicio: `src/services/cleaning.py`
- Endpoint: `POST /documents/{id}/clean?dry_run=<bool>` (dry_run devuelve métricas sin escribir archivos ni actualizar DB)
- Métricas guardadas en columnas de `documents` (`original_char_count`, `cleaned_char_count`, `reduction_percentage`, `cleaning_metadata` JSONB con detalle por capa)

### 4. Clasificación (Objetivo 4) — 🚧 Fase 3: XLM-RoBERTa fine-tuned en progreso

**Arquitectura anterior (DEPRECADA):**
- **Fase 1 (NER genérico):** spaCy (`es_core_news_sm` + `en_core_web_sm`) + `langdetect`
  - Extrae entidades nombradas: PER, ORG, LOC, GPE, MISC, PRODUCT, EVENT, WORK_OF_ART
  - Problemas: corta entidades, falsos positivos estructurales, requiere editar manualmente casi todo
- **Fase 2 (mapeo con reglas):** `entity_classifier.py` con 158 líneas de regex + keywords
  - Mapea spaCy → 9 categorías del proyecto
  - Problemas: ~33% van a `MISC_Spacy`, reglas frágiles, no entiende contexto

**Nueva arquitectura (Fase 3):**
- **Modelo:** `xlm-roberta-base` fine-tuned para Token Classification (NER BIO)
  - Un solo modelo multilingüe (español + inglés), sin necesidad de `langdetect`
  - Predice directamente las 9 categorías del proyecto: B-{cat} / I-{cat} / O
  - Entiende contexto de la oración completa, no solo keywords
- **Dataset de entrenamiento:** `_all_entities_corrected.json` → formato BIO
  - 3,679 oraciones, 19 etiquetas BIO, división por documento
  - ⚠️ Ground truth provisional (contiene errores residuales de la primera iteración)
- **Pipeline de entrenamiento:**
  - `src/training/prepare_ner_dataset.py` → genera dataset BIO
  - `src/training/train_ner_xlm.py` → fine-tuning con `XLMRobertaForTokenClassification`
  - `src/training/infer_ner_xlm.py` → inferencia en texto libre
- **Resultados (1 época, CPU):** Test F1 0.511 | LUGAR F1 0.64 | COMUNIDAD/PRÁCTICA F1 0.00

**Estado actual:**
- Servicio: `src/services/ner.py` (aún usa spaCy, pendiente integrar XLM-R)
- Endpoint: `POST /documents/{id}/extract-entities` (aún usa spaCy)
- Modelo entrenado: `models/ner_xlm_roberta/final/`

### 5. Vectorización (Objetivo 5)
- Representación vectorial de entidades
- Modelo, dimensiones, normalización: TBD

### 6. Matrices de adyacencia (Objetivo 6)
- Relaciones entre entidades
- Definición de relación, pesos, tipos: TBD

### 7. Grafos de conocimiento (Objetivo 7)
- Nodos = entidades, Aristas = relaciones
- Librería, tipo de grafo, exportación: TBD

### 8. Métricas (Objetivo 8)
- Centralidad, grado, comunidades, densidad, distancia
- Globales y por nodo: TBD

### 9. API (Objetivo 9)
- FastAPI + OpenAPI (Swagger)
- Dockerizado
- Sin autenticación por ahora (→ tech-debt.md)

### 10. Base de datos (Objetivo 10)
- PostgreSQL + pgvector
- SQLAlchemy (ORM)
- Alembic (migraciones)
- Docker

## Patrones de diseño

- **Pipeline:** Procesamiento por etapas
- **Híbrido DB + Archivos:** Metadata en DB, datos pesados en archivos
- **API-first:** Todo accesible vía API para dashboard

## Flujos principales

### Subida de documento
```
POST /documents             → data/raw/{id}/file.ext           → DB (status=raw)
POST /documents/{id}/process→ data/processed/txt/{id}.txt      → DB (status=converted)
POST /documents/{id}/clean  → data/processed/cleaned/{id}.txt  → DB (status=cleaned + métricas)
POST /documents/{id}/extract-entities → DB (status=processed + entities)
[futuro] vectors → relationships → graphs → metrics
```

**Endpoint batch (atajo upload+convert en un solo request):**
```
POST /documents/batch  → recibe N archivos → guarda en raw + convierte a txt en serie
```

### Consulta de entidades
```
GET /entities?type=X → DB query → JSON response
```

### Generación de grafo
```
DB relationships → Construir grafo → Guardar .graphml → DB (graph_id) → GET /graphs/{id}
```

## Decisiones arquitectónicas

- **DB:** PostgreSQL + pgvector (ver `decisions.md`)
- **API:** FastAPI
- **ORM:** SQLAlchemy
- **Migraciones:** Alembic
- **Contenerización:** Docker

## Infraestructura Docker

### Servicios

| Servicio | Imagen | Puerto | Función |
|----------|--------|--------|---------|
| `db` | `pgvector/pgvector:pg16` | 5432 | PostgreSQL con extensión vectorial |
| `api` | (custom) | 8000 | FastAPI |

### Archivos de Docker

```
.
├── docker-compose.yml    # Orquesta 2 servicios: db + api
├── Dockerfile            # Imagen custom para la API
├── .env                  # Variables de entorno (DB, passwords)
├── .dockerignore         # Qué excluir de la imagen
└── requirements.txt      # Dependencias de Python
```

### docker-compose.yml

**Servicio `db`:**
- Imagen: `pgvector/pgvector:pg16`
- Puerto: `5432:5432`
- Volumen: `postgres_data` (persistencia)
- Healthcheck: verifica que PostgreSQL esté listo
- Variables: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

**Servicio `api`:**
- Build: desde `Dockerfile`
- Puerto: `8000:8000`
- Volúmenes: 
  - `./src:/app/src` (código, hot-reload)
  - `./data:/app/data` (archivos)
- Depende de: `db` (espera healthcheck)
- Command: `uvicorn src.api.main:app --reload`

### Dockerfile

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Comandos útiles

```bash
# Levantar todo
docker-compose up

# Levantar en background
docker-compose up -d

# Ver logs
docker-compose logs -f

# Ver estado
docker-compose ps

# Parar todo
docker-compose down

# Reiniciar
docker-compose restart
```

### Endpoints actuales

- `GET /` → `{"message": "Semantic Classification API", "status": "running"}`
- `GET /health` → `{"status": "healthy"}`
- `GET /docs` → Swagger UI (OpenAPI automático)
- `POST /documents` → Subir un archivo (multipart/form-data)
- `GET /documents` → Listar documentos (con filtro por status)
- `GET /documents/{id}` → Ver detalle de documento
- `POST /documents/{id}/process` → Procesar documento (conversión a TXT)
- `POST /documents/batch` → Subir y procesar múltiples archivos en un solo request
- `POST /documents/{id}/extract-entities` → Extraer entidades NER de un documento limpio (⚠️ aún usa spaCy; pendiente migrar a XLM-RoBERTa)
- `GET /entities` → Listar entidades (con filtros por categoría y documento)

### Variables de entorno (.env)

```env
POSTGRES_DB=semantic_db
POSTGRES_USER=sc_user
POSTGRES_PASSWORD=sc_password
POSTGRES_PORT=5432
API_PORT=8000
DATABASE_URL=postgresql://sc_user:sc_password@db:5432/semantic_db
```
