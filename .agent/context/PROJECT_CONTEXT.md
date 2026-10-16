# Contexto actual del proyecto

Este documento resume el estado metodológico y técnico del proyecto de clasificación semántica y construcción de redes. Es el contexto estable de trabajo para la fase actual; las decisiones y resultados puntuales de cada sesión se mantienen en `.agent/sessions/`.

## 1. Propósito y fase actual

El proyecto transforma documentos de los incubadores en una base de entidades canónicas y redes semánticas auditables. La unidad de evidencia es la oración: las relaciones entre entidades se derivan de su coocurrencia dentro de `(document_id, sentence_id)` y deben poder rastrearse hasta el documento, la oración, el contexto y las entidades originales.

La fase de trabajo actual con la usuaria es la revisión y validación del
codebook operativo en `codebook_en_construccion.md`. Sus diez categorías,
fichas y reglas de anotación están desarrolladas en el borrador 0.2.
El codebook sirve como especificación
para la extracción y clasificación mediante LLM en la API, con posterior
canonicalización, atributos de nodos y análisis de coocurrencia.

### Punto de reanudación — 16 Oct 2026

Se revisaron los cambios guardados antes de nuevas ediciones y se crearon
los commits `56e2526` (codebook y documentación) y `7e6ff24` (definiciones,
prompts y ejemplos) de la sesión anterior. Se leyó completa la sección 6,
incluidas 6.1–6.3, y se contrastó con fichas, prompt y parser.
El borrador 0.2 completa las reglas generales y las secciones 7–10 y anexo A:
fragmentos mínimos literales, siglas separadas, enumeraciones sin reconstrucción,
una categoría por aparición, negación en contexto y niveles de ambigüedad.
La única anidación admitida es LOC estrictamente dentro de CHAR; el parser
ya la conserva en ambos órdenes, también con repeticiones. No se implementó
resolución de siglas ni relaciones dentro de NER.

La validación real se ejecutó mediante `scripts/validate_ner_document.py`,
con respuestas reales de Anthropic y artefactos separados en
`data/output/ner_pilot/`. El script no abre conexiones ni escribe en la DB.
Docker está detenido; no se comprobó el endpoint de la API en ejecución.
NER tiene cachés de prompt en memoria: iniciar/reiniciar la API al validar
su endpoint con las nuevas instrucciones.

Piloto real: informe de biocarbón `6f98dc30-3b28-42aa-b519-497cec4c8627`,
5.267 caracteres, 42 oraciones y 13 bloques. Las dos extracciones completas
produjeron 74/68 y 86/77 anotaciones recibidas/conservadas, respectivamente,
con descartes por solapamiento. Se incorporó validación estricta al servicio,
con hasta dos correcciones por bloque y fallo explícito si persisten errores.
Las ejecuciones con ese control se detuvieron en el bloque que comienza
en 2113: el modelo insiste en añadir CHAR «UNAMAD» dentro de CHAR
«estudiantes de la UNAMAD». Los resultados completos previos son evidencia
de desarrollo, no extracciones aceptadas. El corpus no se ha procesado.
Hay también errores semánticos para revisar: «podas» usadas como residuos,
hornos productivos clasificados como infraestructura física, sedes usadas
como actores y fragmentos explicativos demasiado amplios.

Regresiones: 108 pruebas ejecutadas, 106 exitosas y 2 omitidas por las
dependencias opcionales de Leiden. Los cambios del 16 Oct se registran en
Git por solicitud de la usuaria. La agenda vigente está en `tasks.md`; la evidencia se resume
en `../sessions/2026-10-16-revision-seccion-6-y-piloto.md`.

### Antecedentes de la revisión — 15 Oct 2026

La usuaria está realizando una última revisión del codebook, ahora junto con
el prompt. Confirmó que NER debe dedicarse exclusivamente a extraer y
clasificar menciones. Fuzzy matching y construcción de relaciones son tareas
posteriores mediante endpoints independientes y consecutivos. Se precisó ese
alcance en las secciones 1 y 3 y en ambos prompts NER, conservando el contrato
de cuatro campos. El código ya exige `ner` antes de fuzzy matching y
`fuzzyMatching` antes de construir la red del documento.

La sección 2.4 contiene los dos párrafos aprobados sobre contexto territorial
y temático del corpus. El informe de Tambopata fue un insumo para comprender
ese contexto; la usuaria pidió que las instrucciones sean autónomas y que no
describan ni dependan de ese informe. Se retiraron también las referencias al
informe de la sección 2.5 y el anexo bibliográfico se conservó en la sesión
`../sessions/2026-10-15-codebook-autonomo.md`. La limpieza editorial elimina
referencias a «la usuaria» y al proceso de elaboración, sin cambiar las diez
definiciones ni aprobar propuestas pendientes. Ambos prompts usan instrucciones
autónomas; el de sistema explicita que no se consulten documentos externos.
En la sección 3, la usuaria ya escribió definición de mención, unidad de
anotación, contexto permitido y evidencia. La sección 4 incluye la regla de
omitir expresiones fuera de las categorías y conservar la grafía de los códigos.
En KNOW se confirmó reservar la etiqueta para contenidos que el texto
identifique como saberes o mediante atribución de conocimiento. Una afirmación
informativa o descripción territorial no basta por sí sola. Se admite el saber
sin portador identificado. La regla está en la ficha 5.2 y en `src/categories.py`,
cuya definición se incorpora al prompt. La ficha recoge también los criterios
de exclusión, frontera con ATT y extracción del contenido del saber; el
pendiente general fue sustituido por esas reglas durante la revisión.
La delimitación de ATT fue aprobada y aplicada en la ficha 5.3 y la definición
que se incorpora al prompt: evidencia explícita y atribución a un actor,
exclusión de descripciones factuales, saberes o actividades por sí solos,
actitudes favorables/desfavorables/ambivalentes y extracción de la actitud con
su objeto. El ejemplo productoras/compromiso ya está en las demostraciones.
Se retiró el pendiente general de ATT; esto no completa las demás fichas.
La delimitación de SKILL también fue aprobada y aplicada en la ficha 5.4 y
`src/categories.py`: competencia atribuida a un actor; conocer, querer o actuar
no basta por sí solo; permiso, recursos u oportunidad tampoco demuestran
habilidad. La palabra «puede» requiere evidencia contextual de competencia.
Se extrae la habilidad con su tarea, conservando la atribución en contexto.
Se retiró el pendiente general de SKILL; el ejemplo ya está en las demostraciones.
Por petición de la usuaria, se completaron las fichas 5.5–5.10: PRAC,
physical_INFRA, soft_INFRA, eco_INFRA, RUL y LOC. Incluyen evidencia, exclusiones,
delimitación literal, fronteras y ejemplos, sin pendientes dentro de esas fichas.
PRAC conserva actividades propuestas, futuras o negadas sin afirmar ejecución;
infraestructura se clasifica por función; eco_INFRA exige respaldo textual de
su función ecológica; RUL incluye reglas formales o informales con función
reguladora y conserva la negación en prescripciones; LOC admite denominaciones
genéricas con referente espacial reconocible y mantiene los ejemplos San Pedro.
Las síntesis están en `src/categories.py`, incorporadas al prompt. Se precisó
la función de la plataforma digital en la demostración soft_INFRA, conservando
diez ejemplos. Siguen pendientes las reglas generales y la validación del
codebook; la anidación LOC/CHAR continúa requiriendo adaptación del parser.
Continuar paso a paso, con respuestas breves, revisando codebook y prompt juntos.

### Acuerdos y comprobaciones anteriores — 12 Oct 2026

El foco acordado con la usuaria es definir las características específicas
que deben identificar las menciones para clasificarse en cada categoría:
rasgos esenciales, inclusión, exclusión, evidencia textual y fronteras.
La usuaria pidió frenar la sucesión de casos de delimitación y nombres
individuales. No seguir abriendo casos de artículos, siglas, enumeraciones
o normalización mientras se revisan los criterios de clasificación.

El conjunto de diez categorías es una decisión final de la usuaria:
CHAR, KNOW, ATT, SKILL, PRAC, physical_INFRA, soft_INFRA, eco_INFRA, RUL y LOC.
El código de extracción ya establece esas diez categorías en
`src/categories.py`; esquema estructurado, parser, prompt y validación de
canonicalización usan la misma fuente. INFRA se admite solo al procesar legado,
sin reclasificar automáticamente registros antiguos.
Las definiciones de las diez categorías ya están acordadas. CHAR reúne
ahora una síntesis de sus criterios aprobados en la sección 5.1. No se
presupone que las demás fichas ni todas las fronteras estén completas.
Los ejemplos se usan únicamente cuando aclaran un criterio general.

Se conservan los acuerdos de extracción, anidación LOC dentro de CHAR,
registro de cada aparición y vinculación posterior de nombre completo
y sigla al mismo nodo canónico. Las reglas de extracción de CHAR están
reunidas en la sección 6.3. El último fragmento confirmado es
«cooperativa La Esperanza», con el nombre propio íntegro.

También se mantiene el criterio aprobado para planes en RUL: el contexto
debe presentarlos como instrumentos que establecen condiciones,
responsabilidades o criterios para las prácticas territoriales.

La usuaria precisó después que necesita un codebook más básico, considerando
el uso eficiente de Claude, y pidió revisar primero el código para aprovechar
la estructura de persistencia existente. La revisión identificó el contrato
NER de cuatro campos por mención (`label`, `text`, `sentence_id`, `ambiguity`),
el enriquecimiento local y la persistencia posterior a la canonicalización.
Los modelos y las comprobaciones locales se documentan en
`../sessions/2026-10-12-revision-contrato-ner.md`; no se inspeccionó la DB
en ejecución ni se hicieron llamadas a Claude.

El codebook puede apoyarse en ese contrato y centrarse en las diez categorías
y sus criterios esenciales. La adaptación local del 12 Oct actualizó código,
prompt y demostraciones: diez ejemplos ilustrativos sustituyen los 25 del
esquema anterior. La red completa y su visualizador admiten las diez categorías;
los artefactos históricos pueden conservar INFRA. La proyección versionada
`prac-infra-rul-v2` conserva su selección histórica PRAC/INFRA/RUL y no representa
el nuevo conjunto completo. No se cambiaron datos, migraciones ni servicios
en ejecución. Pruebas locales: 101 ejecutadas, 99 exitosas y 2 omitidas por
dependencias opcionales de Leiden; proveedor y DB simulados.

El parser aún descarta anidaciones y el nombre completo con sigla no se unifica
automáticamente sin alias previo en el caso comprobado. Estas reglas no se
implementaron en la adaptación de categorías. La limpieza mantiene llamadas
propias a Claude. Consultar `tasks.md` y
`../sessions/2026-10-12-implementacion-diez-categorias.md`. Mantener respuestas breves.

Como antecedente técnico, la promoción de comunidades Leiden aceptadas a nodos
semánticos y la construcción determinista de conexiones intercluster están
implementadas. Sus verificaciones y pendientes anteriores se conservan más
abajo, pero no son el punto de continuidad del trabajo del codebook.

### Antecedente operativo — 28 Sep 2026

La sesión más reciente volvió temporalmente al Objetivo 1 para preparar una
nueva ingesta en Postman. La API y PostgreSQL están activos en Docker y la
migración vigente es `c6d7e8f9a0b1 (head)`. Ya se puede iniciar la carga de
documentos. El siguiente paso de la usuaria es ejecutar una carga real con
`POST /documents`, revisar la respuesta `201` y conservar el `document_id`.

En esa carga solo son obligatorios el archivo y `incubator_number`. `language`,
`year`, `productive_sector`, `document_type` y `metadata` pueden omitirse. Los
tres atributos de clasificación pueden completarse posteriormente con el PATCH
descrito en la sección de arquitectura. No se debe añadir `incubator_number` a
la URL ni fijar manualmente `Content-Type`; los datos se envían por `form-data`.

## 2. Arquitectura general

La aplicación es un servicio FastAPI ejecutado con Uvicorn, PostgreSQL 16 con pgvector, SQLAlchemy 2 y Alembic. Docker Compose coordina los servicios. El almacenamiento local de artefactos usa `s3/`.

La ingesta exige `incubator_number`; `year`, `productive_sector`,
`document_type`, `language` y `metadata` son opcionales. Los tres atributos de
clasificación pueden completarse después mediante
`PATCH /documents/{document_id}/classification` con cuerpo `form-data`, sin
reprocesar el documento. `year` admite cuatro dígitos, el sector controlado
vigente es `Agroforestry` y el tipo documental se elige entre `academic`,
`technical_report`, `project_report`, `policy_document`, `manual_or_guide`,
`institutional_document` y `other`. Las columnas nuevas permiten `NULL` solo
para conservar los registros sin clasificación disponible.

El flujo principal es:

```text
documentos
  -> conversión y extracción de texto
  -> limpieza
  -> NER estructurado (Claude few-shot)
  -> fuzzy matching y canonicalización
  -> menciones persistidas con oración y contexto
  -> evidencia entidad–oración
  -> proyecciones de coocurrencia
  -> backbone/configuración
  -> proyección PRAC/INFRA/RUL y Leiden
  -> nodos semánticos y conexiones intercluster
  -> asociación de CHAR/LOC y descripción editorial de conexiones (pendiente)
```

Las categorías NER actuales son `CHAR`, `KNOW`, `ATT`, `SKILL`, `PRAC`,
`physical_INFRA`, `soft_INFRA`, `eco_INFRA`, `RUL` y `LOC`.
`RUL` identifica reglas, normas e instrumentos institucionales concretos, tanto
formales como informales: leyes, reglamentos, políticas, planes, acuerdos,
contratos, permisos, estándares y reglas comunitarias. La gobernanza permanece
como concepto de análisis, pero no como categoría NER. `GOV` es una etiqueta
histórica sustituida por `RUL`; solo se conserva en migraciones, procedencia y
lectura compatible de artefactos anteriores. `INFRA` también queda reservado
al legado: dividir sus menciones requiere revisar el contexto. La proyección
registrada `prac-infra-rul-v2` conserva su definición histórica.

## 3. Evidencia y modelo de coocurrencia

- La coocurrencia se agrupa por `(document_id, sentence_id)`.
- Una oración con `N` entidades proyectadas genera la clique completa de pares no dirigidos.
- `sentence_entities` conserva todas las entidades de la oración, incluidas `CHAR` y `LOC` aunque no pertenezcan a la topología PRAC–INFRA–RUL.
- `edge_observations` conserva la evidencia de cada pareja: documento, oración, contexto, pareja de entidades, texto y ambigüedad.
- Las aristas agregadas conservan `sentence_count`, `document_count`, métricas fraccionales, `category_pair` y niveles de confianza; por tanto, la arista puede remontarse a sus observaciones sin depender únicamente de `weight`.

La base de datos persiste las menciones canonicalizadas con `document_id`, `sentence_id`, `canonical_id`, categoría, texto/contexto, ambigüedad y offsets. La información de oración no se reconstruye únicamente durante `/analysis/network`.

## 4. Auditorías de canonicalización

- `SM T1.docx` fue retirado completamente del conjunto de trabajo.
- Se unificaron únicamente los alias solicitados de Wyss bajo `Wyss Academy for Nature`: `The Wyss Academy for Nature`, `Wyss Academy for Nature`, `Wyss Academy`, `WYSS Academy`, `Wyss`, `WYSS`, `Wyss Academy for Nature WYSS`, `Wyss Academy (WA)` y `Wyss Academy Hub SAM`.
- No se fusionaron entidades del tipo `socios ...` ni otros nombres no incluidos explícitamente.
- Las redes históricas no se destruyen; las nuevas construcciones se escriben en rutas versionadas.

## 5. Decisiones metodológicas de la red tipada

La proyección `prac-infra-rul-v2` incluye los seis pares no dirigidos:

`PRAC--PRAC`, `PRAC--INFRA`, `PRAC--RUL`, `INFRA--INFRA`, `INFRA--RUL` y `RUL--RUL`.

Se permiten relaciones intratipo y entre tipos. Las vistas disponibles son `all`, `cross`, `intra` y las seis vistas de pares individuales. `CHAR` y `LOC` quedan fuera de la topología inicial para evitar ruido, pero permanecen en la evidencia y se asociarán después a los clusters mediante sus oraciones de soporte.

No se adopta `weight >= 3` como definición universal del backbone. En la red española, ese corte elimina gran parte de la estructura y sesga el resultado hacia `PRAC--PRAC`. La construcción aprobada usa recurrencia documental de nodos:

```text
un nodo es elegible si document_count >= mínimo configurado
una arista se conserva si ambos extremos son elegibles
```

El valor `edge.document_count >= 2` se conserva como señal de confianza (`transversal`), no como requisito universal de inclusión. Se mantiene el conteo crudo de oraciones y se elige una métrica analítica explícita para el peso.

## 6. Contrato de construcción parametrizable

El endpoint heredado `POST /analysis/network` sigue construyendo la red raw con sus parámetros históricos (`minimum_weight`, `include_isolates`).

La proyección tipada usa `POST /analysis/network/projections/{projection_id}`. El contrato aprobado para el backbone documental es:

```json
{
  "incubator_number": "all",
  "language": "es",
  "construction": {
    "method": "document-recurrent-core-v1",
    "minimum_node_document_count": 2,
    "edge_weighting": "fractional-document",
    "include_minor_components": true
  }
}
```

También se mantiene la construcción compatible `raw-threshold-v1`. La construcción documental implementada incluye:

- elegibilidad de nodos por número de documentos;
- inducción de aristas entre nodos elegibles;
- `fractional_weight`, ponderado por oración como `1/(N_s-1)`;
- `fractional_document_weight`, limitado a una contribución máxima por documento;
- `independent_support_count`, basado en soportes contextuales independientes;
- niveles `transversal`, `recurrent-local` y `exploratory`;
- selección de `analysis_weight` para el atributo GraphML estándar `weight`.

Las métricas de todas las vistas continúan en la respuesta, pero la publicación
oficial usa una única vista canónica: `main-component/all`.

## 7. Almacenamiento oficial de grafos

La raíz vigente es `s3/graphs/`, dividida en `graphml/`, `json/` y `csv/`.
Cada formato repite la misma jerarquía de alcance:

```text
corpus/{es|en|all}/
incubators/{number}/{es|en|all}/
documents/{document_id}/
```

Los nombres oficiales son `main_network`, `backbone_<projection_id>` y
`leiden_<projection_id>`. Los parámetros viven en el JSON de metadatos. Los CSV
de red usan los sufijos `_nodes` y `_edges`; los de Leiden, `_communities` y
`_members`.

Cada ejecución reemplaza atómicamente el nombre estable. Ya no se publican PNG,
SVG, HTML, Matrix Market, JSON completos del grafo, manifiestos duplicados,
vistas materializadas ni CSV de evidencia. La evidencia se consulta directamente
en PostgreSQL.

`s3/archivosRed/` conserva los artefactos históricos y no se elimina hasta
validar las nuevas ejecuciones; no es la ubicación usada por el código vigente.

## 8. Estado de implementación y calidad

Implementado en código:

- `src/analysis/backbone.py` — construcción de backbones analíticos;
- `src/analysis/graph_export.py` — exportación mínima GraphML + CSV + JSON;
- `src/analysis/graph_paths.py` — rutas y nombres estables de `s3/graphs/`;
- `src/analysis/leiden.py` — clustering reproducible con atributos para Gephi;
- esquemas de red en `src/api/schemas/network.py`;
- integración de servicio en `src/services/network.py`;
- rutas en `src/api/routers/analysis_networks.py`;
- tabla `sentences` en `src/models/sentences.py` y `src/models/sentences_repo.py`;
- persistencia de oraciones durante fuzzy matching en `src/services/documents.py`;
- migración `d7e8f9a0b1c2_add_sentences_table.py`;
- pruebas en `tests/test_backbone.py`, `tests/test_leiden.py`,
  `tests/test_network_service.py`, `tests/test_graph_paths.py`,
  `tests/test_sentences_repo.py` y `tests/test_network_visualization.py`;
- ejemplo del contrato en `postman_collection.json`.

La suite contiene 98 pruebas: 96 pasan y 2 se omiten porque este entorno no tiene
instalados `igraph` y `leidenalg` (ambos están en `requirements.txt`).
La generación bajo `s3/graphs/` está implementada y validada por tests; la
ejecución real sobre el corpus completo queda pendiente antes de retirar el
almacenamiento histórico.

## 9. Próximos pasos técnicos

1. Regenerar los artefactos oficiales del backbone y Leiden para
   `prac-infra-rul-v2`, registrar su nuevo SHA-256 y volver a vincular los
   meta-nodes a esa partición exacta.
2. Revisar humanamente los títulos y descripciones generados para los meta-nodes;
   corregirlos y aceptarlos cuando corresponda.
3. Crear el prompt editorial separado para describir conexiones intercluster ya
   calculadas, usando evidencia trazable y sin atribuir causalidad por coocurrencia.
4. Asociar `CHAR` y `LOC` a cada configuración mediante las oraciones que soportan
   sus entidades miembro.

Leiden y la construcción de la meta-red están implementados. La metodología
aprobada para las conexiones intercluster se describe en la sección 11.

## 11. Promoción de comunidades a nodos semánticos

El prompt editorial está en `data/prompts/semantic_node_prompt.md`. Describe las
relaciones internas respaldadas por entidades, aristas y oraciones; no clasifica
pathways ni evalúa el carácter transformador.

La implementación actual añade `semantic_nodes` y `semantic_node_members` mediante
la migración `f2b3c4d5e6f7`. Los endpoints especializados bajo `/semantic-nodes`
permiten consultar la partición Leiden publicada y su SHA-256, promover una
comunidad explícita, listar/leer/editar nodos y generar su título y descripción
con Claude. La promoción conserva miembros, alcance, configuración, huellas de
procedencia y soporte documental por incubadora. El texto generado queda en
`draft` hasta su aceptación humana. La construcción determinista de relaciones
entre nodos usa la fórmula `meta-network-relationship-v1`, importa la instantánea
del GraphML exacto a `semantic_network_source_edges` y agrega en PostgreSQL hacia
`semantic_node_relationships`. Claude no participa en la existencia ni el peso de
estas relaciones.

Una conexión no dirigida entre dos meta-nodes registrados existe si al menos una
arista fuente que supera `minimum_source_edge_weight` conecta entidades miembro de
ambos meta-nodes. El umbral predeterminado es `0`, por lo que cualquier arista
fuente positiva basta. El peso de la conexión es la suma de los atributos `weight`
de sus aristas fuente. `source_edge_count` cuenta aristas entre pares de entidades;
`sentence_support_sum` y `document_support_sum` son sumas de los soportes de esas
aristas, no cantidades únicas de oraciones o documentos. La conexión es una
agregación estructural de coocurrencias entre entidades miembro: no afirma una
relación causal, funcional ni una coocurrencia literal entre los meta-nodes.

La configuración metodológica aprobada exige `require_accepted_nodes=true`:
participan solo meta-nodes registrados y aceptados. Las comunidades no promovidas
quedan fuera de esta meta-red; su ausencia no significa que carezcan de aristas en
el grafo fuente. La validación del corpus español registró 40 meta-nodes, 96
conexiones y 836 aristas fuente contraídas sobre la partición histórica GOV v1.

La migración `b5c6d7e8f9a0` cambia las categorías persistidas y la proyección
semántica a `prac-infra-rul-v2`; `c6d7e8f9a0b1` normaliza también los pares de
categoría en la instantánea de aristas. No se modificaron los artefactos de
`s3/`: allí sigue el GraphML oficial español `prac-infra-gov-v1` de 66
comunidades. Por eso `GET /semantic-nodes/leiden-source` con `artifact_source=official`
responde 404 hasta regenerar los artefactos oficiales RUL v2.

Las filas existentes de nodos y relaciones conservan los hashes de sus GraphML
GOV v1 aunque su `projection_id` se haya migrado. No constituyen una partición
RUL v2 regenerada. La fuente histórica `accepted-2026-08-25` sigue disponible y
el servicio normaliza `GOV` a `RUL` en memoria al leerla; contiene 21 comunidades.

## 10. Referencias de trabajo

- Arquitectura: `.agent/context/architecture.md`
- Tareas: `.agent/context/tasks.md`
- Deuda técnica: `.agent/tech-debt.md`
- Sesiones: `.agent/sessions/`
- Artefactos oficiales de grafos: `s3/graphs/`
- Código de servicios: `src/services/network.py`
- Router: `src/api/routers/analysis_networks.py`
- Esquemas: `src/api/schemas/network.py`
- Construcción backbone: `src/analysis/backbone.py`
