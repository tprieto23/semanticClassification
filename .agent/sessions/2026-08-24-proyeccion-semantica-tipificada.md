# Sesión — Proyección semántica tipada PRAC + INFRA + GOV

**Fecha:** 24 Ago 2026  
**Estado:** implementada, probada y generada sobre el corpus completo.

## Decisión metodológica

La base de evidencia continúa siendo `(document_id, sentence_id)` ↔ entidad
canónica. La red analítica proyecta solamente `PRAC`, `INFRA` y `GOV`, pero
permite los seis tipos de arista posibles, incluidas las relaciones intratipo.
`CHAR` y `LOC` permanecen fuera del grafo y dentro de la evidencia de oración.

## Implementación

- Proyección registrada: `prac-infra-gov-v1`.
- Vistas: `all`, `cross`, `intra` y una por cada `category_pair`.
- Evidencia normalizada: `sentences.csv`, `sentence_entities.csv` y
  `edge_observations.csv`.
- GraphML compacto con `weight`, `document_count`, `category_pair` y `edge_key`.
- JSON/HTML interactivo referencian oraciones una sola vez por vista.
- Endpoints nuevos de build, latest, catálogo de vistas y evidencia por arista.
- Rutas históricas y artefactos de cinco categorías preservados.

## Validación real W1 con aislados

- 40.915 menciones fuente.
- 18.755 menciones proyectadas.
- 9.518 nodos: 4.654 PRAC, 1.681 INFRA y 3.183 GOV.
- 10.310 oraciones con al menos una entidad proyectada.
- 4.637 oraciones que producen aristas.
- 13.196 aristas y 14.657 observaciones oración–arista.
- 9.964 presencias contextuales CHAR/LOC en 5.589 oraciones.
- Los pesos coinciden con el número de observaciones y `document_count` con los
  documentos distintos para todas las aristas.
- `all = cross ∪ intra` y ambas vistas son disjuntas.
- 57 pruebas automatizadas exitosas.

También se generaron variantes W1 sin aislados:

- Corpus completo: 7.184 nodos, 13.196 aristas y 1.053 componentes.
- Corpus en español: 4.808 nodos, 8.781 aristas y 719 componentes.

## Próximo paso metodológico

Inspeccionar la red completa y sus vistas para decidir el backbone. Leiden,
clusters semánticos y meta-red quedan fuera de esta entrega.
