# Idioma (`language`) en documentos

**Fecha:** 2026-08-18

## Contexto

Se necesitaba registrar el idioma de cada documento (español, inglés, portugués,
otros) para poder filtrar y procesar el corpus por idioma en el futuro. La
propiedad se había omitido durante el diseño inicial de la ingesta, por lo que
debe registrarse de forma retroactiva sobre documentos ya cargados.

## Decisión de diseño

- La columna se modela como `VARCHAR(10)` nullable, sin enum rígido en base de
datos, para permitir códigos estándar (`es`, `en`, `pt`) y etiquetas regionales
o de uso interno (`quechua`, etc.).
- La validación es suave: Pydantic exige entre 2 y 10 caracteres y normaliza a
minúsculas.
- El campo está disponible de forma opcional en el upload (`POST /documents` y
`POST /documents/batch`), pero el flujo principal de registro es posterior a la
carga.
- Todos los documentos existentes quedan con `language = NULL` hasta que se les
asigne uno.

## Implementación

- Migración `d5e6f7a8b9c0_add_language_to_documents.py`:
  - Agrega `documents.language VARCHAR(10) NULL`.
  - Crea índice `ix_documents_language`.
- `src/models/documents.py`: columna `language` en el ORM.
- `src/models/documents_repo.py`: filtro por idioma y
`actualizar_language()`.
- `src/api/schemas/documents.py`:
  - `DocumentRead` expone `language`.
  - `DocumentLanguageUpdate` para el PATCH individual.
  - `SetLanguageBatchRequest` / `SetLanguageBatchResponse` para lote.
- `src/services/documents.py`:
  - `cargar_documento()` y `cargar_documentos()` aceptan `language` opcional.
  - `actualizar_language()` y `actualizar_language_varios()`.
- `src/api/routers/documents.py`:
  - `language` opcional en `POST /documents`, `POST /documents/batch` y
    `GET /documents`.
  - `PATCH /documents/{id}/language`.
  - `POST /documents/set-language-batch`.

## Migración aplicada

```bash
docker compose exec api alembic upgrade head
```

Resultado: todos los documentos existentes quedan con `language = NULL`.

## Verificación

- `GET /health` responde correctamente.
- `PATCH /documents/{id}/language` con `{"language":"en"}` actualiza el campo.
- `GET /documents?language=en` filtra correctamente.
- `POST /documents/set-language-batch` actualiza varios documentos.

## Commits

Para mantener el historial limpio se separó el trabajo previo del feature de
hoy:

1. `4b23fe4` — `feat: resolución canónica v2, incubadoras numéricas y
documentación asociada`
2. `140e30f` — `feat(ingestion): agrega language a documentos con registro
posterior`

El archivo `.env` quedó fuera de ambos commits porque contiene credenciales.

## Siguiente paso

Asignar el idioma a los documentos ya cargados mediante
`POST /documents/set-language-batch` o `PATCH /documents/{id}/language`,
según lo que se sepa de cada archivo.
