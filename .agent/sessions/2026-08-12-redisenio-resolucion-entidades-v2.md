# Sesión de trabajo — 12 Ago 2026

## Objetivo

Rediseñar el endpoint histórico de fuzzy matching como un proceso de resolución
canónica auditable. Los dos casos guía fueron:

- `MINEROS`, `Mineros`, `mineros`, `minero` → canónico CHAR `minero`;
- `Griselda`, `Griselda Zubizarreta`, `Griselda Zubizarreta Vargas` → una persona.

No se usó una API LLM. Esta primera versión es determinista, reproducible y
deliberadamente conservadora.

## Implementación

`src/services/fuzzy_matching.py` ahora analiza todas las menciones del documento
antes de resolverlas:

1. valida datos y conserva texto literal, offsets, `sentence_id` y contexto;
2. normaliza Unicode, tildes, espacios y caja solo para comparar;
3. singulariza actores genéricos CHAR mediante vocabulario controlado;
4. conserva género y calificadores (`minera != minero`, `minero artesanal != minero`);
5. detecta familias nominales por prefijo dentro del documento;
6. une un nombre corto solo si existe una familia compatible única;
7. excluye marcadores institucionales y sufijos corporativos de la regla personal;
8. resuelve por exacto, alias, nombre personal, fuzzy seguro o canónico nuevo;
9. devuelve y persiste método, puntajes, versión y evidencia.

La etiqueta singular/minúscula se aplica a actores genéricos. Los nombres propios
conservan mayúsculas legibles. `canonical_id` sigue siendo un UUID y nunca se
"convierte a minúscula".

## PostgreSQL

Migración aplicada: `b3c4d5e6f7a8 (head)`.

- `entities.resolution_method`
- `entities.resolution_score`
- `entities.resolution_version`
- `entities.resolution_details JSONB`
- nueva tabla `canonical_entity_aliases`

La migración fue aditiva: no reasignó ni eliminó datos existentes.

## Pruebas

- 33 pruebas pasan.
- Incluyen convergencia morfológica, conservación de género/calificadores,
  variantes de Griselda, rechazo de nombre corto ambiguo y regresión corporativa.
- `GET /health` responde correctamente.
- OpenAPI expone `resolution_version` y `resolution_details`.

## Auditoría reversible sobre Relatos mineros

Documento: `61b5cf8e-8109-408c-a571-cdf5b31512ca`.

La simulación se ejecutó dentro de una transacción con rollback obligatorio.
Antes y después quedaron exactamente:

- 2.858 filas en `canonical_entities`;
- 0 filas en `canonical_entity_aliases`;
- 6.628 filas en `entities`.

Resultados hipotéticos para sus 1.111 menciones:

- 159 menciones cambiarían de `canonical_id`;
- 13 grupos de canónicos convergerían;
- 0 canónicos actuales se dividirían;
- se crearían 48 formas singulares nuevas para 82 menciones;
- los nodos de la red bajarían de 539 a 523.

Red por oración:

| Medida | Antes | Después hipotético |
|---|---:|---:|
| Nodos G₁ | 539 | 523 |
| Aristas G₁ | 1.233 | 1.216 |
| Peso total G₁ | 1.352 | 1.343 |
| Nodos G₃ | 20 | 22 |
| Aristas G₃ | 20 | 20 |
| Peso total G₃ | 86 | 89 |

Casos guía:

- `minero` CHAR: 75 menciones, 67 oraciones, grado G₁ 82, fuerza G₁ 125,
  grado G₃ 8 y fuerza G₃ 42;
- Griselda unificada: 4 menciones, grado G₁ 6 y fuerza G₁ 8; sigue fuera
  de G₃ porque ninguna arista individual alcanza peso 3.

Durante la primera simulación se detectó el falso positivo
`Conirsa ↔ Conirsa SA`. Se agregó el bloqueo corporativo, una prueba de regresión
y se repitió la auditoría; la convergencia ya no aparece.

## Archivos para revisar

Directorio ignorado por Git:

`data/output/entity_resolution/61b5cf8e-8109-408c-a571-cdf5b31512ca/`

- `summary.json`: comparación global y focos Griselda/minero;
- `mention_decisions.csv`: las 1.111 decisiones;
- `canonical_convergences.csv`: 13 fusiones propuestas;
- `created_canonicals.csv`: 48 etiquetas singulares nuevas;
- `decisions_person_alias.csv`: 27 asignaciones por familia personal;
- `decisions_morphology.csv`: 137 decisiones morfológicas;
- `network_g3_before.csv` y `network_g3_after.csv`: núcleo recurrente comparado.

## Siguiente paso

La usuaria aprobó y ejecutó el endpoint v2. Se regeneraron las matrices y la red
completa G₁ con `peso >= 1` e inclusión explícita de aislados:

- 523 nodos, 1.216 aristas y 53 componentes;
- 28 nodos aislados (15 CHAR, 6 PRAC, 1 INFRA y 6 LOC);
- un componente principal de 423 nodos;
- los otros componentes no se eliminan.

La visualización G₁ se encuentra en:

`data/output/cooccurrence/61b5cf8e-8109-408c-a571-cdf5b31512ca/visualizations/g1/`

Abrir `g1_interactive.html`: conserva todos los nodos, permite buscar entidades,
filtrar categorías, cambiar diseño, subir el umbral solo para explorar y activar
etiquetas bajo demanda. Las figuras PNG/SVG muestran las etiquetas de los 25 nodos
con mayor fuerza para evitar ocultar la estructura por sobreimpresión.

Siguiente paso: interpretar G₁ por capas y componentes, y mantener G₃ como una
vista complementaria del núcleo, no como sustituto de la red completa.
