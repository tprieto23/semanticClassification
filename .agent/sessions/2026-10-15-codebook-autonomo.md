# Revisión editorial del codebook y prompt — 15 Oct 2026

La usuaria pidió instrucciones directas y autónomas para NER, sin referencias
a quien acordó las reglas ni invitaciones a consultar documentos externos.
Se retiró la narrativa de elaboración y los estados históricos de las fichas;
se conservaron las diez definiciones, ejemplos, propuestas y pendientes.
La revisión no aprueba propuestas ni completa la validación metodológica.
El prompt explicita el uso exclusivo de las instrucciones y el texto recibido.

La revisión de cobertura conceptual de las categorías, retirada de 2.5.1,
es una actividad de validación del codebook, no una instrucción para NER.

## Antecedente bibliográfico retirado del codebook operativo

Este registro conserva la procedencia metodológica; no se envía al modelo
ni constituye una fuente que NER deba consultar.


### B.1. Análisis de Sensibilidad Participativo en Tambopata

- Procedencia: texto proporcionado por la usuaria en la conversación.
- Ejercicio reportado: taller del 13 y 14 de mayo de 2026 y devolución del
  12 de agosto de 2026, en Puerto Maldonado.
- Uso en el codebook: fortalecer y enriquecer el marco conceptual y los
  lineamientos que se traducirán en reglas operativas para el procesamiento
  de la API.
- Autoría, versión y ubicación del documento de referencia: [Pendiente].

[Pendiente: registrar las demás fuentes y decisiones metodológicas adoptadas].

## Edición posterior — fichas de PRAC hasta LOC

La usuaria pidió completar directamente las seis fichas restantes de la
sección 5. Se desarrollaron criterios de inclusión, evidencia, exclusiones,
delimitación y ejemplos, preservando las definiciones y acuerdos previos.
Se resolvió el tratamiento de actividades propuestas o negadas, la clasificación
funcional del equipamiento, la evidencia ecológica, las reglas informales y
los fragmentos de reglas sin denominación, y la identificación espacial.
Las definiciones de ejecución se actualizaron en `src/categories.py`. El ejemplo
de plataforma digital ahora identifica su función informacional en la propia
denominación. No se cambió el contrato de salida, el parser ni las etapas de
fuzzy matching y red. Los pendientes generales de anotación y validación se
mantienen; completar estas fichas no equivale a validar resultados con Claude.
