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
                        "sentence_id": {
                            "type": "string",
                            "description": "Identificador de la oración que contiene el span.",
                        },
                        "ambiguity": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                    },
                    "required": ["label", "text", "sentence_id", "ambiguity"],
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
        raise ValueError(
            "El archivo few-shot debe contener una lista examples no vacía"
        )

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

        sentence_id = f"{example_id}-s1"
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
                raise ValueError(
                    f"Span no literal en ejemplo {example_id}: {span_text!r}"
                )
            if ambiguity not in {"low", "medium", "high"}:
                raise ValueError(
                    f"Ambigüedad no permitida en ejemplo {example_id}: {ambiguity!r}"
                )
            validated_annotations.append(
                {
                    "label": label,
                    "text": span_text,
                    "sentence_id": sentence_id,
                    "ambiguity": ambiguity,
                }
            )

        demonstration = {
            "id": example_id,
            "input": {
                "document_id": example_id,
                "document_title": "",
                "section_title": "",
                "sentences": [{"sentence_id": sentence_id, "text": source_text}],
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
    sentences: list[dict[str, Any]],
    document_id: str = "",
    document_title: str = "",
    section_title: str = "",
) -> str:
    entrada = {
        "document_id": document_id,
        "document_title": document_title,
        "section_title": section_title,
        "sentences": [
            {"sentence_id": sentence["sentence_id"], "text": sentence["text"]}
            for sentence in sentences
        ],
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


_ABBREVIATIONS = {
    "dr.",
    "dra.",
    "sr.",
    "sra.",
    "srta.",
    "ing.",
    "lic.",
    "etc.",
    "ej.",
    "p.",
    "pp.",
    "n.º",
    "n°.",
}


def _es_limite_oracion(texto: str, boundary_start: int, boundary_end: int) -> bool:
    separator = texto[boundary_start:boundary_end]
    if "\n\n" in separator:
        return True

    prefix = texto[:boundary_start].rstrip()
    token_match = re.search(r"(\S+)$", prefix)
    token = token_match.group(1).casefold() if token_match else ""
    if token in _ABBREVIATIONS or re.fullmatch(r"[a-záéíóúñ]\.", token):
        return False

    suffix = texto[boundary_end:].lstrip()
    if suffix and suffix[0].islower():
        return False
    return True


def _segmentar_oraciones(
    chunk_text: str,
    chunk_offset: int,
) -> list[dict[str, Any]]:
    boundaries = list(re.finditer(r"(?<=[.!?])\s+|\n{2,}", chunk_text))
    sentences: list[dict[str, Any]] = []
    segment_start = 0

    for boundary in boundaries:
        if not _es_limite_oracion(chunk_text, boundary.start(), boundary.end()):
            continue
        raw = chunk_text[segment_start : boundary.start()]
        leading = len(raw) - len(raw.lstrip())
        sentence_text = raw.strip()
        if sentence_text:
            start = chunk_offset + segment_start + leading
            sentences.append(
                {
                    "sentence_id": f"s-{start:09d}",
                    "text": sentence_text,
                    "start": start,
                }
            )
        segment_start = boundary.end()

    raw = chunk_text[segment_start:]
    leading = len(raw) - len(raw.lstrip())
    sentence_text = raw.strip()
    if sentence_text:
        start = chunk_offset + segment_start + leading
        sentences.append(
            {
                "sentence_id": f"s-{start:09d}",
                "text": sentence_text,
                "start": start,
            }
        )

    return sentences


def _buscar_offset_disponible(
    sentence_text: str,
    span_text: str,
    used_ranges: list[tuple[int, int]],
) -> tuple[int, int] | None:
    if not span_text:
        return None
    search_from = 0
    while True:
        start = sentence_text.find(span_text, search_from)
        if start == -1:
            return None
        end = start + len(span_text)
        if all(
            end <= used_start or start >= used_end
            for used_start, used_end in used_ranges
        ):
            return start, end
        search_from = start + 1


def _parsear_datos(
    data: Any,
    sentences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(data, dict):
        logger.warning("Respuesta estructurada inesperada (no es objeto): %r", data)
        return []

    anotaciones = data.get("annotations", [])
    if not isinstance(anotaciones, list):
        logger.warning("Respuesta inesperada: annotations no es un array")
        return []

    sentence_by_id = {sentence["sentence_id"]: sentence for sentence in sentences}
    used_ranges: dict[str, list[tuple[int, int]]] = {
        sentence_id: [] for sentence_id in sentence_by_id
    }
    entidades: list[dict[str, Any]] = []

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

        sentence_id = str(anot.get("sentence_id", ""))
        sentence = sentence_by_id.get(sentence_id)
        if sentence is None:
            logger.warning(
                "sentence_id inválido, se ignora anotación %r: %r",
                sentence_id,
                span_text[:100],
            )
            continue

        offset_result = _buscar_offset_disponible(
            sentence["text"], span_text, used_ranges[sentence_id]
        )
        if offset_result is None:
            logger.warning(
                "Span no disponible literalmente en %s, se ignora: %r",
                sentence_id,
                span_text[:100],
            )
            continue

        start_rel, end_rel = offset_result
        used_ranges[sentence_id].append((start_rel, end_rel))

        ambiguity = anot.get("ambiguity", "low")
        if ambiguity not in {"low", "medium", "high"}:
            logger.warning("Ambigüedad inválida, se normaliza a high: %r", ambiguity)
            ambiguity = "high"

        start = sentence["start"] + start_rel
        end = sentence["start"] + end_rel

        entidades.append(
            {
                "text": span_text,
                "category": label,
                "start": start,
                "end": end,
                "sentence_id": sentence_id,
                "context": sentence["text"],
                "ambiguity": ambiguity,
            }
        )

    return sorted(entidades, key=lambda ent: (ent["start"], ent["end"]))


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

        sentences = _segmentar_oraciones(chunk_text, chunk_offset)
        json_input = _construir_json_entrada(
            sentences=sentences,
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
            entities = _parsear_datos(tool_input, sentences)
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
