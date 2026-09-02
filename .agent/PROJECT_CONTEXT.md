# Contexto actual del proyecto

Este documento resume el estado metodológico y técnico del proyecto de clasificación semántica y construcción de redes. Es el contexto estable de trabajo para la fase actual; las decisiones y resultados puntuales de cada sesión se mantienen en `.agent/sessions/`.

## 1. Propósito y fase actual

El proyecto transforma documentos de los incubadores en una base de entidades canónicas y redes semánticas auditables. La unidad de evidencia es la oración: las relaciones entre entidades se derivan de su coocurrencia dentro de `(document_id, sentence_id)` y deben poder rastrearse hasta el documento, la oración, el contexto y las entidades originales.

La fase actual es la preparación de una red tipada centrada en `PRAC`, `INFRA` y `GOV`, con una construcción parametrizable de recurrencia documental. Ya existe una construcción española generada y auditada. Todavía no se han ejecutado Leiden, la validación sistemática de clusters ni la meta-red de clusters.

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
  -> Leiden y clusters semánticos (pendiente)
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

`include_minor_components` define el alcance primario de la respuesta. Siempre se generan las vistas de todos los componentes y del componente principal, sin modificar destructivamente W1.

## 7. Construcción española ya generada

Ruta raíz:

`s3/archivosRed/corpus/language-es/projections/prac-infra-gov-v1/constructions/document-recurrent-core-v1/node-documents-2/edge-weight-fractional-document/with-minor-components/`

La evidencia base de W1 contiene 6.465 nodos canónicos maestros, 7.364 oraciones y 8.781 aristas undirected. Tras aplicar `document_count >= 2`:

- 1.068 nodos son elegibles;
- el backbone analítico de todos los componentes tiene 840 nodos, 2.205 aristas y 47 componentes;
- el componente principal tiene 732 nodos, 2.121 aristas y un componente;
- los seis `category_pair` están presentes;
- en todos los GraphML auditados `weight == fractional_document_weight` y `fractional_document_weight <= fractional_weight`.

La construcción exporta `evidence/`, `backbone/`, 9 vistas de todos los componentes, 9 vistas del componente principal, `construction_manifest.json` y `api_response.json`. Cada vista contiene `network.graphml`, `nodes.csv`, `edges.csv` y `summary.json`.

GraphML principal:

- [todos los componentes](../s3/archivosRed/corpus/language-es/projections/prac-infra-gov-v1/constructions/document-recurrent-core-v1/node-documents-2/edge-weight-fractional-document/with-minor-components/views/all-components/all/network.graphml)
- [componente principal](../s3/archivosRed/corpus/language-es/projections/prac-infra-gov-v1/constructions/document-recurrent-core-v1/node-documents-2/edge-weight-fractional-document/with-minor-components/views/main-component/all/network.graphml)

## 8. Estado de implementación y calidad

Implementado en código:

- `src/analysis/backbone.py`;
- esquemas de red en `src/api/schemas/network.py`;
- integración de servicio en `src/services/network.py`;
- rutas en `src/api/routers/analysis.py`;
- pruebas unitarias en `tests/test_backbone.py` y `tests/test_network_service.py`;
- ejemplo del contrato en `postman_collection.json`.

La suite actual tiene 63 pruebas y todas pasan. También pasan `git diff --check` y el chequeo de formato Black sobre los archivos modificados. La construcción real española respondió HTTP 200 y su respuesta fue validada con el esquema Pydantic correspondiente; los conteos GraphML/CSV/manifiestos fueron contrastados entre sí.

## 9. Próximos pasos técnicos

1. Elegir y documentar la implementación de Leiden, fijando semilla, parámetro de resolución y criterio de reproducibilidad.
2. Ejecutar Leiden sobre la vista principal y comparar sensibilidades de resolución, peso y alcance de componentes.
3. Validar clusters con evidencia: tamaño mínimo, número de aristas, oraciones y documentos de soporte, concentración documental y lectura de contextos.
4. Clasificar configuraciones como tri-tipo, bi-tipo o intratipo sin confundirlas con clusters pequeños o fragmentos.
5. Asociar `CHAR` y `LOC` a cada configuración usando las oraciones únicas que soportan sus nodos, con conteos y enriquecimiento frente al corpus.
6. Diseñar la meta-red de clusters únicamente después de validar que los clusters semánticos son estables y trazables.
7. Añadir, si procede, endpoints o artefactos específicos para ejecutar y consultar Leiden, validación y asociaciones sin romper el contrato existente.

No se debe presentar Leiden, la meta-red ni la validación de clusters como funcionalidades ya terminadas.

## 10. Referencias de trabajo

- Arquitectura: `.agent/architecture.md`
- Tareas: `.agent/tasks.md`
- Sesiones: `.agent/sessions/`
- Artefactos de redes: `s3/archivosRed/corpus/`
- Código de servicios: `src/services/network.py`
- Router: `src/api/routers/analysis.py`
- Esquemas: `src/api/schemas/network.py`
- Construcción backbone: `src/analysis/backbone.py`
