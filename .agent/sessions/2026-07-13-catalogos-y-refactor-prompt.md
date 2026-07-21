# Sesión de Trabajo — 13 Jul 2026

## Contexto

**Participante:** Tania (Usuario) + OpenCode (Agente)
**Estado inicial:** NER funcionando con 6 etiquetas (LOC, INFRA, ACTR, PRAC, GOV, NARV), prompts externos en `.txt`, sin catálogos, sin ACT.

**Objetivo de la sesión:** Revisar el prompt NER sección por sección, migrar a 6 etiquetas con ACT, poblar catálogos en DB, y mejorar la exhaustividad de la extracción.

---

## Decisiones tomadas

### 1. Catálogos dinámicos (tablas en DB)

Se crearon 6 tablas de catálogos en PostgreSQL con ORM en `src/models/catalogs.py`:

| Tabla | Población |
|-------|-----------|
| `catalog_labels` | 6 (CHAR, LOC, INFRA, GOV, PRAC, ACT) |
| `catalog_types` | 34 subtipos distribuidos entre las 6 etiquetas |
| `catalog_nodes` | 82 entidades concretas normalizadas del documento de mineros |
| `catalog_attributes` | 0 (pendiente, requiere ver más documentos) |
| `catalog_values` | 0 (pendiente) |
| `catalog_ambiguity_levels` | 3 (low, medium, high) |

**Archivos creados:** `src/models/catalogs.py`, `migrations/versions/a1b2c3d4e5f6_add_catalog_tables_and_entity_fks.py`
**Archivos modificados:** `src/models/entities.py` (+6 FKs), `src/models/entities_repo.py`, `migrations/env.py`

### 2. Código actualizado para el nuevo esquema

- `src/services/ner.py`:
  - `VALID_LABELS` de 5 a 6 (incluye ACT)
  - `extraer_entidades()` ahora recibe `db`, `document_id`, `document_title`
  - `_cargar_catalogos()` consulta las tablas en DB y formatea para el prompt
  - `_construir_json_entrada()` arma el JSON con document_id, title, text y catálogos
  - `_parsear_respuesta()` adaptado al nuevo formato de salida (`label_id`, `type_id`, `node_id`, etc.)
  - `_label_name_from_id()` mapea IDs a strings (1→CHAR, 6→ACT)
  - `_ambiguity_name_from_id()` mapea IDs a strings (1→low, etc.)
  - `max_tokens` subido de 8192 a 16384

- `src/api/schemas/entities.py`: `EntityOut` con `category`, `label_id`, `type_id`, `node_id`, `attribute_id`, `value_id`, `ambiguity_id`
- `src/api/routers/documents.py`: `document_id` convertido a `str()` en la respuesta
- `src/services/documents.py`: `extraer_entidades_de_documento()` pasa `db` y metadatos a `extraer_entidades()`
- `data/prompts/ner_user_prompt.md`: simplificado a placeholder `$json_input`
- `src/config.py`: rutas de prompts cambiadas de `.txt` a `.md`

### 3. Migración aplicada

- `a1b2c3d4e5f6` aplicada exitosamente: 6 tablas de catálogos creadas + 6 columnas FK en `entities`
- Seed insertado: 6 labels, 3 ambiguity levels, 34 types, 82 nodes

### 4. Refactor del prompt NER

Se revisó `data/prompts/ner_prompt.md` sección por sección (~715 líneas). Cambios principales:

| Sección | Cambio |
|---------|--------|
| Propósito | +instrucción de exhaustividad ("recorre de principio a fin sin muestreo") |
| Rol | "Nunca inventes" de 8 bullets → 1 oración ("Hay que cuidarse de inventar...") |
| Entidades permitidas | 5→6 etiquetas, +ACT, -NARRATIVE y líneas asociadas |
| CHAR | +personas nombradas con rol, ejemplos con individuos (Fernando Fernández, Ciriaco Pilco, Griselda Zubizarreta), exclusiones mapeadas a etiquetas |
| PRAC | -"acciones" de la definición, -ítems movidos a ACT, +"No incluye", frontera PRAC vs ACT reemplaza regla sobre acciones |
| **ACT** | **Nueva sección completa:** definición, incluye, ejemplos, exclusiones, vs PRAC, vs GOV |
| Reglas generales | Regla 10: exhaustividad; Regla 18: +ACT; Regla 19: "anotar con ambigüedad alta" en vez de "no anotar" |
| PRAC vs GOV | +ACT como tercera vía |
| Objetivos y visiones | "no existe etiqueta" → "se anotan como ACT" |
| Ambigüedad | "omitir" → "anotar con ambigüedad alta" |
| Formato salida | node_id corregido |
| Validación (12) | "evitar narrativas" → "clasificar objetivos como ACT" |
| Referencias obsoletas | Eliminado "Solutionscape", "cinco etiquetas", etc. |

---

## Problemas encontrados

### Error 1: Mapper no encontraba CatalogLabel
**Causa:** `entities.py` tenía `relationship("CatalogLabel")` pero `catalogs.py` no se importaba antes del mapper.
**Fix:** Eliminadas las relaciones ORM de catálogos en Entity (solo FK columns). Las relaciones se pueden agregar después.

### Error 2: UUID vs string en ExtractEntitiesResponse
**Causa:** El schema tenía `document_id: str` pero el router pasaba un `UUID`.
**Fix:** `str(document_id)` en el router.

### Error 3: Solo 10 entidades extraídas de 279 líneas
**Causa:** Prompt restrictivo + falta de ACT + sin instrucción de exhaustividad.
**Fix:** Refactor completo del prompt (ver sección 4 arriba).

### Error 4: JSON response no parsea (sesión actual) 🔧
**Síntoma:** `Error parseando respuesta JSON` a pesar de `_limpiar_contenido_markdown`.
**Estado:** Se agregó logging detallado en `_parsear_respuesta()` para diagnosticar. Pendiente de debug.

### Error 5: `_limpiar_contenido_markdown` usa `[-1]` en vez de `[1]`
**Fix:** Cambiado `split("\n", 1)[-1]` → `split("\n", 1)[1]` y el strip anidado → secuencial.

### Error 6: `ambiguity_id` quedaba sin mapear a string
**Fix:** Agregada `_ambiguity_name_from_id()` en `ner.py`.

---

## Estado actual

- **API:** Funcionando en `http://localhost:8000`, health OK
- **DB:** 6 catálogos poblados (labels, types, nodes, ambiguity_levels; attributes/values vacíos)
- **Prompt:** Refactorizado a 715 líneas con ACT, exhaustividad, y ejemplos con personas individuales
- **Extracción NER:** El endpoint responde 200 pero devuelve `entities: []` — el parseo de la respuesta del LLM falla. Debug pendiente.

---

## Próximo paso

- Diagnosticar por qué `json.loads()` falla en la respuesta limpia del LLM (logs detallados ya agregados)
- Probar nuevamente `POST /documents/{id}/extract-entities` y revisar los nuevos logs
- Verificar si el `_limpiar_contenido_markdown` necesita manejar edge cases adicionales

---

*Documentación generada por OpenCode — 13 Jul 2026*
