# Incubadoras numéricas en la ingesta documental

**Fecha:** 2026-08-13

## Decisión metodológica

Cada documento nuevo pertenece obligatoriamente a una incubadora controlada por
un número entero entre 1 y 8. No se asignan nombres a las incubadoras ni se crea
un catálogo separado. La dimensión se conserva en `documents` y se recupera
desde entidades derivadas mediante `entity.document_id -> document`.

## Implementación

- Nueva columna nullable `documents.incubator_number` de tipo `SMALLINT`.
- Restricción PostgreSQL `incubator_number BETWEEN 1 AND 8` e índice de consulta.
- `POST /documents` exige una incubadora seleccionable 1..8.
- `POST /documents/batch` aplica una incubadora común a todos los archivos del lote.
- `GET /documents` permite filtrar por `incubator_number`.
- `DocumentRead` devuelve la incubadora persistida.
- Migración aplicada: `c4d5e6f7a8b9_add_incubator_number_to_documents.py`.

La columna permanece nullable temporalmente porque existen tres documentos
procesados antes de introducir esta dimensión. Las cargas nuevas no pueden
omitirla. Después de clasificar o retirar el legado podrá aplicarse una segunda
migración para convertirla en `NOT NULL`.

## Limpieza de datos de prueba

Se identificaron y eliminaron 29 documentos que estaban en estado `raw`, junto
con sus archivos de `s3/archivosCrudos`. Después de la operación quedaron cero
filas `raw`. Se conservaron sin modificación un documento `converted` y dos
documentos `fuzzyMatching`.

Durante la eliminación se corrigió `Storage.eliminar` para aceptar rutas
opcionales `None`, condición normal en documentos que todavía no han avanzado
por todas las etapas.

## Verificación

- Alembic en revisión `c4d5e6f7a8b9 (head)`.
- OpenAPI publica el enum entero `[1,2,3,4,5,6,7,8]`.
- El directorio de crudos contiene solamente los tres archivos de documentos
  procesados que continúan registrados.
- Suite automatizada: 39 pruebas exitosas.

## Ajuste posterior

- Se eliminó `1770a776-d813-47c0-8738-b7f23e06f230` después de revertirlo a
  `raw`, incluido su directorio residual de imágenes.
- Se asignó `incubator_number = 1` a
  `61b5cf8e-8109-408c-a571-cdf5b31512ca`, conservando su estado
  `fuzzyMatching` y sus resultados derivados.
- Permanecen dos documentos: el documento anterior en incubadora 1 y un único
  documento histórico con incubadora `NULL`.
- `DocumentService.eliminar` ahora elimina también `images_path`.
- Suite automatizada posterior: 40 pruebas exitosas.
