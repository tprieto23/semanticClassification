# Sesión 20 Ago 2026 — Filtros de red por body

## Contrato implementado

`POST /analysis/network` recibe opcionalmente:

```json
{
  "incubator_number": 4,
  "language": "es",
  "minimum_weight": 1,
  "include_isolates": true
}
```

- `incubator_number`: entero entre 1 y 8 o `"all"`.
- `language`: identificador normalizado a minúsculas o `"all"`.
- Los filtros se combinan mediante AND.
- Sin body se conserva el comportamiento histórico: corpus completo, G1 y aislados.
- Solo entran documentos en estado `fuzzyMatching`.
- La respuesta expone `filters` para hacer explícita la selección aplicada.

`GET /analysis/network/latest` mantiene query params porque un GET no debe depender
de un body. Incubadora, idioma, peso y aislados deben coincidir con una variante
previamente generada.

## Separación de artefactos

- `all/all`: `archivosRed/corpus/…`
- `all/es`: `archivosRed/corpus/language-es/…`
- `4/all`: `archivosRed/incubator-4/…`
- `4/es`: `archivosRed/incubator-4/language-es/…`

Esto evita que una red filtrada sobrescriba otra selección.

## Validación real

- `all/all`, sin body: 78 documentos, 41.148 menciones, 16.527 nodos G1.
- `4/es`, G3 sin aislados: 23 documentos, 8.575 menciones, 149 nodos.
- `all/es`, G3 sin aislados: 59 documentos, 30.162 menciones, 527 nodos.
- `4/all`, G3 sin aislados: 33 documentos, 12.339 menciones, 183 nodos.
- Las cuatro variantes respondieron 200 y devolvieron rutas distintas.
- `GET latest` resolvió correctamente las cuatro selecciones.
- Incubadora 9 y lenguajes con rutas inválidas respondieron 422.
- Suite completa: 47 pruebas exitosas.

La colección `postman_collection.json` incluye build filtrado, build completo sin
body y lectura latest con filtros.
