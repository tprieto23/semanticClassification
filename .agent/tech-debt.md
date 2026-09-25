# Deuda técnica y riesgos conocidos

Este archivo contiene únicamente asuntos abiertos. Las tareas de producto y
los próximos pasos metodológicos se mantienen en `context/tasks.md`.

## Documentación

- Mantener sincronizados `context/PROJECT_CONTEXT.md` y `context/tasks.md` al
  cerrar cada sesión.
- No duplicar el estado actual dentro de las bitácoras; registrar allí solo
  decisiones, evidencia y resultados puntuales.
- Revisar enlaces internos cuando se muevan planes o documentos de contexto.

## Datos y operación

- `documents.incubator_number` sigue nullable por compatibilidad con legado;
  convertirlo a `NOT NULL` cuando todos los documentos históricos estén
  clasificados o retirados.
- Asignar idioma a los documentos que aún tengan `language = NULL`.
- Los artefactos en `s3/` son derivados y deben poder regenerarse desde la DB.

## Análisis

- Asociar `CHAR` y `LOC` a clusters con evidencia de oraciones.
- Reforzar la construcción de relaciones para validar que cada miembro persistido
  coincide con la comunidad exacta del GraphML y no está asignado a dos meta-nodes
  en la misma partición. La instantánea española actualmente validada no presenta
  discrepancias, pero el servicio no verifica explícitamente todas esas invariantes.

## Infraestructura y seguridad

- La API de archivos de red no tiene autenticación; es adecuada para uso local.
- `ANTHROPIC_API_KEY` debe permanecer únicamente en `.env` y nunca entrar al
  historial de Git.
- La suite debe ejecutarse preferentemente dentro del entorno Docker definido
  por el proyecto.
