"""Taxonomía de extracción; las etiquetas históricas solo permiten leer legado."""

CATEGORY_DEFINITIONS = {
    "CHAR": "Persona, colectivo humano u organización que el contexto identifica con agencia, responsabilidad, representación, derechos, intereses o afectación territorial. Puede ser un actor genérico; una referencia que solo ubica un evento no basta.",
    "KNOW": "Saberes técnicos, ecológicos o tradicionales sobre el territorio, sus ecosistemas o su gestión. El texto debe identificar un saber o atribuir conocimiento; no inferirlo de una actividad.",
    "ATT": "Valores, identidades, percepciones o compromisos que el texto atribuye a actores respecto del territorio, sus ecosistemas o su gestión. No inferir una actitud de una actividad.",
    "SKILL": "Destrezas o competencias atribuidas a actores para realizar tareas técnicas, de gestión o de monitoreo. Conocer una técnica es KNOW; saber aplicarla es SKILL; aplicarla es PRAC.",
    "PRAC": "Actividades, rutinas o procesos para producir, aprovechar, conservar, restaurar, monitorear, comercializar o gestionar componentes del territorio. Pueden ser sostenibles, degradantes o ambivalentes.",
    "physical_INFRA": "Elementos construidos o instalados cuya función es permitir o condicionar acceso, movilidad, energía o conectividad tecnológica: carreteras, puentes, puertos, redes eléctricas y antenas. Su construcción o mantenimiento es PRAC.",
    "soft_INFRA": "Sistemas, instalaciones o recursos organizados que sostienen producción, aprendizaje, monitoreo o gestión de información: viveros, bancos de semillas, sistemas de monitoreo y plataformas digitales. Pueden tener componentes materiales; clasificar por su función de soporte.",
    "eco_INFRA": "Estructuras ecológicas naturales o restauradas que sostienen funciones ecosistémicas, conectividad ecológica, resiliencia, biodiversidad o regeneración: bosques primarios, corredores biológicos y humedales. La función ecológica debe estar respaldada por el contexto.",
    "RUL": "Normas, instrumentos o acuerdos que establecen derechos, obligaciones, permisos o criterios para decisiones y prácticas territoriales. Incluir planes solo cuando el contexto los presente estableciendo condiciones, responsabilidades o criterios; la palabra plan no basta.",
    "LOC": "Espacios o unidades geográficas, territoriales, administrativas o ecológicas identificados por su ubicación, extensión o delimitación. Distinguir la comunidad como lugar del colectivo CHAR, y el bosque como lugar de su función eco_INFRA.",
}
CATEGORY_CODES = tuple(CATEGORY_DEFINITIONS)
ACTIVE_CATEGORIES = frozenset(CATEGORY_CODES)

# INFRA no puede convertirse automáticamente en uno de sus tres reemplazos:
# requiere revisar la función descrita en el contexto de cada mención histórica.
LEGACY_CATEGORIES = frozenset({"INFRA"})
LEGACY_CATEGORY_ALIASES = {"GOV": "RUL"}
STORED_CATEGORIES = ACTIVE_CATEGORIES | LEGACY_CATEGORIES

# Conservar el orden de pares en los artefactos históricos (PRAC--INFRA, etc.).
STORED_CATEGORY_ORDER = ("CHAR", "LOC", "PRAC", "INFRA", "RUL") + tuple(
    category for category in CATEGORY_CODES
    if category not in {"CHAR", "LOC", "PRAC", "RUL"}
)
