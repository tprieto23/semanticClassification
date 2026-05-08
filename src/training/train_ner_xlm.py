"""
train_ner_xlm.py

Entrena un modelo XLM-RoBERTa para Token Classification (NER) usando el
dataset BIO generado por prepare_ner_dataset.py.

ADVERTENCIA: El dataset de entrenamiento es provisional (primera iteración
de correcciones manuales sobre salida de spaCy + reglas). Contiene errores
residuales. Este modelo debe considerarse un prototipo iterativo, no un
producto final.

Uso:
    python src/training/train_ner_xlm.py --epochs 5 --batch_size 4

Requiere:
    torch, transformers, datasets, seqeval, evaluate, accelerate
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    DataCollatorForTokenClassification,
    Trainer,
    TrainingArguments,
)

import evaluate

# =============================================================================
# CONFIGURACIÓN
# =============================================================================

DATASET_DIR = Path("data/processed/entities/ner_dataset")
MODEL_OUTPUT_DIR = Path("models/ner_xlm_roberta")
BASE_MODEL = "xlm-roberta-base"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================


def load_label_list(path: Path) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def align_labels_with_tokens(tokenized_inputs, raw_labels, label2id: dict):
    """
    Proyecta etiquetas a nivel de palabra a tokens (subwords).
    Los subwords que no son el primero de una palabra reciben -100 (ignorados en loss).
    """
    labels = []
    for i, label in enumerate(raw_labels):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        label_ids = []
        previous_word_idx = None
        for word_idx in word_ids:
            if word_idx is None:
                # Tokens especiales ([CLS], [SEP], padding)
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                # Primer subword de una palabra → etiqueta real
                label_ids.append(label2id[label[word_idx]])
            else:
                # Subwords subsiguientes de la misma palabra → ignorar
                label_ids.append(-100)
            previous_word_idx = word_idx
        labels.append(label_ids)
    return labels


def tokenize_and_align_labels(examples, tokenizer, label2id: dict):
    tokenized_inputs = tokenizer(
        examples["words"],
        truncation=True,
        is_split_into_words=True,
    )
    tokenized_inputs["labels"] = align_labels_with_tokens(
        tokenized_inputs, examples["ner_tags"], label2id
    )
    return tokenized_inputs


def compute_metrics_factory(label_list: list):
    seqeval = evaluate.load("seqeval")

    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=2)

        true_predictions = [
            [label_list[p] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]
        true_labels = [
            [label_list[l] for (p, l) in zip(prediction, label) if l != -100]
            for prediction, label in zip(predictions, labels)
        ]

        results = seqeval.compute(
            predictions=true_predictions, references=true_labels, zero_division=0
        )

        # Desglose por categoría (solo imprimir, no retornar todo para no saturar logs)
        per_entity = {
            k: v
            for k, v in results.items()
            if k not in ("overall_precision", "overall_recall", "overall_f1", "overall_accuracy")
        }
        if per_entity:
            logger.info("Métricas por entidad (último eval):")
            for k, v in list(per_entity.items())[:10]:  # limitar output
                logger.info(f"  {k}: {v}")

        return {
            "precision": results["overall_precision"],
            "recall": results["overall_recall"],
            "f1": results["overall_f1"],
            "accuracy": results["overall_accuracy"],
        }

    return compute_metrics


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning XLM-RoBERTa para NER")
    parser.add_argument("--epochs", type=int, default=5, help="Épocas de entrenamiento")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size por dispositivo")
    parser.add_argument("--lr", type=float, default=5e-5, help="Learning rate")
    parser.add_argument("--weight_decay", type=float, default=0.01, help="Weight decay")
    parser.add_argument("--max_length", type=int, default=512, help="Máximo de tokens por secuencia")
    parser.add_argument("--seed", type=int, default=42, help="Semilla aleatoria")
    parser.add_argument("--gradient_accumulation_steps", type=int, default=1, help="Pasos de acumulación de gradiente")
    parser.add_argument("--gradient_checkpointing", action="store_true", help="Activar gradient checkpointing (ahorra memoria)")
    parser.add_argument("--force_cpu", action="store_true", help="Forzar entrenamiento en CPU (más lento pero evita OOM en MPS)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("FINE-TUNING XLM-ROBERTA PARA NER")
    logger.info("=" * 60)
    logger.info(f"Modelo base: {BASE_MODEL}")
    logger.info(f"Épocas: {args.epochs} | Batch size: {args.batch_size} | LR: {args.lr}")

    # -------------------------------------------------------------------------
    # Dispositivo
    # -------------------------------------------------------------------------
    if args.force_cpu:
        device = torch.device("cpu")
        logger.info("Dispositivo: CPU (forzado por --force_cpu)")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Dispositivo: Apple Silicon MPS")
        logger.info("AVISO: Si ocurre OOM, usa --force_cpu o reduce --batch_size.")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info("Dispositivo: CUDA")
    else:
        device = torch.device("cpu")
        logger.info("Dispositivo: CPU (será lento)")

    # -------------------------------------------------------------------------
    # Cargar etiquetas
    # -------------------------------------------------------------------------
    label_list_path = DATASET_DIR / "label_list.txt"
    if not label_list_path.exists():
        logger.error(f"No se encontró {label_list_path}. Ejecuta prepare_ner_dataset.py primero.")
        sys.exit(1)

    label_list = load_label_list(label_list_path)
    id2label = {i: label for i, label in enumerate(label_list)}
    label2id = {label: i for i, label in enumerate(label_list)}
    logger.info(f"Etiquetas cargadas: {len(label_list)} → {label_list}")

    # -------------------------------------------------------------------------
    # Cargar dataset BIO
    # -------------------------------------------------------------------------
    data_files = {
        "train": str(DATASET_DIR / "train.jsonl"),
        "validation": str(DATASET_DIR / "validation.jsonl"),
        "test": str(DATASET_DIR / "test.jsonl"),
    }

    for split, path in data_files.items():
        if not Path(path).exists():
            logger.error(f"Archivo no encontrado: {path}")
            sys.exit(1)

    logger.info("Cargando dataset desde JSON Lines...")
    dataset = load_dataset("json", data_files=data_files)
    logger.info(f"Splits → train: {len(dataset['train'])}, val: {len(dataset['validation'])}, test: {len(dataset['test'])}")

    # -------------------------------------------------------------------------
    # Tokenizer
    # -------------------------------------------------------------------------
    logger.info(f"Cargando tokenizer: {BASE_MODEL} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, use_fast=True)

    # -------------------------------------------------------------------------
    # Tokenizar y alinear etiquetas
    # -------------------------------------------------------------------------
    logger.info("Tokenizando y alineando etiquetas BIO...")
    tokenized_dataset = dataset.map(
        lambda examples: tokenize_and_align_labels(examples, tokenizer, label2id),
        batched=True,
        remove_columns=dataset["train"].column_names,
    )
    logger.info("Tokenización completada.")

    # -------------------------------------------------------------------------
    # Modelo
    # -------------------------------------------------------------------------
    logger.info(f"Cargando modelo: {BASE_MODEL} ...")
    model = AutoModelForTokenClassification.from_pretrained(
        BASE_MODEL,
        num_labels=len(label_list),
        id2label=id2label,
        label2id=label2id,
    )
    if args.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        logger.info("Gradient checkpointing activado.")

    model.to(device)

    # -------------------------------------------------------------------------
    # Métricas
    # -------------------------------------------------------------------------
    compute_metrics = compute_metrics_factory(label_list)

    # -------------------------------------------------------------------------
    # Argumentos de entrenamiento
    # -------------------------------------------------------------------------
    output_dir = MODEL_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        logging_dir=str(output_dir / "logs"),
        logging_steps=50,
        seed=args.seed,
        report_to="none",  # evita intentar conectar con WandB/TensorBoard
        fp16=False,
        dataloader_pin_memory=False,
        use_cpu=args.force_cpu,
    )

    data_collator = DataCollatorForTokenClassification(tokenizer)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        eval_dataset=tokenized_dataset["validation"],
        processing_class=tokenizer,  # v5 usa processing_class; fallback a tokenizer si no funciona
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    # -------------------------------------------------------------------------
    # Entrenar
    # -------------------------------------------------------------------------
    logger.info("Iniciando entrenamiento...")
    trainer.train()

    # -------------------------------------------------------------------------
    # Guardar modelo
    # -------------------------------------------------------------------------
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Guardando modelo final en {final_dir} ...")
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))

    # Guardar label mapping para inference
    with open(final_dir / "label_config.json", "w", encoding="utf-8") as f:
        json.dump({"id2label": id2label, "label2id": label2id, "label_list": label_list}, f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------------
    # Evaluar en test set
    # -------------------------------------------------------------------------
    logger.info("Evaluando en test set...")
    test_results = trainer.evaluate(tokenized_dataset["test"])
    logger.info(f"Test results: {test_results}")

    # Guardar métricas
    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)

    logger.info("=" * 60)
    logger.info("ENTRENAMIENTO COMPLETADO")
    logger.info(f"Modelo guardado en: {final_dir}")
    logger.info(f"Métricas guardadas en: {output_dir / 'metrics.json'}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
