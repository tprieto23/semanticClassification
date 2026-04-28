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

### 3. Limpieza (Objetivo 3)
- IA para depuración de textos
- Versión original + versión limpia
- Tipo de ruido y reglas: TBD

### 4. Clasificación (Objetivo 4)
- Entidades: comunidades, instituciones, lugares, prácticas, infraestructuras, valores ecológicos, narrativas, actores, acciones
- Clasificación: TBD

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
POST /documents → data/raw/ → DB (status=raw) → process → converted → cleaned → entities → vectors
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

### Variables de entorno (.env)

```env
POSTGRES_DB=semantic_db
POSTGRES_USER=sc_user
POSTGRES_PASSWORD=sc_password
POSTGRES_PORT=5432
API_PORT=8000
DATABASE_URL=postgresql://sc_user:sc_password@db:5432/semantic_db
```
