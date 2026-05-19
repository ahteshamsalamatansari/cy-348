# Model file URL
# https://drive.google.com/file/d/1uuria6oJest49vUXOzJZ1_HQhYyyilnh/view?usp=sharing
import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
from transformers import Trainer, TrainingArguments

import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def train_model():
    df = pd.read_csv(os.path.join(BASE_DIR, "data/contact_dataset_20k_v3.csv"))

    train_texts, val_texts, train_labels, val_labels = train_test_split(
        df["text"].tolist(),
        df["label"].tolist(),
        test_size=0.1
    )

    tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=2
    )

    class Dataset(torch.utils.data.Dataset):
        def __init__(self, texts, labels):
            self.encodings = tokenizer(texts, truncation=True, padding=True)
            self.labels = labels

        def __getitem__(self, idx):
            item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
            item["labels"] = torch.tensor(self.labels[idx])
            return item

        def __len__(self):
            return len(self.labels)

    train_dataset = Dataset(train_texts, train_labels)
    val_dataset = Dataset(val_texts, val_labels)

    training_args = TrainingArguments(
        output_dir=os.path.join(BASE_DIR, "model"),
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        num_train_epochs=3,
        logging_dir=os.path.join(BASE_DIR, "logs"),
        save_strategy="epoch"
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset
    )

    trainer.train()

    model.save_pretrained(os.path.join(BASE_DIR, "model"))
    tokenizer.save_pretrained(os.path.join(BASE_DIR, "model"))

    return {"status": "completed"}