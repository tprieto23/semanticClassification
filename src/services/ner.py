import json
import logging
from pathlib import Path
from typing import Any

from src.config import settings
from src.services.llm_client import get_anthropic_client

logger = logging.getLogger(__name__)

# ── Definición de las 6 etiquetas ──────────────────────────────────────────

LABEL_DEFINITIONS: dict[str, str] = {
    "LOC": (
        "Lugares geográficos, territorios, regiones, países, ciudades, "
        "áreas geográficas, topónimos."
    ),
    "INFRA": (
        "Infraestructura física o técnica: carreteras, puertos, centrales "
        "eléctricas, redes de monitoreo, sistemas construidos."
    ),
    "ACTR": (
        "Actores individuales o colectivos: personas, grupos, organizaciones, "
        "instituciones en tanto actores, ministerios, comunidades."
    ),
    "PRAC": (
        "Prácticas, actividades productivas, cadenas de valor, procesos "
        "socioeconómicos rutinizados, cultivos, productos."
    ),
    "GOV": (
        "Instrumentos de gobernanza: políticas, normas, leyes, acuerdos, "
        "decretos, regulaciones, estrategias, compromisos oficiales."
    ),
    "NARV": (
        "Narrativas, discursos, conceptos, objetivos, justificaciones, "
        "visiones, ideas-fuerza."
    ),
}

LABEL_EXAMPLES: dict[str, list[str]] = {
    "LOC": ["Amazonía peruana", "Madre de Dios", "Perú", "Loreto", "Unión Europea"],
    "INFRA": ["carretera interoceánica", "puerto fluvial", "red de monitoreo"],
    "ACTR": ["Gobierno peruano", "MINAM", "pueblos indígenas", "agricultores"],
    "PRAC": ["cacao", "palma aceitera", "ganadería", "cadenas de valor"],
    "GOV": ["Acuerdo de París", "Ley Marco sobre Cambio Climático", "compromisos voluntarios"],
    "NARV": ["producción libre de deforestación", "mitigar el cambio climático", "conservar los bosques"],
}


def _formatear_definiciones() -> str:
    lineas: list[str] = []
    for label, desc in LABEL_DEFINITIONS.items():
        ejemplos = ", ".join(LABEL_EXAMPLES.get(label, []))
        lineas.append(f"{label}: {desc}")
        if ejemplos:
            lineas.append(f"   Ejemplos: {ejemplos}")
    return "\n".join(lineas)


SYSTEM_PROMPT = f"""Eres un extractor de entidades especializado en análisis territorial y socioambiental.
Extrae entidades del texto y clasifícalas en UNA de estas 6 categorías:

LOC: Lugares geográficos, territorios, regiones, países, ciudades, áreas geográficas, topónimos.
   Ejemplos: Amazonía peruana, Madre de Dios, Perú, Loreto, Unión Europea
INFRA: Infraestructura física o técnica: carreteras, puertos, centrales eléctricas, redes de monitoreo, sistemas construidos.
   Ejemplos: carretera interoceánica, puerto fluvial, red de monitoreo
ACTR: Actores individuales o colectivos: personas, grupos, organizaciones, instituciones en tanto actores, ministerios, comunidades.
   Ejemplos: Gobierno peruano, MINAM, pueblos indígenas, agricultores
PRAC: Prácticas, actividades productivas, cadenas de valor, procesos socioeconómicos rutinizados, cultivos, productos.
   Ejemplos: cacao, palma aceitera, ganadería, cadenas de valor
GOV: Instrumentos de gobernanza: políticas, normas, leyes, acuerdos, decretos, regulaciones, estrategias, compromisos oficiales.
   Ejemplos: Acuerdo de París, Ley Marco sobre Cambio Climático, compromisos voluntarios
NARV: Narrativas, discursos, conceptos, objetivos, justificaciones, visiones, ideas-fuerza.
   Ejemplos: producción libre de deforestación, mitigar el cambio climático, conservar los bosques

{_formatear_definiciones()}

Reglas:
- Devuelve SOLO un array JSON válido. Sin markdown, sin explicación adicional.
- Cada entidad: {{"text": str, "labels": [str], "start": int, "end": int, "confidence": float}}
- "text" debe ser el fragmento EXACTO del texto original (incluyendo espacios si los tiene).
- "start" y "end": posiciones de carácter 0-indexed en el texto original.
- "labels": array con EXACTAMENTE una etiqueta.
- "confidence": número entre 0.0 y 1.0 indicando qué tan seguro estás de esta extracción.
- No uses etiquetas fuera de la lista.
- Si no hay entidades, devuelve []."""


# ── Carga de few-shot desde el JSON de anotaciones ────────────────────────

def _cargar_few_shot() -> list[dict[str, Any]]:
    """Carga TODAS las anotaciones del JSON de Label Studio como
    ejemplos few-shot para Claude."""
    path = Path(settings.NER_ANNOTATIONS_PATH)
    if not path.exists():
        logger.warning("Archivo de anotaciones no encontrado en %s", path)
        return []

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    if not data:
        return []

    task = data[0]
    texto_fuente: str = task.get("data", {}).get("text", "")
    resultados: list[dict[str, Any]] = (
        task.get("annotations", [{}])[0].get("result", []) if task.get("annotations") else []
    )
    if not texto_fuente or not resultados:
        return []

    todas_las_entidades: list[dict[str, Any]] = []
    for r in resultados:
        value = r.get("value", {})
        labels = value.get("labels", [])
        if not labels:
            continue
        todas_las_entidades.append({
            "text": value["text"],
            "labels": labels,
            "start": value["start"],
            "end": value["end"],
        })

    if not todas_las_entidades:
        return []

    return [
        {
            "role": "user",
            "content": f"Texto:\n{texto_fuente}",
        },
        {
            "role": "assistant",
            "content": json.dumps(todas_las_entidades, ensure_ascii=False),
        },
    ]


# ── Chunking por párrafos ─────────────────────────────────────────────────

def _partir_por_parrafos(texto: str, max_chars: int) -> list[tuple[str, int]]:
    """Divide texto en chunks por párrafos que quepan en max_chars.
    Retorna lista de (chunk, offset_inicial)."""
    parrafos = texto.split("\n\n")
    if len(texto) <= max_chars:
        return [(texto, 0)]

    chunks: list[tuple[str, int]] = []
    chunk_actual: list[str] = []
    chars_actual = 0
    offset = 0
    # saltar párrafos vacíos al inicio
    parrafos_limpios = [p for p in parrafos if p.strip()]

    for p in parrafos_limpios:
        p_len = len(p) + 2  # +2 por el \n\n
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


def _extraer_contexto(texto_original: str, start: int, end: int, ventana: int = 80) -> str:
    """Extrae contexto alrededor de una entidad."""
    ctx_start = max(0, start - ventana)
    ctx_end = min(len(texto_original), end + ventana)
    contexto = texto_original[ctx_start:ctx_end]
    # Si no estamos al inicio, agregar "..."
    if ctx_start > 0:
        partes = contexto.split()
        if len(partes) > 2:
            contexto = "..." + " ".join(partes[1:])
    if ctx_end < len(texto_original):
        partes = contexto.rsplit(maxsplit=1)
        if len(partes) > 1:
            contexto = partes[0] + "..."
        else:
            contexto = contexto + "..."
    return contexto


def _fusionar_entidades(
    chunks_entities: list[list[dict[str, Any]]],
    offsets: list[int],
    texto_original: str,
) -> list[dict[str, Any]]:
    """Fusiona entidades de múltiples chunks, ajustando offsets,
    deduplicando y extrayendo contexto."""
    vistos: set[tuple[str, int]] = set()
    fusionadas: list[dict[str, Any]] = []

    for entities, offset in zip(chunks_entities, offsets):
        for ent in entities:
            start_abs = ent["start"] + offset
            end_abs = ent["end"] + offset
            clave = (ent["text"], start_abs)
            if clave not in vistos:
                vistos.add(clave)
                fusionadas.append({
                    "text": ent["text"],
                    "labels": ent["labels"],
                    "start": start_abs,
                    "end": end_abs,
                    "confidence": ent.get("confidence"),
                    "context": _extraer_contexto(texto_original, start_abs, end_abs),
                })

    fusionadas.sort(key=lambda e: e["start"])
    return fusionadas


# ── Extracción principal ───────────────────────────────────────────────────

def extraer_entidades(texto: str) -> list[dict[str, Any]]:
    """Extrae entidades del texto usando Anthropic Claude con few-shot."""
    if not texto or not texto.strip():
        logger.warning("Texto vacío, no hay entidades que extraer")
        return []

    max_chunk = settings.NER_MAX_CHUNK_LEN
    chunks = _partir_por_parrafos(texto, max_chunk)

    if len(chunks) > 1:
        logger.info("Texto dividido en %d chunks (max %d chars c/u)", len(chunks), max_chunk)

    resultados_por_chunk: list[list[dict[str, Any]]] = []
    offsets: list[int] = []

    few_shot = _cargar_few_shot()
    if not few_shot:
        logger.info("No se cargaron ejemplos few-shot, se usará solo el prompt")

    client = get_anthropic_client()

    for chunk_text, chunk_offset in chunks:
        logger.info(
            "Procesando chunk en offset %d (%d caracteres)",
            chunk_offset, len(chunk_text),
        )
        messages = list(few_shot)
        messages.append({
            "role": "user",
            "content": f"Texto:\n{chunk_text}",
        })

        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        contenido = response.content[0].text if response.content else ""

        # Limpiar posibles wrappers markdown ```json ... ```
        contenido_limpio = contenido.strip()
        if contenido_limpio.startswith("```"):
            contenido_limpio = contenido_limpio.split("\n", 1)[-1] if "\n" in contenido_limpio else ""
            if contenido_limpio.endswith("```"):
                contenido_limpio = contenido_limpio[:-3].strip()

        try:
            entities = json.loads(contenido_limpio)
            if not isinstance(entities, list):
                logger.warning("Respuesta inesperada (no es array): %s", contenido[:200])
                entities = []
        except json.JSONDecodeError:
            logger.warning("Error parseando respuesta JSON: %s", contenido[:200])
            entities = []

        resultados_por_chunk.append(entities)
        offsets.append(chunk_offset)

    if len(resultados_por_chunk) == 0:
        return []

    if len(resultados_por_chunk) == 1:
        solo = resultados_por_chunk[0]
        for ent in solo:
            if "context" not in ent:
                ent["context"] = _extraer_contexto(
                    texto, ent.get("start", 0), ent.get("end", 0)
                )
        return solo

    return _fusionar_entidades(resultados_por_chunk, offsets, texto)
