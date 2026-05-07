"""
Servicio de clasificación de entidades (Fase 2 del NER).

Mapea etiquetas spaCy a las 9 categorías del proyecto + MISC_Spacy (temporal).

Decisiones del proyecto:
- Una entidad puede tener múltiples categorías → se guardan como entidades separadas
- MISC no se descartan, van a MISC_Spacy para revisión manual futura
- Casos claros → reglas deterministas
- Casos ambiguos → marcados para revisión
- NARRATIVA y PRÁCTICA: spaCy no las detecta bien, se dejan para método futuro
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


# =============================================================================
# CATEGORÍAS DEL PROYECTO
# =============================================================================

PROJECT_CATEGORIES = {
    "COMUNIDAD",
    "INSTITUCIÓN",
    "LUGAR",
    "PRÁCTICA",
    "INFRAESTRUCTURA",
    "VALOR_ECOLÓGICO",
    "NARRATIVA",
    "ACTOR",
    "ACCIÓN",
    "MISC_Spacy",  # Temporal: entidades MISC que no pudieron clasificarse
}

# =============================================================================
# MAPEO BASE: spaCy → categorías posibles
# =============================================================================

SPACY_TO_CATEGORIES = {
    "ORG": ["INSTITUCIÓN", "COMUNIDAD"],
    "LOC": ["LUGAR", "INSTITUCIÓN"],
    "GPE": ["LUGAR", "INSTITUCIÓN"],
    "PER": ["ACTOR", "COMUNIDAD"],
    "MISC": ["MISC_Spacy"],  # Se revisan manualmente o con heurísticas adicionales
    "PRODUCT": ["INFRAESTRUCTURA", "PRÁCTICA", "MISC_Spacy"],
    "EVENT": ["ACCIÓN", "MISC_Spacy"],
    "WORK_OF_ART": ["NARRATIVA", "MISC_Spacy"],
}

# =============================================================================
# REGLAS DE REFINAMIENTO: keywords que inclinan la balanza
# =============================================================================

# Si la entidad contiene alguna de estas palabras, se clasifica así
KEYWORD_RULES = {
    # COMUNIDAD
    "COMUNIDAD": [
        r"\bcomunidad\b", r"\basamblea\b", r"\bplataforma\b",
        r"\bred\s+de\b", r"\bcooperativa\b", r"\basociación\b",
        r"\bmesas?\b", r"\bescuelas?\s+de\b", r"\bgrupos?\b",
        r"\bACOPAGRO\b",  # Cooperativa de pequeños productores
    ],
    # INSTITUCIÓN
    "INSTITUCIÓN": [
        r"\bministerio\b", r"\bdirección\s+general\b", r"\balcaldía\b",
        r"\bfundación\b", r"\binstituto\b", r"\buniversidad\b",
        r"\bcorporación\b", r"\bempresa\b", r"\bgobierno\b",
        r"\bproyecto\b", r"\bprograma\b", r"\bconsorcio\b",
        r"\bsecretaría\b", r"\boficina\b", r"\bWWF\b",
        r"\bTFA\b", r"\bUK\s+PACT\b", r"\bGlobal\s+Forest\s+Watch\b",
        r"\bEarthworm\b", r"\bProforest\b", r"\bClimate\s+Group\b",
        r"\bEarth\s+Innovation\b", r"\bClimate\s+Focus\b",
        r"\bLutheran\s+World\b", r"\bKaoka\b", r"\bROMEX\b",
        r"\bADEX\b", r"\bAPPCACAO\b", r"\bCIAT\b",
        r"\bBioversity\b", r"\bUSAID\b", r"\bMIDAGRI\b",
        r"\bFAO\b", r"\bGRSB\b",
        r"\bCoalición\s+por\s+una\s+Producción\s+Sostenible\b",
        r"\bAlianza\s+por\s+una\s+Ganadería\s+Regenerativa\b",
        r"\bAGRAP\b",
        # Añadidos tras revisión manual
        r"\bTropical\s+Forest\s+Alliance\b",
        r"\bThe\s+Nature\s+Conservancy\b", r"\bTNC\b",
        r"\bMINAM\b", r"\bMinam\b",
        r"\bSolidaridad\s+Network\b",
        r"\bCooperativa\s+Agraria\s+CP\s+Cacao\b",
        r"\bLandScale\b",
    ],
    # LUGAR
    "LUGAR": [
        r"\bdepartamento\s+de\b", r"\bregión\b", r"\bprovincia\b",
        r"\bdistrito\b", r"\bvereda\b", r"\brío\b",
        r"\bmontaña\b", r"\bvalle\b", r"\bselva\b",
        r"\bAmazonía\b", r"\bAmazónica\b", r"\bPerú\b",
        r"\bColombia\b", r"\bMéxico\b", r"\bBolivia\b",
        r"\bSan\s+Martín\b", r"\bUcayali\b", r"\bMadre\s+de\s+Dios\b",
        r"\bHuallaga\b", r"\bBellavista\b", r"\bPicota\b",
        r"\bCodo\s+del\s+Pozuzo\b", r"\bTocache\b", r"\bIxtapa\b",
        r"\bPuerto\s+Vallarta\b", r"\bJalisco\b",
        r"\bMariscal\s+Cáceres\b", r"\bLoreto\b",
        r"\bpaisaje\b", r"\bcuenca\b", r"\bhacienda\b",
        r"\bfinca\b", r"\bbosque\b", r"\bparque\b",
    ],
    # ACTOR (personas con roles)
    "ACTOR": [
        r"\bministros?\b", r"\bdirector\b", r"\bcoordinador\b",
        r"\blíder\b", r"\bfuncionario\b", r"\binvestigador\b",
        r"\bautor\b", r"\brevisor\b", r"\beditor\b",
        r"\bproductor\b", r"\bganadero\b", r"\bpresidente\b",
        r"\bJorge\s+Sáenz\b", r"\bNelson\s+Gutiérrez\b",
        r"\bMaricarmen\s+Brenis\b", r"\bDavid\s+Parra\b",
        r"\bCarlos\s+Roque\b", r"\bEthel\s+Huamán\b",
    ],
    # PRÁCTICA
    "PRÁCTICA": [
        r"\bpesca\b", r"\btrueque\b", r"\briego\b",
        r"\bsiembra\b", r"\bcosecha\b", r"\bmanejo\b",
        r"\bconservación\b", r"\brestauración\b", r"\bmonitoreo\b",
        r"\btrazabilidad\b", r"\bcertificación\b",
    ],
    # INFRAESTRUCTURA
    "INFRAESTRUCTURA": [
        r"\bpuente\b", r"\bescuela\b", r"\brepresa\b",
        r"\bcarretera\b", r"\bvía\b", r"\bcanal\b",
        r"\bplanta\b", r"\bcentral\b", r"\btorre\b",
    ],
    # VALOR_ECOLÓGICO
    "VALOR_ECOLÓGICO": [
        r"\bbosque\s+nativo\b", r"\bespecie\s+endémica\b",
        r"\bfuente\s+de\s+agua\b", r"\bhumedal\b",
        r"\bárea\s+protegida\b", r"\breserva\b",
        r"\bbiodiversidad\b", r"\becosistema\b",
    ],
    # NARRATIVA
    "NARRATIVA": [
        r"\bdesarrollo\s+sostenible\b", r"\bjusticia\s+ambiental\b",
        r"\bdespojo\b", r"\bconservación\b", r"\bsostenibilidad\b",
        r"\bdeforestación\b", r"\bno\s+deforestación\b",
        r"\bcambio\s+climático\b", r"\bproducción\s+sostenible\b",
        # Añadidos tras revisión manual
        r"\bPlan\s+Nacional\s+para\s+el\s+Desarrollo\s+de\s+la\s+Cadena\s+de\s+Valor\s+de\s+Cacao\b",
        r"\bPolítica\s+Nacional\s+Forestal\b",
        r"\bLey\s+Forestal\b",
        r"\bRevolución\s+Productiva\b",
        r"\bBosques\s+conservados\s+y\s+restaurados\b",
        r"\bFomento\s+de\s+la\s+ganadería\b",
        r"\bGanadería\s+Sostenible\b",
        r"\bProducción\s+Sostenible\b",
        r"\bAgroPerú\s+y\s+Agroideas\b",
    ],
    # ACCIÓN
    "ACCIÓN": [
        r"\bconsulta\s+previa\b", r"\bprotesta\b",
        r"\bmesa\s+de\s+negociación\b", r"\bacuerdo\b",
        r"\bcompromiso\b", r"\bplan\s+de\s+acción\b",
        r"\btaller\b", r"\bcapacitación\b",
    ],
}

# Palabras que DESCARTAN una categoría (falsos positivos)
EXCLUSION_RULES = {
    "LUGAR": [
        r"\bProducción\s+Sostenible\b",  # "Coalición por una Producción Sostenible" no es lugar
        r"\bGanadería\s+Regenerativa\b",  # no es lugar
        r"\bProforest\b",  # es institución, no lugar
        r"\bWWF\b",  # es institución
    ],
}


# =============================================================================
# FUNCIÓN DE CLASIFICACIÓN
# =============================================================================

def classify_entity(text: str, spacy_label: str, context: str = "") -> str:
    """
    Clasifica una entidad extraída por spaCy en una de las 9 categorías del proyecto
    o en MISC_Spacy si no puede clasificarse.

    Returns:
        Una de: COMUNIDAD, INSTITUCIÓN, LUGAR, PRÁCTICA, INFRAESTRUCTURA,
                VALOR_ECOLÓGICO, NARRATIVA, ACTOR, ACCIÓN, MISC_Spacy
    """
    text_lower = text.lower()
    text_original = text

    # -------------------------------------------------------------------------
    # Paso 0: Protección contra falsos positivos de spaCy
    # -------------------------------------------------------------------------
    # Palabras comunes que spaCy etiqueta mal
    COMMON_FALSE_POSITIVES = {
        "según", "además", "segun", "ganadería", "ganaderia",
        "amazónico", "amazonico", "peruano", "peruana",
        "madre", "dios", "uso", "potencial", "bovina",
        "por otro lado", "sin embargo", "de igual modo",
        "a continuación", "en cuanto a", "al respecto",
        "por un lado", "por lo tanto", "de igual manera",
        "así mismo", "asimismo", "no obstante",
        "con fines de", "a través de", "en función de",
        "con el objetivo de", "con el fin de",
    }
    if text_lower in COMMON_FALSE_POSITIVES:
        return "MISC_Spacy"

    # -------------------------------------------------------------------------
    # Paso 1: MISC de spaCy → MISC_Spacy por defecto (revisión manual futura)
    # -------------------------------------------------------------------------
    if spacy_label == "MISC":
        # PERO: si coincide con alguna keyword específica, clasificar
        for category, patterns in KEYWORD_RULES.items():
            if category == "MISC_Spacy":
                continue
            for pattern in patterns:
                if re.search(pattern, text_original, re.IGNORECASE):
                    # Verificar exclusiones
                    excluded = False
                    for excl_pattern in EXCLUSION_RULES.get(category, []):
                        if re.search(excl_pattern, text_original, re.IGNORECASE):
                            excluded = True
                            break
                    if not excluded:
                        return category
        return "MISC_Spacy"

    # -------------------------------------------------------------------------
    # Paso 2: Aplicar reglas de keywords a ORG, LOC, GPE, PER, etc.
    # -------------------------------------------------------------------------
    # Primero verificamos si hay una regla de keyword muy fuerte
    for category, patterns in KEYWORD_RULES.items():
        for pattern in patterns:
            if re.search(pattern, text_original, re.IGNORECASE):
                # Verificar exclusiones
                excluded = False
                for excl_pattern in EXCLUSION_RULES.get(category, []):
                    if re.search(excl_pattern, text_original, re.IGNORECASE):
                        excluded = True
                        break
                if not excluded:
                    return category

    # -------------------------------------------------------------------------
    # Paso 3: Mapeo por defecto según etiqueta spaCy
    # -------------------------------------------------------------------------
    default_mapping = {
        "ORG": "INSTITUCIÓN",
        "LOC": "LUGAR",
        "GPE": "LUGAR",
        "PER": "ACTOR",
        "PRODUCT": "INFRAESTRUCTURA",
        "EVENT": "ACCIÓN",
        "WORK_OF_ART": "NARRATIVA",
    }

    return default_mapping.get(spacy_label, "MISC_Spacy")


# =============================================================================
# ENTIDAD CLASIFICADA
# =============================================================================

@dataclass
class ClassifiedEntity:
    """Entidad con su clasificación en categorías del proyecto."""

    text: str
    spacy_label: str
    project_category: str
    start: int
    end: int
    context: str = ""
    sentence: str = ""
    lang: str = "unknown"

    def __post_init__(self):
        if self.project_category not in PROJECT_CATEGORIES:
            raise ValueError(
                f"Categoría '{self.project_category}' no válida. "
                f"Use una de: {PROJECT_CATEGORIES}"
            )
