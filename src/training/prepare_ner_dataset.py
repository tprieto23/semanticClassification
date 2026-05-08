"""
prepare_ner_dataset.py

Convierte _all_entities_corrected.json al formato BIO necesario para entrenar
un modelo de Token Classification (NER) con XLM-RoBERTa.

ADVERTENCIA: El dataset _all_entities_corrected.json es producto de la primera
iteración de clasificación (spaCy + reglas deterministas + correcciones manuales
parciales). Contiene errores residuales y debe considerarse un ground truth
provisional, no una base sólida. Se conserva únicamente como punto de partida
para el fine-tuning iterativo.

El formato de salida es JSON Lines con campos:
  - id: identificador único de la instancia
  - words: lista de palabras (strings) de la oración
  - ner_tags: lista de etiquetas BIO correspondientes (O, B-CATEGORY, I-CATEGORY)

Las etiquetas MISC_Spacy se descartan (se marcan como O) porque representan
entidades ambiguas no clasificadas.

División train/val/test se realiza a nivel de documento para evitar data leakage.
"""

import json
import random
import re
from collections import defaultdict
from pathlib import Path

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

INPUT_PATH = Path("data/processed/entities/_all_entities_corrected.json")
OUTPUT_DIR = Path("data/processed/entities/ner_dataset")
RANDOM_SEED = 42
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
# TEST_RATIO se calcula como el resto (0.1)

VALID_CATEGORIES = {
    "COMUNIDAD",
    "INSTITUCIÓN",
    "LUGAR",
    "PRÁCTICA",
    "INFRAESTRUCTURA",
    "VALOR_ECOLÓGICO",
    "NARRATIVA",
    "ACTOR",
    "ACCIÓN",
}

# =============================================================================
# UTILIDADES
# =============================================================================


def normalize_spaces(text: str) -> str:
    """Reemplaza cualquier secuencia de whitespace (incluido \n, \t) por un solo espacio."""
    return re.sub(r"\s+", " ", text).strip()


def find_entity_spans(sentence: str, entities: list) -> list:
    """
    Busca todas las entidades válidas dentro de la oración normalizada.

    Retorna lista de tuplas (start_char, end_char, category) ordenadas por posición.
    Si una entidad aparece múltiples veces, se incluyen todas las ocurrencias.
    Si hay solapamientos, se prioriza la entidad más larga (greedy por longitud).
    """
    spans = []
    for ent in entities:
        cat = ent.get("project_category", "")
        if cat not in VALID_CATEGORIES:
            continue

        ent_text = normalize_spaces(ent["text"])
        if not ent_text:
            continue

        # Buscar TODAS las ocurrencias no solapadas con spans ya aceptados
        idx = 0
        while True:
            pos = sentence.find(ent_text, idx)
            if pos == -1:
                break

            end_pos = pos + len(ent_text)

            # Verificar que no se solape con spans ya detectados
            overlap = any(
                not (end_pos <= s[0] or pos >= s[1]) for s in spans
            )
            if not overlap:
                spans.append((pos, end_pos, cat))
                idx = end_pos  # continuar después de esta ocurrencia
            else:
                idx = pos + 1  # seguir buscando más adelante

    # Resolver solapamientos: ordenar por longitud descendente y mantener la más larga
    spans.sort(key=lambda x: x[0])
    filtered = []
    for span in spans:
        s_start, s_end, cat = span
        conflict = False
        for f_start, f_end, _ in filtered:
            if not (s_end <= f_start or s_start >= f_end):
                conflict = True
                break
        if not conflict:
            filtered.append(span)

    filtered.sort(key=lambda x: x[0])
    return filtered


def get_word_offsets(sentence: str):
    """
    Divide la oración en palabras con split() y calcula los offsets de caracteres
    exactos para cada palabra dentro del string original.

    Retorna (lista_palabras, lista_offsets) donde cada offset es (start, end, word).
    """
    words = sentence.split()
    offsets = []
    pos = 0
    for word in words:
        # Avanzar hasta la siguiente palabra (saltar espacios)
        while pos < len(sentence) and sentence[pos] == " ":
            pos += 1

        if sentence[pos : pos + len(word)] == word:
            offsets.append((pos, pos + len(word), word))
            pos += len(word)
        else:
            # Fallback: usar find desde pos
            start = sentence.find(word, pos)
            if start == -1:
                start = pos
            offsets.append((start, start + len(word), word))
            pos = start + len(word)

    return words, offsets


def assign_bio_labels(words, offsets, spans):
    """
    Asigna etiquetas BIO a cada palabra según los spans de entidades.

    Lógica:
      - Si una palabra se solapa con un span de entidad:
          * B-{cat} si la palabra anterior NO se solapa con ese mismo span.
          * I-{cat} si la palabra anterior SÍ se solapa con ese mismo span.
      - O en caso contrario.
    """
    labels = []
    for i, (w_start, w_end, _word) in enumerate(offsets):
        label = "O"
        for s_start, s_end, cat in spans:
            # Verificar solapamiento entre palabra y span
            overlap_start = max(w_start, s_start)
            overlap_end = min(w_end, s_end)
            if overlap_start < overlap_end:
                # ¿Es la primera palabra de este span?
                is_first = True
                if i > 0:
                    prev_start, prev_end, _ = offsets[i - 1]
                    prev_overlap_start = max(prev_start, s_start)
                    prev_overlap_end = min(prev_end, s_end)
                    if prev_overlap_start < prev_overlap_end:
                        is_first = False

                label = f"B-{cat}" if is_first else f"I-{cat}"
                break  # asumimos no solapamientos entre categorías distintas
        labels.append(label)
    return labels


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================


def main():
    random.seed(RANDOM_SEED)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Cargando dataset desde {INPUT_PATH} ...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        entities = json.load(f)
    print(f"Total de entidades cargadas: {len(entities)}")

    # -------------------------------------------------------------------------
    # 1. Agrupar entidades por oración (sentence)
    # -------------------------------------------------------------------------
    sentences_map = defaultdict(list)
    skipped_misc = 0
    for ent in entities:
        cat = ent.get("project_category", "")
        if cat not in VALID_CATEGORIES:
            skipped_misc += 1
            continue
        sentence = ent.get("sentence", "")
        if not sentence or not sentence.strip():
            continue
        sentences_map[sentence].append(ent)

    print(f"Entidades descartadas (MISC_Spacy): {skipped_misc}")
    print(f"Oraciones únicas con entidades válidas: {len(sentences_map)}")

    # -------------------------------------------------------------------------
    # 2. Agrupar oraciones por documento para la división
    # -------------------------------------------------------------------------
    doc_to_sentences = defaultdict(list)
    for sentence, ent_list in sentences_map.items():
        # Tomamos el document_id de la primera entidad (todas deberían ser iguales)
        doc_id = ent_list[0].get("document_id", "unknown")
        doc_to_sentences[doc_id].append((sentence, ent_list))

    doc_ids = list(doc_to_sentences.keys())
    random.shuffle(doc_ids)
    print(f"Documentos únicos: {len(doc_ids)}")

    n_total = len(doc_ids)
    n_train = int(n_total * TRAIN_RATIO)
    n_val = int(n_total * VAL_RATIO)
    # n_test es el resto

    train_docs = set(doc_ids[:n_train])
    val_docs = set(doc_ids[n_train : n_train + n_val])
    test_docs = set(doc_ids[n_train + n_val :])

    print(f"División por documento → train: {len(train_docs)}, val: {len(val_docs)}, test: {len(test_docs)}")

    splits = {
        "train": ([], []),  # (lista_instancias, contador_entidades)
        "validation": ([], []),
        "test": ([], []),
    }

    instance_counter = 0
    global_stats = {
        "total_oraciones": 0,
        "oraciones_con_entidades": 0,
        "entidades_encontradas": 0,
        "entidades_no_encontradas": 0,
        "solapamientos_resueltos": 0,
        "label_counts": defaultdict(int),
    }

    # -------------------------------------------------------------------------
    # 3. Procesar cada oración
    # -------------------------------------------------------------------------
    for sentence_raw, ent_list in sentences_map.items():
        sentence = normalize_spaces(sentence_raw)
        if not sentence:
            continue

        # Encontrar spans de entidades en esta oración
        spans = find_entity_spans(sentence, ent_list)

        # Estadísticas de cobertura
        unique_texts = set()
        for ent in ent_list:
            if ent.get("project_category", "") in VALID_CATEGORIES:
                unique_texts.add(normalize_spaces(ent["text"]))

        found_texts = set()
        for s_start, s_end, _ in spans:
            found_texts.add(sentence[s_start:s_end])

        missed = unique_texts - found_texts
        global_stats["entidades_encontradas"] += len(found_texts)
        global_stats["entidades_no_encontradas"] += len(missed)

        # Dividir en palabras y calcular offsets
        words, offsets = get_word_offsets(sentence)

        # Asignar etiquetas BIO
        labels = assign_bio_labels(words, offsets, spans)

        # Contar labels
        for lab in labels:
            if lab != "O":
                global_stats["label_counts"][lab] += 1

        # Determinar a qué split pertenece esta oración
        doc_id = ent_list[0].get("document_id", "unknown")
        if doc_id in train_docs:
            split_name = "train"
        elif doc_id in val_docs:
            split_name = "validation"
        else:
            split_name = "test"

        instance = {
            "id": f"{doc_id}_{instance_counter}",
            "words": words,
            "ner_tags": labels,
        }
        splits[split_name][0].append(instance)
        splits[split_name][1].append(len([l for l in labels if l != "O"]))
        instance_counter += 1

    # -------------------------------------------------------------------------
    # 4. Guardar archivos JSON Lines
    # -------------------------------------------------------------------------
    for split_name, (instances, _) in splits.items():
        out_path = OUTPUT_DIR / f"{split_name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for inst in instances:
                f.write(json.dumps(inst, ensure_ascii=False) + "\n")
        print(f"  {split_name}: {len(instances)} oraciones guardadas en {out_path}")

    # -------------------------------------------------------------------------
    # 5. Guardar lista de etiquetas
    # -------------------------------------------------------------------------
    label_list = ["O"] + sorted(
        [f"B-{c}" for c in VALID_CATEGORIES] + [f"I-{c}" for c in VALID_CATEGORIES]
    )
    label_path = OUTPUT_DIR / "label_list.txt"
    with open(label_path, "w", encoding="utf-8") as f:
        for lab in label_list:
            f.write(lab + "\n")
    print(f"Lista de etiquetas guardada en {label_path} ({len(label_list)} etiquetas)")

    # -------------------------------------------------------------------------
    # 6. Reporte de estadísticas
    # -------------------------------------------------------------------------
    print("\n--- ESTADÍSTICAS ---")
    print(f"Oraciones procesadas: {instance_counter}")
    print(f"Entidades encontradas en oraciones: {global_stats['entidades_encontradas']}")
    print(f"Entidades NO alineadas (perdidas): {global_stats['entidades_no_encontradas']}")
    print(f"Tasa de alineación: {global_stats['entidades_encontradas'] / (global_stats['entidades_encontradas'] + global_stats['entidades_no_encontradas']) * 100:.1f}%")
    print("\nDistribución de etiquetas (solo B- e I-):")
    for lab, count in sorted(global_stats["label_counts"].items()):
        print(f"  {lab}: {count}")

    print("\n✅ Dataset BIO generado correctamente.")
    print(f"📁 Directorio: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
