# Revisión de reglas y piloto real — 16 Oct 2026

## Commits de la sesión anterior

Se revisaron los archivos guardados antes de iniciar nuevas ediciones:

- `56e2526`: codebook, contexto, tareas y notas de cierre/editorial del 15 Oct.
- `7e6ff24`: definiciones de categorías, ambos prompts y ejemplo soft_INFRA.

Las seis pruebas locales existentes de NER y categorías pasaron antes de crear
esos commits. El árbol quedó limpio antes de iniciar la revisión de la sección 6.

## Revisión operativa

Se leyó la sección 6 completa, incluidas 6.1–6.3, y se contrastó con todas las
fichas, prompts y código. El borrador 0.2 desarrolla los pendientes generales
y las secciones 7–10 y anexo A. Corrige además el artículo externo de un
ejemplo KNOW/CHAR y aclara que el `.txt` es entrada de NER, sin restringir los
formatos de carga y conversión de la API.

La implementación admite LOC estrictamente dentro de CHAR en ambos órdenes
de respuesta, conserva repeticiones y rechaza las demás superposiciones.
El borrador conserva una categoría por aparición y prohíbe CHAR dentro de
CHAR; esta última delimitación mostró un desacuerdo persistente del modelo
en el piloto y fue presentada para revisión. No se trasladó resolución de
identidades, normalización ni construcción de relaciones a NER.

Se añadió validación del servicio antes de aceptar cada bloque. Comprueba
document_id, los cuatro campos, etiqueta, literalidad, oración, ambigüedad y
posiciones compatibles. Solicita hasta dos correcciones con los fragmentos
en conflicto; si persisten errores, falla sin devolver ni guardar una
extracción parcial. El parser aislado conserva compatibilidad tolerante.
Esta validación no detecta automáticamente omisiones ni errores semánticos.

## Documento y ejecución real

- Documento: informe sobre producción de biocarbón y capacitaciones.
- Identificador: `6f98dc30-3b28-42aa-b519-497cec4c8627`.
- Fuente: `s3/archivosLimpiados/6f98dc30-3b28-42aa-b519-497cec4c8627.txt`.
- SHA-256: `0cb7b42a393380fabdc1f97b292b07c1e033675dff4f029ff54024012f76d936`.
- Extensión: 5.267 caracteres, 42 oraciones, 13 bloques.
- Modelo configurado: `claude-sonnet-4-5-20250929`.
- Herramienta local: `scripts/validate_ner_document.py`.

La herramienta conserva texto, entradas, respuestas reales, manifiesto y,
cuando termina, menciones y revisión por oración. Identifica las versiones
mediante huellas de archivos. Puede preparar entradas sin proveedor y
reanudar reutilizando respuestas reales guardadas si coinciden texto,
entradas, modelo, definiciones, prompts y demostraciones. La reanudación no
es una nueva medición independiente de estabilidad.

| Directorio bajo `data/output/ner_pilot/` | Resultado |
|---|---|
| `2026-10-16-biocarbon-prepared` | Preparación sin proveedor. |
| `2026-10-16-biocarbon-attempt1` | Error de conexión por restricción de red. |
| `2026-10-16-biocarbon-live` | Extracción completa: 74 recibidas, 68 conservadas, 6 descartes. |
| `2026-10-16-biocarbon-revised` | Extracción completa con prompt precisado y título: 86 recibidas, 77 conservadas, 9 descartes. |
| `2026-10-16-biocarbon-validated` | Validación estricta; fallo en el bloque de offset 2113 tras una corrección. |
| `2026-10-16-biocarbon-final` | Reanudación con conflictos detallados; mismo bloque inválido. |
| `2026-10-16-biocarbon-final2` | Reanudación con límite de dos correcciones; persiste CHAR dentro de CHAR. |

Las primeras dos extracciones completas no son salidas aceptadas: sus
descartes muestran por qué no basta un resultado sin error HTTP. Las
ejecuciones estrictas conservan las respuestas para diagnóstico, pero no
generan `entities.json` parcial. No se calcularon precisión, cobertura o F1;
no existe todavía una referencia adjudicada de este documento.

## Hallazgos al leer el texto completo y las anotaciones

| Oración | Hallazgo |
|---|---|
| `s-000000432` | «INIA» se usa como ubicación; el modelo alternó LOC y CHAR sin marcar duda. CHAR requiere evidencia del papel del actor. |
| `s-000000459` | «Colecta y preparación de la materia» fue omitida en la primera extracción y recuperada después; revisar la delimitación de actividades coordinadas. |
| `s-000000496` | «podas» en «contar con las podas de estos árboles» refiere a residuos, mientras «iniciar las podas» nombra una actividad. El modelo clasificó ambos como PRAC. |
| `s-000000496` | «contactar a los propietarios e instituciones» incluyó CHAR internos que se descartaron; la delimitación debe dejar los actores separados. |
| `s-000001095` | Los hornos permiten producir biocarbón; el modelo alternó soft_INFRA y physical_INFRA. La clasificación debe seguir la función productiva descrita. |
| `s-000001757` | «produjo 1 T de biocarbón obtenido con restos de podas» añade una explicación prescindible al fragmento de actividad. |
| `s-000001979` | Una capacitación extensa incluyó actores y otra práctica interna; el reintento consiguió separarlos. Recibir capacitación no basta para añadir SKILL. |
| `s-000002113` | PRAC «capacitación» debe quedar separada de sus destinatarios CHAR. El modelo corrigió esa delimitación, pero sigue añadiendo CHAR «UNAMAD» dentro de CHAR «estudiantes de la UNAMAD». |
| `s-000002377` | La descripción larga de experimentos incluyó LOC «parcela agroforestal»; acortar la actividad permite preservar el lugar aparte. |
| `s-000002573` | «incubadora SAF» apareció como CHAR interno de la denominación del personal; se eliminó en una corrección conforme a la regla actual. |
| `s-000002870` | «ITP» solo ubica el curso en esta oración; el modelo alternó CHAR y LOC. Los estudiantes, investigadores, empresas y público sí tienen participación explícita. |
| `s-000002998` | El contenido KNOW se extendió hasta «Madre de Dios» y provocó el descarte de LOC. Requiere una delimitación más corta. |
| `s-000003468` | Hay conocimiento explícito; distinguir conocimiento práctico de competencia demostrada, sin inferir SKILL por asistir al curso. |
| `s-000003721` | «Revisión bibliográfica sobre el uso de biocarbón» necesita revisión como actividad completa; el modelo omitió la revisión o extrajo solo su tema. |
| `s-000003983` | «USBI - American Biochar Institute» se agrupó en una sola CHAR; debe aplicarse la regla de nombre y sigla separados. |
| `s-000004407` y `s-000004436` | Las referencias a servicios y títulos técnicos no prueban por sí solas una función reguladora RUL; no usar conocimiento externo del estándar. |
| `s-000004638` | La primera extracción omitió Perú, laboratorios y análisis; la segunda los recuperó. Certificación sin regla identificada no autoriza RUL. |
| `s-000005130` | La denominación de laboratorio queda separada del párrafo introductorio por el corte de bloque. Revisar la pérdida de contexto antes de atribuir un papel por conocimiento externo. |
| `s-000005187` | El título nombra análisis de parámetros del biocarbón; fue omitido en las extracciones completas. |

Los hallazgos son una revisión preliminar del agente, no una adjudicación
humana ni un conjunto de referencia. El documento no permite evaluar todas
las categorías; por ejemplo, no ofrece evidencia clara de ATT o eco_INFRA.

## Comprobaciones y operación

108 pruebas ejecutadas: 106 exitosas y 2 omitidas por dependencias opcionales
de Leiden. Las regresiones nuevas cubren anidación en ambos órdenes,
repeticiones, solapamientos rechazados, fragmentos no literales, corrección
exitosa, errores persistentes y document_id incorrecto.

Docker estaba detenido; se comprobó el fallo de conexión también fuera del
sandbox. Se instaló en `.venv` la dependencia Anthropic ya declarada en
requirements.txt para ejecutar el proveedor real. No se modificaron `.env`,
datos de PostgreSQL, artefactos NER oficiales, canónicos ni redes. No se
ejecutaron fuzzy matching ni procesamiento del corpus. La API requiere
iniciarse/reiniciarse para validar el endpoint y recargar las cachés de prompt.

Los cambios de esta sesión permanecen sin commit para revisión. El estado
vigente está en PROJECT_CONTEXT.md y las tareas abiertas solo en tasks.md.

## Registro posterior en Git

La usuaria solicitó registrar los diez cambios pendientes. Se revisaron los
archivos y se repitió la suite: 106 pruebas exitosas y 2 omisiones previstas.
Los cambios descritos se incluyen junto con esta nota en el commit de la
revisión NER y su piloto. La revisión semántica del piloto continúa pendiente.
