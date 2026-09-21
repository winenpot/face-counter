## Dataset Preparation

The dataset preparation process can be organized as:

**Collect → Organize & Preprocess → Annotate → Validate → Split → Version**

### 1. Data Collection

Collect representative images of the actual environments in which the model will eventually be used.

**Sources:**

* Photos taken using smartphones or field devices.
* Existing company image repositories.
* Images collected from stores, supermarkets, warehouses, or other relevant retail environments.
* Optional public datasets for supplementary training material, difficult examples, or hard negatives where appropriate.

**Considerations:**

* Different stores and shelf layouts.
* Different cameras and image resolutions.
* Different lighting conditions.
* Different camera distances and viewing angles.
* Crowded and partially empty shelves.
* Products partially occluded by other products.
* Different product orientations.
* Different packaging versions.

The dataset should prioritize **real company-specific images**. Public datasets can supplement the dataset but should not be considered a substitute for representative production data.

### 2. Organization & Initial Preprocessing

Before annotation, collected images should be normalized and organized into a consistent structure.

Possible tools:

* Python + Pillow.
* OpenCV.
* Simple filesystem scripts.

Typical operations:

* Detect and remove corrupted images.
* Normalize image formats where necessary.
* Resize or downscale excessively large images when appropriate.
* Normalize filenames.
* Remove obvious duplicates.
* Record basic metadata such as image dimensions and source.
* Organize images into a predictable directory structure.
* Generate an initial dataset manifest.

Example:

```text
dataset/
├── images/
│   ├── store_001/
│   ├── store_002/
│   └── store_003/
├── annotations/
├── metadata/
└── manifest.json
```

More substantial preprocessing and augmentation should be treated as a separate part of the ML pipeline rather than being mixed into the initial data-collection process.

### 3. Annotation

Annotation converts the collected images into training targets and is likely to be one of the most significant manual components of the project.

Possible tools:

* **CVAT** — open-source, mature, and well suited to bounding-box and object-detection annotation.
* **Label Studio** — flexible annotation platform with a modern interface.
* **X-AnyLabeling** — useful when AI-assisted annotation is desired.
* **Roboflow** — provides annotation, dataset management, and AI-assisted workflows, depending on deployment and licensing requirements.

The annotation strategy should be determined according to the model architecture.

For object detection, each visible product face would typically be annotated with a bounding box and associated product/class label.

For example:

```text
Image
  │
  ├── Product A → bounding box
  ├── Product A → bounding box
  ├── Product B → bounding box
  └── Product C → bounding box
```

A standardized annotation format should be selected early.

**COCO JSON** is a strong general-purpose choice because it supports images, bounding boxes, categories, and additional annotation metadata.

Other formats can be used depending on the selected training framework, with conversion performed when necessary.

A simple internal manifest can additionally maintain information such as:

```json
{
  "image": "store_001/img_000123.jpg",
  "source": "store_001",
  "annotation": "annotations/img_000123.json",
  "product_count": 12
}
```

The exact annotation schema should ultimately follow the requirements of the selected computer-vision framework.

### 4. Annotation Validation & Dataset Quality Checks

Before training, automated and manual quality checks should be performed.

**Automated checks:**

* Image integrity.
* Missing images or annotations.
* Invalid annotation files.
* Invalid bounding boxes.
* Bounding boxes outside image boundaries.
* Duplicate image/annotation identifiers.
* Unexpected image dimensions.
* Extremely small or unusually large objects.
* Class-label consistency.
* Product/count distribution.
* Images with zero annotations.
* Annotation statistics.

**Visual checks:**

Generate random samples with annotations rendered over the original images and inspect them manually.

For example:

```text
Original Image
      ↓
Render Annotations
      ↓
Random Sample Review
      ↓
Correct / Reject / Re-annotate
```

Simple Python tooling using Pillow, OpenCV, and Matplotlib can be sufficient for these checks initially.

The purpose is to catch annotation errors before they become model-training problems.

### 5. Dataset Splitting

After the dataset has passed quality checks, divide it into training, validation, and test sets.

Typical structure:

```text
Train       → model training
Validation  → model selection / tuning
Test        → final evaluation
```

The split should be reproducible using a fixed random seed.

For this particular problem, a simple random image-level split may not always be sufficient. If multiple photographs come from the same store, shelf, visit, or recording session, related images should preferably remain in the same split.

Otherwise, visually similar images from the same environment may appear in both training and test sets, producing an overly optimistic evaluation.

Where practical, the test set should contain images from stores or collection sessions that were not represented in training.

### 6. Dataset Versioning

Initially, lightweight versioning is sufficient.

For example:

```text
datasets/
├── v0.1/
├── v0.2/
└── v1.0/
```

Each version can contain a manifest describing:

```json
{
  "dataset_version": "v0.2",
  "image_count": 2450,
  "annotation_count": 18320,
  "classes": 24,
  "split_seed": 42,
  "train": 1960,
  "validation": 245,
  "test": 245
}
```

At an early stage, ordinary folders plus `manifest.json` / `dataset.yaml` and Git-tracked metadata may be sufficient.

If the dataset becomes large, changes frequently, or needs reproducible ML experiments across multiple machines, a dedicated data-versioning solution such as DVC can be introduced.

### Recommended Tooling

A practical initial toolset could therefore be:

| Task             | Initial Option                           | Alternatives                          |
| ---------------- | ---------------------------------------- | ------------------------------------- |
| Collection       | Existing folders + simple Python scripts | Object storage / dedicated ingestion  |
| Image processing | Pillow / OpenCV                          | —                                     |
| Annotation       | CVAT                                     | Label Studio, X-AnyLabeling, Roboflow |
| Quality checks   | Python                                   | Great Expectations / custom tooling   |
| Visualization    | Matplotlib / OpenCV                      | —                                     |
| Dataset format   | COCO JSON                                | YOLO / custom JSON                    |
| Splitting        | Python / scikit-learn                    | Framework-specific tooling            |
| Versioning       | Folders + manifests                      | DVC                                   |

The guiding principle is to keep the initial data pipeline simple while preserving enough structure and metadata that the dataset can later become reproducible, auditable, and suitable for systematic model training.
