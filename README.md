# Semantic Classification

API de clasificación semántica para documentos no estructurados y análisis de
redes semánticas auditables.

## Para agentes

La documentación operativa y el historial están en [`.agent/`](.agent/).
Empezar por [`.agent/README.md`](.agent/README.md), que define el orden de
lectura y la organización de las fuentes.

## Inicio rápido

```bash
docker compose up -d
docker compose exec api alembic upgrade head
```

API local: <http://localhost:8000/docs>
Salud: <http://localhost:8000/health>

## Código principal

- API: `src/api/`
- Servicios: `src/services/`
- Modelos y repositorios: `src/models/`
- Análisis de redes: `src/analysis/`
- Pruebas: `tests/`
- Migraciones: `migrations/`

Para el contexto técnico vigente, consultar
[`.agent/context/PROJECT_CONTEXT.md`](.agent/context/PROJECT_CONTEXT.md).
