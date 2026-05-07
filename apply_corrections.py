"""
Aplicar correcciones manuales del CSV al dataset completo de entidades.
Generar dataset corregido para entrenar embeddings.

Lógica:
1. Cargar correcciones manuales del CSV revisado por el usuario.
2. Construir lista de textos a DESCARTAR (proposed_category == "No es entidad").
3. Construir lista de textos a CORREGIR (cambiar nombre + categoría).
4. Aplicar normalizaciones globales basadas en notas del usuario.
5. Filtrar entidades descartadas del dataset completo.
6. Guardar dataset corregido y lista única para embeddings.
"""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ENTITIES_DIR = Path("/Users/tania/Documents/proyectoHUB/semanticClassification/data/processed/entities")
CSV_PATH = ENTITIES_DIR / "_misc_spacy_for_review - _misc_spacy_for_review.csv"

# =============================================================================
# 1. CARGAR CORRECCIONES MANUALES
# =============================================================================

discard_texts = set()   # textos a eliminar del dataset
corrections = {}        # text_lower -> {full_name, category, notes}

with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        text = row["text"].strip()
        text_lower = text.lower()
        full_name = row.get("full_entity_name", "").strip()
        category = row.get("proposed_category", "").strip()
        notes = row.get("notes", "").strip()

        if not text:
            continue

        # Descartar explícitamente (puede estar en proposed_category o en notes)
        if category == "No es entidad" or notes == "No es entidad":
            discard_texts.add(text_lower)
            continue

        # Si tiene categoría asignada
        if category:
            # Mapear categorías compuestas del usuario a categorías del proyecto
            if category == "ORGANIZACION/ACTOR/AGENTE":
                category = "INSTITUCIÓN"

            corrections[text_lower] = {
                "full_name": full_name if full_name else text,
                "category": category,
                "notes": notes,
            }

print(f"🗑️  Textos marcados para descartar: {len(discard_texts)}")
print(f"✏️  Correcciones manuales: {len(corrections)}")

# =============================================================================
# 2. REGLAS DE NORMALIZACIÓN GLOBAL (extraídas de las notas del usuario)
# =============================================================================

# Lista de tuplas: (texto_a_buscar, texto_normalizado, categoría_opcional)
# Estas reglas se aplican a CUALQUIER entidad del dataset, no solo a las del CSV.
NORMALIZATION_RULES = [
    # (search, replacement, category_override or None)
    ("solidaridad", "Solidaridad Network", "INSTITUCIÓN"),
    ("alianza por una ganadería regenerativa en la amazonía peruana", "AGRAP", "INSTITUCIÓN"),
    ("la alianza", "AGRAP", "INSTITUCIÓN"),  # contextual, pero aplicamos globalmente con cuidado
    ("cp cacao", "Cooperativa Agraria CP Cacao", "INSTITUCIÓN"),
    ("bosques tropicales", "Tropical Forest Alliance", "INSTITUCIÓN"),
    ("agroperú", "AgroPerú y Agroideas", "NARRATIVA"),
    ("agroideas", "AgroPerú y Agroideas", "NARRATIVA"),
]

# Añadir reglas extraídas dinámicamente de las notas del CSV
for text_lower, corr in corrections.items():
    notes = corr["notes"].lower()
    full_name = corr["full_name"]
    category = corr["category"]

    # Patrón: "cada vez que diga 'X' ... 'Y'"
    # Patrón: "siempre es 'X'"
    # Patrón: "siempre que diga 'X' ... 'Y'"
    # Solo añadimos si el full_name difiere del texto original
    if full_name.lower() != text_lower:
        # Evitar duplicados
        exists = any(r[0] == text_lower for r in NORMALIZATION_RULES)
        if not exists:
            NORMALIZATION_RULES.append((text_lower, full_name, category))

print(f"📐 Reglas de normalización globales: {len(NORMALIZATION_RULES)}")

# =============================================================================
# 3. CARGAR DATASET COMPLETO Y APLICAR CORRECCIONES
# =============================================================================

with open(ENTITIES_DIR / "_all_entities.json", "r", encoding="utf-8") as f:
    all_entities = json.load(f)

print(f"📄 Entidades totales antes de filtrar: {len(all_entities)}")

filtered_entities = []
updated_count = 0
discarded_count = 0
normalization_count = 0
entity_counts = Counter()

for entity in all_entities:
    text = entity["text"].strip()
    text_lower = text.lower()

    # --- Paso A: Descartar si está en lista negra ---
    if text_lower in discard_texts:
        discarded_count += 1
        continue

    # --- Paso B: Aplicar corrección manual exacta ---
    if text_lower in corrections:
        corr = corrections[text_lower]
        entity["project_category"] = corr["category"]
        if corr["full_name"]:
            entity["text"] = corr["full_name"]
        entity["manual_review"] = True
        entity["review_notes"] = corr["notes"]
        updated_count += 1

    # --- Paso C: Aplicar normalizaciones globales ---
    # Solo si no fue ya corregido manualmente (para no sobreescribir)
    elif not entity.get("manual_review"):
        for search, replacement, cat_override in NORMALIZATION_RULES:
            # Búsqueda exacta case-insensitive
            if text_lower == search:
                entity["text"] = replacement
                if cat_override:
                    entity["project_category"] = cat_override
                entity["auto_normalized"] = True
                normalization_count += 1
                break
            # Búsqueda parcial para frases cortas (>= 3 palabras) que spaCy cortó
            # Solo si el texto original contiene el search como subcadena
            elif len(search.split()) >= 3 and search in text_lower:
                entity["text"] = replacement
                if cat_override:
                    entity["project_category"] = cat_override
                entity["auto_normalized"] = True
                normalization_count += 1
                break

    filtered_entities.append(entity)
    entity_counts[entity["project_category"]] += 1

print(f"🗑️  Entidades descartadas: {discarded_count}")
print(f"✏️  Entidades corregidas manualmente: {updated_count}")
print(f"🤖 Entidades normalizadas automáticamente: {normalization_count}")
print(f"📄 Entidades finales: {len(filtered_entities)}")

print(f"\n📊 Distribución final:")
for cat, count in entity_counts.most_common():
    pct = count / len(filtered_entities) * 100
    print(f"  {cat}: {count} ({pct:.1f}%)")

# =============================================================================
# 4. GUARDAR DATASET CORREGIDO
# =============================================================================

output_path = ENTITIES_DIR / "_all_entities_corrected.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(filtered_entities, f, ensure_ascii=False, indent=2)

print(f"\n✅ Dataset corregido guardado: {output_path}")

# =============================================================================
# 5. GENERAR LISTA ÚNICA PARA EMBEDDINGS
# =============================================================================

unique_entities = {}
for entity in filtered_entities:
    text = entity["text"]
    cat = entity["project_category"]
    key = f"{text.lower()}::{cat}"

    if key not in unique_entities:
        unique_entities[key] = {
            "text": text,
            "category": cat,
            "count": 1,
        }
    else:
        unique_entities[key]["count"] += 1

embeddings_data = sorted(
    unique_entities.values(),
    key=lambda x: x["count"],
    reverse=True,
)

with open(ENTITIES_DIR / "_entities_for_embeddings.json", "w", encoding="utf-8") as f:
    json.dump(embeddings_data, f, ensure_ascii=False, indent=2)

print(f"\n📊 Entidades únicas para embeddings: {len(embeddings_data)}")

# Muestra de las más frecuentes
print(f"\n📋 Top 20 entidades corregidas más frecuentes:")
for data in embeddings_data[:20]:
    print(f"  [{data['category']}] {data['text']} ({data['count']}x)")

# =============================================================================
# 6. RESUMEN DE ESTADÍSTICAS POR DOCUMENTO
# =============================================================================

doc_counts = Counter(e["document_id"] for e in filtered_entities)
print(f"\n📁 Documentos procesados: {len(doc_counts)}")
print(f"   Promedio de entidades por documento: {len(filtered_entities)/len(doc_counts):.1f}")
