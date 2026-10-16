# Codebook para la extracción y etiquetación de entidades semánticas

**Estado:** Borrador operativo para revisión; piloto aún no aprobado.

**Versión:** Borrador 0.2 — 16 de octubre de 2026.

Extrae menciones literales y clasifícalas en las 10 categorías de este
codebook. Utiliza las instrucciones y el texto recibido; no consultes
documentos externos ni añadas información mediante conocimiento externo.
La aplicación al corpus requiere la revisión del piloto descrita en la sección 10.

## 1. Propósito de la anotación

### 1.1. Objetivo inmediato

Identifica palabras o fragmentos cortos presentes en el texto y asígnales
las etiquetas correspondientes al sistema de 10 categorías.

### 1.2. Resultado esperado

Obtén menciones clasificadas, vinculadas con sus documentos y oraciones de
origen. Por ejemplo, una mención de «Wyss» que identifique al actor recibe
la etiqueta `CHAR`.

### 1.3. Uso posterior y objetivo final

El procesamiento se organiza en tres tareas consecutivas, ejecutadas mediante
endpoints independientes:

1. **NER:** extraer menciones literales y clasificarlas en las 10 categorías.
2. **Fuzzy matching:** normalizar y agrupar variantes mediante resolución de
   entidades, conservando las menciones originales y sus evidencias.
3. **Construcción de relaciones:** conectar las entidades consolidadas a partir
   de la coaparición de sus menciones para construir una red semántica.

Cada tarea requiere que se haya completado la anterior. Este codebook define
la extracción y clasificación de NER. Conserva las menciones originales;
la normalización, resolución de entidades y construcción de relaciones
se ejecutan en las tareas posteriores.

### 1.4. Función operativa dentro de la API

El codebook es la referencia metodológica para el prompt, los criterios de
clasificación y el contrato de las anotaciones de NER. Sus reglas deben
trasladarse al prompt y a los controles del código; la API no incorpora
automáticamente este documento completo.

El modelo devuelve las menciones clasificadas mediante los campos `label`,
`text`, `sentence_id` y `ambiguity`. El código calcula su ubicación y conserva
la oración de origen como contexto. NER entrega esas evidencias para las
tareas posteriores; su responsabilidad se limita a extraer y clasificar.

## 2. Dominio y alcance

### 2.1. Marco temático

Conservación de la naturaleza, vida sostenible y gobernanza territorial en la
Amazonía peruana.

Este marco comprende los componentes ecológicos, sociales, económicos,
culturales e institucionales del territorio y sus interacciones en torno
al uso, conservación y transformación de los ecosistemas y a las condiciones
de vida de las poblaciones.

### 2.2. Enfoque

Deforestación y transiciones socioecológicas.

### 2.3. Criterios de alcance

Deforestación y transiciones socioecológicas constituyen una orientación
temática. La inclusión de una mención no requiere que su oración nombre
expresamente la deforestación o una transición socioecológica. Su pertinencia
se determina por la vinculación que el texto y su contexto establecen con
el sistema territorial comprendido en el marco temático y por los criterios
de las 10 categorías de anotación.

- Función del enfoque: orientación temática.
- Entrada de NER: texto limpio procedente de archivos `.txt`; se procesa todo
  su contenido por bloques. La carga y conversión de otros formatos son etapas anteriores.
- Idiomas admitidos: cualquier idioma; conserva los fragmentos en el idioma original.
- Contenido incluido: menciones pertinentes de los componentes ecológicos,
  sociales, económicos, culturales e institucionales del sistema territorial,
  incluidas prácticas, actores, lugares, reglas, infraestructuras, conocimientos,
  actitudes y capacidades, según las 10 categorías. Mercados,
  migración y otros procesos pueden incluirse cuando cumplan esos criterios,
  aunque la oración no mencione expresamente la deforestación.
- Formatos excluidos de NER: archivos que aún no se hayan convertido y limpiado a texto.

### 2.4. Contexto territorial y temático del corpus

El codebook orienta la extracción de menciones en textos sobre los sistemas
socioecológicos de la Amazonía peruana. Interesa comprender cómo se relacionan
los ecosistemas, las poblaciones, las actividades productivas y extractivas
y las formas de organización y gestión del territorio, en torno a la
conservación de la naturaleza, las condiciones de vida y las transformaciones
territoriales.

Este contexto comprende el uso y la transformación de los bosques y otros
ecosistemas; las prácticas productivas y extractivas; la conservación y la
restauración; el acceso a infraestructura y mercados; y las condiciones de
vida de las poblaciones. También abarca la tenencia y los derechos
territoriales, la participación y coordinación entre actores, los saberes
locales y técnicos, las identidades y valores y las capacidades para gestionar
el territorio.

### 2.5. Lineamientos conceptuales para orientar la extracción

#### 2.5.1. Cobertura del sistema socioecológico

**Fundamento conceptual:** El territorio se comprende como un sistema
socioecológico en el que los componentes ecológicos, sociales, económicos,
culturales e institucionales se relacionan. Su comprensión requiere reconocer
tanto las dinámicas de conservación y regeneración como las de extracción,
degradación y conflicto, junto con las condiciones que las habilitan o limitan.

**Lineamiento operativo:** La extracción debe identificar las
menciones pertinentes de esos componentes cuando estén sustentadas por el
texto y cumplan los criterios de alguna de las 10 categorías. La inclusión se
determina por su pertinencia para el dominio y su función contextual. Tanto
las menciones presentadas como favorables como las presentadas como
desfavorables o ambivalentes pueden ser objeto de anotación.

**Ejemplo conceptual:** En un pasaje sobre carreteras, minería, comunidades
y conservación, cada expresión se evalúa según su contexto y los criterios
de las categorías. La selección no se limita a las expresiones asociadas
con resultados deseables.

#### 2.5.2. Clasificación según la función contextual de la mención

**Fundamento conceptual:** Un ámbito del sistema territorial puede reunir
actores, reglas, prácticas, soportes, conocimientos y otros componentes.
Un pasaje sobre gobernanza puede mencionar organizaciones, instrumentos
institucionales y procesos de gestión. Cada mención puede corresponder a
una categoría distinta.

**Lineamiento operativo:** Cada mención se clasificará según el
componente que identifica y la función que el texto le atribuye en su contexto,
aplicando las definiciones y criterios de las 10 categorías. El tema
del pasaje, el título de una sección y las palabras indicadoras podrán
orientar la interpretación; la asignación deberá estar sustentada por la
mención y su contexto.

**Ejemplos orientativos:**
«SERNANP» presentado como organización participante corresponde a un actor
(`CHAR`); un «plan maestro» presentado como instrumento de gestión corresponde
a una regla o instrumento (`RUL`); la «titulación de comunidades nativas»
presentada como proceso corresponde a una práctica (`PRAC`).

Cuando la función no pueda determinarse con el contexto permitido, aplica
la política de ambigüedad de la sección 7.

## 3. Unidades de anotación y contexto

- Qué se entiende por entidad o mención en esta tarea: palabra o fragmento corto del texto que identifica un componente del territorio clasificable en alguna de las 10 categorías.
- Unidad que recibe una etiqueta: fragmento continuo, literal y suficientemente completo para identificar lo mencionado, contenido en una oración.
- Contexto permitido para interpretar una mención: la oración que contiene la mención y las demás oraciones del bloque recibido por el modelo. Se guarda como contexto la oración de origen.
- Evidencia textual requerida e inferencias permitidas: toda anotación debe estar respaldada por el texto. No se añaden entidades ni atributos mediante conocimiento externo.
- Tratamiento de menciones repetidas: se registra cada aparición como
  una mención independiente, con su ubicación y contexto (sección 6.2).
  La vinculación posterior al mismo nodo canónico conserva esas evidencias.
- Distinción entre mención literal y entidad canónica: la extracción
  conserva el texto literal del fragmento seleccionado; la normalización
  y la vinculación a entidades canónicas corresponden a la tarea posterior
  de fuzzy matching.
- Alcance de esta etapa: NER extrae y clasifica menciones. La construcción
  de relaciones y sus reglas de coaparición se definen en la tarea de red.

## 4. Sistema de etiquetas

- Número de categorías: 10.
- Conjunto de etiquetas: fijado en los 10 códigos de la tabla siguiente.
- Una o varias etiquetas para el mismo fragmento: asignar la categoría que corresponda a su función contextual. Se permite anotar un fragmento LOC contenido dentro de otro CHAR conforme a la sección 6; son dos fragmentos distintos.
- Tratamiento de expresiones que no pertenecen a ninguna categoría: omitirlas, sin forzar una clasificación.

Utiliza las etiquetas exactamente como aparecen en la tabla, respetando
mayúsculas, minúsculas y guiones bajos.

| Código | Categoría |
|---|---|
| CHAR | Actores |
| KNOW | Conocimiento |
| ATT | Actitudes y valores |
| SKILL | Habilidades |
| PRAC | Prácticas |
| physical_INFRA | Infraestructura física |
| soft_INFRA | Infraestructura de soporte |
| eco_INFRA | Infraestructura ecológica |
| RUL | Reglas |
| LOC | Lugares |

## 5. Definiciones operativas por categoría

Clasifica cada mención aplicando:

- Definición operativa y características esenciales.
- Criterios de inclusión y exclusión.
- Evidencia textual necesaria para asignar la etiqueta.
- Distinción respecto de categorías cercanas.

### 5.1. CHAR — Actores

**Definición:** Actor individual o colectivo que el texto identifica como participante del sistema territorial, con agencia, responsabilidad, representación, derechos, intereses o afectación en relación con sus procesos socioecológicos. Un actor individual es una persona; un actor colectivo puede ser un grupo humano, una comunidad, un pueblo u organización.

**Características que debe identificar la mención:**

1. Una persona, un grupo humano, una comunidad, un pueblo u organización.
2. Una denominación explícita del actor, por nombre propio, cargo,
   ocupación o expresión genérica.
3. Un papel respaldado por el contexto en el sistema territorial:
   agencia, responsabilidad, representación, derechos, intereses o
   afectación respecto de sus procesos socioecológicos.

**Criterios de inclusión:**

- Se admiten actores individuales y colectivos, nombrados o genéricos.
- Se incluyen los actores afectados aunque no ejecuten una acción.
- Se incluye al actor cuya participación en una actividad está negada;
  se conserva esa negación en el contexto, sin afirmar participación.

**Criterio de exclusión:** Una expresión que solo ubica un
proceso o evento, sin identificar al colectivo como actor en contexto,
no recibe CHAR. En «El taller se realizó en la comunidad de San Pedro»,
se registra únicamente «San Pedro» como LOC.

**Evidencia necesaria:** La denominación y su contexto deben permitir
identificar al actor y su papel territorial. No se requiere un nombre
propio ni la ejecución de una acción. Utiliza el contexto permitido
en la sección 3.

**Fronteras:**

- LOC identifica el lugar; CHAR, la persona o colectivo. Se permite
  LOC dentro de CHAR cuando ambas identificaciones están respaldadas
  por el contexto, conforme a la sección 6.1.
- RUL identifica la regla o instrumento; CHAR, al actor que lo establece
  o aplica. El criterio contextual para planes está en la sección 5.9.
- PRAC identifica la actividad; CHAR, al actor. «Monitoreo comunitario»
  identifica una práctica en el ejemplo de la sección 5.5.

**Ejemplos:**

- «La asociación de productores de Tambopata participa en el proyecto»:
  «asociación de productores de Tambopata» identifica un actor colectivo.
- «Los agricultores de la zona participan en el proyecto»:
  «agricultores de la zona» identifica un actor colectivo mediante
  una denominación genérica.
- «La contaminación del río afecta a las comunidades ribereñas»:
  «comunidades ribereñas» identifica un actor colectivo afectado,
  aunque no ejecute una acción.
- «La municipalidad aprobó el plan de manejo forestal»:
  «municipalidad» identifica un actor colectivo. La clasificación de
  «el plan de manejo forestal» se evalúa con el criterio contextual de
  la sección 5.9; la sola mención de su aprobación no explicita las
  condiciones, responsabilidades o criterios que establece.

Los ejemplos ilustran las características de clasificación; las reglas
sobre pronombres, artículos, nombres propios, siglas y enumeraciones
están reunidas en la sección 6.3.

### 5.2. KNOW — Conocimiento

**Definición:** Saberes técnicos, ecológicos o tradicionales sobre el
territorio, sus ecosistemas y su gestión.

- **Conocimiento técnico:** Saberes sobre técnicas, métodos, herramientas
  o procedimientos, por ejemplo, conocimientos sobre manejo de suelos o
  sistemas agroforestales.
- **Conocimiento ecológico:** Saberes sobre ecosistemas, especies, ciclos
  y relaciones ecológicas, por ejemplo, conocimientos sobre la floración
  de la castaña.
- **Conocimiento tradicional:** Saberes locales o indígenas conservados
  o transmitidos, por ejemplo, conocimientos sobre usos de plantas o
  manejo tradicional del bosque.

Estos tipos son referencias descriptivas dentro de KNOW; no constituyen
nuevos códigos de categoría.

**Criterio de inclusión:** El texto debe identificar un saber o contenido de conocimiento. Puede hacerlo mediante una denominación explícita, como «saberes tradicionales sobre el manejo del bosque», o mediante una expresión que atribuya conocimiento, como «los productores conocen los ciclos de floración de la castaña». Extrae «ciclos de floración de la castaña» como KNOW y «productores» como CHAR.

**Portador del conocimiento:** Se admiten menciones explícitas de saberes aunque el texto no identifique quién los posee. Esto no autoriza a atribuirles un portador que el texto no señale.

**Tratamiento de afirmaciones generales:** Asigna KNOW únicamente cuando el texto identifique el contenido como un saber o atribuya conocimiento. Una afirmación informativa o una descripción del territorio no basta por sí sola para asignar KNOW. No se requiere identificar al portador del saber.

**Evidencia y exclusiones:** La presencia de una práctica, una habilidad o un término técnico por sí sola no demuestra que el texto esté describiendo conocimiento. La realización de una actividad no permite añadir automáticamente una anotación de KNOW. Una afirmación sobre el territorio debe evaluarse en contexto para determinar si presenta un contenido de conocimiento conforme a esta definición.

**Distinción:** KNOW identifica el saber o contenido conocido; SKILL identifica la competencia para realizar una tarea; PRAC identifica la actividad.

**Frontera con ATT:** Las valoraciones, identidades y compromisos se evalúan según ATT. Cada categoría requiere su propia evidencia.

**Ejemplos de distinción entre KNOW, SKILL y PRAC:**

| Texto | Interpretación orientativa |
|---|---|
| Las productoras conocen los ciclos de floración de la castaña. | KNOW: expresa conocimiento ecológico. |
| Las productoras saben usar equipos de monitoreo. | SKILL: expresa competencia operativa. |
| Las productoras monitorean la floración de la castaña. | PRAC: expresa una actividad. |

- Exclusiones: una actividad, habilidad o término técnico aislado no basta para asignar KNOW.
- Frontera con ATT: KNOW identifica saberes o contenidos conocidos; ATT identifica valoraciones, percepciones, identidades y compromisos.
- Afirmaciones generales: una descripción del territorio no recibe automáticamente KNOW. El texto debe presentarla como un saber o contenido de conocimiento.
- Fragmento: extraer el contenido del saber, conservando en el contexto la expresión que permite reconocerlo.

### 5.3. ATT — Actitudes y valores

**Definición:** Valores, identidades, percepciones y compromisos que el texto atribuye a actores individuales o colectivos respecto del territorio, sus ecosistemas o su gestión.

**Inclusión y evidencia:** Asigna ATT cuando el texto exprese una valoración, percepción, identidad o compromiso y lo atribuya a un actor individual o colectivo.

**Exclusión:** Una descripción factual, un saber o la realización de una actividad no bastan por sí solos para asignar ATT.

**Amplitud:** Incluye actitudes favorables, desfavorables o ambivalentes respecto del territorio, sus ecosistemas o su gestión.

**Fragmento:** Extrae la expresión que identifica la actitud y aquello a lo que se refiere, conservando al actor y la atribución en el contexto.

**Ejemplos orientativos:** Sentido de pertenencia, valoración del bosque y compromiso con su conservación.

**Distinción:** Valorar o percibir corresponde a ATT; conocer, a KNOW; actuar, a PRAC. No se infiere una actitud únicamente porque alguien realice una actividad.

**Ejemplo de anotación:** En «Las productoras expresan su compromiso con la conservación del bosque», extrae «compromiso con la conservación del bosque» como ATT y «productoras» como CHAR.

### 5.4. SKILL — Habilidades

**Definición:** Destrezas o competencias que el texto atribuye a actores individuales o colectivos para realizar tareas técnicas, de gestión o de monitoreo en el territorio.

**Tipos de habilidades:** Técnicas, de gestión y de monitoreo.

**Inclusión y evidencia:** Asigna SKILL cuando el texto atribuya a un actor una destreza o competencia para realizar una tarea técnica, de gestión o de monitoreo.

**Exclusión:** Conocer una técnica, querer aplicarla o realizar una actividad no demuestra por sí solo una habilidad.

**Capacidad operativa:** Distingue la competencia para hacer algo de tener permiso, recursos u oportunidad para hacerlo. La palabra «puede» por sí sola no basta para asignar SKILL.

**Fragmento:** Extrae la expresión que identifica la habilidad y la tarea correspondiente, conservando al actor y la atribución en el contexto.

**Ejemplos orientativos:** Capacidad para manejar equipos, gestionar proyectos o aplicar técnicas de restauración.

**Distinción:** Conocer una técnica corresponde a KNOW; saber aplicarla, a SKILL; aplicarla, a PRAC. Realizar una actividad no basta, por sí solo, para anotar una habilidad.

**Ejemplo de anotación:** En «Las productoras poseen capacidad para manejar equipos de monitoreo», extrae «capacidad para manejar equipos de monitoreo» como SKILL y «productoras» como CHAR.

### 5.5. PRAC — Prácticas

**Definición:** Actividades, rutinas o procesos que el texto identifica para producir, aprovechar, conservar, restaurar, monitorear, comercializar o gestionar componentes del territorio.

**Actividades comprendidas:** Agroforestería, monitoreo, comercialización, restauración y gobernanza como actividad o proceso.

**Inclusión y evidencia:** Asigna PRAC cuando el texto nombre una actividad o describa una acción concreta pertinente para el territorio. Puede expresarse como sustantivo o como expresión verbal. No se requiere identificar al actor si la actividad está explícita.

**Exclusión:** Un actor, un soporte, una regla, un saber o una habilidad no constituyen por sí solos una práctica. No anotes verbos genéricos como «mejorar», «fortalecer» o «promover»; si acompañan una actividad concreta, extrae la expresión que identifica esa actividad.

**Amplitud:** Las prácticas pueden ser sostenibles, degradantes o ambivalentes.

**Actividades existentes, propuestas o negadas:** Extrae las actividades explícitas aunque se presenten como propuestas, futuras, necesarias o negadas. Conserva esa condición en el contexto; la anotación identifica la actividad, sin afirmar que se haya realizado. Un deseo u objetivo general sin una actividad identificable no basta para asignar PRAC.

**Fragmento:** Extrae la denominación de la actividad o la expresión verbal mínima que la identifica. Conserva sus complementos necesarios y su forma literal, sin convertir verbos a infinitivo ni reconstruir palabras omitidas.

**Distinción:** Saber realizar una actividad corresponde a SKILL; la actividad, a PRAC; las normas que la regulan, a RUL.

**Ejemplos de anotación:**

- En «Se realizan actividades de monitoreo comunitario», extrae «monitoreo comunitario» como PRAC. El adjetivo «comunitario» no nombra por sí solo un actor y no basta para añadir CHAR.
- En «Se propone la restauración del bosque», extrae «restauración del bosque» como PRAC; conserva la propuesta en el contexto sin afirmar su ejecución.

### 5.6. physical_INFRA — Infraestructura física

**Definición:** Elementos materiales construidos o instalados que permiten o condicionan el acceso, la movilidad, el suministro de energía o la conectividad tecnológica en el territorio.

**Ejemplos:** Carreteras, puentes, puertos, redes eléctricas y antenas de telecomunicaciones.

**Inclusión y evidencia:** Asigna physical_INFRA cuando la denominación del elemento y su contexto permitan identificar una estructura construida o instalada con alguna de esas funciones. La función puede estar expresada en la propia denominación o descrita en el contexto.

**Exclusión:** La materialidad de un objeto no basta. Un equipo, edificio o instalación no recibe automáticamente physical_INFRA por ser físico. Tampoco se clasifican aquí las actividades de construirlo, mantenerlo o utilizarlo, ni las estructuras naturales por su función ecológica.

**Fragmento:** Extrae la denominación del elemento, incluidos el nombre propio y los modificadores necesarios para identificarlo. Conserva el texto literal; las actividades realizadas sobre él se evalúan por separado como PRAC.

**Distinción:** La carretera corresponde a physical_INFRA; su construcción o mantenimiento, a PRAC. La clasificación depende de la función descrita, no solo de que sea un objeto físico.

**Frontera con soft_INFRA:** Se distingue por la función descrita: physical_INFRA corresponde al acceso, movilidad, energía o conectividad tecnológica; soft_INFRA, a los soportes organizados definidos en su ficha. La presencia de componentes materiales no determina por sí sola la etiqueta.

**Equipamiento de monitoreo:** Si el texto lo presenta como un recurso organizado para el monitoreo, evalúalo como soft_INFRA. Si describe una estructura de conectividad tecnológica, evalúala como physical_INFRA. La palabra «equipo» por sí sola no resuelve la categoría.

**Ejemplo de anotación:** En «El puente permite el acceso al territorio», extrae «puente» como physical_INFRA.

### 5.7. soft_INFRA — Infraestructura de soporte

**Definición:** Sistemas, instalaciones y recursos organizados que sostienen la producción, el aprendizaje, el monitoreo o la gestión de información en el territorio.

**Ejemplos:** Viveros, bancos de semillas, sistemas de monitoreo y plataformas digitales.

**Inclusión y evidencia:** Asigna soft_INFRA cuando el texto identifique un sistema, instalación o recurso organizado y su función de soporte para esas actividades. La función puede estar expresada en la denominación o descrita en el contexto; la simple mención de recursos sin esa función no basta.

**Exclusión:** Una actividad, un saber, una competencia, una organización o una regla no constituyen por sí solos infraestructura de soporte. Distingue el soporte de la actividad que permite, del actor que lo gestiona y de sus reglas de uso.

**Criterio funcional:** Estos soportes pueden tener componentes materiales; importa su función de soporte, no solo su materialidad.

**Fragmento:** Extrae la denominación del soporte con los modificadores necesarios para identificar su función, como «sistema de monitoreo» o «banco de semillas». Conserva el texto literal y los nombres propios.

**Distinción frente a PRAC:** El sistema de monitoreo corresponde a soft_INFRA; realizar el monitoreo, a PRAC.

**Frontera con physical_INFRA:** Viveros, bancos de semillas y equipamiento organizado para el monitoreo corresponden a soft_INFRA por su función de soporte. Las estructuras de acceso, movilidad, energía o conectividad tecnológica se evalúan como physical_INFRA.

**Delimitación frente a eco_INFRA:** Bosque primario y corredores se evalúan como eco_INFRA cuando cumplen funciones ecológicas. La función descrita en contexto determina la clasificación.

**Ejemplo de anotación:** En «El banco de semillas conserva material para la producción de plantas», extrae «banco de semillas» como soft_INFRA.

### 5.8. eco_INFRA — Infraestructura ecológica

**Definición:** Estructuras ecológicas naturales o restauradas que sostienen funciones ecosistémicas, conectividad ecológica, resiliencia, biodiversidad o regeneración del territorio.

**Ejemplos:** Bosques primarios, corredores biológicos y humedales.

**Inclusión y evidencia:** Asigna eco_INFRA cuando el texto identifique una estructura ecológica y respalde su función ecosistémica, de conectividad, resiliencia, biodiversidad o regeneración. Su carácter natural o su nombre por sí solos no bastan; no atribuyas funciones mediante conocimiento externo.

**Exclusión:** La ubicación de un evento, una delimitación territorial o la mención de un lugar no demuestran por sí solas una función ecológica. Las actividades de conservar, restaurar o manejar una estructura se evalúan como PRAC. Los soportes organizados para producir plantas o monitorear se
evalúan como soft_INFRA.

**Fragmento:** Extrae la denominación de la estructura ecológica, conservando los modificadores y nombres propios necesarios para identificarla. La explicación de su función permanece en el contexto.

**Distinción:** La estructura por su función ecológica corresponde a eco_INFRA; el espacio por su ubicación o delimitación, a LOC; conservarlo o restaurarlo, a PRAC.

**Frontera con soft_INFRA:** Bosque primario y corredores se evalúan como eco_INFRA cuando el texto respalde sus funciones ecológicas. Un vivero o banco de semillas se clasifica por su función de soporte a la producción, aunque contribuya a la restauración.

**Ejemplos de anotación y frontera:**

- En «Los humedales regulan el agua y sostienen la biodiversidad», extrae «humedales» como eco_INFRA.
- En «El taller se realizó en el humedal», «humedal» identifica la ubicación del evento y corresponde a LOC; esa oración no respalda eco_INFRA.

### 5.9. RUL — Reglas

**Definición:** Normas, instrumentos o acuerdos que establecen derechos, obligaciones, permisos o criterios para orientar las decisiones, la participación y las prácticas en el territorio.

**Ejemplos:** Leyes, ordenanzas, políticas, acuerdos comunitarios, estándares de certificación y mecanismos de participación.

**Inclusión y evidencia:** Asigna RUL cuando el texto identifique una regla o presente un instrumento o acuerdo con función reguladora: establecer derechos, obligaciones, permisos, condiciones o criterios para las decisiones y prácticas territoriales. Una denominación genérica como «acuerdo», «plan» o «mecanismo» por sí sola no basta sin esa función.

**Formalidad:** Incluye reglas legales, institucionales o comunitarias, formales o informales, cuando su función reguladora esté respaldada por el texto. No se requiere verificar su reconocimiento en fuentes externas.

**Exclusión:** Un deseo, preferencia o compromiso personal no constituye por sí solo una regla. Distingue la norma de la organización que la establece, del soporte que permite aplicarla y de la actividad de elaborarla o ejecutarla.

**Fragmento:** Extrae la denominación de la norma, instrumento o acuerdo, conservando el nombre, número y modificadores necesarios para identificarlo. Si no tiene denominación, extrae la expresión mínima que formula el derecho, obligación, permiso o prohibición. Conserva la negación cuando forme parte del contenido de la regla.

**Distinción:** La regla corresponde a RUL; el actor que la establece o aplica, a CHAR; la actividad de aplicarla, a PRAC.

**Criterio de inclusión — planes:** Incluir los planes en RUL cuando el contexto los presente como instrumentos que establecen condiciones, responsabilidades o criterios para las prácticas territoriales. La denominación «plan» por sí sola no basta para asignar RUL; el texto y su contexto deben respaldar esa función.

Este criterio clasifica la mención del plan como instrumento. Las prescripciones que contiene y las actividades de elaborarlo o implementarlo deben distinguirse de esa mención y evaluarse según sus categorías.

**Ejemplo de anotación:** En «El plan de manejo forestal establece responsabilidades», extrae «plan de manejo forestal» como RUL.

### 5.10. LOC — Lugares

**Definición:** Espacios o unidades geográficas, territoriales, administrativas o ecológicas que el texto identifica por su ubicación, extensión o delimitación.

**Ejemplos:** Territorios indígenas, comunidades como lugares, reservas, cuencas, áreas protegidas y zonas de intervención.

**Inclusión y evidencia:** Asigna LOC cuando el texto nombre un espacio o unidad territorial o lo identifique por su ubicación, extensión o delimitación. Admite nombres propios y denominaciones genéricas cuando el contexto permita reconocer su referente espacial; no se requiere un topónimo.

**Exclusión:** Una persona, colectivo u organización no recibe LOC por su vinculación con un territorio. Una estructura descrita por su función ecológica se evalúa como eco_INFRA. No añadas información geográfica ni reconstruyas nombres o límites que no aparezcan en el texto.

**Fragmento:** Extrae la denominación del lugar con los términos necesarios para identificar su unidad geográfica, como «cuenca del río Tambopata». Conserva nombres propios completos y sus artículos integrantes. Omite preposiciones externas que solo introducen la ubicación, como «en» o «hacia».

**Distinción:** La comunidad como colectivo corresponde a CHAR; su territorio, a LOC. Un bosque como espacio geográfico corresponde a LOC; como estructura que sostiene funciones ecológicas, a eco_INFRA.

**Anotación dentro de CHAR:** En «La comunidad de San Pedro decidió participar», «San Pedro» se anota como LOC dentro del fragmento «comunidad de San Pedro», anotado como CHAR, sin el artículo inicial. Véase la sección 6.

**Ejemplo de ubicación:** En «El taller se realizó en la comunidad de San Pedro», se registra únicamente «San Pedro» como LOC. En ese contexto no se identifica al colectivo como actor.

**Anidación y contexto:** En los dos ejemplos anteriores, el fragmento LOC es «San Pedro». La anotación adicional de CHAR requiere que el texto identifique al colectivo como actor. No añadas CHAR únicamente porque un evento se ubique en una comunidad.

## 6. Reglas generales de anotación

- **Literalidad y extensión:** extrae una palabra o el fragmento continuo
  mínimo completo que identifica el componente, dentro de una sola oración.
  Conserva idioma, mayúsculas, tildes, plural y forma verbal. No traduzcas,
  lematices, completes palabras omitidas ni reformules la oración.
- **Delimitación:** incluye nombres propios, números, descriptores y
  modificadores necesarios para identificar el componente y su función.
  Deja las explicaciones, circunstancias y atribuciones en el contexto;
  aplica las reglas específicas de las fichas, como actitud con su objeto
  y habilidad con su tarea. No extraigas una oración explicativa completa
  si una expresión más corta identifica lo mencionado.
  En PRAC conserva la actividad con su objeto necesario y deja actores,
  ubicaciones y soportes separables en contexto; un producto o residuo no
  constituye por sí solo una práctica. En KNOW extrae el contenido del saber
  sin incorporar una explicación completa.
- **Artículos y puntuación:** omite artículos externos que introducen la
  denominación, preposiciones introductorias y signos externos. Conserva
  artículos, preposiciones y puntuación integrantes del nombre o expresión.
  En CHAR, conserva el descriptor que identifica al actor junto a su nombre,
  como «cooperativa La Esperanza» (sección 6.3).
- **Siglas y abreviaturas:** extrae la forma explícita cuando su contexto
  respalde una categoría. Si aparecen nombre completo y sigla, registra
  ambos por separado. No inventes expansiones ni resuelvas identidades.
- **Enumeraciones:** registra cada denominación explícita por separado en
  cualquier categoría. Ante palabras omitidas o modificadores compartidos,
  conserva solo fragmentos continuos identificables en contexto. No copies
  un modificador a otra posición ni reconstruyas denominaciones completas.
- **Referencias:** no anotes pronombres ni referencias vacías como «esto»
  o «allí», ni los sustituyas por su antecedente. Las denominaciones genéricas
  sí se admiten si cumplen los criterios de su categoría.
- **Una categoría por aparición:** elige la función mejor respaldada por
  el contexto, usando las fronteras de las fichas y la sección 7. La misma
  palabra puede recibir categorías distintas en apariciones diferentes.
- **Anidación y solapamientos:** permite únicamente LOC contenido
  estrictamente dentro de CHAR con evidencia para ambos (sección 6.1).
  No generes otros fragmentos anidados, solapamientos parciales ni fragmentos
  discontinuos. Conserva la expresión mínima completa del componente
  principal; sus palabras internas no constituyen anotaciones adicionales.
  Por ejemplo, en ATT «compromiso con la conservación del bosque» no añadas
  una PRAC interna «conservación del bosque».
- **Negación y temporalidad:** una mención explícita puede conservarse
  aunque aparezca negada, ausente, propuesta, hipotética, futura u obligatoria,
  si cumple los criterios de categoría. La anotación no afirma existencia,
  posesión o ejecución. Conserva esa condición en contexto; incluye la
  negación en el fragmento cuando forma parte de una prescripción RUL.
  No añadas campos de polaridad o tiempo ni deduzcas KNOW, ATT o SKILL de
  una actividad o intención.
- **Repeticiones:** registra cada aparición con su ubicación y contexto,
  también dentro de una misma oración (sección 6.2).
- **Etapas posteriores:** conserva texto y categoría de cada mención.
  La agrupación de variantes, resolución de identidades, discrepancias entre
  nodos y relaciones corresponden a fuzzy matching y construcción de red;
  quedan fuera de las instrucciones de NER.

### 6.1. Anotación de LOC dentro de CHAR

Se permite anotar un fragmento que identifica un lugar (LOC) dentro de
otro que identifica un actor (CHAR), cuando el texto y su contexto
respaldan ambas identificaciones. Cada anotación conserva su propio
fragmento y categoría.

**Ejemplo:** «La comunidad de San Pedro decidió participar».

| Fragmento | Categoría | Referente |
|---|---|---|
| comunidad de San Pedro | CHAR | El colectivo que decidió participar; se omite el artículo inicial. |
| San Pedro | LOC | El lugar identificado en la denominación del colectivo. |

**Límite contextual:** En «El taller se realizó en la comunidad
de San Pedro», se registra únicamente «San Pedro» como LOC. La expresión
solo ubica el taller; no basta para añadir CHAR. La presencia de un nombre
de lugar dentro de la expresión no activa automáticamente dos anotaciones.

La anidación permite los dos fragmentos del ejemplo
«La comunidad de San Pedro decidió participar», uno contenido en el otro.
No permite asignar dos etiquetas al mismo intervalo ni generalizar la
anidación a otras combinaciones. Las consecuencias para la canonicalización
y el conteo de coocurrencia corresponden a sus etapas posteriores.

### 6.2. Registro de menciones repetidas

Se registra cada aparición de una mención como una anotación independiente,
con su ubicación en el documento y su contexto. La repetición del mismo
texto no elimina las apariciones posteriores.

**Ejemplo:** Si «productoras de cacao» aparece en tres oraciones,
se conservan tres menciones, cada una vinculada a su ubicación y contexto.
Posteriormente podrán vincularse al mismo nodo canónico sin perder las
tres evidencias.

El código calcula posiciones y contexto conforme a la sección 8. El modelo
registra las apariciones en orden textual para que la búsqueda local asigne
posiciones sucesivas. El contrato de cuatro campos no distingue qué aparición
se quiso seleccionar si un texto idéntico se repite en la misma oración y
solo se anota alguna de ellas; esos casos requieren revisión del piloto.
Las reglas de conteo o ponderación de coocurrencia se definen en la etapa de red.

### 6.3. Extracción de menciones CHAR

**Criterio de evidencia y exclusión — pronombres:** Para CHAR
se extraen únicamente las expresiones que nombran al actor, ya sea por
nombre propio, cargo, ocupación o denominación del colectivo. Los pronombres
que remiten a un actor no se anotan como CHAR, aunque su referente sea
claro en el contexto. Esto mantiene la inclusión de denominaciones
genéricas; no exige un nombre propio.

**Ejemplo:** En «Los agricultores participan en el monitoreo.
Ellos registran los cambios del bosque», se anota «agricultores»
como CHAR y no se anota «Ellos» como CHAR. No se sustituye el pronombre
por una nueva mención de «agricultores» en la segunda oración.

**Límite del fragmento — artículo inicial:** Se omite el artículo
que introduce la denominación del actor. En «Las productoras de cacao
participaron en el taller», se anota «productoras de cacao» como CHAR,
dejando fuera «Las» y conservando «de cacao».
Los artículos integrantes de un nombre propio se conservan conforme al
criterio siguiente; la delimitación general se aplica según el inicio de la sección 6.

**Nombre propio íntegro — criterio:** Se conserva completo el
nombre propio del actor, incluidos sus artículos integrantes. «La Esperanza»
es un nombre propio y se mantiene íntegro: no se elimina «La» ni se
extrae como una anotación separada. La omisión del artículo que introduce
una denominación no autoriza a recortar un artículo integrante del nombre.

**Fragmento:** En «La cooperativa La Esperanza participó en el
taller», se extrae «cooperativa La Esperanza» como CHAR. Se incluye
«cooperativa» y se conserva íntegro el nombre «La Esperanza». Incluye los
descriptores que identifican al actor; deja las explicaciones adicionales en contexto.

**Conservación del fragmento:** Una vez delimitada la mención,
se conserva el texto tal como aparece. En el ejemplo de las productoras
se extrae «productoras de cacao», manteniendo el plural. La normalización queda
para una etapa posterior y no reemplaza el fragmento original extraído.

**Nombre completo y sigla — extracción:** Cuando el nombre
completo de un actor y su sigla aparecen explícitamente, se extraen como
dos registros CHAR independientes, cada uno con su fragmento literal,
ubicación y contexto.

**Ejemplo:** En «La Asociación de Productores de Cacao (APC)
participó en el taller», se extraen por separado:

- «Asociación de Productores de Cacao» → CHAR.
- «APC» → CHAR.

**Canonicalización para el ejemplo:** Las dos menciones se
vinculan posteriormente al mismo nodo canónico porque el texto presenta
«APC» como sigla de «Asociación de Productores de Cacao». Se conservan
ambos registros originales, con su ubicación y contexto.

La coincidencia de siglas por sí sola no establece una identidad entre
actores. NER clasifica la forma observada con su contexto y ambigüedad;
la resolución de identidad corresponde a fuzzy matching.

**Enumeraciones de actores — extracción:** Cuando el texto
enumera actores mediante denominaciones explícitas, se extrae cada una
como una mención CHAR independiente. Se conservan sus fragmentos
literales y se omiten los artículos iniciales y la conjunción que los une.

**Ejemplo:** En «Las productoras de cacao y los recolectores de
castaña participaron en el taller», se extraen por separado:

- «productoras de cacao» → CHAR.
- «recolectores de castaña» → CHAR.

En enumeraciones con palabras omitidas o modificadores compartidos, conserva
solo fragmentos continuos identificables en contexto, conforme a la regla general.

## 7. Ambigüedad y casos no resolubles

Hay ambigüedad cuando el contexto permite más de una interpretación de la
categoría, referente o límites. Elige la categoría mejor respaldada por la
función contextual; omite la expresión si ninguna tiene evidencia suficiente.
No uses una categoría genérica de reserva ni etiquetes por conocimiento externo.

| `ambiguity` | Criterio |
|---|---|
| `low` | Denominación, función y límites claros en el contexto recibido. |
| `medium` | Existe otra lectura plausible, pero el contexto favorece la elegida. |
| `high` | Persiste una duda relevante aunque haya evidencia para la categoría elegida. |

Son niveles de necesidad de revisión, no probabilidades calibradas. `high`
no compensa la ausencia de evidencia. NER devuelve solo la categoría elegida
y el nivel; las alternativas y motivos se registran aparte durante la revisión
del piloto, sin añadir campos al contrato. Revisa todas las menciones `high`
y las fronteras `medium` antes de aceptar la extracción del documento.

## 8. Formato de entrada y salida

El servicio segmenta el texto limpio y envía bloques de hasta tres párrafos,
con un umbral objetivo de 12.000 caracteres. Un párrafo individual mayor
que ese umbral se conserva completo en la implementación actual.

La entrada contiene `document_id`, `document_title`, `section_title` y
`sentences`, una lista de objetos con `sentence_id` y `text`. Los títulos
pueden estar vacíos; orientan la interpretación sin crear menciones ausentes
de las oraciones. Los identificadores de oración se calculan localmente a
partir de su posición absoluta y deben copiarse sin modificaciones.

Ejemplo de entrada:

```json
{
  "document_id": "ejemplo",
  "document_title": "",
  "section_title": "",
  "sentences": [{"sentence_id": "s-000000000", "text": "La cooperativa La Esperanza participa."}]
}
```

Responde mediante `submit_entity_annotations`, con `document_id` y
`annotations`. Cada anotación contiene exactamente cuatro campos obligatorios:

| Campo | Contenido |
|---|---|
| `label` | Uno de los diez códigos exactos de la sección 4. |
| `text` | Fragmento continuo literal de una oración de entrada. |
| `sentence_id` | Identificador de esa oración. |
| `ambiguity` | `low`, `medium` o `high`, según la sección 7. |

```json
{
  "document_id": "ejemplo",
  "annotations": [{"label": "CHAR", "text": "cooperativa La Esperanza", "sentence_id": "s-000000000", "ambiguity": "low"}]
}
```

Si no hay menciones válidas, devuelve `annotations: []`. No añadas
explicaciones, alternativas, posiciones, atributos canónicos ni relaciones.

El código renombra `label` a `category`, localiza cada aparición literal y
añade `start`, `end` (exclusivo) y `context` (oración de origen), manteniendo
`sentence_id`, `text` y `ambiguity`. Las posiciones son índices de caracteres
de Python sobre el texto limpio: `texto[start:end] == text`. El JSON de NER
guarda `document_id` y `entities`; todavía no crea nodos canónicos.

El servicio verifica los campos, el identificador de documento, etiquetas,
oraciones, literalidad, ambigüedad y solapamientos. Si una respuesta pierde
anotaciones por estos errores, solicita hasta dos correcciones del bloque al
modelo, indicando los fragmentos en conflicto. Si persisten, falla sin guardar
un resultado parcial; también falla ante truncamiento o falta de la herramienta
requerida. El parser usado aisladamente conserva su modo tolerante para
compatibilidad, pero NER exige una respuesta válida antes de aceptar el bloque.
Una salida estructuralmente válida todavía requiere revisión semántica.

## 9. Ejemplos completos de aplicación

Las diez demostraciones de `data/ner/few_shot_examples.json` ilustran las diez
categorías; su procedencia es ilustrativa y no son un conjunto de referencia
anotado sobre el corpus. Las fichas de la sección 5 explican las fronteras.

Los siguientes casos acotados muestran todas las anotaciones esperadas;
en cada caso se copia el `sentence_id` de entrada:

| Texto | Anotaciones (`label`: `text`, `ambiguity`) |
|---|---|
| La comunidad de San Pedro decidió participar. | CHAR: «comunidad de San Pedro», `low`; LOC: «San Pedro», `low`. |
| El taller se realizó en la comunidad de San Pedro. | LOC: «San Pedro», `low`. |
| La municipalidad no participó. | CHAR: «municipalidad», `low`; la negación permanece en contexto. |
| La Asociación de Productores de Cacao (APC) participó. | CHAR: «Asociación de Productores de Cacao», `low`; CHAR: «APC», `low`. |
| minería y minería. | Dos anotaciones PRAC: «minería», `low`, en posiciones distintas. |
| Gracias por su atención. | `annotations: []`. |

En una oración factual como «La floración ocurre en agosto», no se añade
KNOW sin identificación de un saber o atribución de conocimiento. Una sigla
sin función reconocible tampoco recibe automáticamente CHAR. Las dudas
reales del piloto se revisan con la sección 7; no se inventa un caso de alta
ambigüedad para sustituir esa revisión.

## 10. Validación y mantenimiento

1. Selecciona un documento real de extensión manejable y conserva el texto
   limpio completo, su identificador y huella SHA-256. Ejecuta solo NER con
   las versiones vigentes; conserva resultados y advertencias para revisión.
2. Comprueba etiquetas, literalidad, posiciones, oraciones, repeticiones y
   anidación. Contrasta las anotaciones finales recibidas con las conservadas:
   deben coincidir. Conserva también las respuestas anteriores corregidas y
   el número de reintentos. Revisa los bloques vacíos.
3. Lee todas las oraciones del piloto, incluidas las que no tienen menciones,
   para detectar omisiones, asignaciones incorrectas y fragmentos demasiado
   amplios. Revisa especialmente KNOW/ATT/SKILL/PRAC, infraestructuras/LOC,
   reglas propuestas, siglas y las menciones `medium` o `high`.
4. Registra correcciones y su fundamento; la revisión humana adjudica el
   conjunto de referencia. Separa estos datos de desarrollo de una evaluación
   posterior con documentos distintos y mantén las demostraciones identificadas
   como ilustrativas. Un solo documento no valida categorías ausentes ni
   demuestra calidad para todos los idiomas.
5. Antes de iniciar el corpus, exige cero errores estructurales pendientes y
   revisión de todos los desacuerdos detectados en el piloto. No declares una
   precisión o cobertura medidas sin referencia adjudicada. Cuando exista,
   calcula precisión, cobertura y F1 por coincidencia exacta de posición y
   categoría, junto con errores por categoría; los umbrales de evaluación
   ampliada se fijan antes de medir sobre documentos reservados.
6. Si se cambia una regla a partir del piloto, actualiza codebook, definiciones,
   prompt y ejemplos afectados, ejecuta las regresiones y repite únicamente
   la validación afectada. Contrasta las anotaciones entre versiones antes
   de procesar lotes. La repetibilidad del LLM se evalúa sobre texto fijo;
   las pruebas con proveedor simulado verifican el código, no su estabilidad.

Registra versión del codebook, commit, modelo configurado y huellas del texto,
definiciones, prompts y demostraciones en el artefacto del piloto. Al cargar
cambios en la API, inicia o reinicia su proceso: los prompts se mantienen
en caché en memoria y editar únicamente sus archivos no garantiza recarga.
Fuzzy matching y relaciones se validan después mediante sus endpoints propios.

## Anexo A. Instrucciones para el modelo de lenguaje

Las instrucciones operativas se mantienen en los archivos usados por el servicio:

| Fuente | Reglas que incorpora |
|---|---|
| `src/categories.py` | Diez códigos y síntesis de las fichas de la sección 5. |
| `data/prompts/ner_prompt.md` | Dominio, evidencia, contexto, delimitación, anidación, repeticiones, ambigüedad y salida de las secciones 1–8. |
| `data/prompts/ner_user_prompt.md` | Demostraciones y oraciones objetivo; extracción limitada a `target_input`. |
| `data/ner/few_shot_examples.json` | Diez demostraciones ilustrativas de categorías. |
| `src/services/ner.py` | Esquema de cuatro campos, segmentación, localización literal y controles del contrato. |

El servicio incorpora las definiciones en `$category_definitions` y ensambla
el prompt de usuario con ejemplos y entrada. No envía este codebook completo
ni instrucciones de canonicalización o construcción de relaciones al modelo.
