"""Extract Agroforestry mentions locally, without an external LLM."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import spacy
from sqlalchemy import select

from src.config import settings
from src.models.database import SessionLocal
from src.models.documents import Document


LABELS = {
    "CHAR",
    "KNOW",
    "ATT",
    "SKILL",
    "PRAC",
    "physical_INFRA",
    "soft_INFRA",
    "eco_INFRA",
    "RUL",
    "LOC",
}

PRACTICE = re.compile(
    r"\b(?:agroforestry|agroforester(?:y|ía)|conservation|conservación|"
    r"restoration|restauración|monitoring|monitoreo|cultivation|cultivo|"
    r"production|producción|harvesting|cosecha|collection|colecta|"
    r"training|capacitación|assessment|evaluación|research|investigación|"
    r"management|gestión|governance|gobernanza|tourism|turismo|"
    r"reforestation|reforestación|planting|siembra|marketing|comercialización|"
    r"logging|tala|mining|minería|fishing|pesca|pollination|polinización)\b[^.\n;:]{0,70}",
    re.IGNORECASE,
)
KNOWLEDGE = re.compile(
    r"\b(?:knowledge|saber(?:es)?|conocimiento(?:s)?|traditional knowledge|"
    r"ancestral knowledge|conocimientos tradicionales|know-how|expertise|"
    r"insights?|sabiduría|understanding|comprensión)\b[^.\n;:]{0,80}",
    re.IGNORECASE,
)
SKILL = re.compile(
    r"\b(?:skills?|capacidades?|competenc(?:ia|ias)|ability|abilities|"
    r"habilidad(?:es)?|capacit(?:y|ación)|aptitud(?:es)?)\b[^.\n;:]{0,70}",
    re.IGNORECASE,
)
ATTITUDE = re.compile(
    r"\b(?:commitment|compromiso|values?|valores?|identity|identidad|"
    r"perception|percepción|attitude|actitud|interest|interés|vision|visión|"
    r"concern|preocupación|willingness|disposición)\b[^.\n;:]{0,70}",
    re.IGNORECASE,
)
RULE = re.compile(
    r"\b(?:law|ley|regulation|reglamento|policy|política|plan|agreement|"
    r"acuerdo|contract|contrato|permit|permiso|standard|estándar|rule|regla|"
    r"decree|decreto|resolution|resolución|strategy|estrategia)\b[^.\n;:]{0,80}",
    re.IGNORECASE,
)
PHYSICAL = re.compile(
    r"\b(?:road|carretera|highway|puente|bridge|port|puerto|electric(?:ity|al)"
    r"|energía|power grid|red eléctrica|antenna|antena|internet|connectivity|"
    r"conectividad|transport|transporte)\b[^.\n;:]{0,60}",
    re.IGNORECASE,
)
SOFT = re.compile(
    r"\b(?:nursery|vivero|seed bank|banco de semillas|laborator(?:y|io)|"
    r"platform|plataforma|database|base de datos|training center|centro de"
    r" capacitación|monitoring system|sistema de monitoreo|research station|"
    r"estación experimental)\b[^.\n;:]{0,70}",
    re.IGNORECASE,
)
ECO = re.compile(
    r"\b(?:forest|bosque|wetland|humedal|biological corridor|corredor"
    r" biológico|swamp|aguajal|ecosystem|ecosistema|river|río|watershed|"
    r"cuenca)\b[^.\n;:]{0,55}",
    re.IGNORECASE,
)
ACTOR_WORD = re.compile(
    r"\b(?:community|comunidad(?:es)?|farmers?|agricultor(?:es|as)?|"
    r"producers?|productor(?:es|as)?|researchers?|investigador(?:es|as)?|"
    r"authorit(?:y|ies)|autoridad(?:es)?|women|mujeres|men|hombres|"
    r"students?|estudiantes|workers?|trabajador(?:es|as)?|organisations?|"
    r"organizaciones?|association|asociación|university|universidad|"
    r"government|gobierno|partners?|socios?)\b(?:\s+[^.\n;:]{0,55})?",
    re.IGNORECASE,
)


def sentence_id(start: int) -> str:
    return f"s-{start:09d}"


def add_match(out: list[dict], seen: set[tuple[int, int, str]], text: str, start: int, label: str, context: str, sid: str) -> None:
    text = text.strip(" \t,;:-")
    # The codebook asks for the minimal complete literal span. Regex context
    # is deliberately capped so a whole explanatory clause cannot become one
    # entity; the sentence remains the evidence context.
    words = re.findall(r"\S+", text)
    if len(words) > 6:
        text = " ".join(words[:6]).rstrip(" ,;:-")
    if not text or label not in LABELS:
        return
    end = start + len(text)
    key = (start, end, label)
    if key in seen or end <= start:
        return
    seen.add(key)
    out.append({"text": text, "category": label, "start": start, "end": end, "sentence_id": sid, "context": context, "ambiguity": "high"})


def extract(text: str, nlp) -> list[dict]:
    doc = nlp(text)
    out: list[dict] = []
    seen: set[tuple[int, int, str]] = set()
    for sent in doc.sents:
        context = sent.text.strip()
        if not context:
            continue
        sent_start = sent.start_char
        sid = sentence_id(sent_start)
        for ent in sent.ents:
            label = "LOC" if ent.label_ in {"GPE", "LOC", "FAC"} else "CHAR" if ent.label_ in {"PERSON", "ORG", "PER"} else None
            if label:
                add_match(out, seen, ent.text, ent.start_char, label, context, sid)
        rules = ((PRACTICE, "PRAC"), (KNOWLEDGE, "KNOW"), (SKILL, "SKILL"), (ATTITUDE, "ATT"), (RULE, "RUL"), (PHYSICAL, "physical_INFRA"), (SOFT, "soft_INFRA"), (ECO, "eco_INFRA"), (ACTOR_WORD, "CHAR"))
        for pattern, label in rules:
            for match in pattern.finditer(context):
                add_match(out, seen, match.group(0), sent_start + match.start(), label, context, sid)
    return sorted(out, key=lambda item: (item["start"], item["end"], item["category"]))


def main() -> None:
    nlp = spacy.load("es_core_news_sm")
    codebook = Path(settings.NER_CODEBOOK_PATH).read_bytes()
    codebook_sha = hashlib.sha256(codebook).hexdigest()
    db = SessionLocal()
    try:
        docs = list(db.scalars(select(Document).where(Document.productive_sector == "Agroforestry", Document.status == "cleaned").order_by(Document.uploaded_at, Document.id)).all())
        print(f"targets={len(docs)}", flush=True)
        for index, doc in enumerate(docs, 1):
            source = Path(doc.cleaned_path)
            text = source.read_text(encoding="utf-8")
            entities = extract(text, nlp)
            result = {"document_id": str(doc.id), "entities": entities, "metadata": {"prompt_strategy": "local-codebook-rules", "codebook_sha256": codebook_sha, "provider": "local-spacy-es_core_news_sm", "review_required": True}}
            target = Path(settings.STORAGE_NER) / f"{doc.id}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            doc.ner_path = str(target)
            doc.status = "ner"
            db.commit()
            print(f"{index}/{len(docs)} OK {doc.id} mentions={len(entities)}", flush=True)
    finally:
        db.close()


if __name__ == "__main__":
    main()
