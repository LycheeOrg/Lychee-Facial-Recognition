# API Reference

**Base URL:** wherever the service is deployed (default `http://localhost:8000`)

**Authentication:** all endpoints except `GET /health` require the `X-API-Key: <VISION_FACE_API_KEY>` header.

Interactive Swagger docs are available at `/docs` when the service is running.

---

## `GET /health`

Service health check. No authentication required (safe for load-balancer probes).

**Response `200`**

```json
{
  "status": "ok",
  "model_loaded": true,
  "embedding_count": 1234
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | `"ok"` when fully operational; `"degraded"` if the model has not loaded |
| `model_loaded` | bool | Whether ArcFace/RetinaFace is initialised |
| `embedding_count` | int | Total stored face embeddings |

---

## `GET /config`

Current runtime configuration with secrets redacted.

**Response `200`**

```json
{
  "config": {
    "model_name": "ArcFace",
    "detector_backend": "retinaface",
    "detection_threshold": "0.5",
    "match_threshold": "0.5",
    "blur_threshold": "0.5",
    "cluster_eps": "0.6",
    "max_faces_per_photo": "10",
    "min_face_size_pixels": "0",
    "rescan_iou_threshold": "0.5",
    "thread_pool_size": "1",
    "verify_ssl": "true",
    "workers": "1"
  }
}
```

---

## `POST /detect`

Enqueue a face-detection job. Returns immediately; results arrive via callback.

**Request body (JSON)**

```json
{
  "photo_id": "123",
  "photo_path": "/uploads/original/ab/cd/photo.jpg"
}
```

| Field | Type | Description |
|---|---|---|
| `photo_id` | string | Lychee photo identifier |
| `photo_path` | string | Absolute path within `VISION_FACE_PHOTOS_PATH` |

**Response `202 Accepted`** — job accepted, empty body.

**Response `400`** — `photo_path` is outside the allowed directory, or the file does not exist.

### Success callback

POSTed to `{LYCHEE_API_URL}/api/v2/FaceDetection/results`:

```json
{
  "photo_id": "123",
  "status": "success",
  "faces": [
    {
      "x": 0.15,
      "y": 0.20,
      "width": 0.30,
      "height": 0.40,
      "confidence": 0.92,
      "embedding_id": "a1b2c3d4-0000-0000-0000-000000000000",
      "crop": "<base64 150x150 JPEG>",
      "laplacian_variance": 145.2,
      "suggestions": [
        {"lychee_face_id": "456", "confidence": 0.81}
      ]
    }
  ]
}
```

Bounding box values (`x`, `y`, `width`, `height`) are normalised fractions (0.0–1.0). `embedding_id` is a transient UUID used only to correlate this result with the callback acknowledgement.

### Error callback

POSTed to the same URL on failure:

```json
{
  "photo_id": "123",
  "status": "error",
  "error_code": "internal_error",
  "message": "Detection pipeline failed"
}
```

### Callback acknowledgement

Lychee must respond `200` with a face-mapping body. The service uses these to persist embeddings under stable Lychee IDs:

```json
{
  "faces": [
    {"embedding_id": "a1b2c3d4-...", "lychee_face_id": "789"}
  ]
}
```

---

## `POST /match`

Synchronous selfie-to-face similarity search. No callback — response is immediate.

**Request** — multipart form upload with a single image field named `file`.

**Response `200`**

```json
{
  "matches": [
    {"lychee_face_id": "456", "confidence": 0.87},
    {"lychee_face_id": "789", "confidence": 0.62}
  ]
}
```

Results are ordered by descending confidence. Only faces above `VISION_FACE_MATCH_THRESHOLD` are returned.

**Response `422`** — no face detected in the uploaded image.

---

## `POST /cluster`

Enqueue a DBSCAN clustering job over all stored embeddings. Returns immediately; results arrive via callback.

**Request body** — empty.

**Response `202 Accepted`** — job accepted, empty body.

### Cluster callback

POSTed to `{LYCHEE_API_URL}/api/v2/FaceDetection/cluster-results`:

```json
{
  "labels": [
    {"face_id": "123", "cluster_label": 0},
    {"face_id": "456", "cluster_label": 0},
    {"face_id": "789", "cluster_label": 1},
    {"face_id": "999", "cluster_label": -1}
  ],
  "suggestions": [
    {
      "face_id": "123",
      "suggested_face_id": "789",
      "confidence": 0.71
    }
  ]
}
```

`cluster_label = -1` means the face is noise (not assigned to any cluster). Suggestions are cross-cluster pairs with similarity above `VISION_FACE_MATCH_THRESHOLD`, offered for human review.

---

## `DELETE /embeddings`

Delete one or more face embeddings by Lychee Face ID.

**Request body (JSON)**

```json
{"face_ids": ["123", "456"]}
```

**Response `200`**

```json
{"deleted": 2}
```

IDs not found in the store are silently skipped.

---

## `GET /embeddings/export`

Export all stored embeddings with metadata. Used by Lychee for re-synchronisation after callback failures.

**Response `200`**

```json
{
  "embeddings": [
    {
      "lychee_face_id": "123",
      "photo_id": "42",
      "laplacian_variance": 145.2,
      "crop_path": "faces/123.jpg"
    }
  ]
}
```
