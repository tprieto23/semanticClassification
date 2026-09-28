# Clasificación documental durante la ingesta

**Fecha:** 28 Sep 2026

## Decisión

Las cargas individuales y por lote incorporan tres atributos obligatorios:

- `year`: entero de cuatro dígitos entre 1000 y 9999;
- `productive_sector`: vocabulario controlado, inicialmente `Agroforestry`;
- `document_type`: `academic`, `technical_report`, `project_report`,
  `policy_document`, `manual_or_guide`, `institutional_document` u `other`.

Se eligió `document_type` en lugar de `class` para expresar claramente el
significado del atributo y evitar el término reservado de Python. En una carga
por lote, los tres valores son comunes para todos los archivos de la petición.

## Implementación y compatibilidad

La migración `a4b5c6d7e8f9` añade los campos a `documents`, sus restricciones e
índices para año y tipo documental. Las columnas aceptan `NULL` para no alterar
los documentos históricos; FastAPI las exige para toda carga nueva.

La colección `postman_collection.json` incluye los campos en las solicitudes
individual y batch. El encabezado multipart no se fija manualmente, de modo que
Postman pueda generar el boundary correcto.

## Verificación

- 6 pruebas de ingesta con `unittest`: correctas.
- Validación JSON de la colección de Postman: correcta.
- Migración aplicada en PostgreSQL.
- Contrato activo verificado mediante respuesta 422 con los cinco campos
  obligatorios: archivo, incubadora, año, sector y tipo documental.
