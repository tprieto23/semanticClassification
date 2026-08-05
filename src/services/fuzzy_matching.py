import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from src.models.canonical_entities import CanonicalEntity
from src.models.canonical_entities_repo import CanonicalEntityRepo

VALID_CATEGORIES = frozenset({"CHAR", "LOC", "INFRA", "GOV", "PRAC"})
FUZZY_THRESHOLDS = {
    "CHAR": 93.0,
    "LOC": 93.0,
    "INFRA": 96.0,
    "GOV": 96.0,
    "PRAC": 96.0,
}
MIN_SCORE_MARGIN = 5.0
MIN_FUZZY_LENGTH = 5

_DASHES = str.maketrans("‐‑‒–—―", "------")
_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


class FuzzyMatchingDataError(ValueError):
    pass


@dataclass(frozen=True)
class MatchDecision:
    canonical_entity: CanonicalEntity
    match_type: str
    score: float
    second_score: float | None


def normalizar_nombre(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKC", texto)
    normalizado = normalizado.translate(_DASHES).translate(_QUOTES)
    normalizado = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", normalizado)
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", normalizado).strip().casefold()


def _nombre_canonico(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip()


def _puntaje(nombre: str, candidato: str) -> float:
    return max(
        float(fuzz.ratio(nombre, candidato)),
        float(fuzz.token_sort_ratio(nombre, candidato)),
    )


def _validar_mencion(mencion: dict[str, Any], index: int) -> None:
    if not isinstance(mencion, dict):
        raise FuzzyMatchingDataError(f"La entidad {index} no es un objeto JSON")

    texto = mencion.get("text")
    categoria = mencion.get("category")
    if not isinstance(texto, str) or not texto.strip():
        raise FuzzyMatchingDataError(f"La entidad {index} no tiene text válido")
    if categoria not in VALID_CATEGORIES:
        raise FuzzyMatchingDataError(
            f"La entidad {index} tiene category inválida: {categoria!r}"
        )
    if not isinstance(mencion.get("start"), int) or not isinstance(
        mencion.get("end"), int
    ):
        raise FuzzyMatchingDataError(
            f"La entidad {index} no tiene offsets enteros válidos"
        )


def asociar_entidades_canonicas(
    db: Session, menciones: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    canonicas_por_categoria: dict[str, list[CanonicalEntity]] = defaultdict(list)
    normalizados: dict[object, str] = {}

    for canonica in CanonicalEntityRepo.leer_todas(db):
        canonicas_por_categoria[canonica.category].append(canonica)
        normalizados[canonica.id] = normalizar_nombre(canonica.canonical_name)

    resultado: list[dict[str, Any]] = []
    estadisticas = {"exact": 0, "fuzzy": 0, "new": 0}

    for index, mencion in enumerate(menciones):
        _validar_mencion(mencion, index)
        texto = mencion["text"]
        categoria = mencion["category"]
        nombre_normalizado = normalizar_nombre(texto)
        candidatos = canonicas_por_categoria[categoria]

        decision = _decidir_canonica(
            db,
            texto,
            categoria,
            nombre_normalizado,
            candidatos,
            normalizados,
        )
        estadisticas[decision.match_type] += 1

        mencion_asociada = dict(mencion)
        mencion_asociada["canonical_id"] = decision.canonical_entity.id
        mencion_asociada["canonical_name"] = decision.canonical_entity.canonical_name
        mencion_asociada["match_type"] = decision.match_type
        mencion_asociada["match_score"] = round(decision.score, 2)
        mencion_asociada["second_match_score"] = (
            round(decision.second_score, 2)
            if decision.second_score is not None
            else None
        )
        resultado.append(mencion_asociada)

    return resultado, estadisticas


def _decidir_canonica(
    db: Session,
    texto: str,
    categoria: str,
    nombre_normalizado: str,
    candidatos: list[CanonicalEntity],
    normalizados: dict[object, str],
) -> MatchDecision:
    for candidata in candidatos:
        if normalizados[candidata.id] == nombre_normalizado:
            return MatchDecision(candidata, "exact", 100.0, None)

    puntajes = sorted(
        (
            (_puntaje(nombre_normalizado, normalizados[candidata.id]), candidata)
            for candidata in candidatos
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    mejor_puntaje = puntajes[0][0] if puntajes else 0.0
    segundo_puntaje = puntajes[1][0] if len(puntajes) > 1 else None
    margen = mejor_puntaje - segundo_puntaje if segundo_puntaje is not None else 100.0

    if (
        len(nombre_normalizado) >= MIN_FUZZY_LENGTH
        and mejor_puntaje >= FUZZY_THRESHOLDS[categoria]
        and margen >= MIN_SCORE_MARGIN
    ):
        return MatchDecision(puntajes[0][1], "fuzzy", mejor_puntaje, segundo_puntaje)

    nueva = CanonicalEntityRepo.crear(
        db,
        canonical_name=_nombre_canonico(texto),
        category=categoria,
    )
    candidatos.append(nueva)
    normalizados[nueva.id] = nombre_normalizado
    return MatchDecision(nueva, "new", 0.0, mejor_puntaje or None)
