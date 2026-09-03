# Sesión — Endpoint Leiden y exportación para Gephi

**Fecha:** 25 Ago 2026  
**Estado:** implementado y ejecutado sobre la construcción española.

## Contrato

`POST /analysis/network/projections/{projection_id}/clusterings/leiden`

El endpoint recibe los parámetros de la construcción existente, una vista, un
alcance de componentes y la configuración reproducible de Leiden. No acepta rutas
de filesystem ni reconstruye la red fuente.

Configuración predeterminada:

```json
{
  "method": "leiden-v1",
  "objective_function": "modularity",
  "resolution": 1.0,
  "seed": 42,
  "iterations": -1,
  "weight_attribute": "weight"
}
```

El resultado se guarda bajo la vista fuente en una ruta que codifica objetivo,
resolución, semilla, iteraciones y atributo de peso. Las llamadas repetidas con el
mismo hash SHA-256 y configuración devuelven `cached=true`; el GraphML original no
se modifica.

## Artefactos

Los artefactos se publican bajo `s3/graphs/` con nombres estables que codifican
la construcción y la configuración de Leiden:

- `<base_name>.graphml`: red para Gephi con `modularity_class`, `community_id`,
  `community_size` y `community_color` en nodos.
- `<base_name>_communities.csv`: una fila por comunidad con tamaño, composición,
  aristas internas/externas y pesos.
- `<base_name>_members.csv`: pertenencia de cada entidad y atributos originales.
- `<base_name>.json`: parámetros, versiones, hash, calidad, modularidad y
  advertencias.

## Validación española

Sobre `main-component/all`, con `resolution=1.0`, `seed=42`, convergencia y `weight`:

- 732 nodos y 2.121 aristas de entrada.
- 21 comunidades.
- Tamaño máximo: 87 nodos; mínimo: 4 nodos.
- Modularidad clásica: `0.591829407843`.
- Ninguna comunidad singleton.

## Dependencias

Se añadieron `igraph>=1.0.0,<2.0.0` y `leidenalg>=0.11.0,<0.13.0`. La partición de
modularidad usa `RBConfigurationVertexPartition`; `cpm` queda disponible para
comparaciones de sensibilidad.

## Pruebas

- 6 pruebas de análisis Leiden y backbone pasan.
- 16 pruebas de servicio pasan, incluidas OpenAPI, Pydantic, caché y exportación.
- El artefacto español real fue generado y leído nuevamente con NetworkX,
  verificando los atributos de Gephi.
