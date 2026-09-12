"""R1/D016: assemble a small demo set of infrared crops for the technician screen.

Every image comes from the held-out test split, reproduced with the same seed and stratification the training
run used, so none of them was seen during training. For each class the most confident correct prediction is
kept, plus one honest "hard" case per class where the model was right but unsure, or wrong. Filenames carry the
true class and the model's answer so a demo can never quietly pass off a miss as a hit.
"""
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.train_ir_classifier import SEED, load_images, stratified_split
from services.ml.ir_classifier import CLASSES, DATA_ROOT, IRClassifier, load_metadata

OUT = Path(__file__).resolve().parents[1] / "artifacts/ir_demo"


def main():
    records = load_metadata()
    x, y = load_images(records)
    _, _, test_idx = stratified_split(y, np.random.default_rng(SEED))
    model = IRClassifier()

    rows = []
    for i in test_idx:
        pred = model.predict(x[i, 0] * 1.0)  # normalise() is idempotent on an already-normalised crop
        rows.append({"index": int(i), "path": records[i][0], "true": records[i][1],
                     "pred": pred.label, "confidence": pred.confidence})

    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "confident").mkdir(parents=True)
    (OUT / "hard").mkdir(parents=True)
    manifest = {"source": "Raptor Maps Infrared Solar Modules (MIT). All images are from the held-out test split, never seen in training.",
                "split": "stratified 70/15/15, seed 0, identical to scripts/train_ir_classifier.py", "confident": [], "hard": [], "per_class_test_accuracy": {}}

    for cls in CLASSES:
        of_class = [r for r in rows if r["true"] == cls]
        correct = sorted((r for r in of_class if r["pred"] == cls), key=lambda r: -r["confidence"])
        manifest["per_class_test_accuracy"][cls] = round(len(correct) / len(of_class), 3) if of_class else None
        if correct:
            best = correct[0]
            name = f"{cls}__pred-{best['pred']}__conf-{best['confidence']:.2f}.jpg"
            shutil.copy(best["path"], OUT / "confident" / name)
            manifest["confident"].append({"file": f"confident/{name}", **{k: best[k] for k in ("true", "pred", "confidence")}})
        # Hard case: the least confident correct one if it exists, otherwise a miss.
        hard = correct[-1] if len(correct) > 1 else next((r for r in of_class if r["pred"] != cls), None)
        if hard:
            name = f"{cls}__pred-{hard['pred']}__conf-{hard['confidence']:.2f}.jpg"
            shutil.copy(hard["path"], OUT / "hard" / name)
            manifest["hard"].append({"file": f"hard/{name}", **{k: hard[k] for k in ("true", "pred", "confidence")}})

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (OUT / "README.md").write_text(
        "# Infrared demo crops\n\n"
        "Twenty-four real 24x40 thermal module crops from the Raptor Maps Infrared Solar Modules dataset (MIT),\n"
        "all drawn from the held-out test split of `scripts/train_ir_classifier.py`, so the classifier never saw\n"
        "them in training. Regenerate with `python scripts/select_ir_demo_images.py`.\n\n"
        "- `confident/` — for each class, the correct prediction the model was most sure about.\n"
        "- `hard/` — for each class, the correct prediction it was least sure about, or a miss where it had no\n"
        "  other correct answer. Show these too; a demo that only shows wins is not a demo of a classifier.\n\n"
        "Filenames read `<true class>__pred-<model answer>__conf-<confidence>.jpg`, so a miss is visible in the\n"
        "name before the image is even opened.\n\n"
        "To test: run the API (`make api` or `docker compose up`), open the technician screen's Infrared\n"
        "inspection tab, drop a file, press Screen image. The response shows the predicted class, its\n"
        "confidence, and a Grad-CAM map of where the network looked.\n")
    print(json.dumps({"confident": len(manifest["confident"]), "hard": len(manifest["hard"]),
                      "per_class_test_accuracy": manifest["per_class_test_accuracy"]}, indent=2))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
