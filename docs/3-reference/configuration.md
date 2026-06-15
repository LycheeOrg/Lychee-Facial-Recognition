# Configuration Reference

All environment variables use the `VISION_FACE_` prefix. Copy `.env.example` to `.env` and fill in at minimum the two required variables. Missing required variables produce a formatted error at startup instead of a raw traceback.

## Required

| Variable | Description |
|---|---|
| `VISION_FACE_LYCHEE_API_URL` | Lychee base URL for callbacks, no trailing slash. Example: `http://lychee` |
| `VISION_FACE_API_KEY` | Shared secret validated on inbound requests (`X-API-Key` header) and sent on outbound callbacks. Must match `AI_VISION_FACE_API_KEY` in Lychee's `.env`. |

## Connection

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_VERIFY_SSL` | `true` | Verify SSL certificates on callbacks to Lychee. Set to `false` for self-signed certs in dev. |
| `VISION_FACE_SKIP_LYCHEE_CHECK` | `false` | Skip the Lychee `/up` connectivity check at startup. |

## Model

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_MODEL_NAME` | `ArcFace` | DeepFace recognition model. `ArcFace` produces 512-dimensional embeddings. Other options: `Facenet512`, `VGG-Face`. |
| `VISION_FACE_DETECTOR_BACKEND` | `retinaface` | DeepFace detector backend. Options: `retinaface`, `mtcnn`, `opencv`, `ssd`. |
| `VISION_FACE_MODEL_ROOT` | `/root/.deepface` | Directory for cached DeepFace model weights. Exposed as `DEEPFACE_HOME` at startup. |

## Detection & quality

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_DETECTION_THRESHOLD` | `0.5` | Minimum bounding-box confidence score (0.0–1.0). Faces below this are discarded. |
| `VISION_FACE_BLUR_THRESHOLD` | `0.5` | Minimum Laplacian variance. Faces below this sharpness score are discarded. Set to `0.0` to disable. |
| `VISION_FACE_MIN_FACE_SIZE_PIXELS` | `0` | Minimum longest-side size in pixels. `0` disables the filter. |
| `VISION_FACE_MAX_FACES_PER_PHOTO` | `10` | Maximum number of faces in a detection callback (top-N by confidence). |

## Matching & clustering

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_MATCH_THRESHOLD` | `0.5` | Cosine-similarity cutoff for detection suggestions and selfie matching results. |
| `VISION_FACE_RESCAN_IOU_THRESHOLD` | `0.5` | IoU threshold for bounding-box matching when re-scanning a photo (preserves existing `person_id`). |
| `VISION_FACE_CLUSTER_EPS` | `0.6` | DBSCAN maximum cosine distance (`1 − similarity`) for two faces to be neighbours. |

## Storage

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_STORAGE_BACKEND` | `sqlite` | `sqlite` or `pgvector`. |
| `VISION_FACE_STORAGE_PATH` | `/data/embeddings` | Directory for the SQLite embedding database (sqlite backend only). |
| `VISION_FACE_PHOTOS_PATH` | `/data/photos` | Read-only Docker volume mount for photo files. `photo_path` values in `/detect` requests are validated against this prefix. |

### PostgreSQL / pgvector

Only required when `VISION_FACE_STORAGE_BACKEND=pgvector`.

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_PG_HOST` | `localhost` | PostgreSQL host. |
| `VISION_FACE_PG_PORT` | `5432` | PostgreSQL port. |
| `VISION_FACE_PG_DATABASE` | `ai_vision` | Database name. |
| `VISION_FACE_PG_USER` | `ai_vision` | Username. |
| `VISION_FACE_PG_PASSWORD` | _(empty)_ | Password. |

## Concurrency

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_THREAD_POOL_SIZE` | `1` | Threads in the `ThreadPoolExecutor` for CPU-bound inference (DeepFace calls). Increase for multi-core hosts with heavy workloads. |
| `VISION_FACE_WORKERS` | `1` | Uvicorn worker processes. Each process loads its own model copy. |

## Logging

| Variable | Default | Description |
|---|---|---|
| `VISION_FACE_LOG_LEVEL` | `info` | Log verbosity: `debug`, `info`, `warning`, `error`, `critical`. |
