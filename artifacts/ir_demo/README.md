# Infrared demo crops

Twenty-four real 24x40 thermal module crops from the Raptor Maps Infrared Solar Modules dataset (MIT),
all drawn from the held-out test split of `scripts/train_ir_classifier.py`, so the classifier never saw
them in training. Regenerate with `python scripts/select_ir_demo_images.py`.

- `confident/` — for each class, the correct prediction the model was most sure about.
- `hard/` — for each class, the correct prediction it was least sure about, or a miss where it had no
  other correct answer. Show these too; a demo that only shows wins is not a demo of a classifier.

Filenames read `<true class>__pred-<model answer>__conf-<confidence>.jpg`, so a miss is visible in the
name before the image is even opened.

To test: run the API (`make api` or `docker compose up`), open the technician screen's Infrared
inspection tab, drop a file, press Screen image. The response shows the predicted class, its
confidence, and a Grad-CAM map of where the network looked.
