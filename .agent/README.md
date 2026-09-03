# Semantic Classification — documentación para agentes

Este directorio es la fuente de contexto y seguimiento del proyecto. La
información vigente vive en `context/`; las decisiones históricas viven en
`sessions/`; los planes se clasifican por estado.

## Orden de lectura recomendado

1. `context/PROJECT_CONTEXT.md` — resumen vigente, decisiones y métricas.
2. `context/tasks.md` — roadmap y pendientes accionables.
3. `context/architecture.md` — arquitectura y flujos técnicos.
4. `tech-debt.md` — riesgos y deuda conocida.
5. `plans/active/` — planes en ejecución.
6. `sessions/` — consultar solo la bitácora relacionada con la tarea actual.

## Estructura documental

```text
.agent/
├── README.md
├── context/
│   ├── PROJECT_CONTEXT.md
│   ├── architecture.md
│   ├── tasks.md
│   └── tech-debt.md
├── plans/
│   ├── active/
│   ├── completed/
│   └── future/
└── sessions/                 # historial cronológico, no fuente de estado
```

## Regla de fuentes

- El estado actual se escribe una sola vez en `context/PROJECT_CONTEXT.md`.
- Las tareas abiertas se mantienen únicamente en `context/tasks.md`.
- Una sesión registra decisiones y resultados puntuales; no duplica todo el
  contexto estable.
- Un plan describe una entrega; al terminar se mueve a `plans/completed/`.
- Los documentos históricos no se reescriben: se marcan como superados cuando
  una decisión posterior los reemplaza.

## Operación local

```bash
docker compose up -d
docker compose exec api alembic upgrade head
# API: http://localhost:8000/docs
```

Para el stack, endpoints, estados de documentos y convenciones de código,
consultar `context/PROJECT_CONTEXT.md` y `context/architecture.md`.
