# Nota de continuidad — construcción del codebook

Fecha de registro: 9 de octubre de 2026.

## Qué se acordó

El documento de trabajo es
[codebook_en_construccion.md](../../codebook_en_construccion.md).
Se conservaron sin modificar el borrador previo y la implementación de la API.

Se aprobaron las definiciones operativas de las diez categorías, con estos
códigos exactos: `CHAR`, `KNOW`, `ATT`, `SKILL`, `PRAC`, `physical_INFRA`,
`soft_INFRA`, `eco_INFRA`, `RUL` y `LOC`. Esto no equivale a haber completado
todos los criterios de anotación de sus fichas.

Acuerdos especialmente importantes:

- CHAR incluye personas individuales y actores colectivos.
- KNOW puede anotarse sin que el texto identifique al portador del saber.
- Conocer se distingue de saber ejecutar (SKILL) y de la actividad (PRAC).
  No se infieren automáticamente actitudes ni habilidades por observar una
  actividad.
- PRAC admite prácticas sostenibles, degradantes o ambivalentes.
- La infraestructura se clasifica por su función contextual, no solo por su
  materialidad. Viveros, bancos de semillas, sistemas de monitoreo y plataformas
  digitales quedaron como referencias de soft_INFRA. Bosque primario y
  corredores, cuando cumplen funciones ecológicas, se evalúan como eco_INFRA.
- LOC identifica el espacio; CHAR, el colectivo; eco_INFRA, la estructura
  por su función ecológica. Estas distinciones no resuelven todavía la política
  general de etiquetas múltiples o fragmentos solapados.

El informe «Análisis de Sensibilidad Participativo en Tambopata» enriquece
el marco conceptual y los lineamientos; no sustituye las diez categorías ni
autoriza a interpretar coocurrencia como causalidad.

## Cómo retomar

El estado vigente está en
[PROJECT_CONTEXT.md](../context/PROJECT_CONTEXT.md) y el punto exacto de
reanudación y los pendientes en [tasks.md](../context/tasks.md), bajo
«Trabajo actual: codebook».

Al volver, mantener respuestas breves, avanzar paso a paso y solicitar
acuerdo sobre las nuevas propuestas. No dar por completado el codebook ni
por implementado su nuevo esquema en la API.
