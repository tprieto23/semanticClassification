Usa los siguientes ejemplos para interpretar las categorías y reglas de extracción y clasificación. Extrae únicamente fragmentos que aparezcan literalmente en las oraciones de `target_input`.

<few_shot_examples>
$few_shot_examples
</few_shot_examples>

Ahora analiza exclusivamente las oraciones de `sentences` del siguiente objeto. Recorre todas las oraciones, extrae y clasifica cada aparición válida según las categorías y reglas indicadas y copia en cada anotación el `sentence_id` de la oración que contiene el span. Entrega el resultado mediante `submit_entity_annotations`.

<target_input>
$json_input
</target_input>
