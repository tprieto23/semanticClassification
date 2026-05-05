"""
Servicio de extracción de entidades nombradas (NER) con spaCy.

Fase 2: Extracción + Clasificación en categorías del proyecto.

Estrategia para corpus bilingüe (español / inglés):
- Detectar idioma predominante del texto con langdetect.
- Procesar con el modelo spaCy correspondiente.
- Extraer entidades con contexto.
- Clasificar en categorías del proyecto usando entity_classifier.
"""

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import spacy
from langdetect import detect, LangDetectException

from src.services.entity_classifier import classify_entity

logger = logging.getLogger(__name__)

# Modelos spaCy por idioma
SPACY_MODELS = {
    "es": "es_core_news_sm",
    "en": "en_core_web_sm",
}

# Etiquetas NER que nos interesan (universal en es/en spaCy)
TARGET_LABELS = {"PER", "ORG", "LOC", "GPE", "MISC", "PRODUCT", "EVENT", "WORK_OF_ART"}

# Palabras/frases que suelen ser títulos/secciones y no entidades reales.
# Se filtran si la entidad coincide exactamente (case-insensitive).
STRUCTURAL_WORDS = {
    # Español
    "plan", "créditos", "crédito", "introducción", "introduccion",
    "contenido", "índice", "indice", "resumen", "agradecimientos",
    "reconocimientos", "proyecto", "programa", "informe", "reporte",
    "estudio", "análisis", "analisis", "marco", "contexto",
    "objetivos", "objetivo", "metodología", "metodologia",
    "resultados", "conclusiones", "bibliografía", "bibliografia",
    "referencias", "anexos", "anexo", "glosario", "acrónimos",
    "acronimos", "siglas", "cuadro", "cuadros", "tabla", "tablas",
    "figura", "gráfico", "grafico", "gráficos", "graficos",
    "acciones", "acción", "accion", "ejes", "eje",
    "plan de acción", "plan de accion", "plan de trabajo",
    "alianza", "coalición", "coalcion", "fomento", "programa",
    # Inglés
    "credits", "credit", "introduction", "contents", "index",
    "summary", "abstract", "acknowledgements", "acknowledgments",
    "project", "program", "report", "study", "analysis",
    "framework", "context", "objectives", "objective",
    "methodology", "results", "conclusions", "bibliography",
    "references", "annexes", "annex", "glossary", "acronyms",
    "abbreviations", "table", "tables", "figure", "figures",
    "graph", "chart", "actions", "action", "axes", "axis",
    "action plan", "work plan", "alliance", "coalition",
}

# Idiomas soportados
SUPPORTED_LANGS = set(SPACY_MODELS.keys())

# Cache de modelos cargados
_model_cache: dict = {}


@dataclass
class ExtractedEntity:
    """Entidad extraída de un documento."""

    text: str
    label: str  # etiqueta spaCy original
    project_category: str  # categoría del proyecto (Fase 2)
    start: int  # posición de caracter en el texto
    end: int
    context: str = ""  # párrafo/líneas alrededor
    sentence: str = ""  # oración completa donde aparece
    lang: str = "unknown"


def _ensure_model(model_name: str) -> spacy.Language:
    """Carga un modelo spaCy; lo descarga si no existe."""
    try:
        return spacy.load(model_name)
    except OSError:
        logger.warning(f"Modelo {model_name} no encontrado. Descargando...")
        subprocess.run(
            [sys.executable, "-m", "spacy", "download", model_name],
            check=True,
        )
        return spacy.load(model_name)


def _get_nlp(lang: str) -> Optional[spacy.Language]:
    """Obtiene el pipeline spaCy para un idioma (con cache)."""
    if lang not in SUPPORTED_LANGS:
        logger.warning(f"Idioma '{lang}' no soportado. Modelos disponibles: {SUPPORTED_LANGS}")
        return None

    model_name = SPACY_MODELS[lang]
    if model_name not in _model_cache:
        _model_cache[model_name] = _ensure_model(model_name)
    return _model_cache[model_name]


def detect_language(text: str) -> str:
    """Detecta idioma predominante. Fallback a 'es' si falla."""
    try:
        lang = detect(text)
        if lang in SUPPORTED_LANGS:
            return lang
        # Si detecta algo cercano (ej. pt, ca, gl), asumir español
        if lang in ("pt", "ca", "gl", "it", "fr"):
            return "es"
        if lang in ("de", "nl"):
            return "en"
        logger.warning(f"Idioma detectado '{lang}' no soportado. Fallback a 'es'.")
        return "es"
    except LangDetectException:
        logger.warning("No se pudo detectar idioma. Fallback a 'es'.")
        return "es"


def _get_context(text: str, start: int, end: int, window_chars: int = 300) -> str:
    """Extrae un fragmento de texto alrededor de la entidad."""
    context_start = max(0, start - window_chars)
    context_end = min(len(text), end + window_chars)
    return text[context_start:context_end].strip()


def _get_sentence(doc: spacy.tokens.Doc, start: int, end: int) -> str:
    """Devuelve la oración (span) que contiene la entidad."""
    for sent in doc.sents:
        if sent.start_char <= start < sent.end_char:
            return sent.text.strip()
    return ""


def extract_entities(
    text: str,
    document_id: Optional[str] = None,
) -> Tuple[List[ExtractedEntity], str]:
    """
    Extrae entidades nombradas de un texto.

    Returns:
        (lista de entidades, idioma detectado)
    """
    if not text or len(text.strip()) == 0:
        return [], "unknown"

    lang = detect_language(text)
    nlp = _get_nlp(lang)
    if nlp is None:
        return [], lang

    # spaCy tiene un límite de caracteres por doc (por defecto 1M).
    # Si el texto es muy largo, lo procesamos en chunks.
    MAX_LENGTH = nlp.max_length
    if len(text) > MAX_LENGTH:
        logger.warning(
            f"Texto de {len(text)} chars excede max_length={MAX_LENGTH}. "
            f"Truncando para NER."
        )
        text = text[:MAX_LENGTH]

    doc = nlp(text)

    entities: List[ExtractedEntity] = []
    seen: set = set()

    for ent in doc.ents:
        if ent.label_ not in TARGET_LABELS:
            continue

        # Normalizar texto: strip y colapsar espacios internos
        entity_text = " ".join(ent.text.split())
        if not entity_text:
            continue

        # Filtrar falsos positivos estructurales
        if _is_structural_false_positive(entity_text):
            continue

        # Deduplicar exacto mismo texto+label+start
        key = (entity_text, ent.label_, ent.start_char)
        if key in seen:
            continue
        seen.add(key)

        context = _get_context(text, ent.start_char, ent.end_char)
        sentence = _get_sentence(doc, ent.start_char, ent.end_char)

        # Fase 2: clasificar en categorías del proyecto
        project_category = classify_entity(entity_text, ent.label_, context)

        entities.append(
            ExtractedEntity(
                text=entity_text,
                label=ent.label_,
                project_category=project_category,
                start=ent.start_char,
                end=ent.end_char,
                context=context,
                sentence=sentence,
                lang=lang,
            )
        )

    logger.info(
        f"Documento {document_id}: {len(entities)} entidades extraídas "
        f"(idioma={lang})"
    )
    return entities, lang


def _is_structural_false_positive(text: str) -> bool:
    """
    Detecta si una entidad es un falso positivo estructural
    (título de sección, encabezado, etc.) y no una entidad real.
    """
    stripped = text.strip()
    lower = stripped.lower()

    # Coincidencia exacta case-insensitive con palabras/frases estructurales
    if lower in STRUCTURAL_WORDS:
        return True

    # Si son 1-2 caracteres
    if len(stripped) <= 2:
        return True

    # Si es solo números o puntuación
    if stripped.replace(".", "").replace(",", "").replace("-", "").isdigit():
        return True

    return False


def normalize_entity_name(text: str) -> str:
    """
    Normaliza el nombre de una entidad para deduplicación.
    - Elimina espacios sobrantes
    - Lowercase para comparación (pero NO para display)
    - Elimina artículos iniciales comunes en español
    """
    text = text.strip()
    # Artículos iniciales comunes que no aportan a la identidad
    lower = text.lower()
    for prefix in ("el ", "la ", "los ", "las ", "un ", "una ", "unos ", "unas "):
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text
