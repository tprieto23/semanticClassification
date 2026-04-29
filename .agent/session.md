# Session Context

## Última sesión

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
