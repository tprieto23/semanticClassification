# Codebook para la extracción y etiquetación de entidades semánticas

**Estado:** En construcción, sección por sección.

**Versión:** Borrador 0.1 — 6 de octubre de 2026.

Los campos marcados como `[Pendiente]` requieren definición. El marco temático
y el enfoque han sido confirmados. Los diez códigos de categoría han sido
definidos por la usuaria y sus definiciones operativas han sido acordadas.
El conjunto de diez categorías es una decisión final; su número y códigos
no están pendientes de elección.
Las fichas detalladas y las reglas generales de anotación siguen en construcción.

## 1. Propósito de la anotación

### 1.1. Objetivo inmediato

Establecer una especificación operativa para la minería de texto, extracción
y clasificación semántica que formará parte del procesamiento de la API.
Esta especificación debe permitir identificar fragmentos de texto, palabras
o términos presentes en los documentos de un corpus y asignarles las etiquetas
correspondientes a un sistema de diez categorías.

### 1.2. Resultado esperado

Obtener menciones clasificadas, vinculadas con los fragmentos y documentos
de los que proceden, que permitan construir nodos con atributos. La categoría
asignada es uno de esos atributos: por ejemplo, una mención de «Wyss» que
identifique al actor recibe la etiqueta `CHAR`.

Los demás atributos y su formato se definirán en las secciones correspondientes.

### 1.3. Uso posterior y objetivo final

Las menciones extraídas y clasificadas se someterán a un proceso de resolución
de entidades mediante fuzzy matching, con criterios por definir, para agrupar
las variantes que correspondan a una misma entidad o concepto y representarlas
mediante un nodo canónico. Ese nodo deberá registrar su categoría y los demás
atributos acordados, conservando la vinculación con sus menciones de origen.

El objetivo final es construir una red semántica cuyos nodos representen las
entidades o conceptos identificados y cuyas relaciones se deriven de la
coocurrencia o coaparición de sus menciones dentro del corpus.

La secuencia prevista es:

1. Extraer menciones y asignarles categorías.
2. Resolver variantes mediante fuzzy matching y consolidar nodos con atributos.
3. Construir relaciones a partir de la coaparición de las menciones de esos nodos.

La unidad o ventana que define la coaparición, sus reglas de conteo y el
tratamiento de posibles discrepancias de categoría durante la consolidación
quedan pendientes de definición. Estos acuerdos no se presuponen a partir de
la mera pertenencia de dos entidades al mismo corpus.

### 1.4. Función operativa dentro de la API

El codebook será la referencia para las instrucciones del modelo de lenguaje,
los criterios de clasificación y el contrato de las anotaciones generadas
durante el procesamiento. Sus definiciones y lineamientos deberán traducirse
en instrucciones aplicables, salidas estructuradas y controles de validación.

También establecerá los requisitos que la extracción debe satisfacer para
alimentar la resolución mediante fuzzy matching, el registro de atributos de
los nodos y la construcción de relaciones por coaparición. La distribución de
responsabilidades entre el modelo de lenguaje y los servicios de la API se
precisará al definir cada etapa.

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
de las categorías de anotación acordadas.

- Función del enfoque: orientación temática.
- Documentos y secciones que se procesan: [Pendiente].
- Idiomas admitidos: [Pendiente].
- Contenido incluido: menciones pertinentes de los componentes ecológicos,
  sociales, económicos, culturales e institucionales del sistema territorial,
  incluidas prácticas, actores, lugares, reglas, infraestructuras, conocimientos,
  actitudes y capacidades, según las categorías que se acuerden. Mercados,
  migración y otros procesos pueden incluirse cuando cumplan esos criterios,
  aunque la oración no mencione expresamente la deforestación.
- Contenido excluido: [Pendiente].

### 2.4. Referencia para el marco conceptual y los lineamientos

El informe «Análisis de Sensibilidad Participativo en Tambopata», proporcionado
para fortalecer y enriquecer el marco conceptual y los lineamientos del
codebook, presenta una lectura participativa del sistema socioecológico de
Tambopata. Describe dieciséis factores y sus
interacciones, organizados en siete dominios temáticos: economía, uso del suelo,
naturaleza, infraestructura, población, bienestar e interés público.

Su función en esta elaboración es fundamentar la comprensión del dominio,
revisar la cobertura conceptual de las categorías y orientar las distinciones
que deberán convertirse en reglas operativas. Los acuerdos sobre el corpus
que procesará la API se definirán por separado.

Su contenido aporta referencias sobre prácticas productivas y extractivas,
conservación y restauración, infraestructura, mercados, migración, economía
criminal, cambio climático, participación, saberes e identidad, gobernanza,
tenencia y capacidades colectivas. También identifica actores y lugares
concretos y registra actividades presentes, actividades ausentes o propuestas
y diferentes perspectivas de los participantes.

Tambopata constituye aquí un caso de referencia dentro del marco amazónico
confirmado. Los dieciséis factores y los siete dominios del informe son
niveles de organización de su análisis territorial; la lista y las definiciones
de las diez categorías de anotación del codebook se acordarán por separado.

El informe distingue entre calificaciones de los participantes, discusiones
grupales y elaboraciones posteriores del equipo. Sus relaciones de influencia
representan juicios participativos. La red prevista en este codebook se
construirá a partir de coapariciones; la dirección, intensidad o valoración
de las influencias descritas en el informe no se trasladan automáticamente
a esas relaciones.

### 2.5. Lineamientos conceptuales para orientar la extracción

#### 2.5.1. Cobertura del sistema socioecológico

**Estado:** Acordado.

**Fundamento conceptual:** El territorio se comprende como un sistema
socioecológico en el que los componentes ecológicos, sociales, económicos,
culturales e institucionales se relacionan. Su comprensión requiere reconocer
tanto las dinámicas de conservación y regeneración como las de extracción,
degradación y conflicto, junto con las condiciones que las habilitan o limitan.

**Lineamiento operativo:** La extracción debe identificar las
menciones pertinentes de esos componentes cuando estén sustentadas por el
texto y cumplan los criterios de una categoría acordada. La inclusión se
determina por su pertinencia para el dominio y su función contextual. Tanto
las menciones presentadas como favorables como las presentadas como
desfavorables o ambivalentes pueden ser objeto de anotación.

**Implicación para las categorías:** El conjunto de las diez categorías deberá
revisarse para comprobar qué componentes del dominio puede representar y
cuáles quedan fuera. Esta revisión de cobertura no presupone una equivalencia
entre las categorías de anotación y los factores o dominios del informe.

**Ejemplo conceptual:** En un pasaje sobre carreteras, minería, comunidades
y conservación, cada expresión se evalúa según su contexto y los criterios
de las categorías. La selección no se limita a las expresiones asociadas
con resultados deseables.

#### 2.5.2. Clasificación según la función contextual de la mención

**Estado:** Acordado.

**Fundamento conceptual:** Un ámbito del sistema territorial puede reunir
actores, reglas, prácticas, soportes, conocimientos y otros componentes.
El informe muestra, por ejemplo, que los marcos de gobernanza y la seguridad
jurídica incluyen organizaciones, instrumentos institucionales y procesos de
gestión. El tema de un pasaje puede contener menciones de categorías distintas.

**Lineamiento operativo:** Cada mención se clasificará según el
componente que identifica y la función que el texto le atribuye en su contexto,
aplicando las definiciones y criterios de las categorías acordadas. El nombre
de un factor, el título de una sección y las palabras indicadoras podrán
orientar la interpretación; la asignación deberá estar sustentada por la
mención y su contexto.

**Ejemplos orientativos:** Con las categorías actualmente propuestas,
«SERNANP» presentado como organización participante corresponde a un actor
(`CHAR`); un «plan maestro» presentado como instrumento de gestión corresponde
a una regla o instrumento (`RUL`); la «titulación de comunidades nativas»
presentada como proceso corresponde a una práctica (`PRAC`). Las definiciones
operativas y los límites exactos de estos fragmentos se desarrollarán después.

**Caso pendiente:** Cuando la función no pueda determinarse con el contexto
permitido, se aplicará la política de ambigüedad que se acuerde en la sección 7.

## 3. Unidades de anotación y contexto

- Qué se entiende por entidad o mención en esta tarea: [Pendiente].
- Unidad que recibe una etiqueta: [Pendiente].
- Contexto permitido para interpretar una mención: [Pendiente].
- Evidencia textual requerida e inferencias permitidas: [Pendiente].
- Tratamiento de menciones repetidas: se registra cada aparición como
  una mención independiente, con su ubicación y contexto (sección 6.2).
  La vinculación posterior al mismo nodo canónico conserva esas evidencias.
- Distinción entre mención literal y entidad canónica: la extracción
  conserva el texto literal del fragmento seleccionado; la normalización
  se realiza posteriormente. Criterios de normalización: [Pendiente].
- Unidad o ventana de coaparición para las relaciones posteriores: [Pendiente].

## 4. Sistema de etiquetas

- Número de categorías: diez, por decisión final de la usuaria.
- Conjunto de etiquetas: fijado en los diez códigos de la tabla siguiente.
- Una o varias etiquetas para el mismo fragmento: [Pendiente]. Se permite
  anotar un fragmento LOC contenido dentro de otro CHAR conforme al
  acuerdo de la sección 6; son dos fragmentos distintos.
- Tratamiento de expresiones que no pertenecen a ninguna categoría: [Pendiente].

Las diez categorías y sus códigos son los proporcionados por la usuaria.
Los códigos se conservarán con esta grafía en las anotaciones y los atributos
de los nodos. Las definiciones y fronteras se revisarán categoría por categoría.

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

El trabajo actual se centra en definir las características que debe
identificar una mención para clasificarse en cada categoría. Se revisan
criterios generales aplicables al corpus, utilizando ejemplos solo cuando
ayuden a aclarar una frontera entre categorías.

Cada ficha desarrolla:

- Definición operativa y características esenciales.
- Criterios de inclusión y exclusión.
- Evidencia textual necesaria para asignar la etiqueta.
- Distinción respecto de categorías cercanas.

Las definiciones operativas de las diez categorías ya fueron acordadas.
Cada ficha distingue los criterios acordados de las propuestas y pendientes.
Los acuerdos de delimitación, registro de menciones y normalización se
conservan en las secciones correspondientes; su resolución exhaustiva no
es el foco de la revisión actual de categorías.

### 5.1. CHAR — Actores

**Estado:** Síntesis de los criterios de clasificación ya acordados.
Los acuerdos de extracción se conservan en la sección 6. La revisión
operativa y la validación del codebook siguen pendientes.

**Definición:** Actor individual o colectivo que el texto identifica como
participante del sistema territorial, con agencia, responsabilidad,
representación, derechos, intereses o afectación en relación con sus procesos
socioecológicos. Un actor individual es una persona; un actor colectivo puede
ser un grupo humano, una comunidad, un pueblo u organización.

**Características que debe identificar la mención:**

1. Una persona, un grupo humano, una comunidad, un pueblo u organización.
2. Una denominación explícita del actor, por nombre propio, cargo,
   ocupación o expresión genérica.
3. Un papel respaldado por el contexto en el sistema territorial:
   agencia, responsabilidad, representación, derechos, intereses o
   afectación respecto de sus procesos socioecológicos.

**Criterios de inclusión acordados:**

- Se admiten actores individuales y colectivos, nombrados o genéricos.
- Se incluyen los actores afectados aunque no ejecuten una acción.
- Se incluye al actor cuya participación en una actividad está negada;
  se conserva esa negación en el contexto, sin afirmar participación.

**Criterio de exclusión acordado:** Una expresión que solo ubica un
proceso o evento, sin identificar al colectivo como actor en contexto,
no recibe CHAR. En «El taller se realizó en la comunidad de San Pedro»,
se registra únicamente «San Pedro» como LOC.

**Evidencia necesaria:** La denominación y su contexto deben permitir
identificar al actor y su papel territorial. No se requiere un nombre
propio ni la ejecución de una acción. La ventana de contexto permitida
se definirá en la sección 3.

**Fronteras acordadas:**

- LOC identifica el lugar; CHAR, la persona o colectivo. Se permite
  LOC dentro de CHAR cuando ambas identificaciones están respaldadas
  por el contexto, conforme a la sección 6.1.
- RUL identifica la regla o instrumento; CHAR, al actor que lo establece
  o aplica. El criterio contextual para planes está en la sección 5.9.
- PRAC identifica la actividad; CHAR, al actor. «Monitoreo comunitario»
  identifica una práctica en el ejemplo acordado de la sección 5.5.

**Ejemplos acordados:**

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

Los criterios adicionales y las demás fronteras siguen sujetos a revisión.
Los ejemplos ilustran las características de clasificación; las reglas
sobre pronombres, artículos, nombres propios, siglas y enumeraciones
están reunidas en la sección 6.3.

### 5.2. KNOW — Conocimiento

**Estado:** Definición, criterio de inclusión, portador y distinción frente
a SKILL y PRAC acordados; el resto de la ficha continúa en revisión.

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

**Criterio de inclusión acordado:** El texto debe identificar un saber
o contenido de conocimiento. Puede hacerlo mediante una denominación
explícita, como «saberes tradicionales sobre el manejo del bosque», o
mediante una expresión que atribuya conocimiento, como «los productores
conocen los ciclos de floración de la castaña».

**Portador del conocimiento — acordado:** Se admiten menciones explícitas
de saberes aunque el texto no identifique quién los posee. Esto no autoriza
a atribuirles un portador que el texto no señale.

**Evidencia y exclusiones propuestas:** La presencia de una práctica,
una habilidad o un término técnico por sí sola no demuestra que el texto
esté describiendo conocimiento. La realización de una actividad no
permite añadir automáticamente una anotación de KNOW. Una afirmación
sobre el territorio debe evaluarse en contexto para determinar si presenta
un contenido de conocimiento conforme a esta definición.

**Distinción acordada:** KNOW identifica el saber o contenido conocido;
SKILL identifica la competencia para realizar una tarea; PRAC identifica
la actividad.

**Frontera propuesta con ATT:** Las valoraciones, identidades y compromisos
se evalúan según ATT. Cada categoría requiere su propia evidencia.

**Ejemplos construidos para discutir la frontera:**

| Texto | Interpretación orientativa |
|---|---|
| Las productoras conocen los ciclos de floración de la castaña. | KNOW: expresa conocimiento ecológico. |
| Las productoras saben usar equipos de monitoreo. | SKILL: expresa competencia operativa. |
| Las productoras monitorean la floración de la castaña. | PRAC: expresa una actividad. |

[Pendiente: revisar las exclusiones y precisar las fronteras con ATT,
el tratamiento de afirmaciones generales, los límites de los fragmentos
y ejemplos completos de anotación].

### 5.3. ATT — Actitudes y valores

**Estado:** Definición y distinción frente a KNOW y PRAC acordadas;
el resto de la ficha está pendiente.

**Definición:** Valores, identidades, percepciones y compromisos que el
texto atribuye a actores individuales o colectivos respecto del territorio,
sus ecosistemas o su gestión.

**Referencias proporcionadas:** Valores, identidades, percepciones y compromisos.

**Ejemplos orientativos:** Sentido de pertenencia, valoración del bosque
y compromiso con su conservación.

**Distinción acordada:** Valorar o percibir corresponde a ATT; conocer,
a KNOW; actuar, a PRAC. No se infiere una actitud únicamente porque
alguien realice una actividad.

[Pendiente: completar criterios, evidencia, límites y ejemplos].

### 5.4. SKILL — Habilidades

**Estado:** Definición y distinción frente a KNOW y PRAC acordadas;
el resto de la ficha está pendiente.

**Definición:** Destrezas o competencias que el texto atribuye a actores
individuales o colectivos para realizar tareas técnicas, de gestión o de
monitoreo en el territorio.

**Referencias proporcionadas:** Habilidades técnicas, de gestión y de monitoreo.

**Ejemplos orientativos:** Capacidad para manejar equipos, gestionar
proyectos o aplicar técnicas de restauración.

**Distinción acordada:** Conocer una técnica corresponde a KNOW; saber
aplicarla, a SKILL; aplicarla, a PRAC. Realizar una actividad no basta,
por sí solo, para anotar una habilidad.

[Pendiente: completar criterios, evidencia, límites y ejemplos].

### 5.5. PRAC — Prácticas

**Estado:** Definición, amplitud y distinción frente a SKILL y RUL
acordadas, así como la anotación de «monitoreo comunitario» como PRAC
en el ejemplo revisado; el resto de la ficha está pendiente.

**Definición:** Actividades, rutinas o procesos que el texto identifica
para producir, aprovechar, conservar, restaurar, monitorear, comercializar
o gestionar componentes del territorio.

**Referencias proporcionadas:** Agroforestería, monitoreo, comercialización,
restauración y gobernanza como actividad o proceso.

**Ejemplos orientativos:** Agroforestería, extracción minera, monitoreo
comunitario, comercialización y coordinación entre instituciones.

**Amplitud acordada:** Las prácticas pueden ser sostenibles, degradantes
o ambivalentes.

**Distinción acordada:** Saber realizar una actividad corresponde a SKILL;
la actividad, a PRAC; las normas que la regulan, a RUL.

**Ejemplo de anotación acordado:** En «Se realizan actividades de
monitoreo comunitario», el fragmento «monitoreo comunitario» se anota
como PRAC porque identifica una actividad. Este acuerdo fija el fragmento
y la categoría para este ejemplo; no resuelve el tratamiento general de
adjetivos como «comunitario» para la extracción de actores.

[Pendiente: completar criterios, evidencia, límites, tratamiento de
actividades existentes o propuestas y ejemplos].

### 5.6. physical_INFRA — Infraestructura física

**Estado:** Definición, ejemplos y distinción frente a PRAC acordados;
delimitación funcional frente a soft_INFRA acordada. El resto de la ficha
está pendiente.

**Definición:** Elementos materiales construidos o instalados que permiten
o condicionan el acceso, la movilidad, el suministro de energía o la
conectividad tecnológica en el territorio.

**Ejemplos acordados:** Carreteras, puentes, puertos, redes eléctricas y
antenas de telecomunicaciones.

**Distinción acordada:** La carretera corresponde a physical_INFRA;
su construcción o mantenimiento, a PRAC. La clasificación depende de la
función descrita, no solo de que sea un objeto físico.

**Frontera acordada con soft_INFRA:** Se distingue por la función descrita:
physical_INFRA corresponde al acceso, movilidad, energía o conectividad
tecnológica; soft_INFRA, a los soportes organizados definidos en su ficha.
La presencia de componentes materiales no determina por sí sola la etiqueta.

[Pendiente: completar criterios, evidencia, límites y ejemplos de frontera,
incluidos casos de equipamiento de monitoreo].

### 5.7. soft_INFRA — Infraestructura de soporte

**Estado:** Definición, ejemplos y delimitación funcional frente a PRAC,
physical_INFRA y eco_INFRA acordados; el resto de la ficha está pendiente.

**Definición:** Sistemas, instalaciones y recursos organizados que
sostienen la producción, el aprendizaje, el monitoreo o la gestión de
información en el territorio.

**Ejemplos acordados:** Viveros, bancos de semillas, sistemas de monitoreo
y plataformas digitales.

**Criterio funcional acordado:** Estos soportes pueden tener componentes
materiales; importa su función de soporte, no solo su materialidad.

**Distinción acordada frente a PRAC:** El sistema de monitoreo corresponde
a soft_INFRA; realizar el monitoreo, a PRAC.

**Delimitación acordada frente a eco_INFRA:** Bosque primario y corredores,
incluidos originalmente entre las referencias de soft_INFRA, se evalúan
como eco_INFRA cuando cumplen funciones ecológicas. La función descrita
en contexto determina la clasificación.

[Pendiente: completar criterios, evidencia, límites y ejemplos de frontera].

### 5.8. eco_INFRA — Infraestructura ecológica

**Estado:** Definición, ejemplos y distinción frente a LOC y PRAC
acordados; el resto de la ficha está pendiente.

**Definición:** Estructuras ecológicas naturales o restauradas que sostienen
funciones ecosistémicas, conectividad ecológica, resiliencia, biodiversidad
o regeneración del territorio.

**Ejemplos acordados:** Bosques primarios, corredores biológicos y humedales.

**Distinción acordada:** La estructura por su función ecológica corresponde
a eco_INFRA; el espacio por su ubicación o delimitación, a LOC;
conservarlo o restaurarlo, a PRAC.

**Frontera acordada con soft_INFRA:** Bosque primario y corredores se
evalúan como eco_INFRA cuando cumplen funciones ecológicas, conforme a
la delimitación de la sección 5.7.

[Pendiente: completar criterios, evidencia, límites y ejemplos de frontera,
incluidos casos específicos de infraestructura y lugares].

### 5.9. RUL — Reglas

**Estado:** Definición, ejemplos y distinción frente a CHAR y PRAC
acordados, así como el criterio de inclusión contextual de planes;
el resto de la ficha está pendiente.

**Definición:** Normas, instrumentos o acuerdos que establecen derechos,
obligaciones, permisos o criterios para orientar las decisiones, la
participación y las prácticas en el territorio.

**Ejemplos acordados:** Leyes, ordenanzas, políticas, acuerdos comunitarios,
estándares de certificación y mecanismos de participación.

**Distinción acordada:** La regla corresponde a RUL; el actor que la
establece o aplica, a CHAR; la actividad de aplicarla, a PRAC.

**Criterio de inclusión acordado — planes:** Incluir los planes en RUL
cuando el contexto los presente como instrumentos que establecen
condiciones, responsabilidades o criterios para las prácticas territoriales.
La denominación «plan» por sí sola no basta para asignar RUL; el texto y
su contexto deben respaldar esa función.

Este criterio clasifica la mención del plan como instrumento. Las
prescripciones que contiene y las actividades de elaborarlo o implementarlo
deben distinguirse de esa mención y evaluarse según sus categorías.

[Pendiente: completar criterios, formalidad de las reglas, evidencia,
límites y ejemplos].

### 5.10. LOC — Lugares

**Estado:** Definición, ejemplos y distinción frente a CHAR y eco_INFRA
acordados; el resto de la ficha está pendiente.

**Definición:** Espacios o unidades geográficas, territoriales,
administrativas o ecológicas que el texto identifica por su ubicación,
extensión o delimitación.

**Ejemplos acordados:** Territorios indígenas, comunidades como lugares,
reservas, cuencas, áreas protegidas y zonas de intervención.

**Distinción acordada:** La comunidad como colectivo corresponde a CHAR;
su territorio, a LOC. Un bosque como espacio geográfico corresponde a LOC;
como estructura que sostiene funciones ecológicas, a eco_INFRA.

**Anotación acordada dentro de CHAR:** En «La comunidad de San Pedro
decidió participar», «San Pedro» se anota como LOC dentro del fragmento
«comunidad de San Pedro», anotado como CHAR, sin el artículo inicial.
Véase la sección 6.

**Ejemplo de ubicación acordado:** En «El taller se realizó en la comunidad
de San Pedro», se registra únicamente «San Pedro» como LOC. En ese
contexto no se identifica al colectivo como actor.

[Pendiente: completar criterios, evidencia, límites y ejemplos].

## 6. Reglas generales de anotación

- Conservación del texto literal: acordada. Una vez seleccionado el
  fragmento según las reglas de delimitación, se conserva tal como aparece
  en el texto, incluido el plural. La normalización se realiza en una
  etapa posterior, sin reemplazar la mención original extraída.
- Artículo inicial que introduce una denominación CHAR: se omite
  (sección 6.3). Los artículos integrantes de un nombre propio se conservan
  y el nombre no se divide, como en «La Esperanza». Inclusión de descriptores
  antepuestos al nombre, otros modificadores, puntuación y delimitación
  en las demás categorías: [Pendiente].
- Nombre completo y sigla de un actor: se extraen como dos registros CHAR
  independientes cuando ambos aparecen explícitamente (sección 6.3).
  Otras abreviaturas y categorías: [Pendiente].
- Enumeraciones explícitas de actores: cada denominación se extrae como
  una mención CHAR independiente (sección 6.3). Palabras omitidas,
  modificadores compartidos y otras categorías: [Pendiente].
- Pronombres referidos a actores: no se anotan como CHAR, aunque el
  referente sea claro; se extraen las expresiones que nombran al actor
  (sección 6.3). Otras referencias y categorías: [Pendiente].
- Fragmentos anidados LOC dentro de CHAR: acuerdo detallado a continuación.
- Otros fragmentos anidados, solapamientos parciales y fragmentos
  discontinuos: [Pendiente].
- Negación de participación de un actor: no impide anotar CHAR; se
  conserva en el contexto y no se afirma participación (sección 5.1).
  Negación en otras categorías, hipótesis, intención, obligación y
  temporalidad: [Pendiente].
- Reglas para resolver fronteras entre categorías: [Pendiente].
- Relación con etapas posteriores de normalización y análisis: [Pendiente].
- Conservación de la categoría y resolución de discrepancias al consolidar nodos: [Pendiente].
- Menciones repetidas: se registra cada aparición con su ubicación y
  contexto, conforme al acuerdo de la sección 6.2.

### 6.1. Anotación de LOC dentro de CHAR

**Estado:** Acordado para la combinación LOC dentro de CHAR.

Se permite anotar un fragmento que identifica un lugar (LOC) dentro de
otro que identifica un actor (CHAR), cuando el texto y su contexto
respaldan ambas identificaciones. Cada anotación conserva su propio
fragmento y categoría.

**Ejemplo acordado:** «La comunidad de San Pedro decidió participar».

| Fragmento | Categoría | Referente |
|---|---|---|
| comunidad de San Pedro | CHAR | El colectivo que decidió participar; se omite el artículo inicial. |
| San Pedro | LOC | El lugar identificado en la denominación del colectivo. |

**Límite contextual acordado:** En «El taller se realizó en la comunidad
de San Pedro», se registra únicamente «San Pedro» como LOC. La expresión
solo ubica el taller; no basta para añadir CHAR. La presencia de un nombre
de lugar dentro de la expresión no activa automáticamente dos anotaciones.

El acuerdo de anidación permite los dos fragmentos del ejemplo
«La comunidad de San Pedro decidió participar», uno contenido en el otro.
La política de asignar varias etiquetas a un mismo fragmento y el
tratamiento de otras combinaciones anidadas siguen pendientes. Las
consecuencias para la canonicalización y el conteo de coocurrencia se
definirán en las etapas correspondientes.

### 6.2. Registro de menciones repetidas

**Estado:** Acordado.

Se registra cada aparición de una mención como una anotación independiente,
con su ubicación en el documento y su contexto. La repetición del mismo
texto no elimina las apariciones posteriores.

**Ejemplo acordado:** Si «productoras de cacao» aparece en tres oraciones,
se conservan tres menciones, cada una vinculada a su ubicación y contexto.
Posteriormente podrán vincularse al mismo nodo canónico sin perder las
tres evidencias.

El formato de los campos de localización y contexto se definirá en la
sección 8. Este registro no fija todavía la ventana ni las reglas de
conteo o ponderación de coocurrencia para construir la red.

### 6.3. Acuerdos de extracción de menciones CHAR

Estas reglas conservan los acuerdos de anotación alcanzados. La prioridad
actual es precisar las características de clasificación de las categorías;
los demás detalles de extracción se retomarán en su etapa correspondiente.

**Criterio de evidencia y exclusión acordado — pronombres:** Para CHAR
se extraen únicamente las expresiones que nombran al actor, ya sea por
nombre propio, cargo, ocupación o denominación del colectivo. Los pronombres
que remiten a un actor no se anotan como CHAR, aunque su referente sea
claro en el contexto. Esto mantiene la inclusión de denominaciones
genéricas; no exige un nombre propio.

**Ejemplo acordado:** En «Los agricultores participan en el monitoreo.
Ellos registran los cambios del bosque», se anota «agricultores»
como CHAR y no se anota «Ellos» como CHAR. No se sustituye el pronombre
por una nueva mención de «agricultores» en la segunda oración.

**Límite del fragmento acordado — artículo inicial:** Se omite el artículo
que introduce la denominación del actor. En «Las productoras de cacao
participaron en el taller», se anota «productoras de cacao» como CHAR,
dejando fuera «Las» y conservando «de cacao».
Los ejemplos anteriores de CHAR se ajustan a este criterio. Los artículos
que forman parte de un nombre propio se conservan, conforme al acuerdo
siguiente; las demás reglas de delimitación siguen pendientes.

**Nombre propio íntegro — criterio acordado:** Se conserva completo el
nombre propio del actor, incluidos sus artículos integrantes. «La Esperanza»
es un nombre propio y se mantiene íntegro: no se elimina «La» ni se
extrae como una anotación separada. La omisión del artículo que introduce
una denominación no autoriza a recortar un artículo integrante del nombre.

**Fragmento acordado:** En «La cooperativa La Esperanza participó en el
taller», se extrae «cooperativa La Esperanza» como CHAR. Se incluye
«cooperativa» y se conserva íntegro el nombre «La Esperanza». Este ejemplo
no resuelve por sí solo todos los casos de descriptores antepuestos.

**Conservación del fragmento acordada:** Una vez delimitada la mención,
se conserva el texto tal como aparece. En el ejemplo de las productoras
se extrae «productoras de cacao», manteniendo el plural. La normalización queda
para una etapa posterior y no reemplaza el fragmento original extraído.

**Nombre completo y sigla — extracción acordada:** Cuando el nombre
completo de un actor y su sigla aparecen explícitamente, se extraen como
dos registros CHAR independientes, cada uno con su fragmento literal,
ubicación y contexto.

**Ejemplo acordado:** En «La Asociación de Productores de Cacao (APC)
participó en el taller», se extraen por separado:

- «Asociación de Productores de Cacao» → CHAR.
- «APC» → CHAR.

**Canonicalización acordada para el ejemplo:** Las dos menciones se
vinculan posteriormente al mismo nodo canónico porque el texto presenta
«APC» como sigla de «Asociación de Productores de Cacao». Se conservan
ambos registros originales, con su ubicación y contexto.

La coincidencia de siglas por sí sola no establece una identidad entre
actores. Los criterios para resolver siglas ambiguas o sin correspondencia
explícita siguen pendientes.

**Enumeraciones de actores — extracción acordada:** Cuando el texto
enumera actores mediante denominaciones explícitas, se extrae cada una
como una mención CHAR independiente. Se conservan sus fragmentos
literales y se omiten los artículos iniciales y la conjunción que los une.

**Ejemplo acordado:** En «Las productoras de cacao y los recolectores de
castaña participaron en el taller», se extraen por separado:

- «productoras de cacao» → CHAR.
- «recolectores de castaña» → CHAR.

El tratamiento de enumeraciones con palabras omitidas o modificadores
compartidos sigue pendiente; no se reconstruyen fragmentos en este acuerdo.

## 7. Ambigüedad y casos no resolubles

- Qué se considera ambiguo: [Pendiente].
- Cuándo asignar una etiqueta, omitir o solicitar revisión: [Pendiente].
- Cómo registrar alternativas y motivos de revisión: [Pendiente].
- Niveles de ambigüedad o confianza, si corresponde: [Pendiente].

## 8. Formato de entrada y salida

- Estructura de los textos e identificadores de entrada: [Pendiente].
- Campos obligatorios y opcionales de cada anotación: [Pendiente].
- Localización de las menciones en el texto: [Pendiente].
- Respuesta cuando no hay menciones válidas: [Pendiente].
- Contrato estructurado de salida y ejemplo: [Pendiente].

## 9. Ejemplos completos de aplicación

- Casos claros de cada categoría: [Pendiente].
- Casos de exclusión y textos sin menciones válidas: [Pendiente].
- Casos de frontera entre categorías: [Pendiente].
- Casos de delimitación, repetición y ambigüedad: [Pendiente].
- Entradas con todas sus anotaciones esperadas: [Pendiente].

## 10. Validación y mantenimiento

- Piloto de anotación y revisión de desacuerdos: [Pendiente].
- Construcción y adjudicación del conjunto de referencia: [Pendiente].
- Separación de ejemplos, datos de desarrollo y evaluación final: [Pendiente].
- Métricas y criterios de aceptación: [Pendiente].
- Controles automáticos y revisión humana: [Pendiente].
- Evaluación de estabilidad de las anotaciones: [Pendiente].
- Versionado del codebook, prompt, ejemplos y configuración del modelo: [Pendiente].
- Procedimiento para modificar reglas y revisar anotaciones afectadas: [Pendiente].

## Anexo A. Instrucciones para el modelo de lenguaje

[Pendiente: redactar el prompt operativo a partir de las secciones acordadas].

## Anexo B. Referencias y fundamento de las decisiones

### B.1. Análisis de Sensibilidad Participativo en Tambopata

- Procedencia: texto proporcionado por la usuaria en la conversación.
- Ejercicio reportado: taller del 13 y 14 de mayo de 2026 y devolución del
  12 de agosto de 2026, en Puerto Maldonado.
- Uso en el codebook: fortalecer y enriquecer el marco conceptual y los
  lineamientos que se traducirán en reglas operativas para el procesamiento
  de la API.
- Autoría, versión y ubicación del documento de referencia: [Pendiente].

[Pendiente: registrar las demás fuentes y decisiones metodológicas adoptadas].
