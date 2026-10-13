# Revisión del código — contrato NER y PostgreSQL

La usuaria pidió un codebook más básico, considerando el uso eficiente de
Claude, y revisar primero el código para aprovechar la estructura existente.
Se revisaron modelos, repositorios, servicios y prompts. No se inspeccionó
la DB en ejecución ni se consumió la API de Claude. No se modificaron código,
prompts ni datos; solo se documentaron hallazgos.

## Contrato y persistencia

- `src/services/ner.py`: la herramienta pide `document_id` y `annotations`.
  Cada anotación contiene `label`, `text`, `sentence_id` y `ambiguity`
  (`low`, `medium`, `high`). Las etiquetas activas son CHAR, LOC, INFRA,
  RUL y PRAC. La API renombra label a category, localiza el fragmento
  y calcula start/end; context se toma de la oración, no lo genera Claude.
- `src/services/documents.py`: la extracción guarda JSON en archivosNER y
  actualiza documents. Las menciones se escriben en PostgreSQL durante
  fuzzy matching, junto con las oraciones y el estado del documento.
- `entities`: menciones con document_id, canonical_id, category, text,
  position_start/end, sentence_id, context, ambiguity, resolution_method,
  resolution_score, resolution_version, resolution_details, id y created_at.
- `canonical_entities`: id, canonical_name, category.
- `canonical_entity_aliases`: alias textual y normalizado, canonical_id,
  método de resolución y documento de origen, además de id/fecha.
- `sentences`: document_id, sentence_id y texto, además de id/fecha.

Los campos canónicos y de resolución se asignan localmente, sin Claude.
El codebook puede apoyarse en este contrato y centrarse en criterios
esenciales de clasificación; no hace falta pedir al LLM toda la fila DB.

## Diferencias y consumo observados

1. NER y fuzzy matching aceptan cinco categorías; las diez del codebook
   todavía no están implementadas. Los modelos usan Text para category.
2. El prompt prohíbe anidación y la búsqueda de offsets rechaza intervalos
   solapados. En una prueba local de CHAR «comunidad de San Pedro» y LOC
   «San Pedro», el parser conservó solo CHAR.
3. El prompt une nombre completo y sigla contiguos en un solo fragmento.
   El acuerdo nuevo pide extraerlos por separado. Además, una prueba del
   resolver con repositorios simulados, sin canónicos ni alias previos,
   produjo dos nodos para «Asociación de Productores de Cacao» y «APC»
   pese a compartir el contexto con paréntesis. No debe darse por implementada
   la unión automática por la correspondencia contextual.
4. Cada llamada NER vuelve a incluir 25 demostraciones formateadas
   (9.451 caracteres) y el prompt de sistema (8.663 caracteres). Son
   caracteres, no tokens ni costos medidos. La caché de lectura en variables
   Python no evita enviar estos textos. La llamada no configura cache_control
   ni registra usage; no se verificó el comportamiento de caché del proveedor.
5. linguisticCleaning también llama a Claude por fragmentos, antes de NER.
   Los fragmentos NER agrupan hasta tres párrafos con umbral configurado
   de 12.000 caracteres; un párrafo largo no se subdivide en esa función.

## Comprobaciones

- 3 pruebas existentes de posiciones NER: pasan.
- 18 pruebas existentes de resolución canónica: pasan.
- Dos comprobaciones locales adicionales: rechazo de anidación y dos
  nodos para nombre/sigla sin alias previo. Sin red ni escritura en DB.

Las diferencias se documentan para la adaptación posterior; esta revisión
no altera el esquema de categorías ni descarta acuerdos de la usuaria.

## Aclaración posterior — diez categorías como decisión final

La usuaria reafirmó que la modificación a diez categorías es la decisión
final. Se fijó explícitamente ese conjunto en el codebook y en el contexto:
CHAR, KNOW, ATT, SKILL, PRAC, physical_INFRA, soft_INFRA, eco_INFRA, RUL y LOC.

El hallazgo de cinco etiquetas describe exclusivamente el código existente.
Es un desfase que se debe corregir; no una alternativa al esquema aprobado.
Esta aclaración no implica que la adaptación técnica ya se haya ejecutado.
