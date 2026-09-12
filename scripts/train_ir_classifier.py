"""R1/D007: train and evaluate the infrared module classifier on real Raptor Maps data.

Protocol, stated so the numbers can be read correctly:
  * Stratified 70/15/15 split into train, validation and test, fixed by seed.
  * The test split is touched exactly once, at the end. Early stopping and model selection use validation only.
  * Class-balanced loss weights, because half the collection is No-Anomaly and predicting that for everything
    would already score 50 percent accuracy while being useless.
  * Reported headline is macro-F1 with per-class recall, not accuracy.
"""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ml.ir_classifier import CLASSES, DATA_ROOT, IRNet, WEIGHTS, load_metadata, normalise

SEED = 0
METRICS_OUT = Path(__file__).resolve().parents[1] / "artifacts/metrics/ir-classifier.json"


def load_images(records: list[tuple[Path, str]]) -> tuple[np.ndarray, np.ndarray]:
    index = {c: i for i, c in enumerate(CLASSES)}
    x = np.zeros((len(records), 1, 40, 24), dtype=np.float32)
    y = np.zeros(len(records), dtype=np.int64)
    for i, (path, label) in enumerate(records):
        with Image.open(path) as im:
            array = np.array(im.convert("L"), dtype=np.float32)
        if array.shape != (40, 24):  # a handful are stored rotated
            array = array.T
        x[i, 0] = normalise(array)
        y[i] = index[label]
    return x, y


def stratified_split(y: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per class, so the rare classes are present in every split rather than landing entirely in one."""
    train, val, test = [], [], []
    for cls in np.unique(y):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        n_val, n_test = int(len(idx) * 0.15), int(len(idx) * 0.15)
        test.extend(idx[:n_test]); val.extend(idx[n_test:n_test + n_val]); train.extend(idx[n_test + n_val:])
    return (np.array(sorted(train)), np.array(sorted(val)), np.array(sorted(test)))


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    preds, actual = [], []
    with torch.no_grad():
        for xb, yb in loader:
            preds.append(model(xb.to(device)).argmax(1).cpu().numpy())
            actual.append(yb.numpy())
    return np.concatenate(preds), np.concatenate(actual)


def scores(pred: np.ndarray, actual: np.ndarray) -> dict:
    per_class, f1s = {}, []
    for i, name in enumerate(CLASSES):
        tp = int(((pred == i) & (actual == i)).sum())
        fp = int(((pred == i) & (actual != i)).sum())
        fn = int(((pred != i) & (actual == i)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s.append(f1)
        per_class[name] = {"support": int((actual == i).sum()), "precision": round(precision, 3),
                           "recall": round(recall, 3), "f1": round(f1, 3)}
    anomaly_pred, anomaly_true = pred != CLASSES.index("No-Anomaly"), actual != CLASSES.index("No-Anomaly")
    tp = int((anomaly_pred & anomaly_true).sum()); fp = int((anomaly_pred & ~anomaly_true).sum())
    fn = int((~anomaly_pred & anomaly_true).sum())
    return {
        "accuracy": round(float((pred == actual).mean()), 4),
        "macro_f1": round(float(np.mean(f1s)), 4),
        "per_class": per_class,
        # Operationally the first question is simply whether a module needs a human to look at it.
        "anomaly_vs_normal": {
            "precision": round(tp / (tp + fp), 3) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 3) if tp + fn else 0.0,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=3e-3)
    parser.add_argument("--patience", type=int, default=8)
    args = parser.parse_args()

    if not DATA_ROOT.exists(): raise SystemExit(f"Dataset missing. Run: python scripts/download_datasets.py ir")
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    print("loading images ...", flush=True)
    records = load_metadata()
    x, y = load_images(records)
    tr, va, te = stratified_split(y, rng)
    print(f"train {len(tr)}  val {len(va)}  test {len(te)}", flush=True)

    device = torch.device("cpu")
    def loader(idx, shuffle):
        return DataLoader(TensorDataset(torch.from_numpy(x[idx]), torch.from_numpy(y[idx])),
                          batch_size=args.batch_size, shuffle=shuffle)
    train_loader, val_loader, test_loader = loader(tr, True), loader(va, False), loader(te, False)

    counts = np.bincount(y[tr], minlength=len(CLASSES)).astype(np.float32)
    weights = torch.from_numpy((counts.sum() / (len(CLASSES) * np.maximum(counts, 1))).astype(np.float32))
    model = IRNet().to(device)
    criterion = nn.CrossEntropyLoss(weight=weights.to(device), label_smoothing=0.05)
    optimiser = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(optimiser, T_max=args.epochs)

    best_f1, best_state, stale, started = -1.0, None, 0, time.time()
    for epoch in range(1, args.epochs + 1):
        model.train()
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            # Horizontal flips only. A vertical flip would move a hot cell to the opposite end of the module,
            # which changes what the defect physically is.
            if torch.rand(1).item() < 0.5: xb = torch.flip(xb, dims=[3])
            optimiser.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimiser.step()
        schedule.step()
        val = scores(*evaluate(model, val_loader, device))
        marker = ""
        if val["macro_f1"] > best_f1:
            best_f1, best_state, stale = val["macro_f1"], {k: v.clone() for k, v in model.state_dict().items()}, 0
            marker = "  <- best"
        else:
            stale += 1
        print(f"epoch {epoch:>3}  val macro-F1 {val['macro_f1']:.4f}  acc {val['accuracy']:.4f}{marker}", flush=True)
        if stale >= args.patience:
            print(f"no validation gain in {args.patience} epochs, stopping", flush=True)
            break

    model.load_state_dict(best_state)
    test = scores(*evaluate(model, test_loader, device))
    print("\n=== held-out test ===")
    print(f"macro-F1 {test['macro_f1']}   accuracy {test['accuracy']}")
    print(f"anomaly vs normal: precision {test['anomaly_vs_normal']['precision']}  recall {test['anomaly_vs_normal']['recall']}")
    for name, m in sorted(test["per_class"].items(), key=lambda kv: -kv[1]["support"]):
        print(f"  {name:<16} support {m['support']:>5}  recall {m['recall']:.3f}  f1 {m['f1']:.3f}")

    report = {
        "model": "IRNet, small CNN trained from scratch",
        "data": "Raptor Maps Infrared Solar Modules (20,000 crops, 12 classes, MIT)",
        "protocol": "stratified 70/15/15 split, seed 0; model selected on validation macro-F1; test split scored once",
        "caveat": "Half the collection is No-Anomaly, so accuracy is inflated by the majority class. Macro-F1 is the headline.",
        "images": len(records), "train_images": len(tr), "validation_images": len(va), "test_images": len(te),
        "validation_macro_f1": round(best_f1, 4), "test": test,
        "training_seconds": round(time.time() - started, 1),
    }
    WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": best_state, "classes": CLASSES, "metrics": report}, WEIGHTS)
    METRICS_OUT.parent.mkdir(parents=True, exist_ok=True)
    METRICS_OUT.write_text(json.dumps(report, indent=2))
    print(f"\nweights -> {WEIGHTS}  ({WEIGHTS.stat().st_size / 1e6:.2f} MB)")
    print(f"metrics -> {METRICS_OUT}")


if __name__ == "__main__":
    main()
