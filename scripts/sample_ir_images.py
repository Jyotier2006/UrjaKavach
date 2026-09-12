"""R1/D016: export a random blind sample of infrared crops for testing the classifier.

Draws only from the held-out test split, reproduced with the same seed and stratification as training, so
nothing here was seen during training. Filenames carry the true class and a running number but never the
model's answer, so the sample can be used as a blind test: upload, read the prediction off the screen, then
check it against answers.json afterwards.

    python scripts/sample_ir_images.py --count 30
    python scripts/sample_ir_images.py --count 12 --classes Hot-Spot Soiling --seed 7
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.train_ir_classifier import SEED, load_images, stratified_split
from services.ml.ir_classifier import CLASSES, DATA_ROOT, load_metadata

OUT = Path(__file__).resolve().parents[1] / "artifacts/ir_sample"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=24, help="how many images to export")
    parser.add_argument("--classes", nargs="*", choices=CLASSES, help="restrict to these classes")
    parser.add_argument("--seed", type=int, default=1, help="changes which images are drawn, not the split")
    args = parser.parse_args()

    if not DATA_ROOT.exists():
        raise SystemExit("Dataset missing. Run: python scripts/download_datasets.py ir")

    records = load_metadata()
    _, y = load_images(records)
    # The split seed is fixed so "held out" keeps its meaning; --seed only chooses within that split.
    _, _, test_idx = stratified_split(y, np.random.default_rng(SEED))

    wanted = set(args.classes) if args.classes else set(CLASSES)
    pool = [i for i in test_idx if records[i][1] in wanted]
    if not pool:
        raise SystemExit("No test images match those classes.")

    rng = np.random.default_rng(args.seed)
    picked = rng.choice(pool, size=min(args.count, len(pool)), replace=False)

    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    answers = []
    for n, i in enumerate(sorted(picked), start=1):
        source, true_label = records[i]
        name = f"sample-{n:02d}.jpg"  # no class in the filename: this is a blind test
        shutil.copy(source, OUT / name)
        answers.append({"file": name, "true_class": true_label})

    (OUT / "answers.json").write_text(json.dumps(
        {"source": "Raptor Maps Infrared Solar Modules (MIT)",
         "split": f"held-out test split, stratified 70/15/15, split seed {SEED}; sampled with seed {args.seed}",
         "note": "Filenames are deliberately anonymous. Upload each one, write down what the model says, then compare here.",
         "answers": answers}, indent=2))

    counts: dict[str, int] = {}
    for a in answers: counts[a["true_class"]] = counts.get(a["true_class"], 0) + 1
    print(f"{len(answers)} blind test images -> {OUT}")
    for cls, n in sorted(counts.items(), key=lambda kv: -kv[1]): print(f"  {cls:<16} {n}")
    print("\nanswers.json holds the key. Every image is from the held-out split and was never trained on.")


if __name__ == "__main__":
    main()
