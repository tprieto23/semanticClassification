# Contexto actual del proyecto

Este documento resume el estado metodológico y técnico del proyecto de clasificación semántica y construcción de redes. Es el contexto estable de trabajo para la fase actual; las decisiones y resultados puntuales de cada sesión se mantienen en `.agent/sessions/`.

## 1. Propósito y fase actual

El proyecto transforma documentos de los incubadores en una base de entidades canónicas y redes semánticas auditables. La unidad de evidencia es la oración: las relaciones entre entidades se derivan de su coocurrencia dentro de `(document_id, sentence_id)` y deben poder rastrearse hasta el documento, la oración, el contexto y las entidades originales.

La fase actual es la validación de comunidades Leiden sobre una red tipada centrada en `PRAC`, `INFRA` y `GOV`. Ya existe una construcción española generada y auditada, y Leiden está implementado y ejecutado sobre su componente principal. La validación sistemática de clusters, la asociación de `CHAR`/`LOC` y la meta-red siguen pendientes.

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

La suite contiene 81 pruebas: 79 pasan localmente y 2 se omiten porque este entorno
no tiene instalados `igraph` y `leidenalg` (ambos ya están en `requirements.txt`).
La generación bajo `s3/graphs/` está implementada y validada por tests; la
ejecución real sobre el corpus completo queda pendiente antes de retirar el
almacenamiento histórico.

## 9. Próximos pasos técnicos

1. Comparar sensibilidades de resolución, peso y alcance de componentes en Leiden.
2. Validar clusters con evidencia: tamaño mínimo, aristas, oraciones, documentos, concentración documental y lectura de contextos.
3. Clasificar configuraciones como tri-tipo, bi-tipo o intratipo.
4. Asociar `CHAR` y `LOC` a cada configuración usando las oraciones únicas que soportan sus nodos.
5. Diseñar la meta-red únicamente después de validar clusters estables y trazables.

Leiden está implementado; la validación metodológica de clusters y la meta-red aún no están terminadas.

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
