import json
import logging
from pathlib import Path
from string import Template
from typing import Any

from sqlalchemy.orm import Session

from src.config import settings
from src.services.llm_client import get_anthropic_client

logger = logging.getLogger(__name__)

VALID_LABELS = {"CHAR", "LOC", "INFRA", "GOV", "PRAC", "ACT"}

_SYSTEM_PROMPT: str | None = None
_USER_PROMPT_TEMPLATE: Template | None = None


def _cargar_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        path = Path(settings.NER_PROMPT_PATH)
        if not path.exists():
            raise FileNotFoundError(f"System prompt no encontrado: {path}")
        _SYSTEM_PROMPT = path.read_text(encoding="utf-8")
    return _SYSTEM_PROMPT


def _cargar_user_prompt_template() -> Template:
    global _USER_PROMPT_TEMPLATE
    if _USER_PROMPT_TEMPLATE is None:
        path = Path(settings.NER_USER_PROMPT_PATH)
        if not path.exists():
            raise FileNotFoundError(f"User prompt no encontrado: {path}")
        _USER_PROMPT_TEMPLATE = Template(path.read_text(encoding="utf-8"))
    return _USER_PROMPT_TEMPLATE


def _build_user_prompt(json_input: str) -> str:
    template = _cargar_user_prompt_template()
    return template.substitute(json_input=json_input)


def _cargar_catalogos(db: Session) -> dict[str, list[dict[str, Any]]]:
    from src.models.catalogs import (
        CatalogAmbiguityLevel,
        CatalogAttribute,
        CatalogLabel,
        CatalogNode,
        CatalogType,
        CatalogValue,
    )

    labels = [
        {"id": row.id, "name": row.name}
        for row in db.query(CatalogLabel).order_by(CatalogLabel.id).all()
    ]
    types = [
        {"id": row.id, "name": row.name, "label_id": row.label_id}
        for row in db.query(CatalogType).order_by(CatalogType.id).all()
    ]
    nodes = [
        {"id": row.id, "name": row.name, "type_id": row.type_id}
        for row in db.query(CatalogNode).order_by(CatalogNode.id).all()
    ]
    attributes = [
        {"id": row.id, "name": row.name}
        for row in db.query(CatalogAttribute).order_by(CatalogAttribute.id).all()
    ]
    values = [
        {"id": row.id, "name": row.name, "attribute_id": row.attribute_id}
        for row in db.query(CatalogValue).order_by(CatalogValue.id).all()
    ]
    ambiguity_levels = [
        {"id": row.id, "name": row.name}
        for row in db.query(CatalogAmbiguityLevel)
        .order_by(CatalogAmbiguityLevel.id)
        .all()
    ]

    return {
        "labels": labels,
        "types": types,
        "nodes": nodes,
        "attributes": attributes,
        "values": values,
        "ambiguity_levels": ambiguity_levels,
    }


def _construir_json_entrada(
    chunk: str,
    catalogos: dict[str, list[dict[str, Any]]],
    document_id: str = "",
    document_title: str = "",
    section_title: str = "",
) -> str:
    entrada = {
        "document_id": document_id,
        "document_title": document_title,
        "section_title": section_title,
        "text": chunk,
        "catalogs": catalogos,
    }
    return json.dumps(entrada, ensure_ascii=False)


def _cargar_few_shot() -> list[dict[str, Any]]:
    path = Path(settings.NER_ANNOTATIONS_PATH)
    if not path.exists():
        logger.warning("Archivo de anotaciones no encontrado en %s", path)
        return []

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        logger.warning("No se pudo parsear el archivo de anotaciones %s", path)
        return []

    if not data or not isinstance(data, list):
        return []

    task = data[0]
    texto_fuente: str = task.get("data", {}).get("text", "")
    resultados: list[dict[str, Any]] = (
        task.get("annotations", [{}])[0].get("result", [])
        if task.get("annotations")
        else []
    )
    if not texto_fuente or not resultados:
        return []

    anotaciones: list[dict[str, Any]] = []
    for r in resultados:
        value = r.get("value", {})
        labels = value.get("labels", [])
        if not labels:
            continue
        label = labels[0]
        if label not in VALID_LABELS:
            continue
        label_to_id = {"CHAR": 1, "LOC": 2, "INFRA": 3, "GOV": 4, "PRAC": 5, "ACT": 6}
        anotaciones.append(
            {
                "label_id": label_to_id.get(label),
                "text": value["text"],
                "type_id": None,
                "node_id": None,
                "context": "",
                "attribute_id": None,
                "value_id": None,
                "ambiguity_id": 1,
            }
        )

    if not anotaciones:
        return []

    return [
        {
            "role": "user",
            "content": _build_user_prompt(
                json.dumps(
                    {
                        "document_id": "",
                        "document_title": "",
                        "section_title": "",
                        "text": texto_fuente,
                        "catalogs": {},
                    },
                    ensure_ascii=False,
                )
            ),
        },
        {
            "role": "assistant",
            "content": json.dumps(
                {"document_id": "", "annotations": anotaciones}, ensure_ascii=False
            ),
        },
    ]


def _partir_por_parrafos(texto: str, max_chars: int) -> list[tuple[str, int]]:
    if len(texto) <= max_chars:
        return [(texto, 0)]

    parrafos = [p for p in texto.split("\n\n") if p.strip()]
    chunks: list[tuple[str, int]] = []
    chunk_actual: list[str] = []
    chars_actual = 0
    offset = 0

    for p in parrafos:
        p_len = len(p) + 2
        if chars_actual + p_len > max_chars and chunk_actual:
            chunk_text = "\n\n".join(chunk_actual)
            chunks.append((chunk_text, offset))
            offset += len(chunk_text) + 2
            chunk_actual = []
            chars_actual = 0
        chunk_actual.append(p)
        chars_actual += p_len

    if chunk_actual:
        chunk_text = "\n\n".join(chunk_actual)
        chunks.append((chunk_text, offset))

    return chunks


def _extraer_contexto(
    texto_original: str, start: int, end: int, ventana: int = 80
) -> str:
    ctx_start = max(0, start - ventana)
    ctx_end = min(len(texto_original), end + ventana)
    contexto = texto_original[ctx_start:ctx_end]
    if ctx_start > 0:
        contexto = "..." + contexto.lstrip()
    if ctx_end < len(texto_original):
        contexto = contexto.rstrip() + "..."
    return contexto.strip()


def _buscar_offset(
    chunk_text: str,
    span_text: str,
    last_index: int = 0,
) -> tuple[int, int] | None:
    if not span_text:
        return None
    start = chunk_text.find(span_text, last_index)
    if start == -1:
        return None
    return start, start + len(span_text)


def _limpiar_contenido_markdown(contenido: str) -> str:
    contenido_limpio = contenido.strip()
    if contenido_limpio.startswith("```"):
        contenido_limpio = (
            contenido_limpio.split("\n", 1)[1] if "\n" in contenido_limpio else ""
        )
    contenido_limpio = contenido_limpio.rstrip()
    if contenido_limpio.endswith("```"):
        contenido_limpio = contenido_limpio[:-3].rstrip()
    return contenido_limpio


def _parsear_respuesta(
    contenido: str,
    chunk_text: str,
) -> list[dict[str, Any]]:
    contenido_limpio = _limpiar_contenido_markdown(contenido)

    try:
        data = json.loads(contenido_limpio)
    except json.JSONDecodeError as e:
        logger.warning(
            "Error parseando respuesta JSON (len=%d): %s",
            len(contenido_limpio),
            str(e)[:200],
        )
        logger.warning(
            "Últimos 200 chars del contenido limpio: %s", contenido_limpio[-200:]
        )
        return []

    if not isinstance(data, dict):
        logger.warning("Respuesta inesperada (no es objeto): %s", contenido[:200])
        return []

    anotaciones = data.get("annotations", [])
    if not isinstance(anotaciones, list):
        logger.warning(
            "Respuesta inesperada (annotations no es array): %s", contenido[:200]
        )
        return []

    entidades: list[dict[str, Any]] = []
    last_index = 0

    for anot in anotaciones:
        if not isinstance(anot, dict):
            continue

        label_id = anot.get("label_id")
        span_text = str(anot.get("text", "")).strip()
        if not span_text:
            continue

        offset_result = _buscar_offset(chunk_text, span_text, last_index)
        if offset_result is None:
            logger.warning(
                "Span no encontrado literalmente en chunk, se ignora: %r",
                span_text[:100],
            )
            continue

        start_rel, end_rel = offset_result
        last_index = end_rel

        ctx = anot.get("context") or _extraer_contexto(chunk_text, start_rel, end_rel)
        amb_id = anot.get("ambiguity_id")

        entidades.append(
            {
                "text": span_text,
                "category": _label_name_from_id(label_id),
                "context": ctx,
                "ambiguity": _ambiguity_name_from_id(amb_id),
                "label_id": label_id,
                "type_id": anot.get("type_id"),
                "node_id": anot.get("node_id"),
                "attribute_id": anot.get("attribute_id"),
                "value_id": anot.get("value_id"),
                "ambiguity_id": amb_id,
            }
        )

    return entidades


def _label_name_from_id(label_id: int | None) -> str:
    mapping = {
        1: "CHAR",
        2: "LOC",
        3: "INFRA",
        4: "GOV",
        5: "PRAC",
        6: "ACT",
    }
    return mapping.get(label_id or 0, "CHAR")


def _ambiguity_name_from_id(amb_id: int | None) -> str | None:
    mapping = {
        1: "low",
        2: "medium",
        3: "high",
    }
    if amb_id is None:
        return None
    return mapping.get(amb_id)


def _fusionar_entidades(
    chunks_entities: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    vistos: set[str] = set()
    fusionadas: list[dict[str, Any]] = []

    for entities in chunks_entities:
        for ent in entities:
            if ent["text"] in vistos:
                continue
            vistos.add(ent["text"])
            fusionadas.append(ent)

    return fusionadas


def extraer_entidades(
    texto: str,
    db: Session,
    document_id: str = "",
    document_title: str = "",
) -> list[dict[str, Any]]:
    if not texto or not texto.strip():
        logger.warning("Texto vacío, no hay entidades que extraer")
        return []

    system_prompt = _cargar_system_prompt()
    catalogos = _cargar_catalogos(db)
    max_chunk = settings.NER_MAX_CHUNK_LEN
    chunks = _partir_por_parrafos(texto, max_chunk)

    if len(chunks) > 1:
        logger.info(
            "Texto dividido en %d chunks (max %d chars c/u)", len(chunks), max_chunk
        )

    resultados_por_chunk: list[list[dict[str, Any]]] = []
    few_shot = _cargar_few_shot()
    if not few_shot:
        logger.info("No se cargaron ejemplos few-shot")

    client = get_anthropic_client()

    for chunk_text, chunk_offset in chunks:
        logger.info(
            "Procesando chunk en offset %d (%d caracteres)",
            chunk_offset,
            len(chunk_text),
        )

        json_input = _construir_json_entrada(
            chunk=chunk_text,
            catalogos=catalogos,
            document_id=document_id,
            document_title=document_title,
        )

        messages = list(few_shot)
        messages.append(
            {
                "role": "user",
                "content": _build_user_prompt(json_input),
            }
        )

        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=16384,
            system=system_prompt,
            messages=messages,
        )

        contenido = response.content[0].text if response.content else ""
        entities = _parsear_respuesta(contenido, chunk_text)
        resultados_por_chunk.append(entities)

    if not resultados_por_chunk:
        return []

    if len(resultados_por_chunk) == 1:
        return resultados_por_chunk[0]

    return _fusionar_entidades(resultados_por_chunk)
