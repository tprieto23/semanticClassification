# Definición matemática de las relaciones de la meta-red

Versión: `meta-network-relationship-v1`

## Propósito

Este documento define una construcción determinista para contraer una red
tipada de entidades en una meta-red cuyos nodos son comunidades Leiden ya
registradas como nodos semánticos.

La construcción no interpreta el significado de la relación y no llama a un
LLM. La interpretación textual de una relación, si se solicita después, es una
operación editorial separada. PostgreSQL ejecuta las agregaciones sobre la
instantánea de aristas que corresponde exactamente a la partición seleccionada.

## Entrada formal

Sea la red fuente no dirigida:

\[
G=(V,E),
\]

donde cada entidad canónica es un nodo `u \in V` y cada arista es un par no
ordenado `e=\{u,v\} \in E`. Cada arista fuente conserva los siguientes campos:

\[
 w_e>0,\qquad s_e\geq 0,\qquad d_e\geq 0.
\]

- `w_e`: atributo analítico `weight` del GraphML de Leiden. Es el único peso
  usado para el peso principal de la meta-arista.
- `s_e`: `sentence_count` de la arista fuente, cuando está disponible.
- `d_e`: `document_count` de la arista fuente, cuando está disponible.

Los contadores `s_e` y `d_e` se conservan como soportes aditivos de las aristas
fuente. Sus sumas no se presentan como número de oraciones o documentos únicos
de la meta-arista, porque dos aristas fuente pueden compartir una oración o un
documento.

Sea `C` el conjunto de comunidades de una ejecución exacta de Leiden y sea:

\[
 c:V_C\to C
\]

la función que asigna cada entidad de la partición a su `community_id`. `V_C`
es el subconjunto de entidades de `V` que tienen comunidad en el GraphML
seleccionado.

Cada comunidad aceptada se registra como un nodo semántico `A \in C_A`. Solo se
usan comunidades que pertenecen a la misma partición (`clustering_sha256`), al
mismo alcance, idioma, proyección y fuente de artefactos.

## Selección de aristas

Se conserva una arista fuente si:

1. sus dos extremos existen en la partición seleccionada;
2. sus dos extremos están asociados a nodos semánticos registrados;
3. los nodos semánticos de sus extremos son distintos;
4. `w_e \geq \tau`, donde `\tau` es `minimum_source_edge_weight`.

La condición 3 elimina relaciones internas de un mismo cluster. La condición 4
es un filtro explícito del endpoint y por defecto `\tau=0`, de modo que no se
descarta ninguna arista positiva del GraphML.

## Contracción y peso

Para dos nodos semánticos distintos `A` y `B`, sea:

\[
 E_{A,B}=\{e=\{u,v\}\in E : c(u)=A,\ c(v)=B\}.
\]

La meta-red contiene una sola arista no dirigida `\{A,B\}` si y solo si:

\[
 |E_{A,B}|>0.
\]

Su peso principal es la suma de los pesos analíticos originales:

\[
 W_{A,B}=\sum_{e\in E_{A,B}}w_e.
\]

Los soportes auxiliares son:

\[
 N^{edge}_{A,B}=|E_{A,B}|,
\]

\[
 S^{sum}_{A,B}=\sum_{e\in E_{A,B}}s_e,
\qquad
 D^{sum}_{A,B}=\sum_{e\in E_{A,B}}d_e.
\]

`N^{edge}` es el número de aristas fuente contraídas. `S^{sum}` y `D^{sum}`
son sumas de soporte de aristas fuente y deben llevar ese nombre en la API.
No equivalen a `unique_sentence_count` ni a `unique_document_count`.

El endpoint también devuelve la media del peso fuente:

\[
 \bar w_{A,B}=\frac{W_{A,B}}{N^{edge}_{A,B}}.
\]

Si una arista fuente no trae `sentence_count` o `document_count`, el endpoint
usa cero para ese soporte y conserva una advertencia en los metadatos de la
ejecución. El peso `w_e` es obligatorio y debe ser finito y positivo.

## Reproducibilidad e idempotencia

Una ejecución queda determinada por:

\[
(
  projection\_id,
  artifact\_source,
  clustering\_sha256,
  formula\_version,
  minimum\_source\_edge\_weight
).
\]

El GraphML se importa como instantánea identificada por sus hashes de clustering
y de red fuente. Una ejecución repetida con la misma tupla no crea duplicados y
devuelve el resultado existente. Si cambia el GraphML, el hash cambia y se crea
otra construcción reproducible.

La meta-red es no dirigida. La fórmula no infiere causalidad, dirección,
cooperación, dependencia ni equivalencia semántica entre los nodos. Solo
contrae las aristas fuente observadas.

## Cálculo en PostgreSQL

Después de importar la instantánea, la agregación equivalente es:

```sql
SELECT
  LEAST(node_a.id, node_b.id) AS source_node_id,
  GREATEST(node_a.id, node_b.id) AS target_node_id,
  COUNT(*) AS source_edge_count,
  SUM(source_edge.weight) AS weight,
  SUM(COALESCE(source_edge.sentence_count, 0)) AS sentence_support_sum,
  SUM(COALESCE(source_edge.document_count, 0)) AS document_support_sum,
  AVG(source_edge.weight) AS mean_source_weight
FROM semantic_network_source_edges AS source_edge
JOIN semantic_node_members AS member_a
  ON member_a.canonical_id = source_edge.source_canonical_id
JOIN semantic_nodes AS node_a
  ON node_a.id = member_a.semantic_node_id
JOIN semantic_node_members AS member_b
  ON member_b.canonical_id = source_edge.target_canonical_id
JOIN semantic_nodes AS node_b
  ON node_b.id = member_b.semantic_node_id
WHERE source_edge.clustering_sha256 = :clustering_sha256
  AND node_a.clustering_sha256 = :clustering_sha256
  AND node_b.clustering_sha256 = :clustering_sha256
  AND node_a.id <> node_b.id
  AND source_edge.weight >= :minimum_source_edge_weight
GROUP BY LEAST(node_a.id, node_b.id), GREATEST(node_a.id, node_b.id);
```

El código puede usar SQLAlchemy para emitir esta consulta; la operación
matemática no depende del orden de las filas ni de un cálculo en memoria.

## Alcance del LLM

Claude no participa en la existencia de la arista, su peso, sus conteos ni su
selección. Esos valores provienen de PostgreSQL. Claude solo podría intervenir
en una etapa posterior para proponer un título o una descripción humana de una
relación ya calculada, usando sus evidencias como entrada.
