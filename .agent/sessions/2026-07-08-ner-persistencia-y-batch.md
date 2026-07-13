# Sesión de Trabajo — 08 Jul 2026

## Contexto

**Participante:** Tania (Usuario) + OpenCode (Agente)
**Duración:** Sesión continua
**Estado inicial:** 31 documentos en DB (varios en cleaned), NER funcionando con Anthropic Claude

**Problema reportado:** La self-verificación automática de Claude estaba filtrando demasiadas entidades, y se necesitaba un flujo más mecánico de endpoints con persistencia de resultados NER en archivos.

---

## Diagnóstico

### Causas identificadas

1. **Self-verificación con el mismo modelo** no es eficiente: Claude extrae y luego Claude verifica, lo que genera sobre-corrección y menos entidades.
2. **No había persistencia de archivos NER**: el endpoint solo devolvía entidades en el body, sin guardar un JSON en `s3/`.
3. **No había status para NER**: el documento se quedaba en `cleaned` después de extraer entidades, dificultando el flujo de revert/delete.
4. **No había endpoint batch para NER**: solo se podía extraer entidades documento por documento.

---

## Acciones realizadas

### 1. Revertir self-verificación automática

**Archivo:** `src/services/ner.py`
- Eliminada constante `SELF_VERIFICATION_PROMPT`
- Eliminada función `_verificar_entidad()`
- `extraer_entidades()` vuelve a devolver todas las entidades extraídas por Claude

**Archivo:** `src/config.py`
- Eliminado flag `NER_SELF_VERIFY`

### 2. Persistencia de resultados NER en archivos

**Archivo:** `src/config.py`
- Agregado `STORAGE_NER: Path = Path("s3/archivosNER")`

**Archivo:** `src/models/documents.py`
- Agregada columna `ner_path: Mapped[str | None]`

**Archivo:** `migrations/versions/5ea1bb7e236a_add_ner_path_to_documents.py`
- Migración para agregar `ner_path` a la tabla `documents`
- Ajustado `down_revision` a `b8e3f2a1c4d5` para evitar múltiples heads

**Archivo:** `src/services/documents.py`
- `extraer_entidades_de_documento()` ahora:
  - Extrae entidades con Claude
  - Guarda JSON en `s3/archivosNER/{id}.json`
  - Actualiza `doc.ner_path`
  - Persiste en tabla `entities`
  - Retorna el array de entidades

**Archivo:** `src/api/schemas/documents.py`
- `DocumentRead` incluye `ner_path`

### 3. Nuevo status "ner"

**Archivo:** `src/services/documents.py`
- `extraer_entidades_de_documento()` actualiza el status del documento a `"ner"`
- `revertir()` soporta la cadena completa:
  - `ner` → `cleaned`: borra entidades de DB + archivo NER
  - `cleaned` → `converted`: borra archivo limpio + NER + entidades
  - `converted` → `raw`: borra archivo convertido
- `eliminar()` borra todos los archivos generados: raw, converted, cleaned, NER

### 4. Endpoint batch para NER

**Archivo:** `src/services/documents.py`
- Agregado `extraer_entidades_de_varios()` que procesa todos los documentos en status `cleaned`
- Maneja errores por documento (por ejemplo, si un documento no está en `cleaned`)

**Archivo:** `src/api/routers/documents.py`
- Agregado `POST /documents/extract-entities-batch`
- Devuelve `BatchProcessResponse` con `processed` y `errors`

### 5. Commit local

**Hash:** `0d64c27`
**Mensaje:** `feat(ner): persistir resultados NER en s3/archivosNER, agregar status 'ner' y endpoint batch`
**Archivos:** 7 (1 migración nueva + 6 modificados)

---

## Resultados

### Test final realizado

- **Extracción individual:** Documento `bf9140cb-751c-4183-a691-7b86c873e53d`
  - Status: `ner`
  - Archivo NER: `s3/archivosNER/bf9140cb-751c-4183-a691-7b86c873e53d.json` (105K)
  - Entidades extraídas: 302

- **Revert desde `ner`:**
  - Status pasó a `cleaned`
  - `ner_path` quedó vacío
  - Archivo NER eliminado
  - Entidades de DB eliminadas

- **Health check:** API respondiendo correctamente

---

## Estados del documento actualizados

| Estado | Significado |
|---|---|
| `raw` | Recién subido |
| `converted` | Convertido a Markdown |
| `cleaned` | Texto limpio |
| `ner` | Entidades extraídas |

---

## Decisiones tomadas

1. **No usar self-verificación automática** — Claude no se entrena con correcciones manuales; es mejor mejorar el prompt.
2. **Guardar resultados NER en archivos** — Sigue el mismo patrón mecánico que raw/converted/cleaned.
3. **Agregar status `ner`** — Permite trazabilidad completa y operaciones de revert/delete coherentes.
4. **Endpoint batch** — Procesa todos los documentos `cleaned` de una vez, reportando errores individuales.

---

## Próximos pasos sugeridos

1. **Fine-tuning del prompt de NER** — Mejorar definiciones de etiquetas, ejemplos few-shot, o probar otro modelo de Claude.
2. **Resolver push pendiente** — Rotar API key de Anthropic o reescribir historial para poder hacer `git push`.
3. **Objetivo 5** — Vectores, matrices, grafos, métricas.

---

## Pregunta para la próxima sesión

¿Por dónde empezamos el fine-tuning del prompt de NER?

1. Revisar ejemplos mal etiquetados de los JSON guardados en `s3/archivosNER/` y ajustar las definiciones de las 6 etiquetas en `src/services/ner.py`.
2. Reescribir el `SYSTEM_PROMPT` para ser más explícito sobre qué NO es cada etiqueta (ej. `NARV` vs `GOV`, `PRAC` vs `INFRA`).
3. Probar un modelo diferente de Claude (ej. `claude-3-5-sonnet-20241022`) y comparar resultados.
4. Mejorar el few-shot usando solo anotaciones representativas de `data/ner/annotations/a251048a.json` en vez de todo el JSON.

---

## Notas técnicas

- **Push bloqueado:** GitHub detectó la Anthropic API key en un commit anterior (`ecc502c`, `.env:14`). Para poder pushear, hay que rotar la clave o reescribir el historial.
- **Migración aplicada:** `5ea1bb7e236a_add_ner_path_to_documents.py` aplicada exitosamente.
- **API saludable:** `GET /health` responde `{"status":"ok"}`.

---

*Documentación generada por OpenCode — 08 Jul 2026*
