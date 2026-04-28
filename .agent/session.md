# Session Context

## Última sesión

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
