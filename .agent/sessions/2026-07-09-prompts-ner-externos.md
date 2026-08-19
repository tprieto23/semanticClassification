# Sesión de Trabajo — 09 Jul 2026

## Contexto

**Participante:** Tania (Usuario) + OpenCode (Agente)
**Estado inicial:** NER funcionando con prompts hardcodeados en `src/services/ner.py`; el usuario quería separar los prompts del código y aplicar un codebook más estricto.

**Objetivo de la sesión:**
1. Separar el system prompt y user prompt de `src/services/ner.py` a archivos externos.
2. Aplicar el nuevo codebook con definiciones de etiquetas y reglas de frontera.
3. Cambiar la salida esperada del LLM a `{"annotations": [{label, span_text, evidence, ambiguity}]}`.
4. Actualizar la documentación del agente (`.agent/`).

---

## Acciones realizadas

### 1. Prompts externos

**Archivos creados:**
- `data/prompts/ner_prompt.txt` — system prompt completo con:
  - Rol del anotador semántico.
  - Definiciones de las 6 etiquetas (`LOC`, `INFRA`, `ACTR`, `PRAC`, `GOV`, `NARV`).
  - Ejemplos por etiqueta.
  - Reglas generales de anotación.
  - Reglas de frontera entre etiquetas.
  - Formato de salida JSON.
- `data/prompts/ner_user_prompt.txt` — plantilla del user prompt que inyecta el chunk con `$chunk`.

### 2. Configuración

**Archivo:** `src/config.py`
- Agregadas rutas:
  ```python
  NER_PROMPT_PATH: Path = Path("data/prompts/ner_prompt.txt")
  NER_USER_PROMPT_PATH: Path = Path("data/prompts/ner_user_prompt.txt")
  ```

### 3. Refactor de `src/services/ner.py`

**Cambios:**
- Eliminadas definiciones hardcodeadas (`LABEL_DEFINITIONS`, `LABEL_EXAMPLES`, `_formatear_definiciones()`, `SYSTEM_PROMPT`).
- Agregadas funciones para cargar prompts desde archivos con caché en memoria:
  - `_cargar_system_prompt()`
  - `_cargar_user_prompt_template()`
  - `_build_user_prompt(chunk)`
- Adaptado `_cargar_few_shot()` para convertir anotaciones del JSON al formato nuevo:
  `label`, `span_text`, `evidence`, `ambiguity`.
- Nueva función `_parsear_respuesta()` que espera `{"annotations": [...]}`.
- Nueva función `_buscar_offset()` para calcular `start`/`end` buscando el span literal.
- Nueva función `_ambiguity_to_confidence()` para mapear `ambiguity` → `confidence`.
- `_extraer_contexto()` mejorado para no cortar palabras bruscamente.
- `extraer_entidades()` ahora devuelve entidades con:
  `text`, `labels`, `start`, `end`, `confidence`, `context`, `evidence`, `ambiguity`.

### 4. Schema y persistencia

**Archivo:** `src/api/schemas/entities.py`
- `EntityOut` ahora incluye `evidence` y `ambiguity`.

**Archivo:** `src/services/documents.py`
- Al persistir entidades en DB, `metadata_` ahora guarda `context`, `evidence` y `ambiguity`.

### 5. Actualización de documentación `.agent/`

**Archivo:** `.agent/architecture.md`
- Agregada carpeta `data/prompts/` al diagrama de estructura.
- Actualizado el flujo de NER para reflejar prompts externos y nueva estructura de salida.

**Archivo:** `.agent/tasks.md`
- Actualizada la sección del Objetivo 4 con los nuevos detalles de `src/services/ner.py`.
- Actualizado `EntityOut` y `src/config.py`.
- Reemplazado el "Status de sesión — Jul 08 2026" por "Status de sesión — Jul 09 2026".

**Archivo:** `.agent/sessions/2026-07-09-prompts-ner-externos.md`
- Esta sesión documentada.

---

## Validación

- ✅ Sintaxis OK en `src/services/ner.py`, `src/config.py`, `src/api/schemas/entities.py`, `src/services/documents.py` (`py_compile`).
- ✅ Prueba manual del parser con ejemplo simulado: extrajo 4 entidades, calculó offsets correctos, asignó confianzas según ambigüedad.
- ✅ Plantilla de user prompt renderiza correctamente el chunk.
- ⚠️ No se pudo importar el módulo completo localmente porque el `.venv` no tiene `anthropic` instalado (el proyecto corre con Docker).

---

## Decisiones tomadas

1. **Prompts fuera del código** — facilita iteración, auditoría y colaboración con especialistas de dominio.
2. **Nueva salida del LLM** — de array plano a objeto `{"annotations": [...]}` con metadatos de evidencia y ambigüedad.
3. **Offsets calculados localmente** — el LLM ya no devuelve `start`/`end`; se busca el `span_text` literal en el chunk.
4. **Confidence derivado de ambiguity** — mapeo mecánico: `low=0.9`, `medium=0.7`, `high=0.5`.
5. **Few-shot convertido automáticamente** — se mantiene el JSON de Label Studio pero se transforma al formato nuevo.

---

## Próximos pasos sugeridos

1. Probar `POST /documents/{id}/extract-entities` con un documento real en Docker/Postman.
2. Revisar los resultados: calidad de spans, etiquetas de frontera, evidencias coherentes.
3. Ajustar el prompt en `data/prompts/ner_prompt.txt` según errores observados.
4. Considerar curar el few-shot a mano (claro, frontera, negativo) en lugar de usar todo el JSON automáticamente.

---

*Documentación generada por OpenCode — 09 Jul 2026*
