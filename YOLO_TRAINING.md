# Training a YOLO Barcode Region Detector

This guide describes training a model to replace the OpenCV contour and rectangle heuristics in `find_barcode_rectangle()` in `job_flow.py`. The model should locate the whole region to cover, including printed barcode panels and solid boxes used in place of readable barcodes.

The guide prepares model weights and describes the intended inference contract. It does not switch the runtime from OpenCV to YOLO; the workflow must be wired to the trained weights before YOLO detections are used during processing.

## 1. Define the label

Use one detection class named `barcode_region`. Draw one bounding box tightly around the complete rectangle that should be painted over:

- For a printed barcode, include the whole surrounding label or panel, not only the parallel bars or the digits.
- For a solid black or other solid-color placeholder, mark the whole rectangular placeholder.
- Do not label a barcode elsewhere on the page if the workflow should only clean the lower half.
- Include examples with no barcode or placeholder and leave their label files empty. These teach the model not to select artwork, title boxes, or ordinary page borders.
- Annotate the original unmodified image. Keep `_o` backups as source images; do not train on images already covered with green.

Using one class is intentional: both kinds of regions receive the same green fill. If later processing needs to distinguish their types, add separate classes and retrain with consistent labels.

## 2. Collect and split images

Collect representative first-page images from different comics, publishers, eras, scan qualities, and barcode placements. Include portrait and landscape pages, barcodes at different lower-page positions, solid placeholders, and negative examples without a region to remove.

Split by comic or source archive before training so alternate covers or pages from the same issue cannot leak across splits. A starting split is 70% training, 20% validation, and 10% test. Keep the test set untouched until model selection. Ultralytics recommends splitting before augmentation to avoid leaking information into validation and test data ([preprocessing guidance](https://docs.ultralytics.com/guides/preprocessing-annotated-data)).

Annotate with an image-labeling tool that exports Ultralytics YOLO detection labels. Review every label visually. YOLO detection labels use one text file per image; each row is `class_id x_center y_center width height`, with coordinates normalized to the image dimensions ([dataset format](https://docs.ultralytics.com/datasets/detect)). A negative image may have an empty label file.

Arrange the exported dataset like this:

```text
barcode_dataset/
├── data.yaml
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

Example `data.yaml`:

```yaml
path: /absolute/path/to/barcode_dataset
train: images/train
val: images/val
test: images/test

names:
  0: barcode_region
```

Each image must have a label file with the same basename, for example `001.jpg` and `001.txt`. An example label for a box centered at `(cx, cy)` is:

```text
0 0.78 0.91 0.31 0.10
```

The values in this example are illustrative; create labels from the actual image dimensions and rectangle coordinates.

## 3. Install the training package

Use a separate virtual environment for model training so the training stack does not become a runtime dependency until the workflow migration is complete.

```bash
python3 -m venv .venv-yolo
source .venv-yolo/bin/activate
python -m pip install --upgrade pip
python -m pip install ultralytics
```

Ultralytics documents pip installation and custom object-detection training with its Python API and CLI ([training guide](https://docs.ultralytics.com/modes/train)).

## 4. Train a starter model

Start with a small pretrained model, then inspect the labels and validation results before increasing model size or training time. Comic pages are large and the target can be small, so begin with a larger image size than the default and adjust to available memory.

```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")
model.train(
    data="/absolute/path/to/barcode_dataset/data.yaml",
    epochs=100,
    imgsz=1024,
    batch=4,
    device="mps",  # Apple Silicon; use "cpu" or a CUDA device as appropriate
    project="runs/barcode",
    name="region-v1",
)
```

Ultralytics' training API accepts the dataset YAML, epoch count, image size, batch size, and device as training arguments. Apple Silicon is supported through `device="mps"` in current Ultralytics training documentation ([training guide](https://docs.ultralytics.com/modes/train)). Reduce `batch` if training runs out of memory. Review the training output images to confirm that boxes match the complete panel or solid placeholder, not just the barcode bars.

The best checkpoint is normally written to:

```text
runs/barcode/region-v1/weights/best.pt
```

Keep the checkpoint, `data.yaml`, class-name mapping, training command, and package versions together with the training notes. Do not commit comic scans or trained weights to the repository unless that is an intentional project decision.

## 5. Evaluate before using it

Evaluate on the held-out test split:

```python
from ultralytics import YOLO

model = YOLO("runs/barcode/region-v1/weights/best.pt")
metrics = model.val(data="/absolute/path/to/barcode_dataset/data.yaml", split="test")
print("mAP50-95:", metrics.box.map)
```

Also make annotated predictions on unseen pages and manually review every false positive and miss. The workflow modifies images, so prefer high precision: a false positive paints over comic art. Tune the confidence threshold using this review and verify that the box encloses the full panel. Ultralytics returns pixel-coordinate boxes in `result.boxes.xyxy` with confidence values in `result.boxes.conf` ([prediction results](https://docs.ultralytics.com/modes/predict)).

Example review prediction:

```python
results = model.predict("unseen-cover.jpg", imgsz=1024, conf=0.35)
results[0].save(filename="unseen-cover-review.jpg")
```

## 6. Runtime integration target

When migrating `job_flow.py` to YOLO:

1. Load `best.pt` once, not once per comic folder.
2. Run inference on the first image as the current job does.
3. Keep detections whose center lies in the image's lower half.
4. Choose the best accepted `barcode_region` detection, clip its `xyxy` bounds to the image dimensions, and fill that rectangle with `#00FF00` using Pillow.
5. Continue making the `_o` original backup before editing.
6. Log when the model finds no acceptable region; do not paint an uncertain prediction.

After that integration is in place, remove the OpenCV-only contour logic and its direct dependency if no other workflow code uses it. Keep Pillow for image loading, backups, and filling. `zxing-cpp` can also be removed if the workflow no longer uses decoded barcode coordinates. The Ultralytics package may install OpenCV as one of its own dependencies; removing this project's direct OpenCV requirement does not guarantee OpenCV is absent from the environment.

## Licensing

Ultralytics states that its open-source code and models are licensed under AGPL-3.0, with an Enterprise license available for uses that do not meet the AGPL requirements. Review the [official licensing information](https://docs.ultralytics.com/) before distributing or deploying a workflow that uses Ultralytics. This note is informational, not legal advice.
