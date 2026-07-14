"""
M4 -- Sequence Model (LSTM for temporal gesture recognition)
=============================================================
Trains LSTM on temporal keypoint sequences for dynamic sign recognition

Architecture:
    Input: [batch, seq_len, 300] keypoints
    ↓
    LSTM(128, 2 layers, dropout=0.2)
    ↓
    Dense(vocab_size + 1) with softmax
    ↓
    Output: [batch, vocab_size+1] logits

Usage:
    python m4_sequence_model.py --train --data-dir data/processed
    python m4_sequence_model.py --evaluate --model models/sequence_model.pt
"""

import os
import json
import pickle
from pathlib import Path
from typing import Tuple, List
import argparse

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import LabelEncoder


class KeypointSequenceDataset(Dataset):
    """PyTorch dataset for keypoint sequences."""

    def __init__(self, sequences: List[np.ndarray], labels: List[str],
                 label_encoder=None, max_seq_len: int = 45):
        self.sequences = sequences
        self.labels = labels
        self.max_seq_len = max_seq_len

        if label_encoder is None:
            self.label_encoder = LabelEncoder()
            self.label_encoder.fit(labels)
        else:
            self.label_encoder = label_encoder

        self.encoded_labels = self.label_encoder.transform(labels)

    def __len__(self):
        return len(self.sequences)

    def __getitem__(self, idx):
        seq = self.sequences[idx]

        # Pad or truncate to max_seq_len
        if len(seq) < self.max_seq_len:
            seq = np.pad(seq, ((0, self.max_seq_len - len(seq)), (0, 0)))
        else:
            seq = seq[:self.max_seq_len]

        label = self.encoded_labels[idx]

        return torch.FloatTensor(seq), torch.LongTensor([label]).squeeze()


class SequenceModel(nn.Module):
    """LSTM-based sequence classifier."""

    def __init__(self, input_size: int = 300, hidden_size: int = 128,
                 num_classes: int = 26, num_layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers=num_layers,
                           batch_first=True, dropout=dropout)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        # x: [batch, seq_len, 300]
        lstm_out, _ = self.lstm(x)  # [batch, seq_len, hidden]
        # Use last timestep
        last_out = lstm_out[:, -1, :]  # [batch, hidden]
        out = self.dropout(last_out)
        logits = self.fc(out)  # [batch, num_classes]
        return logits


class SequenceModelTrainer:
    """Trainer for sequence classification."""

    def __init__(self, model_path: str = "models/sequence_model.pt",
                 device: str = "cuda" if torch.cuda.is_available() else "cpu"):
        self.model_path = model_path
        self.device = torch.device(device)
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        self.model = None
        self.label_encoder = None

    def train(self, train_loader, val_loader, num_epochs: int = 50,
             num_classes: int = 26, lr: float = 0.001):
        """Train the model."""
        self.model = SequenceModel(num_classes=num_classes).to(self.device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.CrossEntropyLoss()

        for epoch in range(num_epochs):
            # Training
            self.model.train()
            train_loss = 0
            for sequences, labels in train_loader:
                sequences = sequences.to(self.device)
                labels = labels.to(self.device)

                optimizer.zero_grad()
                logits = self.model(sequences)
                loss = criterion(logits, labels)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            # Validation
            self.model.eval()
            val_loss = 0
            val_acc = 0
            with torch.no_grad():
                for sequences, labels in val_loader:
                    sequences = sequences.to(self.device)
                    labels = labels.to(self.device)

                    logits = self.model(sequences)
                    loss = criterion(logits, labels)
                    val_loss += loss.item()

                    preds = logits.argmax(dim=1)
                    val_acc += (preds == labels).float().mean().item()

            if (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{num_epochs} | "
                      f"Train loss: {train_loss/len(train_loader):.4f} | "
                      f"Val loss: {val_loss/len(val_loader):.4f} | "
                      f"Val acc: {val_acc/len(val_loader):.4f}")

        print("✓ Training complete")
        self.save()

    def save(self):
        """Save model to disk."""
        torch.save(self.model.state_dict(), self.model_path)
        print(f"Model saved to {self.model_path}")

    def load(self, num_classes: int = 26):
        """Load model from disk."""
        self.model = SequenceModel(num_classes=num_classes).to(self.device)
        self.model.load_state_dict(torch.load(self.model_path,
                                             map_location=self.device))
        self.model.eval()
        print(f"Model loaded from {self.model_path}")


def main():
    parser = argparse.ArgumentParser(description="M4: Sequence Model")
    parser.add_argument("--train", action="store_true", help="Train model")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate model")
    parser.add_argument("--data-dir", default="data/processed", help="Data directory")
    parser.add_argument("--model", default="models/sequence_model.pt", help="Model path")
    args = parser.parse_args()

    if args.train:
        # Load data
        train_file = Path(args.data_dir) / "train.pkl"
        val_file = Path(args.data_dir) / "val.pkl"

        if not train_file.exists() or not val_file.exists():
            print("Run m3_data_pipeline.py --process first")
            return

        with open(train_file, 'rb') as f:
            train_data = pickle.load(f)
        with open(val_file, 'rb') as f:
            val_data = pickle.load(f)

        # Create datasets
        train_dataset = KeypointSequenceDataset(train_data['sequences'],
                                               train_data['labels'])
        val_dataset = KeypointSequenceDataset(val_data['sequences'],
                                             val_data['labels'],
                                             train_dataset.label_encoder)

        train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=32)

        # Train
        num_classes = len(train_dataset.label_encoder.classes_)
        trainer = SequenceModelTrainer(model_path=args.model)
        trainer.label_encoder = train_dataset.label_encoder
        trainer.train(train_loader, val_loader, num_classes=num_classes)

    elif args.evaluate:
        print("Evaluation not yet implemented")


if __name__ == "__main__":
    main()
