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
