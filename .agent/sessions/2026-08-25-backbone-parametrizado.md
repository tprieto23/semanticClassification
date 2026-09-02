# Sesión — Backbone parametrizado desde el endpoint

**Fecha:** 25 Ago 2026  
**Estado:** implementado, probado, generado y auditado sobre español.

## Contrato aprobado

`POST /analysis/network/projections/prac-infra-gov-v1` mantiene el contrato histórico
y acepta opcionalmente:

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

## Implementación

- La evidencia W1 se regenera dentro de la construcción.
- Los nodos deben alcanzar el mínimo documental dentro del scope solicitado.
- Se conservan aristas cuyos dos extremos son elegibles.
- Se exportan peso bruto, documentos, soporte independiente y dos pesos fraccionales.
- `Weight`/`analysis_weight` en GraphML sigue `edge_weighting`.
- Se generan nueve vistas para todos los componentes y para la componente principal.
- Se exportan CSV de nodos/aristas excluidos con la razón de exclusión.
- Las rutas codifican método, umbral, peso y modo de componentes.
- Sin `construction` la API continúa generando W1/W2/W3 como antes.

## Validación automatizada

- Cálculo controlado de `fractional-document` sobre oraciones de distintos tamaños.
- Selección documental y exclusiones verificadas.
- GraphML verificado con atributos analíticos.
- Contrato Pydantic discriminado y ruta determinista verificados.
- 63 pruebas exitosas.

## Generación real española

Parámetros: documentos españoles de todas las incubadoras, mínimo documental 2,
`fractional-document` y componentes menores incluidos.

- Evidencia W1: 6.465 nodos maestros; 4.808 incidentes y 1.657 aislados.
- Backbone: 840 nodos, 2.205 aristas y 47 componentes.
- Categorías: 460 PRAC, 89 INFRA y 291 GOV.
- Componente principal: 732 nodos y 2.121 aristas.
- Confianza: 452 aristas transversales, 129 recurrentes locales y 1.624
  exploratorias entre entidades recurrentes.
- Se conservan los seis `category_pair`.
- 18 vistas GraphML/CSV auditadas: nueve para todos los componentes y nueve para
  la componente principal.
- `Weight == fractional_document_weight` en todas las aristas del GraphML.
- Tamaño total de la construcción: 32 MB.

Ruta:

```
s3/archivosRed/corpus/language-es/projections/prac-infra-gov-v1/
  constructions/document-recurrent-core-v1/node-documents-2/
  edge-weight-fractional-document/with-minor-components/
```

## Próximo paso

Abrir el GraphML de todos los componentes o el de la componente principal en
Gephi; después definir y ejecutar Leiden sin mezclarlo con esta construcción.
