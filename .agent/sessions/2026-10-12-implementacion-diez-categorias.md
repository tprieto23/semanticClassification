# Implementación local del conjunto final de diez categorías — 12 Oct 2026

La usuaria precisó que las categorías deben quedar establecidas en el código.
La API key autentica solicitudes al proveedor; no define ni actualiza la taxonomía.

Se creó `src/categories.py` con los diez códigos exactos y una síntesis de sus
definiciones acordadas. El esquema de tool use y el parser NER admiten solo
ese conjunto. El prompt incorpora las definiciones desde el código. Se
sustituyeron 25 demostraciones del esquema anterior por diez ejemplos
ilustrativos, identificados como tales y basados en el codebook en construcción.
Esta síntesis no da por completadas las fichas metodológicas del codebook.

La canonicalización admite las diez categorías y usa el umbral conservador
existente de 96 para las categorías nuevas; CHAR y LOC mantienen 93.
La comparación continúa separada por categoría. INFRA histórico se conserva
sin conversión automática y GOV mantiene su alias anterior hacia RUL.

La red completa y el visualizador admiten las diez categorías. Se conserva
el orden de pares históricos para mantener la lectura de artefactos. La red
completa agrega INFRA solo si aparece en los datos fuente. No se redefine
la proyección histórica `prac-infra-rul-v2` ni sus particiones y meta-nodos.
El parser conserva sus límites previos de solapamiento; no se implementó
la unificación contextual de nombre completo y sigla en este cambio.

Verificación: `.venv/bin/python -m unittest discover -s tests` ejecutó
101 pruebas: 99 exitosas y 2 omitidas por dependencias opcionales de Leiden.
Las regresiones nuevas comprueban las diez etiquetas en el request simulado,
las posiciones literales, la canonicalización y preparación ORM de todas
las menciones, la red completa y lectura del visualizador (10 nodos, 45 aristas,
55 tipos posibles de par), y el aislamiento de INFRA histórico respecto de
soft_INFRA. `git diff --check` pasó.

No se invocó Claude ni se modificó una DB real. Las columnas category existentes
son Text, por lo que añadir etiquetas no requiere una migración de esquema.
Los cambios están en el workspace local; no se reiniciaron contenedores ni se
reprocesó el corpus. Esta sesión sucede a la revisión técnica anterior;
el estado vigente y las tareas se mantienen en context/.
