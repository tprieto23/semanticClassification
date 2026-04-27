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
