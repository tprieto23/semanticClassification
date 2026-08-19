import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from src.models.canonical_entities import CanonicalEntity
from src.models.canonical_entities_repo import CanonicalEntityRepo
from src.models.canonical_entity_aliases import CanonicalEntityAlias
from src.models.canonical_entity_aliases_repo import CanonicalEntityAliasRepo

VALID_CATEGORIES = frozenset({"CHAR", "LOC", "INFRA", "GOV", "PRAC"})
RESOLUTION_VERSION = "deterministic-v2"
FUZZY_THRESHOLDS = {
    "CHAR": 93.0,
    "LOC": 93.0,
    "INFRA": 96.0,
    "GOV": 96.0,
    "PRAC": 96.0,
}
MIN_SCORE_MARGIN = 5.0
MIN_FUZZY_LENGTH = 5
MATCH_TYPES = (
    "exact",
    "morphology",
    "person_alias",
    "stored_alias",
    "person_name",
    "fuzzy",
    "new",
)

_DASHES = str.maketrans("‐‑‒–—―", "------")
_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
_WORD_RE = re.compile(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.UNICODE)

# La morfología solo se aplica cuando el primer sustantivo pertenece a este
# vocabulario controlado. No se singularizan indiscriminadamente nombres
# propios, instituciones ni lugares.
_GENERIC_ACTOR_HEADS = frozenset(
    {
        "abogada",
        "abogado",
        "actor",
        "agricultor",
        "agricultora",
        "autoridad",
        "cargador",
        "carretillero",
        "cauchero",
        "chambero",
        "chichiquero",
        "colega",
        "colono",
        "comerciante",
        "companero",
        "comprador",
        "comunidad",
        "contador",
        "dirigente",
        "docente",
        "empresario",
        "entrevistado",
        "espanol",
        "facturador",
        "familiar",
        "funcionario",
        "hijo",
        "hispano",
        "indigena",
        "ingeniero",
        "joyera",
        "joyero",
        "machetero",
        "miembro",
        "minera",
        "minero",
        "motorista",
        "mujer",
        "nativo",
        "obrera",
        "obrero",
        "padre",
        "paisano",
        "persona",
        "policia",
        "poblacion",
        "presidenta",
        "presidente",
        "propietaria",
        "propietario",
        "prostituta",
        "pueblo",
        "recolector",
        "serrano",
        "sociedad",
        "talador",
        "tecnica",
        "tecnico",
        "titular",
        "trabajador",
        "transportista",
        "tripulante",
        "varon",
    }
)
_SINGULAR_IRREGULAR = {
    "actores": "actor",
    "autoridades": "autoridad",
    "comunidades": "comunidad",
    "hombres": "hombre",
    "jóvenes": "joven",
    "mujeres": "mujer",
    "padres": "padre",
    "personas": "persona",
    "poblaciones": "población",
    "presidentes": "presidente",
}
_INFLECTION_BOUNDARIES = frozenset(
    {"a", "al", "con", "de", "del", "en", "para", "por", "sin"}
)
_GENERIC_BLOCKERS = frozenset({"llamado", "llamada"})
_COMPLEX_CONNECTORS = frozenset({"o", "que", "u", "y"})

_PERSON_PARTICLES = frozenset({"de", "del", "la", "las", "los", "y"})
_PERSON_BLOCKERS = frozenset(
    {
        "academia",
        "amazonas",
        "asociacion",
        "banco",
        "comite",
        "comunidad",
        "congreso",
        "corporacion",
        "direccion",
        "empresa",
        "estado",
        "estados",
        "federacion",
        "frente",
        "gobierno",
        "goremad",
        "iglesia",
        "imperio",
        "inei",
        "madre",
        "midagri",
        "mincul",
        "minem",
        "ministerio",
        "mineria",
        "organizacion",
        "peru",
        "policia",
        "proyecto",
        "pueblo",
        "red",
        "republica",
        "sa",
        "sac",
        "sociedad",
        "universidad",
        "virreinato",
        "eirl",
        "inc",
        "ltda",
    }
)


class FuzzyMatchingDataError(ValueError):
    pass


@dataclass(frozen=True)
class MatchDecision:
    canonical_entity: CanonicalEntity
    match_type: str
    score: float
    second_score: float | None
    reason: str


@dataclass(frozen=True)
class MentionPlan:
    preferred_name: str
    comparison_key: str
    strategy: str
    confidence: float
    details: dict[str, Any]


@dataclass(frozen=True)
class PersonForm:
    index: int
    text: str
    normalized: str
    tokens: tuple[str, ...]


def normalizar_nombre(texto: str) -> str:
    """Normaliza una cadena para compararla, sin modificar el texto fuente."""
    normalizado = unicodedata.normalize("NFKC", texto)
    normalizado = normalizado.translate(_DASHES).translate(_QUOTES)
    normalizado = "".join(
        caracter
        for caracter in unicodedata.normalize("NFKD", normalizado)
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", normalizado).strip().casefold()


def canonicalizar_actor_generico(texto: str) -> str | None:
    """Devuelve una forma singular segura para ciertos actores genéricos CHAR.

    El resultado es deliberadamente conservador: si la expresión contiene una
    estructura compleja, un nombre propio interno o un sustantivo no reconocido,
    no se aplica esta regla.
    """
    limpio = _nombre_canonico(texto)
    if not limpio or re.search(r"\d|[,;:()&/@]", limpio):
        return None

    palabras = limpio.translate(_DASHES).split()
    if not palabras or any(not _WORD_RE.fullmatch(palabra) for palabra in palabras):
        return None

    todo_mayusculas = limpio.isupper()
    if not todo_mayusculas and any(palabra[0].isupper() for palabra in palabras[1:]):
        return None

    palabras_minusculas = [palabra.casefold() for palabra in palabras]
    if any(normalizar_nombre(palabra) in _GENERIC_BLOCKERS for palabra in palabras):
        return None
    if any(normalizar_nombre(palabra) in _COMPLEX_CONNECTORS for palabra in palabras):
        return None

    primera_singular = _singularizar_token(palabras_minusculas[0])
    if normalizar_nombre(primera_singular) not in _GENERIC_ACTOR_HEADS:
        return None

    resultado = [primera_singular]
    flexionar = True
    for palabra in palabras_minusculas[1:]:
        normalizada = normalizar_nombre(palabra)
        if normalizada in _INFLECTION_BOUNDARIES:
            flexionar = False
        resultado.append(_singularizar_token(palabra) if flexionar else palabra)

    return " ".join(resultado)


def _singularizar_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token).casefold()
    if token in _SINGULAR_IRREGULAR:
        return _SINGULAR_IRREGULAR[token]
    if len(token) <= 3:
        return token
    if token.endswith("iones") and len(token) > 6:
        return f"{token[:-5]}ión"
    if token.endswith("ces") and len(token) > 4:
        return f"{token[:-3]}z"
    if token.endswith(("antes", "entes")) and len(token) > 5:
        return token[:-1]
    if token.endswith("es") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and token[-2] in "aeiouáéíóú":
        return token[:-1]
    return token


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
    if mencion["start"] < 0 or mencion["end"] < mencion["start"]:
        raise FuzzyMatchingDataError(f"La entidad {index} tiene offsets inconsistentes")


def asociar_entidades_canonicas(
    db: Session,
    menciones: list[dict[str, Any]],
    document_id: UUID | str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Resuelve todas las menciones después de analizar el documento completo."""
    for index, mencion in enumerate(menciones):
        _validar_mencion(mencion, index)

    source_document_id = _normalizar_document_id(document_id)
    canonicas = CanonicalEntityRepo.leer_todas(db)
    aliases = CanonicalEntityAliasRepo.leer_todos(db)

    canonicas_por_categoria: dict[str, list[CanonicalEntity]] = defaultdict(list)
    normalizados: dict[object, str] = {}
    canonicas_por_id: dict[object, CanonicalEntity] = {}
    for canonica in canonicas:
        canonicas_por_categoria[canonica.category].append(canonica)
        normalizados[canonica.id] = normalizar_nombre(canonica.canonical_name)
        canonicas_por_id[canonica.id] = canonica

    aliases_por_categoria = _indexar_aliases(aliases, canonicas_por_id)
    planes = _planear_menciones(menciones)

    grupos: dict[tuple[str, str], list[int]] = defaultdict(list)
    for index, (mencion, plan) in enumerate(zip(menciones, planes, strict=True)):
        grupos[(mencion["category"], plan.comparison_key)].append(index)

    decisiones: dict[int, MatchDecision] = {}
    for (categoria, comparison_key), indices in grupos.items():
        plan_representativo = _seleccionar_plan_representativo(
            [planes[index] for index in indices]
        )
        decision = _decidir_canonica(
            db=db,
            texto_preferido=plan_representativo.preferred_name,
            categoria=categoria,
            nombre_normalizado=comparison_key,
            estrategia=plan_representativo.strategy,
            candidatos=canonicas_por_categoria[categoria],
            normalizados=normalizados,
            aliases_por_categoria=aliases_por_categoria,
        )
        for index in indices:
            decisiones[index] = decision

    resultado: list[dict[str, Any]] = []
    estadisticas = Counter({match_type: 0 for match_type in MATCH_TYPES})
    aliases_registrados: set[tuple[object, str]] = set()

    for index, mencion in enumerate(menciones):
        plan = planes[index]
        decision = decisiones[index]
        match_type, score = _metodo_para_mencion(mencion, plan, decision)
        estadisticas[match_type] += 1

        detalles = {
            "preferred_name": plan.preferred_name,
            "comparison_key": plan.comparison_key,
            "strategy": plan.strategy,
            "reason": decision.reason,
            "base_match_type": decision.match_type,
            **plan.details,
        }
        mencion_asociada = dict(mencion)
        mencion_asociada["canonical_id"] = decision.canonical_entity.id
        mencion_asociada["canonical_name"] = decision.canonical_entity.canonical_name
        mencion_asociada["match_type"] = match_type
        mencion_asociada["match_score"] = round(score, 2)
        mencion_asociada["second_match_score"] = (
            round(decision.second_score, 2)
            if decision.second_score is not None
            else None
        )
        mencion_asociada["resolution_version"] = RESOLUTION_VERSION
        mencion_asociada["resolution_details"] = detalles
        resultado.append(mencion_asociada)

        alias_normalizado = normalizar_nombre(mencion["text"])
        alias_key = (decision.canonical_entity.id, alias_normalizado)
        if alias_key not in aliases_registrados:
            CanonicalEntityAliasRepo.registrar(
                db,
                canonical_id=decision.canonical_entity.id,
                alias_text=_nombre_canonico(mencion["text"]),
                normalized_alias=alias_normalizado,
                resolution_method=match_type,
                source_document_id=source_document_id,
            )
            aliases_registrados.add(alias_key)

    return resultado, dict(estadisticas)


def _normalizar_document_id(document_id: UUID | str | None) -> UUID | None:
    if document_id is None or isinstance(document_id, UUID):
        return document_id
    try:
        return UUID(document_id)
    except (TypeError, ValueError) as exc:
        raise FuzzyMatchingDataError("document_id no es un UUID válido") from exc


def _indexar_aliases(
    aliases: list[CanonicalEntityAlias],
    canonicas_por_id: dict[object, CanonicalEntity],
) -> dict[tuple[str, str], set[object]]:
    indice: dict[tuple[str, str], set[object]] = defaultdict(set)
    for alias in aliases:
        canonica = canonicas_por_id.get(alias.canonical_id)
        if canonica is not None:
            indice[(canonica.category, alias.normalized_alias)].add(alias.canonical_id)
    return indice


def _planear_menciones(menciones: list[dict[str, Any]]) -> list[MentionPlan]:
    planes: list[MentionPlan] = []
    for mencion in menciones:
        texto = _nombre_canonico(mencion["text"])
        actor_generico = (
            canonicalizar_actor_generico(texto)
            if mencion["category"] == "CHAR"
            else None
        )
        if actor_generico is not None:
            planes.append(
                MentionPlan(
                    preferred_name=actor_generico,
                    comparison_key=normalizar_nombre(actor_generico),
                    strategy="generic_actor",
                    confidence=100.0,
                    details={
                        "rule": "controlled_spanish_singularization",
                        "source_name": texto,
                    },
                )
            )
        else:
            planes.append(
                MentionPlan(
                    preferred_name=texto,
                    comparison_key=normalizar_nombre(texto),
                    strategy="standard",
                    confidence=100.0,
                    details={},
                )
            )

    for index, evidencia in _detectar_aliases_persona(menciones, planes).items():
        preferred_name, confidence, details = evidencia
        planes[index] = MentionPlan(
            preferred_name=preferred_name,
            comparison_key=normalizar_nombre(preferred_name),
            strategy="document_person",
            confidence=confidence,
            details=details,
        )
    return planes


def _detectar_aliases_persona(
    menciones: list[dict[str, Any]], planes: list[MentionPlan]
) -> dict[int, tuple[str, float, dict[str, Any]]]:
    formas: list[PersonForm] = []
    for index, (mencion, plan) in enumerate(zip(menciones, planes, strict=True)):
        if mencion["category"] != "CHAR" or plan.strategy == "generic_actor":
            continue
        tokens = _tokens_nombre_persona(mencion["text"])
        if tokens is not None:
            formas.append(
                PersonForm(
                    index=index,
                    text=_nombre_canonico(mencion["text"]),
                    normalized=normalizar_nombre(mencion["text"]),
                    tokens=tokens,
                )
            )

    por_normalizado: dict[str, list[PersonForm]] = defaultdict(list)
    for forma in formas:
        por_normalizado[forma.normalized].append(forma)

    anchors = {
        normalizado: ocurrencias[0]
        for normalizado, ocurrencias in por_normalizado.items()
        if _cantidad_tokens_significativos(ocurrencias[0].tokens) >= 2
    }
    if not anchors:
        return {}

    parent = {normalizado: normalizado for normalizado in anchors}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    anchor_items = list(anchors.items())
    for position, (left_key, left) in enumerate(anchor_items):
        for right_key, right in anchor_items[position + 1 :]:
            if _es_prefijo(left.tokens, right.tokens) or _es_prefijo(
                right.tokens, left.tokens
            ):
                union(left_key, right_key)

    familias: dict[str, set[str]] = defaultdict(set)
    for normalizado in anchors:
        familias[find(normalizado)].add(normalizado)

    datos_familia: list[dict[str, Any]] = []
    for keys in familias.values():
        ocurrencias = [forma for key in keys for forma in por_normalizado.get(key, [])]
        preferida = max(
            ocurrencias,
            key=lambda forma: (
                _cantidad_tokens_significativos(forma.tokens),
                len(forma.tokens),
                len(por_normalizado[forma.normalized]),
                _cantidad_acentos(forma.text),
                len(forma.text),
            ),
        )
        datos_familia.append(
            {
                "keys": keys,
                "preferred": preferida,
                "indices": {forma.index for forma in ocurrencias},
            }
        )

    # Las formas parciales se asignan solo si apuntan a una única familia.
    for forma in formas:
        if any(forma.index in familia["indices"] for familia in datos_familia):
            continue
        compatibles = [
            familia
            for familia in datos_familia
            if _es_prefijo(forma.tokens, familia["preferred"].tokens)
        ]
        if len(compatibles) == 1:
            compatibles[0]["indices"].add(forma.index)

    resultado: dict[int, tuple[str, float, dict[str, Any]]] = {}
    for familia in datos_familia:
        indices = familia["indices"]
        formas_familia = [forma for forma in formas if forma.index in indices]
        variantes = {forma.normalized for forma in formas_familia}
        if len(variantes) < 2:
            continue

        preferida: PersonForm = familia["preferred"]
        anchors_visibles = sorted(
            {
                por_normalizado[key][0].text
                for key in familia["keys"]
                if key in por_normalizado
            }
        )
        for forma in formas_familia:
            confidence = 95.0 if len(forma.tokens) == 1 else 100.0
            resultado[forma.index] = (
                preferida.text,
                confidence,
                {
                    "rule": "unique_document_name_prefix",
                    "document_anchors": anchors_visibles,
                    "source_name": forma.text,
                },
            )
    return resultado


def _tokens_nombre_persona(texto: str) -> tuple[str, ...] | None:
    limpio = _nombre_canonico(texto)
    if not limpio or re.search(r"\d|[,;:()&/@]", limpio):
        return None
    palabras = limpio.translate(_DASHES).split()
    if not 1 <= len(palabras) <= 6:
        return None
    if any(not _WORD_RE.fullmatch(palabra) for palabra in palabras):
        return None

    tokens = tuple(normalizar_nombre(palabra) for palabra in palabras)
    significativos = [
        (palabra, token)
        for palabra, token in zip(palabras, tokens, strict=True)
        if token not in _PERSON_PARTICLES
    ]
    if not significativos or any(
        not palabra[0].isupper() for palabra, _ in significativos
    ):
        return None
    if any(token in _PERSON_BLOCKERS for _, token in significativos):
        return None
    return tokens


def _cantidad_tokens_significativos(tokens: tuple[str, ...]) -> int:
    return sum(token not in _PERSON_PARTICLES for token in tokens)


def _es_prefijo(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return len(left) <= len(right) and left == right[: len(left)]


def _cantidad_acentos(texto: str) -> int:
    return sum(unicodedata.normalize("NFD", caracter) != caracter for caracter in texto)


def _seleccionar_plan_representativo(planes: list[MentionPlan]) -> MentionPlan:
    prioridad = {"generic_actor": 2, "document_person": 1, "standard": 0}
    return max(
        planes,
        key=lambda plan: (
            prioridad[plan.strategy],
            len(plan.preferred_name.split()),
            len(plan.preferred_name),
        ),
    )


def _decidir_canonica(
    *,
    db: Session,
    texto_preferido: str,
    categoria: str,
    nombre_normalizado: str,
    estrategia: str,
    candidatos: list[CanonicalEntity],
    normalizados: dict[object, str],
    aliases_por_categoria: dict[tuple[str, str], set[object]],
) -> MatchDecision:
    exactas = [
        candidata
        for candidata in candidatos
        if normalizados[candidata.id] == nombre_normalizado
    ]
    if estrategia == "generic_actor":
        exactas = [
            candidata
            for candidata in exactas
            if candidata.canonical_name == texto_preferido
        ]
    if exactas:
        candidata = _mejor_canonica_exacta(exactas, texto_preferido)
        return MatchDecision(candidata, "exact", 100.0, None, "normalized_exact_name")

    ids_alias = aliases_por_categoria.get((categoria, nombre_normalizado), set())
    if len(ids_alias) == 1 and not (
        categoria == "CHAR" and len(nombre_normalizado.split()) == 1
    ):
        canonical_id = next(iter(ids_alias))
        candidata = next((item for item in candidatos if item.id == canonical_id), None)
        if candidata is not None:
            return MatchDecision(
                candidata, "stored_alias", 100.0, None, "unique_stored_alias"
            )

    if estrategia == "generic_actor":
        return _crear_canonica(
            db,
            texto_preferido,
            categoria,
            candidatos,
            normalizados,
            reason="new_controlled_singular_form",
        )

    candidata_persona = _buscar_nombre_persona_mas_completo(
        texto_preferido, categoria, candidatos
    )
    if candidata_persona is not None:
        return MatchDecision(
            candidata_persona,
            "person_name",
            98.0,
            None,
            "unique_longer_person_name",
        )

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
        return MatchDecision(
            puntajes[0][1],
            "fuzzy",
            mejor_puntaje,
            segundo_puntaje,
            "fuzzy_threshold_and_margin",
        )

    return _crear_canonica(
        db,
        texto_preferido,
        categoria,
        candidatos,
        normalizados,
        second_score=mejor_puntaje or None,
        reason="no_safe_existing_match",
    )


def _mejor_canonica_exacta(
    candidatas: list[CanonicalEntity], texto_preferido: str
) -> CanonicalEntity:
    return max(
        candidatas,
        key=lambda candidata: (
            candidata.canonical_name == texto_preferido,
            candidata.canonical_name.casefold() == texto_preferido.casefold(),
            _cantidad_acentos(candidata.canonical_name),
            -len(candidata.canonical_name),
            str(candidata.id),
        ),
    )


def _buscar_nombre_persona_mas_completo(
    texto: str, categoria: str, candidatos: list[CanonicalEntity]
) -> CanonicalEntity | None:
    if categoria != "CHAR":
        return None
    tokens = _tokens_nombre_persona(texto)
    if tokens is None or _cantidad_tokens_significativos(tokens) < 2:
        return None

    compatibles: list[tuple[tuple[str, ...], CanonicalEntity]] = []
    for candidata in candidatos:
        candidate_tokens = _tokens_nombre_persona(candidata.canonical_name)
        if (
            candidate_tokens is not None
            and len(candidate_tokens) > len(tokens)
            and _es_prefijo(tokens, candidate_tokens)
        ):
            compatibles.append((candidate_tokens, candidata))
    nombres_compatibles = {tokens_candidata for tokens_candidata, _ in compatibles}
    if len(nombres_compatibles) != 1:
        return None
    return _mejor_canonica_exacta([candidata for _, candidata in compatibles], texto)


def _crear_canonica(
    db: Session,
    texto: str,
    categoria: str,
    candidatos: list[CanonicalEntity],
    normalizados: dict[object, str],
    *,
    second_score: float | None = None,
    reason: str,
) -> MatchDecision:
    nueva = CanonicalEntityRepo.crear(
        db,
        canonical_name=_nombre_canonico(texto),
        category=categoria,
    )
    candidatos.append(nueva)
    normalizados[nueva.id] = normalizar_nombre(nueva.canonical_name)
    return MatchDecision(nueva, "new", 0.0, second_score, reason)


def _metodo_para_mencion(
    mencion: dict[str, Any], plan: MentionPlan, decision: MatchDecision
) -> tuple[str, float]:
    texto = _nombre_canonico(mencion["text"])
    if plan.strategy == "generic_actor" and texto != plan.preferred_name:
        return "morphology", plan.confidence
    if plan.strategy == "document_person" and texto != plan.preferred_name:
        return "person_alias", plan.confidence
    return decision.match_type, decision.score
