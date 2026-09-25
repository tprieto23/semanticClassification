# Contexto actual del proyecto

Este documento resume el estado metodológico y técnico del proyecto de clasificación semántica y construcción de redes. Es el contexto estable de trabajo para la fase actual; las decisiones y resultados puntuales de cada sesión se mantienen en `.agent/sessions/`.

## 1. Propósito y fase actual

El proyecto transforma documentos de los incubadores en una base de entidades canónicas y redes semánticas auditables. La unidad de evidencia es la oración: las relaciones entre entidades se derivan de su coocurrencia dentro de `(document_id, sentence_id)` y deben poder rastrearse hasta el documento, la oración, el contexto y las entidades originales.

La fase actual es la promoción de comunidades Leiden aceptadas a nodos semánticos con título y descripción auditables. La auditoría y aceptación metodológica de los clusters ya concluyó. La construcción determinista de conexiones intercluster está implementada y validada para los meta-nodes registrados y aceptados. Siguen pendientes la revisión humana de los textos editoriales, el prompt para describir las conexiones ya calculadas y la asociación de `CHAR`/`LOC`.

## 2. Arquitectura general

La aplicación es un servicio FastAPI ejecutado con Uvicorn, PostgreSQL 16 con pgvector, SQLAlchemy 2 y Alembic. Docker Compose coordina los servicios. El almacenamiento local de artefactos usa `s3/`.

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
  -> Leiden y clusters semánticos
  -> asociación de CHAR/LOC y meta-red (pendiente)
```

Las categorías NER actuales son `CHAR`, `LOC`, `PRAC`, `INFRA` y `GOV`.

## 3. Evidencia y modelo de coocurrencia

- La coocurrencia se agrupa por `(document_id, sentence_id)`.
- Una oración con `N` entidades proyectadas genera la clique completa de pares no dirigidos.
- `sentence_entities` conserva todas las entidades de la oración, incluidas `CHAR` y `LOC` aunque no pertenezcan a la topología PRAC–INFRA–GOV.
- `edge_observations` conserva la evidencia de cada pareja: documento, oración, contexto, pareja de entidades, texto y ambigüedad.
- Las aristas agregadas conservan `sentence_count`, `document_count`, métricas fraccionales, `category_pair` y niveles de confianza; por tanto, la arista puede remontarse a sus observaciones sin depender únicamente de `weight`.

La base de datos persiste las menciones canonicalizadas con `document_id`, `sentence_id`, `canonical_id`, categoría, texto/contexto, ambigüedad y offsets. La información de oración no se reconstruye únicamente durante `/analysis/network`.

## 4. Auditorías de canonicalización

- `SM T1.docx` fue retirado completamente del conjunto de trabajo.
- Se unificaron únicamente los alias solicitados de Wyss bajo `Wyss Academy for Nature`: `The Wyss Academy for Nature`, `Wyss Academy for Nature`, `Wyss Academy`, `WYSS Academy`, `Wyss`, `WYSS`, `Wyss Academy for Nature WYSS`, `Wyss Academy (WA)` y `Wyss Academy Hub SAM`.
- No se fusionaron entidades del tipo `socios ...` ni otros nombres no incluidos explícitamente.
- Las redes históricas no se destruyen; las nuevas construcciones se escriben en rutas versionadas.

## 5. Decisiones metodológicas de la red tipada

La proyección `prac-infra-gov-v1` incluye los seis pares no dirigidos:

`PRAC--PRAC`, `PRAC--INFRA`, `PRAC--GOV`, `INFRA--INFRA`, `INFRA--GOV` y `GOV--GOV`.

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

La suite contiene 93 pruebas: 91 pasan y 2 se omiten porque este entorno no tiene
instalados `igraph` y `leidenalg` (ambos están en `requirements.txt`).
La generación bajo `s3/graphs/` está implementada y validada por tests; la
ejecución real sobre el corpus completo queda pendiente antes de retirar el
almacenamiento histórico.

## 9. Próximos pasos técnicos

1. Revisar humanamente los títulos y descripciones generados para los meta-nodes;
   corregirlos y aceptarlos cuando corresponda.
2. Crear el prompt editorial separado para describir conexiones intercluster ya
   calculadas, usando evidencia trazable y sin atribuir causalidad por coocurrencia.
3. Asociar `CHAR` y `LOC` a cada configuración mediante las oraciones que soportan
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
conexiones y 836 aristas fuente contraídas.

Los artefactos oficiales usan nombres estables y pueden reemplazarse. Por ello
la promoción exige el hash del GraphML Leiden exacto. El artefacto español
publicado al 22 Sep 2026 contiene 66 comunidades; la bitácora del 25 Ago registra
una ejecución histórica de 21 que aún está disponible en `s3/archivosRed/`.
La API ofrece las fuentes `official` y `accepted-2026-08-25` para seleccionar
explícitamente la partición y evitar confundirlas.

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
