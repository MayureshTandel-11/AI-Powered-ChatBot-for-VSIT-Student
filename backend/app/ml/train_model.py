"""CLI entry point for training the intent classifier."""

import json
import logging

from app.ml.training import train_and_save

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    metrics = train_and_save()
    print("Intent classifier trained successfully.")
    print(json.dumps(
        {
            "training_examples": metrics["training_examples"],
            "accuracy": metrics["accuracy"],
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1_score": metrics["f1_score"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
