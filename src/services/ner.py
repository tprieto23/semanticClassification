import json
import logging
import re
from pathlib import Path
from string import Template
from typing import Any

from src.config import settings
from src.services.llm_client import get_anthropic_client

logger = logging.getLogger(__name__)

VALID_LABELS = {"CHAR", "LOC", "INFRA", "GOV", "PRAC"}
NER_TOOL_NAME = "submit_entity_annotations"

NER_TOOL = {
    "name": NER_TOOL_NAME,
    "description": "Entrega todas las menciones semánticas encontradas en el fragmento.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "document_id": {"type": "string"},
            "annotations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {
                            "type": "string",
                            "enum": sorted(VALID_LABELS),
                        },
                        "text": {
                            "type": "string",
                            "description": "Span literal exacto copiado del fragmento.",
                        },
                        "ambiguity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["label", "text", "ambiguity"],
                },
            },
        },
        "required": ["document_id", "annotations"],
    },
}

_SYSTEM_PROMPT: str | None = None
_USER_PROMPT_TEMPLATE: Template | None = None
_FEW_SHOT_EXAMPLES: str | None = None


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


def _cargar_few_shot_examples() -> str:
    global _FEW_SHOT_EXAMPLES
    if _FEW_SHOT_EXAMPLES is not None:
        return _FEW_SHOT_EXAMPLES

    path = Path(settings.NER_FEW_SHOT_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Ejemplos few-shot no encontrados: {path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON few-shot inválido en {path}: {exc}") from exc

    examples = payload.get("examples") if isinstance(payload, dict) else None
    if not isinstance(examples, list) or not examples:
        raise ValueError("El archivo few-shot debe contener una lista examples no vacía")

    formatted: list[str] = []
    for index, example in enumerate(examples, start=1):
        if not isinstance(example, dict):
            raise ValueError(f"Ejemplo few-shot #{index} no es un objeto")

        example_id = str(example.get("id", f"example-{index}"))
        source_text = example.get("text")
        annotations = example.get("annotations")
        if not isinstance(source_text, str) or not source_text.strip():
            raise ValueError(f"Texto inválido en ejemplo few-shot {example_id}")
        if not isinstance(annotations, list):
            raise ValueError(f"Annotations inválido en ejemplo few-shot {example_id}")

        validated_annotations: list[dict[str, str]] = []
        for annotation in annotations:
            if not isinstance(annotation, dict):
                raise ValueError(f"Anotación inválida en ejemplo {example_id}")
            label = annotation.get("label")
            span_text = annotation.get("text")
            ambiguity = annotation.get("ambiguity")
            if label not in VALID_LABELS:
                raise ValueError(
                    f"Etiqueta no permitida {label!r} en ejemplo {example_id}"
                )
            if not isinstance(span_text, str) or span_text not in source_text:
                raise ValueError(f"Span no literal en ejemplo {example_id}: {span_text!r}")
            if ambiguity not in {"low", "medium", "high"}:
                raise ValueError(
                    f"Ambigüedad no permitida en ejemplo {example_id}: {ambiguity!r}"
                )
            validated_annotations.append(
                {"label": label, "text": span_text, "ambiguity": ambiguity}
            )

        demonstration = {
            "id": example_id,
            "input": {
                "document_id": example_id,
                "document_title": "",
                "section_title": "",
                "text": source_text,
            },
            "expected_output": {
                "document_id": example_id,
                "annotations": validated_annotations,
            },
        }
        formatted.append(json.dumps(demonstration, ensure_ascii=False))

    _FEW_SHOT_EXAMPLES = "\n".join(formatted)
    logger.info("Cargados %d ejemplos few-shot desde %s", len(examples), path)
    return _FEW_SHOT_EXAMPLES


def _build_user_prompt(json_input: str, few_shot_examples: str) -> str:
    template = _cargar_user_prompt_template()
    return template.substitute(
        few_shot_examples=few_shot_examples,
        json_input=json_input,
    )


def _construir_json_entrada(
    chunk: str,
    document_id: str = "",
    document_title: str = "",
    section_title: str = "",
) -> str:
    entrada = {
        "document_id": document_id,
        "document_title": document_title,
        "section_title": section_title,
        "text": chunk,
    }
    return json.dumps(entrada, ensure_ascii=False)


def _partir_por_parrafos(texto: str, max_chars: int) -> list[tuple[str, int]]:
    parrafos = [
        (match.start(), match.end())
        for match in re.finditer(r"\S.*?(?=\n{2,}|\Z)", texto, re.DOTALL)
    ]
    chunks: list[tuple[str, int]] = []
    chunk_start: int | None = None
    chunk_end: int | None = None
    paragraph_count = 0

    for paragraph_start, paragraph_end in parrafos:
        if chunk_start is None:
            chunk_start = paragraph_start
            chunk_end = paragraph_end
            paragraph_count = 1
            continue
        if paragraph_end - chunk_start > max_chars or paragraph_count >= 3:
            chunks.append((texto[chunk_start:chunk_end], chunk_start))
            chunk_start = paragraph_start
            paragraph_count = 1
        else:
            paragraph_count += 1
        chunk_end = paragraph_end

    if chunk_start is not None and chunk_end is not None:
        chunks.append((texto[chunk_start:chunk_end], chunk_start))

    return chunks or [(texto, 0)]


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


def _parsear_datos(
    data: Any,
    chunk_text: str,
    chunk_offset: int = 0,
) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        logger.warning("Respuesta estructurada inesperada (no es objeto): %r", data)
        return []

    anotaciones = data.get("annotations", [])
    if not isinstance(anotaciones, list):
        logger.warning("Respuesta inesperada: annotations no es un array")
        return []

    entidades: list[dict[str, Any]] = []
    last_index = 0

    for anot in anotaciones:
        if not isinstance(anot, dict):
            continue

        label = anot.get("label")
        if label not in VALID_LABELS:
            logger.warning("Etiqueta inválida, se ignora anotación: %r", label)
            continue

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

        ambiguity = anot.get("ambiguity", "low")
        if ambiguity not in {"low", "medium", "high"}:
            logger.warning("Ambigüedad inválida, se normaliza a high: %r", ambiguity)
            ambiguity = "high"

        ctx = _extraer_contexto(chunk_text, start_rel, end_rel)

        entidades.append(
            {
                "text": span_text,
                "category": label,
                "start": chunk_offset + start_rel,
                "end": chunk_offset + end_rel,
                "context": ctx,
                "ambiguity": ambiguity,
            }
        )

    return entidades


def _fusionar_entidades(
    chunks_entities: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    vistos: set[tuple[int, int, str]] = set()
    fusionadas: list[dict[str, Any]] = []

    for entities in chunks_entities:
        for ent in entities:
            clave = (ent["start"], ent["end"], ent["category"])
            if clave in vistos:
                continue
            vistos.add(clave)
            fusionadas.append(ent)

    return sorted(fusionadas, key=lambda ent: (ent["start"], ent["end"]))


def extraer_entidades(
    texto: str,
    document_id: str = "",
    document_title: str = "",
) -> list[dict[str, Any]]:
    if not texto or not texto.strip():
        logger.warning("Texto vacío, no hay entidades que extraer")
        return []

    system_prompt = _cargar_system_prompt()
    few_shot_examples = _cargar_few_shot_examples()
    max_chunk = settings.NER_MAX_CHUNK_LEN
    chunks = _partir_por_parrafos(texto, max_chunk)

    if len(chunks) > 1:
        logger.info(
            "Texto dividido en %d chunks (max %d chars c/u)", len(chunks), max_chunk
        )

    resultados_por_chunk: list[list[dict[str, Any]]] = []
    client = get_anthropic_client()

    for chunk_text, chunk_offset in chunks:
        logger.info(
            "Procesando chunk en offset %d (%d caracteres)",
            chunk_offset,
            len(chunk_text),
        )

        json_input = _construir_json_entrada(
            chunk=chunk_text,
            document_id=document_id,
            document_title=document_title,
        )

        messages = [
            {
                "role": "user",
                "content": _build_user_prompt(json_input, few_shot_examples),
            }
        ]

        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=16384,
            system=system_prompt,
            messages=messages,
            tools=[NER_TOOL],
            tool_choice={"type": "tool", "name": NER_TOOL_NAME},
        )

        if getattr(response, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                f"Respuesta NER truncada por límite de tokens en offset {chunk_offset}"
            )

        tool_input = next(
            (
                block.input
                for block in response.content
                if getattr(block, "type", None) == "tool_use"
                and getattr(block, "name", None) == NER_TOOL_NAME
            ),
            None,
        )
        if tool_input is not None:
            entities = _parsear_datos(tool_input, chunk_text, chunk_offset)
        else:
            raise RuntimeError(
                f"Claude no usó la herramienta NER requerida en offset {chunk_offset}"
            )
        resultados_por_chunk.append(entities)

    if not resultados_por_chunk:
        return []

    if len(resultados_por_chunk) == 1:
        return resultados_por_chunk[0]

    return _fusionar_entidades(resultados_por_chunk)
