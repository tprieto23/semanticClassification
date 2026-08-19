# Sesión de trabajo — 5 Ago 2026

## Propósito de esta bitácora

Este archivo es el punto de reentrada para la próxima sesión. Al retomar, leer primero:

1. `.agent/README.md`
2. `.agent/architecture.md`
3. `.agent/tasks.md`
4. Este archivo

Solicitud sugerida al agente: **“Contextualicémonos con el proyecto, lee `.agent` y dime en qué estado vamos y en qué debemos seguir.”**

## Estado de Git al cierre

- Rama: `feat/reedireccion2`
- Working tree: limpio
- Últimos commits relevantes:
  - `7945ad8 feat(fuzzy-matching): canonicalize entity mentions`
  - `4764610 feat(fuzzy-matching): add canonical entity foundation`
  - `a6dfc06 fix(ner): locate repeated mentions by sentence`
  - `7fb2a5e feat(ner): simplify schema and add curated few-shot extraction`

La bitácora de esta sesión se crea después de `7945ad8`, por lo que requerirá su propio commit en la siguiente sesión o antes de apagar si se desea dejar todo limpio.

## Arquitectura vigente

El pipeline documental es:

```text
raw → converted → cleaned → ner → fuzzyMatching
```

### NER

- Usa Anthropic Claude con extracción **few-shot**, no zero-shot.
- Usa 25 ejemplos curados en `data/ner/few_shot_examples.json`.
- Solo reconoce cinco categorías: `CHAR`, `LOC`, `INFRA`, `GOV` y `PRAC`.
- `ACT`, `NARV` y los catálogos antiguos están fuera del flujo vigente.
- Claude devuelve menciones mediante tool use obligatorio.
- El backend calcula y valida offsets absolutos.
- Cada oración tiene un `sentence_id` estable.
- Las apariciones repetidas se conservan por separado, incluso cuando tienen el mismo texto.
- El endpoint NER guarda `s3/archivosNER/{document_id}.json`, registra `ner_path` y cambia `cleaned → ner`.
- El endpoint NER **no escribe en `entities`**.

### Fuzzy matching canónico

Endpoint:

```text
POST /documents/{document_id}/fuzzy-matching
```

Responsabilidades actuales:

1. Exigir que el documento exista, esté en `ner` y tenga `ner_path`.
2. Leer y validar el JSON NER.
3. Normalizar el texto solo para comparación:
   - Unicode;
   - mayúsculas/minúsculas;
   - tildes;
   - espacios repetidos;
   - variantes de guiones y comillas.
4. Comparar exclusivamente dentro de la misma categoría.
5. Reutilizar coincidencias exactas normalizadas.
6. Aplicar RapidFuzz con `ratio` y `token_sort_ratio`:
   - umbral `93` para `CHAR` y `LOC`;
   - umbral `96` para `INFRA`, `GOV` y `PRAC`;
   - margen mínimo de `5` puntos frente al segundo candidato;
   - expresiones menores de cinco caracteres solo aceptan exact match.
7. Crear una fila en `canonical_entities` cuando no hay coincidencia segura.
8. Guardar cada aparición en `entities`, preservando texto, offsets, oración, contexto y ambigüedad.
9. Asociar obligatoriamente cada mención mediante `entities.canonical_id`.
10. Reemplazar menciones anteriores del documento.
11. Confirmar canónicos, menciones y estado en una única transacción.
12. Hacer rollback completo si falla cualquier parte.

La respuesta expone:

- `canonical_id`;
- `canonical_name`;
- `match_type`: `exact`, `fuzzy` o `new`;
- `match_score`;
- `second_match_score`.

La reversión soporta `fuzzyMatching → ner` conservando el JSON; una segunda reversión desde `ner` elimina menciones y el JSON para volver a `cleaned`.

## Esquema de PostgreSQL

- Migración aplicada: `a2b3c4d5e6f7 (head)`.
- `canonical_entities`:
  - `id UUID PK`;
  - `canonical_name TEXT NOT NULL`;
  - `category TEXT NOT NULL`.
- `entities.canonical_id`:
  - UUID;
  - `NOT NULL`;
  - FK hacia `canonical_entities.id`;
  - `ON DELETE RESTRICT`.

## Estado real de datos al cierre

Consulta realizada el 5 Ago 2026:

- 31 documentos en `cleaned`.
- 1 documento en `fuzzyMatching`.
- 0 documentos en `ner`.

Documento procesado:

```text
id: 61b5cf8e-8109-408c-a571-cdf5b31512ca
archivo: Relatos mineros.docx
status: fuzzyMatching
ner_path: s3/archivosNER/61b5cf8e-8109-408c-a571-cdf5b31512ca.json
```

Resultados persistidos:

| Categoría | Menciones | Entidades canónicas usadas |
|---|---:|---:|
| CHAR | 494 | 256 |
| GOV | 35 | 31 |
| INFRA | 30 | 20 |
| LOC | 351 | 149 |
| PRAC | 201 | 83 |
| **Total** | **1111** | **539** |

Todas las filas de `canonical_entities` están referenciadas actualmente por el documento procesado.

## Verificación técnica realizada

- 13 pruebas unitarias pasan.
- API reconstruida con RapidFuzz `3.14.5`.
- `GET /health` respondió `{"status":"ok"}`.
- La ruta fuzzy matching aparece en OpenAPI.
- Smoke test de normalización y similitud pasó dentro del contenedor.
- La ejecución real produjo 1.111 menciones asociadas a 539 canónicos.

Docker estaba activo al redactar esta bitácora. La usuaria indicó que lo bajará antes de apagar el equipo.

## Decisiones de diseño vigentes

- Es preferible crear duplicados canónicos temporales antes que fusionar conceptos distintos.
- Nunca comparar menciones de categorías diferentes.
- El texto literal y cada aparición siguen siendo la fuente para coocurrencias futuras.
- La normalización canónica no reemplaza ni altera offsets o textos originales.
- `PRAC`, `GOV` e `INFRA` tienen umbrales más conservadores porque pequeñas diferencias pueden alterar el concepto.
- No eliminar automáticamente canónicos sin menciones.
- No se introdujo todavía una tabla de eventos o trazabilidad persistente del matching; puntajes y tipo se devuelven en HTTP y se resumen en logs.

## Próximo paso recomendado

La prioridad no es agregar más complejidad algorítmica todavía. Primero auditar cualitativamente el resultado real:

1. Revisar muestras de las 539 entidades canónicas por categoría.
2. Detectar **falsas fusiones**: conceptos distintos que comparten `canonical_id`.
3. Detectar **falsas separaciones**: variantes equivalentes con distintos canónicos.
4. Prestar especial atención a:
   - actores y lugares genéricos;
   - nombres muy cortos;
   - entidades contenidas dentro de otras;
   - modificadores de `PRAC`;
   - nombres institucionales de `GOV`;
   - singular/plural y abreviaturas.
5. Construir una pequeña muestra adjudicada con pares `same entity / different entity`.
6. Ajustar umbrales y reglas con evidencia de esa muestra.

Después de la auditoría, decidir entre estos desarrollos:

- endpoint de consulta/revisión de canónicos y sus menciones;
- persistencia de `match_type`, puntajes y versión del algoritmo;
- reglas específicas por categoría;
- manejo de abreviaturas;
- protección contra duplicados concurrentes;
- limpieza controlada de canónicos huérfanos;
- inicio de relaciones por coocurrencia usando offsets y `sentence_id`.

## Comandos de reentrada

```bash
docker compose up -d
docker compose ps
docker compose exec -T api alembic current
docker compose exec -T api python -c "import rapidfuzz; print(rapidfuzz.__version__)"
```

Luego comprobar:

```text
GET  /health
GET  /documents?status=fuzzyMatching
POST /documents/{id}/fuzzy-matching   # solo para documentos actualmente en ner
```

No volver a ejecutar fuzzy matching sobre el documento actual sin revertir primero, porque el endpoint exige status `ner`.
