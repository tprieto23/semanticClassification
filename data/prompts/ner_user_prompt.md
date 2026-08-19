Estas son demostraciones curadas de cómo aplicar el codebook. Estudia el patrón de decisión, pero no copies spans de las demostraciones si no aparecen literalmente en el fragmento real.

<few_shot_examples>
$few_shot_examples
</few_shot_examples>

Ahora analiza exclusivamente las oraciones de `sentences` del siguiente objeto. Recorre todas las oraciones, extrae cada aparición válida según el codebook y copia en cada anotación el `sentence_id` de la oración que contiene el span. Entrega el resultado mediante `submit_entity_annotations`.

<target_input>
$json_input
</target_input>
