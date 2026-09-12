"""R1/D007: publish the measured infrared classifier metrics into the web artifacts.

Reads artifacts/metrics/ir-classifier.json, written once by train_ir_classifier.py from the held-out test split,
and copies the headline figures into the metrics block the Performance page reads. Nothing is computed here.
Refreshes the artifact manifest hashes afterwards so the "verify the hashes" claim on that page stays true.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/metrics/ir-classifier.json"
BUNDLE_ROOTS = [ROOT / "artifacts/demo_bundle", ROOT / "apps/web/public/demo"]
REPORT = ROOT / "artifacts/metrics/models.json"


def ir_block(report: dict) -> dict:
    test = report["test"]
    return {
        "macro_f1": test["macro_f1"],
        "accuracy": test["accuracy"],
        "anomaly_recall": test["anomaly_vs_normal"]["recall"],
        "anomaly_precision": test["anomaly_vs_normal"]["precision"],
        # Summed from the per-class supports, so it is right regardless of which count keys the report carries.
        "test_images": sum(c["support"] for c in test["per_class"].values()),
        "dataset": report["data"],
        "protocol": report["protocol"],
        "status": "Measured on the held-out test split; weights committed at artifacts/models/ir_classifier.pt",
    }


def main():
    if not SOURCE.exists():
        raise SystemExit("No IR metrics found. Run scripts/train_ir_classifier.py first.")
    report = json.loads(SOURCE.read_text())
    block = ir_block(report)

    for root in BUNDLE_ROOTS:
        for name in ("metrics.json", "bundle.json"):
            path = root / name
            data = json.loads(path.read_text())
            target = data if name == "metrics.json" else data["metrics"]
            target["ir"] = block
            path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False))
        manifest_path = root / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for tracked in manifest.get("files", {}):
            f = root / tracked
            if f.exists():
                manifest["files"][tracked] = hashlib.sha256(f.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest, separators=(",", ":"), allow_nan=False))

    models = json.loads(REPORT.read_text())
    models["ir"] = block
    REPORT.write_text(json.dumps(models, indent=2))
    print(json.dumps(block, indent=2))


if __name__ == "__main__":
    main()
