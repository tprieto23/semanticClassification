# Simplificación del almacenamiento de grafos — 2026-09-03

## Decisión

La publicación vigente usa `s3/graphs/{graphml,json,csv}/<scope>/`. Los nombres
son estables: `main_network`, `backbone_<projection_id>` y
`leiden_<projection_id>`. Los parámetros se guardan en el JSON; cada ejecución
reemplaza atómicamente el nombre oficial.

Solo se conservan GraphML, JSON de metadatos y los CSV canónicos de nodos,
aristas, comunidades y miembros. Las vistas adicionales se calculan como
resúmenes sin materializar archivos. La evidencia por arista se consulta
directamente en PostgreSQL, combinando `sentences` con las menciones `entities`.

## Compatibilidad

`s3/archivosRed/` queda intacto como legado hasta validar las nuevas ejecuciones.
El mount público vigente es `/files/graphs`; `/files/networks` se mantiene solo
para los artefactos históricos.

## Implementación cerrada

- `src/analysis/graph_paths.py`, `src/analysis/graph_export.py`,
  `src/analysis/backbone.py`, `src/analysis/leiden.py`.
- `src/services/network.py` con rutas relativas a `STORAGE_GRAPHS`, escritura
  atómica y caché por hash SHA-256.
- `src/models/sentences.py`, `src/models/sentences_repo.py` y migración
  `d7e8f9a0b1c2_add_sentences_table.py`.
- `src/config.py` añade `STORAGE_GRAPHS`; `STORAGE_NETWORK` es alias legado.
- `src/api/main.py` monta `/files/graphs` y conserva `/files/networks`.
- La suite de 81 pruebas pasa localmente con 2 omisiones de Leiden cuando
  `igraph`/`leidenalg` no están instalados.
