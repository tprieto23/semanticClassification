# Sesión 19 Ago 2026 — Endpoints de red plana

## Resultado

Se implementó el plan de red de coocurrencia como una sola red plana, sin layers
ni macrocapa L2. Las cinco categorías participan en igualdad de condiciones y se
admiten todas las combinaciones, incluidas CHAR–CHAR y LOC–LOC.

## Endpoints activos

- `POST /analysis/network`: corpus completo o `incubator_number=1..8`.
- `GET /analysis/network/latest`: lectura del último resultado para la misma
  combinación de scope, `minimum_weight` e `include_isolates`.
- `POST /documents/{document_id}/network`: red de un documento en estado
  `fuzzyMatching`.

Los tres usan `minimum_weight` (por defecto 1) e `include_isolates` (por defecto
true). La respuesta incluye cobertura documental, conteos, nodos por categoría,
las 15 combinaciones de categorías, nodos con mayor fuerza y URLs absolutas.

## Decisiones técnicas

- La DB sigue siendo la única fuente de verdad; no se añadió ninguna tabla.
- Los resultados se calculan desde `entities` + `canonical_entities`.
- Las menciones con distintos contextos dentro de una misma oración ya no causan
  error. Cada observación de arista conserva el contexto de las dos entidades.
- Los artefactos se escriben primero en un directorio temporal y se reemplazan de
  forma atómica, con bloqueo por destino.
- Cada variante tiene su propio directorio para evitar sobrescrituras.
- Solo `s3/archivosRed` se monta como estático en `/files/networks`; los crudos,
  textos limpios y NER no quedan expuestos.
- El HTML interactivo tiene una sola disposición plana y exporta también el mismo
  payload como `g{peso}_graph.json` para una futura interfaz propia.
- Para componentes de más de 500 nodos se usa un layout determinista de costo
  lineal; para componentes pequeños se conserva el layout por fuerzas.

## Validación

- Suite completa dentro de Docker: 44 pruebas exitosas.
- Documento `aabdeb37-2e89-42be-bd38-62fa571db5c5`: 233 menciones, 182 nodos,
  694 aristas; artefacto JSON servido por HTTP.
- Corpus G₃ sin aislados: 78/78 documentos, 41.148 menciones, 661 nodos, 1.208
  aristas; build HTTP exitoso en aproximadamente 5 segundos.
- Corpus G₁ completo con aislados: 16.527 nodos, 45.866 aristas y 2.649
  componentes; build HTTP exitoso en aproximadamente 15 segundos.
- `GET latest`, HTML interactivo, JSON y GraphML verificados mediante sus URLs.
- La imagen Docker se reconstruyó con NetworkX y Matplotlib y la API quedó sana.

## Reentrada

El código está en la rama local `feat/endpoints-red-coocurrencia`, sin commit
porque no fue solicitado. El archivo `.DS_Store` ya estaba modificado y se dejó
intacto. Próximo paso funcional: usar el HTML generado para explorar asociaciones
o decidir si una UI v2a necesita filtros/comparaciones adicionales.
