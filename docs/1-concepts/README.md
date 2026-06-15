# Core Concepts

## Face embeddings

A face embedding is a 512-dimensional float vector produced by the ArcFace recognition model. It encodes the geometric relationships between facial landmarks in a way that is identity-stable:

- Two photos of the **same person** produce embeddings with high cosine similarity (score close to 1.0).
- Two photos of **different people** produce lower similarity (typically below the match threshold, default 0.5).

Embeddings are the fundamental unit of identity in this service. Each one is stored alongside:
- The Lychee `Face.id` (stable primary key assigned by Lychee)
- The Lychee `photo_id`
- A Laplacian variance sharpness score
- A relative path to the 150×150 JPEG crop

## Detection pipeline

When `/detect` is called the following steps run in a background task after returning `202`:

1. **Path validation** — confirm `photo_path` is inside `VISION_FACE_PHOTOS_PATH` (path-traversal protection).
2. **Idempotency check** — if embeddings already exist for this `photo_id`, send an empty success callback and stop.
3. **Face detection** — RetinaFace finds bounding boxes and assigns a confidence score (0.0–1.0) to each.
4. **Confidence filter** — discard faces below `VISION_FACE_DETECTION_THRESHOLD` (default 0.5).
5. **Size filter** — discard faces whose longest bounding-box side (pixels) does not exceed `VISION_FACE_MIN_FACE_SIZE_PIXELS` (disabled by default).
6. **Laplacian variance** — compute a sharpness score for each face crop region.
7. **Blur filter** — discard faces whose Laplacian variance is below `VISION_FACE_BLUR_THRESHOLD` (default 0.5).
8. **ArcFace embedding** — generate a 512-dimensional vector for each surviving face.
9. **Crop generation** — produce a 150×150 JPEG, base64-encoded.
10. **Similarity search** — query the embedding store for similar faces to attach as suggestions.
11. **Limit** — keep at most `VISION_FACE_MAX_FACES_PER_PHOTO` faces, top by confidence.

## Bounding box coordinates

All bounding box values (`x`, `y`, `width`, `height`) are **normalised fractions** (0.0–1.0) of the image dimensions. `x` and `y` are the top-left corner. This makes coordinates resolution-independent.

## Callback flow

Detection is fully asynchronous:

1. `POST /detect` returns `202 Accepted` immediately.
2. A background task runs the detection pipeline.
3. On success the service POSTs to `{LYCHEE_API_URL}/api/v2/FaceDetection/results`.
4. Lychee creates `Face` records and returns a mapping of `embedding_id → lychee_face_id`.
5. The service persists each embedding under the stable `lychee_face_id`.
6. On failure the service POSTs an error callback (`status: "error"`) to the same URL.

The `embedding_id` is a transient UUID generated per detection run and is never stored. It exists only to correlate the service's intermediate result with Lychee's assigned IDs in the same round-trip.

## Selfie matching

`POST /match` is synchronous (no callback):

1. Detect faces in the uploaded image; return `422` if none found.
2. Take the highest-confidence face.
3. Run a cosine similarity search against all stored embeddings.
4. Return all matches above `VISION_FACE_MATCH_THRESHOLD`, ordered by descending confidence.

## Clustering

`POST /cluster` groups all stored embeddings with DBSCAN:

- Uses **cosine distance** (`1 − cosine_similarity`) as the distance metric.
- `VISION_FACE_CLUSTER_EPS` is the maximum cosine distance for two faces to be considered neighbours (default 0.6).
- `min_samples = 1` means a single face always forms its own cluster — no face is discarded as noise simply for being unique.
- Faces assigned `cluster_label = -1` are noise: embeddings too dissimilar from all others to join any cluster.

After labelling, the service generates **cross-cluster suggestions**: pairs of faces from *different* clusters with cosine similarity above `VISION_FACE_MATCH_THRESHOLD`. These surface potential mis-clusterings for human review in Lychee.

Results are POSTed to `{LYCHEE_API_URL}/api/v2/FaceDetection/cluster-results`.

## Storage backends

Two backends implement the `EmbeddingStore` protocol:

| Backend | Use case | Extra dependency |
|---|---|---|
| `sqlite` (default) | Small-to-medium libraries; no extra infrastructure | `sqlite-vec` |
| `pgvector` | Large libraries or existing PostgreSQL setup | PostgreSQL + `pgvector` extension |

Both expose the same operations: `add`, `delete`, `delete_many`, `similarity_search`, `get_all`, `get_all_with_metadata`, `count_by_photo_id`, `count`. Application code is backend-agnostic.

## Thread safety

CPU-bound DeepFace calls are offloaded to a `ThreadPoolExecutor` so the async event loop stays responsive. The `FaceDetector` wraps `DeepFace.represent()` with a lock because the underlying call is not thread-safe. Storage backends must be thread-safe independently.
