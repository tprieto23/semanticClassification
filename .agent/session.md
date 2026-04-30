# Session Context

## Última sesión

**Fecha:** 2026-04-29 (sesión 4)

**Trabajado en:**
- Pruebas manuales end-to-end del pipeline de conversión (Objetivo 1 + 2) con archivos reales
- Aclaración conceptual sobre cómo funciona una API HTTP, qué hace Postman, y cómo se suben archivos (multipart/form-data)
- Definición del plan para procesar el resto del corpus (script bash vs. endpoint batch)

**Resumen de la sesión:**

### Conceptos aclarados (importante para futuras sesiones)
La usuaria está aprendiendo APIs/HTTP, no había usado Postman para subir archivos antes. Los conceptos que se documentaron explícitamente:

- **La API HTTP vive corriendo todo el tiempo** dentro de Docker. No se "ejecuta" cada vez. Se le mandan mensajes (requests) y reacciona.
- **Postman es solo un cliente HTTP** — empaca y manda mensajes; no ejecuta código del servidor. Curl, navegador o cualquier cliente sirven igual.
- **El flujo es de 2 pasos separados, no uno:**
  - `POST /documents` → upload (sube y guarda)
  - `POST /documents/{id}/process` → conversión a `.txt`
  
  Razón: permite re-procesar sin re-subir, o subir en lote y procesar después.
- **Los archivos no se pre-colocan en una carpeta especial del proyecto antes de probar.** Pueden estar en cualquier ruta del Mac. Postman/curl los lee de donde sea y los empaca dentro del request HTTP. La API los guarda automáticamente en `data/raw/{id}/`.
- **Para subir un archivo en Postman:** Body → `form-data` → KEY=`file` con el dropdown cambiado de "Text" a **"File"** → Select Files. **Sin el cambio a "File" no hay manera de mandar el archivo** — es la trampa más común para quien arranca.
- **La arquitectura ya es portable a S3:** la API es la abstracción entre "el cliente tiene un archivo" y "el archivo queda almacenado en algún lado". Hoy guarda en disco, mañana puede guardar en S3 cambiando solo la línea de almacenamiento, sin afectar a los clientes (Postman/script/dashboard futuro).

### Pruebas manuales realizadas
- ✅ 5 archivos (PDF + DOCX) subidos y procesados manualmente desde Postman
- ✅ Usuaria familiarizada con el flujo de Postman (form-data, File field, copiar id, llamar a process)
- ⏳ Pendiente verificar: que los 5 hayan terminado con `status: "converted"`, que los `.txt` resultantes se vean correctos, y si alguno era PDF escaneado (PyMuPDF no hace OCR — saldría vacío)

### Decisión pendiente para próxima sesión

Para procesar los ~25 archivos restantes del corpus, dos opciones evaluadas:

| Opción | Qué hace | Tiempo | Cuándo conviene |
|---|---|---|---|
| **A. Script bash + curl** | Recorre una carpeta local y sube + procesa cada archivo. Se corre una vez con `./batch_upload.sh /ruta/carpeta` | ~10 min | Resolver tanda específica sin tocar la API |
| **B. Endpoint `POST /documents/batch`** | Múltiples archivos en un solo request HTTP. Reutilizable. | ~30-40 min | Si batch se vuelve capacidad permanente |

**Recomendación elegida (pendiente de ejecutar):** Opción A primero. Si más adelante el patrón batch es recurrente, agregamos B sin haber perdido nada.

Para implementar la A, falta saber:
- Ruta de la carpeta donde estarán los 30 archivos
- Si es mezcla de PDF/DOCX (para que el script filtre y no falle con `.DS_Store` u otros)

---

**Fecha:** 2026-04-29 (sesión 3)

**Trabajado en:**
- Definición de librerías para Objetivo 2 (conversión de documentos)
- Implementación completa de la 1ra iteración del Objetivo 2 (PDF + DOCX)
- Mejora de `POST /documents` para recibir archivos reales (multipart)
- Implementación del endpoint `POST /documents/{id}/process`
- Pruebas end-to-end con DOCX y PDF

**Resumen de la sesión:**

### Decisiones (ver `decisions.md`)
- **1ra iteración Objetivo 2:** PyMuPDF (PDF) + python-docx (DOCX)
- **2da iteración (diferida):** OCR (pytesseract), audio (faster-whisper), video (ffmpeg + faster-whisper)
- Razón: cubre la mayoría del corpus típico sin instalar dependencias pesadas; OCR/audio/video se agregan cuando se necesiten

### Implementación

1. **`requirements.txt`:** agregadas `PyMuPDF==1.24.0` y `python-docx==1.1.0`. Imagen Docker reconstruida.

2. **`src/services/conversion.py`** (nuevo): servicio puro con
   - `convert_pdf(file_path) -> str`
   - `convert_docx(file_path) -> str`
   - `convert_document(file_path, file_type) -> str` (dispatcher)
   - `save_converted_text(text, output_path)`
   - Excepciones: `UnsupportedFileTypeError`, `ConversionError`

3. **`src/api/main.py`** actualizado:
   - **`POST /documents`** ahora recibe `multipart/form-data` con `file` (UploadFile) y `metadata` (string JSON opcional). Guarda en `data/raw/{document_id}/{original_filename}` (folder por documento para evitar colisiones de nombre). El `file_type` se infiere automáticamente del sufijo del archivo.
   - **`POST /documents/{id}/process`** (nuevo): lee el documento de DB, llama al converter según `file_type`, guarda `.txt` en `data/processed/txt/{document_id}.txt`, actualiza `status` a `'converted'` (o `'failed'` si hay error). Devuelve `ProcessResponse` con `txt_path` y `char_count`.
   - Manejo de errores: 404 si el archivo no está en disco, 415 si el formato no es soportado, 500 si falla la conversión.

4. **Fix Pydantic v2 + SQLAlchemy:** SQLAlchemy reserva el atributo `metadata` en `Base`, así que el modelo usa la columna como `metadata_` (con `name="metadata"` en el SQL). Pydantic v2 estaba leyendo `MetaData()` en vez del JSONB. Solucionado con `validation_alias="metadata_"` en `DocumentResponse.metadata`.

### Verificación end-to-end
- ✅ DOCX: subido, procesado, texto extraído correctamente
- ✅ PDF: subido, procesado, texto extraído correctamente
- ✅ Listado `GET /documents` muestra status `converted` después de procesar
- ✅ Error 415 al intentar procesar `.txt` (formato no soportado)
- ✅ Validación de metadata como JSON válido (400 si está malformado)

### Aprendizajes

- **Pydantic v2 + SQLAlchemy con campo `metadata`:** siempre usar `metadata_` en el modelo SQLAlchemy (con `name="metadata"`) y `validation_alias="metadata_"` en el schema Pydantic. Si no, Pydantic toma el `Base.metadata` registry de SQLAlchemy.
- **`UploadFile` de FastAPI** requiere `python-multipart` (ya estaba en requirements). Para combinar archivo + metadata JSON en multipart, se manda un `file` (UploadFile) y un `metadata` (Form, string que parseamos como JSON).
- **Convención de almacenamiento:** `data/raw/{document_id}/{original_filename}` da folder por documento (sin colisiones de nombre, preserva nombre original).

### Estado actual del corpus
En la DB hay 4 documentos de prueba (1 raw orphan de un test fallido + 2 DOCX/PDF convertidos correctamente + 1 .txt que falló por formato no soportado). No hay valor real en estos datos — son solo de prueba. Si se quiere DB limpia para empezar Objetivo 3: `docker-compose down -v && docker-compose up -d db` y aplicar migración.

---

**Fecha:** 2026-04-29 (sesión 2)

**Trabajado en:**
- Levantar Docker por primera vez con DB + API + migraciones
- Diagnóstico y corrección de errores en la migración inicial de Alembic
- Ajuste de `docker-compose.yml` para montar `migrations/` y `alembic.ini` como volúmenes

**Resumen de la sesión:**

### Problema encontrado
Al ejecutar `docker-compose run api alembic upgrade head`, la migración fallaba con:
```
AttributeError: module 'alembic.op' has no attribute 'create_extension'
```

**Causa raíz:** dos cosas combinadas:
1. La migración `001_initial.py` había sido escrita usando `op.create_extension('vector')` y `op.drop_extension('vector')`, métodos que **no existen** en Alembic. La forma correcta es `op.execute('CREATE EXTENSION IF NOT EXISTS vector')` y `op.execute('DROP EXTENSION IF EXISTS vector')`.
2. La carpeta `migrations/` no estaba montada como volumen en `docker-compose.yml`, sino que se copiaba a la imagen con `COPY . .` en el `Dockerfile`. Por eso, aunque se editara el archivo local, el contenedor seguía corriendo la versión vieja hasta hacer `docker-compose build`.

### Cambios aplicados

1. **`migrations/versions/001_initial.py` línea 114:** corregido `op.drop_extension('vector')` → `op.execute('DROP EXTENSION IF EXISTS vector')`. (La línea 20 del `upgrade` ya estaba correcta con `op.execute(...)` localmente, pero el contenedor tenía la versión vieja).

2. **`docker-compose.yml`:** agregados dos volúmenes al servicio `api` para que los cambios futuros en migraciones no requieran reconstruir la imagen:
   ```yaml
   volumes:
     - ./src:/app/src
     - ./data:/app/data
     - ./migrations:/app/migrations
     - ./alembic.ini:/app/alembic.ini
   ```

3. **Imagen reconstruida** con `docker-compose build api` y migración aplicada con `docker-compose run --rm api alembic upgrade head`.

### Verificación

- ✅ Extensión `vector` instalada en PostgreSQL
- ✅ 6 tablas creadas: `alembic_version`, `documents`, `entities`, `graphs`, `metrics`, `relationships`
- ✅ API respondiendo en `http://localhost:8000`:
  - `GET /` → `{"message":"Semantic Classification API","status":"running"}`
  - `GET /health` → `{"status":"healthy"}`
  - Swagger UI disponible en `http://localhost:8000/docs`

### Aprendizajes para futuras sesiones

- **Alembic no tiene `op.create_extension` ni `op.drop_extension`** — usar `op.execute('CREATE EXTENSION ...')` y `op.execute('DROP EXTENSION ...')`.
- **Si se edita un archivo local pero los cambios no se reflejan en el contenedor**, verificar si la carpeta está montada como volumen en `docker-compose.yml`. Si no, hay que hacer `docker-compose build` para reconstruir la imagen.
- **Comando para migraciones nuevas:**
  ```bash
  docker-compose run --rm api alembic revision --autogenerate -m "descripción"
  docker-compose run --rm api alembic upgrade head
  ```

---

**Fecha:** 2026-04-29 (sesión 1)

**Trabajado en:**
- Definición del schema de la base de datos (5 modelos SQLAlchemy)
- Creación de migraciones iniciales con Alembic
- Integración de la API con la base de datos
- Endpoints básicos para documentos y entidades

**Resumen de la sesión:**
- Se crearon los modelos `Document`, `Entity`, `Relationship`, `Graph`, `Metric` en `src/models/models.py`
- Se configuró `src/core/database.py` con SQLAlchemy + pgvector
- Se creó la migración inicial `migrations/versions/001_initial.py` con las 5 tablas e índices
- Se actualizaron los endpoints de la API: `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /entities`
- La API ahora inicializa la DB automáticamente al arrancar

---

**Fecha:** 2026-04-27

**Trabajado en:**
- Creación de estructura de documentación (.agent/)
- Definición de objetivos del proyecto (1-10)
- Decisiones tecnológicas principales
- Configuración de Docker
- Redacción de metodología técnica completa

## Resumen de la sesión

### Completado:
1. ✅ Estructura de carpetas `.agent/` creada con 9 archivos
2. ✅ README en raíz apuntando a `.agent/` para agentes
3. ✅ `project-overview.md` con contexto del proyecto
4. ✅ `architecture.md` con flujo y estructura
5. ✅ `tech-stack.md` con tecnologías decididas
6. ✅ `conventions.md` con convenciones de código
7. ✅ `tasks.md` con los 10 objetivos como roadmap
8. ✅ `decisions.md` con 5 ADRs registrados
9. ✅ `tech-debt.md` con deuda técnica conocida
10. ✅ Docker configurado (docker-compose.yml + Dockerfile)
11. ✅ Estructura de carpetas `src/` y `data/`
12. ✅ API básica con 2 endpoints probada con Postman
13. ✅ `methodology.md` con las 10 etapas, métricas e interpretación crítica

### Decisiones tomadas:
- PostgreSQL + pgvector como DB
- FastAPI para API
- SQLAlchemy + Alembic para ORM y migraciones
- Arquitectura híbrida (DB + Archivos)
- Docker para desarrollo local
- Sin autenticación inicial

### Pendientes de decisión:
- Librerías de conversión (Obj 2)
- Limpieza de textos (Obj 3)
- Clasificación de entidades (Obj 4)
- Modelo de embeddings (Obj 5)
- Matrices y relaciones (Obj 6)
- Grafos (Obj 7)
- Métricas (Obj 8)

## Pendientes para próxima sesión

1. Definir schema de la base de datos (modelos SQLAlchemy)
2. Crear migraciones iniciales con Alembic
3. Implementar endpoint POST /documents
4. Empezar con Objetivo 2 (conversión)

## Notas

- El proyecto es para análisis territorial con perspectiva crítica, feminista y de género
- El dashboard es el consumidor principal de la API (tenerlo en mente)
- La documentación debe leerse completa al iniciar cada sesión nueva

---

## Historial de sesiones

| Fecha | Trabajado en |
|-------|--------------|
| 2026-04-27 | Creación de documentación, definición de objetivos, decisiones tecnológicas, configuración de Docker, metodología técnica |
| 2026-04-29 (s1) | Schema de DB (5 modelos SQLAlchemy), migración inicial con Alembic, integración API ↔ DB, endpoints `POST /documents`, `GET /documents`, `GET /documents/{id}`, `GET /entities` |
| 2026-04-29 (s2) | Levantar Docker por primera vez; corrección de errores en migración (`op.create_extension`/`op.drop_extension` no existen); ajuste de volúmenes en `docker-compose.yml` para `migrations/` y `alembic.ini`; verificación de tablas creadas y API respondiendo |
| 2026-04-29 (s3) | Definición de librerías Objetivo 2 (PyMuPDF + python-docx, 1ra iteración); creación de `src/services/conversion.py`; mejora de `POST /documents` para recibir archivos reales (multipart); nuevo endpoint `POST /documents/{id}/process`; fix Pydantic v2 + SQLAlchemy `metadata`; pruebas end-to-end con PDF y DOCX |
| 2026-04-29 (s4) | Pruebas manuales del pipeline con 5 archivos reales desde Postman; aclaración conceptual de APIs HTTP / Postman / multipart uploads / arquitectura portable a S3; plan definido para procesar los ~25 restantes (Opción A: script bash + curl) |
