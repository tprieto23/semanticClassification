# v2 — Explorador interactivo (filtrar y explorar)

**Estado:** futuro. La v1 entrega el grafo de corpus + Gephi + el HTML interactivo
que ya genera el script. Este documento describe los pasos siguientes para cuando
"filtrar y explorar en vivo" pase de *deseable* a *necesario*.

## Los tres escalones

1. **v1 (actual)** — Gephi + `g{w}_interactive.html`. Ese HTML **ya** filtra
   client-side: perilla de peso, toggles por categoría, buscador, y evidencia
   textual por oración al clickear una arista. **Cero infraestructura nueva.**
2. **v2a** — interfaz propia, filtrado en el navegador sobre datos ya cargados.
   Sin tablas nuevas.
3. **v2b** — tabla materializada de coocurrencias como **caché**, solo si el corpus
   ya no entra cómodo en el navegador.

---

## v2a — Explorador propio (client-side)

**Cuándo:** se quiere una UI más allá del HTML autogenerado (comparar incubadoras,
resaltar comunidades, exportar sub-grafos, estilos propios).

**Cómo:**
- El endpoint de v1 ya produce el JSON del grafo (nodos + aristas + evidencia).
  La UI lo carga entero y filtra **en memoria**.
- Sigue siendo derivado: se regenera con el build. **Sin fuente de verdad nueva.**

**Límite:** cuando el grafo es tan grande que el navegador se traba al cargarlo todo.

---

## v2b — Tabla materializada (caché)

**Cuándo:** corpus demasiado grande para mandar entero al navegador, y se necesita
filtrar **server-side** rápido (ej.: "PRAC×LOC, peso ≥ 3, en ≥ 3 documentos"
respondido en milisegundos, muchas veces por sesión).

**Diseño:**
- Tabla `entity_cooccurrences` **por documento**:
  `(document_id, canonical_a, canonical_b, category_a, category_b, sentence_count)`.
  Índices por `(category_a, category_b)` y por `document_id`.
- El endpoint de lectura consulta y agrega con `GROUP BY` + `HAVING`
  (peso total y nº de documentos).
- Es **caché, no verdad**: se reconstruye entera desde `entities` (mismo principio
  idempotente que v1). Siempre existe un botón "rebuild total".

**Costo real a tener en cuenta:** mantenerla sincronizada cuando llegan o se borran
documentos. Por eso el rebuild total debe estar siempre disponible (no confiar solo
en updates incrementales).

**Referencia:** el benchmark A (al vuelo) / B (vista) / C (materializada) mostró que
materializar se justifica por **patrón de uso** (muchas consultas filtradas por
sesión), **no** por la velocidad cruda de una sola generación. B (vista SQL) no da
velocidad extra sobre A, solo código más limpio.

---

## Disparadores para subir de escalón

- **v1 → v2a:** el HTML autogenerado se queda corto para lo que se quiere
  explorar/comparar.
- **v2a → v2b:** cargar el grafo entero en el navegador se vuelve lento
  (miles y miles de nodos).

## Principios que se mantienen en todos los escalones

- La DB (`entities` + `canonical_entities`) es la **única fuente de verdad**.
- Todo lo demás (grafo, caché) es **derivado y reconstruible**.
- **Recompute total = idempotente** y a prueba de desincronización.
