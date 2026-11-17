import json
from pathlib import Path

import torch
import torch.nn as nn
from transformers import AutoModel, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODEL_DIR = (
    PROJECT_ROOT
    / "models"
    / "m1_distilbert"
    / "final_6_intent_balanced"
)

MAX_LENGTH = 64
DEVICE = torch.device("cpu")


class M1DistilBERT(nn.Module):
    """Original SatQuery AI seven-head DistilBERT architecture."""

    def __init__(self, model_name, labels):
        super().__init__()

        self.encoder = AutoModel.from_pretrained(
            model_name,
            local_files_only=True,
        )

        hidden_size = self.encoder.config.hidden_size

        self.heads = nn.ModuleDict({
            head: nn.Linear(hidden_size, len(label_list))
            for head, label_list in labels.items()
        })

    def forward(self, input_ids, attention_mask):
        outputs = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask
        )

        pooled = outputs.last_hidden_state[:, 0, :]

        return {
            head: layer(pooled)
            for head, layer in self.heads.items()
        }


class M1Predictor:

    def __init__(self, model_dir=MODEL_DIR):
        self.model_dir = Path(model_dir)

        config_path = self.model_dir / "config.json"
        checkpoint_path = self.model_dir / "model.pt"

        if not config_path.is_file():
            raise FileNotFoundError(
                f"M1 config not found: {config_path}"
            )

        if not checkpoint_path.is_file():
            raise FileNotFoundError(
                f"M1 checkpoint not found: {checkpoint_path}"
            )

        with config_path.open("r", encoding="utf-8") as file:
            self.config = json.load(file)

        self.labels = self.config["labels"]
        self.max_length = self.config.get("max_length", MAX_LENGTH)

        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_dir),
            local_files_only=True
        )

        self.model = M1DistilBERT(
            self.config["model_name"],
            self.labels
        )

        checkpoint = torch.load(
            checkpoint_path,
            map_location=DEVICE,
            weights_only=True
        )

        self.model.load_state_dict(checkpoint, strict=True)
        self.model.to(DEVICE)
        self.model.eval()

        self.head_names = list(self.labels.keys())

        print("M1 DistilBERT loaded successfully.")
        print(f"Checkpoint: {checkpoint_path}")
        print(f"Device: {DEVICE}")
        print(f"Heads: {self.head_names}")

    def predict(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        encoded = self.tokenizer(
            query.strip(),
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
            padding="max_length"
        )

        input_ids = encoded["input_ids"].to(DEVICE)
        attention_mask = encoded["attention_mask"].to(DEVICE)

        with torch.inference_mode():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask
            )

        predictions = {}

        for head, logits in outputs.items():
            probabilities = torch.softmax(logits, dim=-1)
            confidence, predicted_id = probabilities.max(dim=-1)

            label_id = predicted_id.item()

            predictions[head] = {
                "label": self.labels[head][label_id],
                "confidence": round(confidence.item(), 6)
            }

        token_count = int(attention_mask[0].sum().item())
        tokens = self.tokenizer.convert_ids_to_tokens(
            input_ids[0][:token_count].tolist()
        )

        return {
            "query": query,
            "tokenized_input": tokens,
            "intent": predictions["intent"]["label"],
            "predictions": predictions,
            "model": "DistilBERT",
            "checkpoint": self.model_dir.name
        }


if __name__ == "__main__":
    predictor = M1Predictor()

    test_queries = [
        "How many buildings are visible in the image?",
        "What land cover types are present in the image?",
        "Are there any changes in the buildings?"
    ]

    for query in test_queries:
        print("\n" + "=" * 60)
        print(predictor.predict(query))
