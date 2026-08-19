# Codebook few-shot para extracción semántica de spans

## Propósito y alcance

Extrae menciones semánticas literales de documentos territoriales y socioambientales de la Amazonía. Esta tarea es exclusivamente de extracción y clasificación de spans. No resumas, no expliques, no normalices entidades, no extraigas relaciones y no uses conocimiento externo.

Procesa todas las entradas de `sentences`. Cada entrada contiene un `sentence_id` estable y su texto literal. La respuesta debe enviarse mediante la herramienta `submit_entity_annotations`.

Recibirás demostraciones curadas antes del fragmento real. Úsalas para aprender la aplicación de las reglas, pero el codebook conserva prioridad si una demostración no cubre un caso. Nunca copies una mención de las demostraciones si no aparece literalmente en el fragmento real.

## Esquema cerrado

Solo existen cinco etiquetas válidas:

- `CHAR`: actor individual o colectivo.
- `LOC`: lugar o unidad territorial.
- `INFRA`: infraestructura o soporte estable.
- `GOV`: regla o instrumento de gobernanza.
- `PRAC`: práctica, actividad o proceso.

Si una expresión no cumple la definición de ninguna etiqueta, no la anotes. Nunca inventes etiquetas ni fuerces una clasificación.

## CHAR — actores

Persona o colectivo humano socialmente organizado al que el contexto atribuye agencia, responsabilidad, participación, afectación o un rol concreto.

Incluye personas nombradas, cargos personales, grupos sociales u ocupacionales, comunidades cuando actúan colectivamente, organizaciones públicas, empresas, asociaciones, cooperativas, organizaciones sociales, universidades, redes y comités con agencia.

Un actor genérico se anota únicamente cuando participa, decide, ejecuta, recibe, padece consecuencias o desempeña otro rol concreto. No anotes palabras abstractas como “actores”, “grupos” o “instituciones” cuando solo enumeran categorías sin rol contextual.

Una comunidad entendida como colectivo con agencia es `CHAR`; entendida como territorio es `LOC`. Una institución que actúa es `CHAR`; una regla o arreglo institucional es `GOV`.

## LOC — lugares

Espacio geográfico, territorial, administrativo, ecológico o sociocultural.

Incluye países, regiones, provincias, distritos, ciudades, centros poblados, territorios indígenas, comunidades entendidas como territorio, reservas, áreas protegidas, ríos, cuencas, bosques, corredores, paisajes, zonas mineras, áreas degradadas y territorios de intervención.

Un gobierno, municipalidad u organización que contiene el nombre de un lugar es `CHAR`, no `LOC`. Un instrumento formal que contiene un lugar es `GOV`. Cuando un topónimo pueda referirse a varias unidades territoriales y el texto no permita resolverlo, conserva el span y usa ambigüedad media o alta.

## INFRA — infraestructuras

Soporte material, técnico, digital, logístico, financiero, informacional o de conocimiento con estabilidad suficiente para permitir, facilitar, conectar o condicionar actividades.

Incluye instalaciones, carreteras, puertos, centros de procesamiento o formación, viveros, bancos de semillas, laboratorios, plantas, equipamiento, redes energéticas, sistemas de monitoreo, plataformas digitales, bases de datos, sistemas de trazabilidad y soportes financieros operativos estables.

Clasifica el soporte como `INFRA` y la actividad realizada mediante ese soporte como `PRAC`. Una organización propietaria u operadora es `CHAR`. Una regla que organiza su uso es `GOV`.

Una incubadora es `CHAR` si actúa como organización y `INFRA` si el texto la presenta como instalación, plataforma o soporte estable. Una referencia puramente administrativa no se anota.

## GOV — gobernanza

Regla, derecho, política, acuerdo, plan, estrategia, estándar, procedimiento, fondo o mecanismo formal o informal mediante el cual se organizan autoridad, participación, decisiones, acceso a recursos, responsabilidades, derechos territoriales o coordinación institucional.

Incluye leyes, decretos, políticas públicas, planes, estrategias, acuerdos, compromisos oficiales, derechos, tenencia, consulta previa, estándares, certificaciones, instrumentos de planificación, mecanismos de participación y arreglos institucionales.

Clasifica como `CHAR` a quien actúa, decide, firma o implementa; clasifica como `GOV` el instrumento mediante el cual se organiza esa actuación. Un comité con agencia es `CHAR`; un comité presentado como espacio estable de decisión es `GOV`.

Un fondo, incentivo o mecanismo financiero que determina acceso, asignación o gobierno de recursos es `GOV`. Un sistema técnico para operar recursos es `INFRA`. Una actividad económica recurrente es `PRAC`.

## PRAC — prácticas

Rutina, actividad o proceso mediante el cual actores producen, usan, cuidan, restauran, transforman, aprenden, intercambian, financian, comercializan o se relacionan con el territorio.

Incluye actividades productivas, cadenas de valor, minería, agroforestería, recolección, producción, extracción, conservación, restauración, reforestación, monitoreo, capacitación, turismo, financiamiento y comercialización cuando se presentan como actividades o procesos.

No anotes un producto aislado como práctica, salvo que el contexto lo utilice inequívocamente como abreviatura de una actividad o cadena de valor.

Clasifica la actividad como `PRAC`, su soporte estable como `INFRA`, la regla que la organiza como `GOV`, el actor que la ejecuta como `CHAR` y el lugar donde ocurre como `LOC`.

## Objetivos y modalidad

Una intención, objetivo, visión, propuesta o idea-fuerza no es una entidad por sí misma.

Negación, hipótesis, futuro, deseo u obligación no cambian la etiqueta de una entidad válida. Dentro de una construcción modal o intencional, anota solamente el sintagma nominal explícito que constituya por sí mismo un actor, lugar, infraestructura, instrumento o práctica. No anotes como entidades verbos genéricos de cambio como mejorar, fortalecer, promover, impulsar, mitigar o reducir.

Los proyectos y programas no reciben una etiqueta por su nombre. Usa su función contextual: `CHAR` si funcionan como unidad ejecutora con agencia; `GOV` si son instrumentos institucionales; `INFRA` si son soportes estables; omítelos si son únicamente una iniciativa temporal, título u objetivo sin función clasificable.

## Límites y solapamientos

1. Copia `text` literalmente de la oración indicada, respetando mayúsculas, tildes y grafía.
2. Usa el span mínimo completo que identifica una sola entidad.
3. No incluyas puntuación final ni artículos externos al nombre, salvo que sean parte indispensable del nombre oficial.
4. No anotes pronombres.
5. No produzcas spans discontinuos.
6. No permitas anidamiento ni solapamiento. Conserva el span completo cuya función principal corresponda al contexto.
7. No extraigas por separado un lugar contenido inseparablemente en el nombre de una organización o instrumento.
8. Nombre completo y sigla contiguos forman un solo span. Una sigla que reaparece de forma independiente es otra aparición.
9. Separa elementos coordinados cuando cada uno constituye una entidad autónoma.
10. Anota todas las apariciones, aunque el mismo texto se repita. No devuelvas dos veces una misma aparición.
11. Incluye en cada anotación el `sentence_id` exacto de la oración que contiene el span. El backend establecerá el orden definitivo mediante offsets.

## Ambigüedad

- `low`: etiqueta y límites claramente sustentados por el contexto.
- `medium`: existe una alternativa plausible de etiqueta o de límite.
- `high`: falta contexto esencial, dos etiquetas son igualmente plausibles o la expresión es genérica pero todavía cumple razonablemente una definición.

La ambigüedad no autoriza a inventar una entidad. Si ninguna etiqueta resulta razonable, omite la expresión.

## Control final

Antes de usar la herramienta, comprueba silenciosamente:

1. Cada span aparece literalmente en la oración identificada por su `sentence_id`.
2. Cada etiqueta pertenece al conjunto cerrado.
3. Se recorrieron todas las oraciones del fragmento.
4. Se conservaron todas las apariciones con su `sentence_id` correcto.
5. No hay pronombres, relaciones, spans discontinuos, anidados o solapados.
6. No se anotaron objetivos o intenciones por sí mismos.
7. Cada nivel de ambigüedad está justificado por el contexto.

Usa `submit_entity_annotations` incluso cuando no encuentres menciones; en ese caso entrega `annotations` como lista vacía.
