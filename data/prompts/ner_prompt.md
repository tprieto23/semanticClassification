# Extracción semántica territorial

Extrae menciones literales de documentos sobre conservación, vida sostenible y gobernanza territorial en la Amazonía peruana. Procesa todas las oraciones de `sentences` y responde mediante `submit_entity_annotations`. No resumas, no expliques, no normalices y no uses conocimiento externo.

## Diez categorías válidas

Las etiquetas y definiciones siguientes se incorporan desde la taxonomía del código. Clasifica según la función descrita en el contexto, sin inventar etiquetas ni forzar una clasificación.

$category_definitions

## Criterios generales

- Extrae solo expresiones explícitas respaldadas por el texto. Una actividad no demuestra por sí sola conocimiento, habilidad o actitud.
- Distingue actor, saber, valoración, competencia, actividad, soporte, regla y lugar por su función contextual.
- Una intención u objetivo no constituye por sí mismo una entidad. Conserva las menciones válidas dentro de construcciones negadas, propuestas o futuras sin afirmar que ocurrieron. No anotes verbos genéricos como mejorar, fortalecer o promover.
- Los proyectos y programas se clasifican por su función contextual; su nombre por sí solo no determina una categoría.

## Registro de menciones

- Copia el fragmento mínimo completo literalmente: conserva mayúsculas, tildes y plural. Excluye puntuación final y artículos externos; conserva artículos integrantes de nombres propios, como en «cooperativa La Esperanza».
- Anota cada aparición, incluidas repeticiones dentro de una oración. Separa actores explícitamente enumerados; no inventes fragmentos discontinuos ni expandas siglas.
- No anotes pronombres. Usa las denominaciones explícitas de los actores.
- Las demostraciones ilustran las categorías. No copies sus menciones si no aparecen en las oraciones recibidas.

## Salida estructurada

Entrega `document_id` y `annotations`. Cada anotación contiene únicamente `label`, `text`, `sentence_id` y `ambiguity` (`low`, `medium` o `high`). Usa el identificador de la oración que contiene el fragmento. Si no hay menciones válidas, devuelve `annotations: []`.

El backend calcula posiciones y contexto; no los incluyas en la respuesta. No unifiques menciones ni generes identificadores canónicos.
