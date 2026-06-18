# Sesión de Trabajo — 12 Jun 2026

## Contexto

**Participante:** Tania (Usuario) + OpenCode (Agente)
**Duración:** Sesión continua
**Estado inicial:** 29 documentos en DB (27 raw, 2 converted), 27 PDFs + 2 DOCX

**Problema reportado:** La conversión de PDFs fallaba o era extremadamente lenta (solo DOCX funcionaban). Los PDFs son esenciales para el proyecto y contienen imágenes no seleccionables + anexos escaneados.

---

## Diagnóstico

### Causas identificadas

1. **Falta de librerías del sistema** (`libxcb.so.1`, `libgl1`, etc.) en el contenedor Docker → `ImportError` al inicializar Docling para PDFs
2. **OCR por defecto** en Docling: intentaba descargar ~40MB de modelos y procesar cada PDF en ~468s en CPU
3. **Carga de modelos repetida** en cada conversión (no se reutilizaba `DocumentConverter`)
4. **Todos los PDFs actuales tienen texto nativo** pero Docling los procesaba como si fueran escaneados

### Métricas de referencia

| Método | Tiempo por PDF |
|---|---|
| Docling con OCR (original) | ~468 segundos |
| Docling sin OCR | ~70-146 segundos |
| PyMuPDF (texto nativo) | **0.5 segundos** |
| PyMuPDF (imágenes) | **0.0 segundos** (23 imágenes) |

---

## Acciones realizadas

### 1. Actualización de dependencias

**Archivo:** `requirements.txt`
- Agregado `PyMuPDF>=1.24.0` (fast path para PDFs nativos)

**Archivo:** `Dockerfile`
- Agregadas librerías del sistema faltantes:
  - `libxcb-shm0`, `libxcb-xfixes0`, `libxcb-xinerama0`, `libglx-mesa0`
- Estas son **necesarias** para OpenCV/Docling en la imagen base `python:3.11-slim`

### 2. Nuevo convertidor híbrido

**Archivo:** `src/services/pdf_converter.py` (nuevo)
- Implementa `PdfConverter` con dos estrategias:
  - **Fast path:** PyMuPDF para PDFs nativos (detección automática por umbral de texto >500 chars)
  - **Fallback:** Docling con OCR para PDFs escaneados (lazy-loaded, solo si se necesita)
- Extrae imágenes embebidas como archivos PNG/JPEG a `s3/imagenesExtraidas/{doc_id}/`
- Genera Markdown con referencias locales a las imágenes: `![image]({doc_id}/page_1_img_1.png)`
- DOCX y otros formatos siguen usando Docling directamente

### 3. Actualización de la capa de servicios

**Archivo:** `src/services/documents.py`
- `convertir()` ahora acepta `converter: PdfConverter | None = None` para reutilización
- `convertir_varios()` crea un solo `PdfConverter` antes del loop (evita carga repetida de modelos)
- `revertir()` ahora elimina el directorio de imágenes asociado si existe

**Archivo:** `src/models/storage.py`
- Agregado `eliminar_directorio()` usando `shutil.rmtree()`

### 4. Actualización de la capa de datos

**Archivo:** `src/models/documents.py`
- Agregada columna `images_path: Mapped[str | None]`

**Archivo:** `src/config.py`
- Agregado `STORAGE_IMAGES: Path = Path("s3/imagenesExtraidas")`

**Archivo:** `src/api/schemas/documents.py`
- Agregado `images_path: str | None = None` al schema `DocumentRead`

### 5. Migración de base de datos

**Archivo:** `migrations/versions/cfe959221fc7_add_images_path_to_documents.py`
- Migración automática generada con `alembic revision --autogenerate`
- Aplicada exitosamente con `alembic upgrade head`

### 6. Actualización de documentación

**Archivos:** `.agent/tasks.md` y `.agent/README.md`
- Documentados todos los cambios en la sección "Objetivo 2"
- Actualizado stack y dependencias del sistema

---

## Resultados

### Test final realizado

- **Revert + Convert** de documento real con imágenes: **0.2s** (exitoso)
- **Batch de 27 PDFs:** **28 segundos** (todos convertidos)
- **Imágenes extraídas:** 3-23 imágenes por documento, dependiendo del contenido

### Antes vs Después

| Métrica | Antes (Docling puro) | Ahora (Híbrido) |
|---|---|---|
| 1 PDF nativo | ~465 segundos | **0.2-0.6 segundos** |
| 27 PDFs batch | ~2-3 horas | **28 segundos** |
| Imágenes extraídas | No | **Sí, como PNGs/JPEGs** |
| Reversión de estado | Eliminaba .md | **Elimina .md + imágenes** |

---

## Estado actual del sistema

- **DB:** 29 documentos en estado `converted`
- **Storage:**
  - `s3/archivosCrudos/` — 27 PDFs + 2 DOCX
  - `s3/archivosConvertidos/` — 29 archivos .md
  - `s3/imagenesExtraidas/` — ~200-300 imágenes extraídas
- **API:** Funcionando en `http://localhost:8000`
- **Contenedor:** Reconstruido con nuevas librerías del sistema

---

## Decisiones tomadas

1. **No activar OCR por defecto** — Los 27 PDFs actuales son nativos, no escaneados. OCR solo como fallback automático.
2. **Usar PyMuPDF para texto nativo** — 1000x más rápido que Docling para este caso de uso.
3. **Mantener Docling como fallback** — Si llega un PDF escaneado puro, se detectará automáticamente y usará OCR.
4. **Extraer imágenes como archivos separados** — No base64 embebido en markdown. Esto permite procesamiento posterior (OCR en imágenes, vectores, etc.).

---

## Próximos pasos sugeridos

1. **Probar conversión de DOCX** — Verificar que Docling sigue funcionando correctamente para archivos .docx
2. **Limpieza lingüística (Objetivo 3)** — Implementar `linguisticCleaning()` con spaCy + langdetect
3. **Extracción de entidades (Objetivo 4)** — NER con XLM-RoBERTa fine-tuned
4. **Optimización:** Si el batch crece a 1000+ documentos, considerar procesamiento asíncrono con Celery/Redis

---

## Notas técnicas

- **Importante:** Si se reconstruye el contenedor desde cero (`docker compose build --no-cache`), PyMuPDF se instalará correctamente desde `requirements.txt`. Las librerías del sistema también están en el Dockerfile.
- **Arm64:** El entorno es `aarch64` (Apple Silicon). Las librerías instaladas son `arm64`.
- **RapidOCR:** Se actualizó a `3.8.3` en el contenedor existente para fix de `arch_config.yaml`. El contenedor reconstruido instalará la versión correcta.
- **Modelos de Docling:** Se descargan automáticamente en primer uso (layout, OCR, etc.). ~200MB en total.

---

*Documentación generada por OpenCode — 12 Jun 2026*
