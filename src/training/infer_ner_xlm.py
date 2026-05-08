"""
infer_ner_xlm.py

Script de inferencia para probar el modelo XLM-RoBERTa fine-tuned en una oración
de ejemplo. Útil para comparar visualmente con la salida del pipeline anterior (spaCy).

Uso:
    python src/training/infer_ner_xlm.py "WWF trabaja con la Alianza por una Ganadería Regenerativa en la Amazonía Peruana."
"""

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer


def main():
    parser = argparse.ArgumentParser(description="Inferencia NER con XLM-RoBERTa fine-tuned")
    parser.add_argument("text", type=str, help="Texto de entrada para analizar")
    parser.add_argument(
        "--model_path",
        type=str,
        default="models/ner_xlm_roberta/final",
        help="Ruta al modelo entrenado",
    )
    args = parser.parse_args()

    model_path = Path(args.model_path)
    if not model_path.exists():
        print(f"ERROR: No se encontró el modelo en {model_path}")
        print("Ejecuta primero src/training/train_ner_xlm.py")
        return

    # Cargar config de etiquetas
    config_path = model_path / "label_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    id2label = {int(k): v for k, v in config["id2label"].items()}

    # Cargar modelo y tokenizer
    print(f"Cargando modelo desde {model_path} ...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForTokenClassification.from_pretrained(str(model_path))
    model.eval()

    # Tokenizar
    inputs = tokenizer(
        args.text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    # Inferencia
    with torch.no_grad():
        logits = model(**inputs).logits

    predictions = torch.argmax(logits, dim=2)[0]
    tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0])

    # Agrupar tokens en entidades BIO
    entities = []
    current = None

    for token, pred_id in zip(tokens, predictions):
        label = id2label[pred_id.item()]

        # Ignorar tokens especiales
        if token in (tokenizer.pad_token, tokenizer.cls_token, tokenizer.sep_token):
            continue

        # Limpiar prefijo ▁ de SentencePiece (reemplazar por espacio)
        clean_token = token.replace("▁", " ")

        if label.startswith("B-"):
            if current:
                entities.append(current)
            current = {
                "category": label[2:],
                "text": clean_token.strip(),
            }
        elif label.startswith("I-") and current and current["category"] == label[2:]:
            current["text"] += clean_token
        else:
            if current:
                entities.append(current)
                current = None

    if current:
        entities.append(current)

    # Mostrar resultados
    print(f"\nTexto: {args.text}")
    print(f"Tokens: {len(tokens)}")
    print("\nEntidades detectadas:")
    if not entities:
        print("  (ninguna)")
    for e in entities:
        print(f"  [{e['category']}] {e['text']}")


if __name__ == "__main__":
    main()
