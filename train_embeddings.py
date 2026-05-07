"""
Entrenar modelo de embeddings para clasificación de entidades.

Estrategia:
- Usar sentence-transformers con BatchHardTripletLoss
- Entidades del mismo categoría → embeddings cercanos
- Entidades de categorías diferentes → embeddings lejanos

Base model: paraphrase-multilingual-MiniLM-L12-v2 (rápido, multilingüe)
"""
import json
import os
import random
from collections import Counter
from pathlib import Path

# Forzar CPU en Mac para evitar OOM en MPS
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    losses,
)
from sentence_transformers.training_args import SentenceTransformerTrainingArguments
from datasets import Dataset

ENTITIES_DIR = Path("/Users/tania/Documents/proyectoHUB/semanticClassification/data/processed/entities")
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
OUTPUT_DIR = Path("/Users/tania/Documents/proyectoHUB/semanticClassification/models/entity_embeddings")

# =============================================================================
# 1. CARGAR Y FILTRAR ENTIDADES
# =============================================================================

with open(ENTITIES_DIR / "_entities_for_embeddings.json", "r", encoding="utf-8") as f:
    all_entities = json.load(f)

print(f"Entidades únicas totales: {len(all_entities)}")

# Filtrar: excluir MISC_Spacy y categorías con muy pocos ejemplos únicos
MIN_UNIQUE_PER_CATEGORY = 5

cat_counts = Counter(e["category"] for e in all_entities)
valid_categories = {
    cat for cat, count in cat_counts.items()
    if cat != "MISC_Spacy" and count >= MIN_UNIQUE_PER_CATEGORY
}

filtered = [
    e for e in all_entities
    if e["category"] in valid_categories
]

print(f"\n📊 Distribución de entidades únicas:")
for cat, count in cat_counts.most_common():
    status = "✅" if cat in valid_categories else "❌"
    print(f"  {status} {cat}: {count}")

print(f"\nEntidades para entrenamiento: {len(filtered)}")

# Mapeo de categoría a ID
label2id = {cat: idx for idx, cat in enumerate(sorted(valid_categories))}
id2label = {idx: cat for cat, idx in label2id.items()}

# =============================================================================
# 2. PREPARAR DATASET
# =============================================================================

# Para BatchHardTripletLoss necesitamos: sentence, label
# Usamos el texto de la entidad directamente como oración
sentences = [e["text"] for e in filtered]
labels = [label2id[e["category"]] for e in filtered]

# Aumentar datos levemente: añadir prefijo contextual para robustez
augmented_sentences = []
augmented_labels = []

for text, label in zip(sentences, labels):
    augmented_sentences.append(text)
    augmented_labels.append(label)
    # Variante con contexto categórico implícito
    # (no incluimos la categoría explícita para evitar data leakage en inference)

# Shuffle
combined = list(zip(augmented_sentences, augmented_labels))
random.seed(42)
random.shuffle(combined)
train_sentences, train_labels = zip(*combined)

train_dataset = Dataset.from_dict({
    "sentence": list(train_sentences),
    "label": list(train_labels),
})

print(f"\n📚 Ejemplos de entrenamiento: {len(train_dataset)}")
print(f"🏷️  Categorías: {len(label2id)}")

# =============================================================================
# 3. CARGAR MODELO Y CONFIGURAR ENTRENAMIENTO
# =============================================================================

print(f"\n🔄 Cargando modelo base: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME, device="cpu")

# BatchHardTripletLoss: en cada batch, selecciona el positive más difícil
# y el negative más difícil para cada anchor.
loss = losses.BatchHardTripletLoss(model=model)

# Hiperparámetros conservadores para primera iteración
BATCH_SIZE = 8
EPOCHS = 1
LEARNING_RATE = 2e-5
WARMUP_STEPS = 100

print(f"\n⚙️  Hiperparámetros:")
print(f"   Batch size: {BATCH_SIZE}")
print(f"   Epochs: {EPOCHS}")
print(f"   Learning rate: {LEARNING_RATE}")
print(f"   Warmup steps: {WARMUP_STEPS}")

# =============================================================================
# 4. ENTRENAR
# =============================================================================

trainer = SentenceTransformerTrainer(
    model=model,
    train_dataset=train_dataset,
    loss=loss,
)

print("\n🚀 Iniciando entrenamiento...")

training_args = SentenceTransformerTrainingArguments(
    output_dir=str(OUTPUT_DIR / "checkpoints"),
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    learning_rate=LEARNING_RATE,
    warmup_steps=WARMUP_STEPS,
    save_strategy="epoch",
    logging_steps=50,
    report_to="none",
)

trainer = SentenceTransformerTrainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    loss=loss,
)

trainer.train()

# =============================================================================
# 5. GUARDAR MODELO Y METADATOS
# =============================================================================

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
model.save(str(OUTPUT_DIR))

# Guardar metadatos
metadata = {
    "base_model": MODEL_NAME,
    "trained_categories": sorted(valid_categories),
    "label2id": label2id,
    "id2label": id2label,
    "num_training_examples": len(train_dataset),
    "hyperparameters": {
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "warmup_steps": WARMUP_STEPS,
    },
}

with open(OUTPUT_DIR / "metadata.json", "w", encoding="utf-8") as f:
    json.dump(metadata, f, ensure_ascii=False, indent=2)

print(f"\n✅ Modelo guardado en: {OUTPUT_DIR}")
print(f"📄 Metadatos guardados en: {OUTPUT_DIR / 'metadata.json'}")

# =============================================================================
# 6. EVALUACIÓN RÁPIDA: embedding de muestra
# =============================================================================

print("\n🔍 Evaluación rápida con muestras:")
samples = [
    ("AGRAP", "INSTITUCIÓN"),
    ("Solidaridad Network", "INSTITUCIÓN"),
    ("Madre de Dios", "LUGAR"),
    ("Perú", "LUGAR"),
    ("trazabilidad", "PRÁCTICA"),
]

embeddings = model.encode([s[0] for s in samples])

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

sim_matrix = cosine_similarity(embeddings)
print("\nMatriz de similitud coseno:")
for i, (text, cat) in enumerate(samples):
    print(f"  {text} ({cat})")

print("\nSimilitudes intra-categoría (deberían ser altas):")
for i, (text1, cat1) in enumerate(samples):
    for j, (text2, cat2) in enumerate(samples):
        if i < j and cat1 == cat2:
            print(f"  {text1} <-> {text2}: {sim_matrix[i][j]:.3f}")

print("\nSimilitudes inter-categoría (deberían ser bajas):")
for i, (text1, cat1) in enumerate(samples):
    for j, (text2, cat2) in enumerate(samples):
        if i < j and cat1 != cat2:
            print(f"  {text1} ({cat1}) <-> {text2} ({cat2}): {sim_matrix[i][j]:.3f}")
