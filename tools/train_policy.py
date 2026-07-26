#!/usr/bin/env python3
"""训练行为克隆策略网络"""
import argparse, os, sys
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

class HandDataset(Dataset):
    def __init__(self, path):
        data = np.load(path)
        self.states = torch.from_numpy(data['states'])
        self.actions = torch.from_numpy(data['actions'])
        # Normalize states and actions
        self.s_mean, self.s_std = self.states.mean(0), self.states.std(0).clamp(min=1)
        self.a_mean, self.a_std = self.actions.mean(0), self.actions.std(0).clamp(min=1)
        self.states = (self.states - self.s_mean) / self.s_std
        self.actions = (self.actions - self.a_mean) / self.a_std
        print(f"Loaded {len(self)} samples, state_dim={self.states.shape[1]}, action_dim={self.actions.shape[1]}")

    def __len__(self): return len(self.states)

    def __getitem__(self, i):
        # Add dummy image input (zeros, 3x224x224 — simplified since we only use state)
        return {'state': self.states[i], 'action': self.actions[i],
                'image': torch.zeros(3, 224, 224)}


class Policy(nn.Module):
    def __init__(self, state_dim=13, action_dim=18, hidden=128):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(state_dim, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
            nn.Linear(hidden // 2, action_dim),
        )

    def forward(self, image, state):
        return self.fc(state)


def train(dataset_path, epochs=100, batch_size=32, lr=1e-4, output='models/policy.pt'):
    ds = HandDataset(dataset_path)
    # Split train/val
    split = int(len(ds) * 0.8)
    train_ds, val_ds = torch.utils.data.random_split(ds, [split, len(ds)-split])
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = Policy().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-5)
    loss_fn = nn.MSELoss()
    best_loss = float('inf')

    print(f"Training on {device}, {epochs} epochs, {len(train_ds)} train / {len(val_ds)} val samples")

    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for batch in train_loader:
            state = batch['state'].to(device)
            image = batch['image'].to(device)
            target = batch['action'].to(device)
            pred = model(image, state)
            loss = loss_fn(pred, target)
            opt.zero_grad()
            loss.backward()
            opt.step()
            train_loss += loss.item()

        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for batch in val_loader:
                state = batch['state'].to(device)
                image = batch['image'].to(device)
                target = batch['action'].to(device)
                pred = model(image, state)
                val_loss += loss_fn(pred, target).item()

        train_loss /= len(train_loader)
        val_loss /= len(val_loader)

        if (epoch + 1) % 10 == 0:
            print(f"Epoch {epoch+1}/{epochs}: train_loss={train_loss:.4f} val_loss={val_loss:.4f}")

        if val_loss < best_loss:
            best_loss = val_loss
            os.makedirs('models', exist_ok=True)
            torch.save({'model': model.state_dict(),
                        's_mean': ds.s_mean, 's_std': ds.s_std,
                        'a_mean': ds.a_mean, 'a_std': ds.a_std}, output)
            if epoch > 50:
                print(f"  → saved best model (val_loss={best_loss:.4f})")

    print(f"Done. Best val_loss={best_loss:.4f}, saved to {output}")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--dataset', required=True)
    p.add_argument('--epochs', type=int, default=100)
    p.add_argument('--batch_size', type=int, default=32)
    p.add_argument('--lr', type=float, default=1e-4)
    p.add_argument('--output', default='models/policy.pt')
    train(**vars(p.parse_args()))
