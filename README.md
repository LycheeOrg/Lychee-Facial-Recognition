# Lychee AI Vision Service

Facial recognition microservice for [Lychee](https://github.com/LycheeOrg/Lychee).

Detects faces in photos, stores embeddings, and supports selfie-based person
claiming via a REST API consumed by the Lychee PHP backend.

[![Build Status][build-status-shield]](https://github.com/LycheeOrg/Lychee-Facial-Recognition/actions)
[![Code Coverage][codecov-shield]](https://codecov.io/gh/LycheeOrg/Lychee-Facial-Recognition)
[![CII Best Practices Summary][cii-shield]](https://bestpractices.coreinfrastructure.org/projects/2855)
[![OpenSSF Scorecard][ossf-shield]](https://securityscorecards.dev/viewer/?uri=github.com/LycheeOrg/Lychee-Facial-Recognition)
<br>
[![Website][website-shield]](https://lycheeorg.dev)
[![Documentation][docs-shield]](https://lycheeorg.dev/docs/)
[![Changelog][changelog-shield]](https://lycheeorg.dev/docs/releases.html)
[![Discord][discord-shield]][discord]
[![GitGem](https://gitgem.org/api/badge/github/LycheeOrg/Lychee.svg)](https://gitgem.org/github/LycheeOrg/Lychee)

## Disclaimer

> **Legal notice:** Facial recognition technology may be subject to strict legal restrictions or outright prohibited in your jurisdiction. Before deploying this service, ensure you comply with all applicable laws and regulations.
>
> **Example — the Netherlands:** Under the Dutch implementation of the EU General Data Protection Regulation (GDPR), biometric data (including facial recognition embeddings) is classified as **special category data** (Article 9 GDPR). Processing such data is prohibited unless a specific legal basis applies (e.g. explicit informed consent). The Dutch Data Protection Authority (*Autoriteit Persoonsgegevens*) has issued guidance making clear that using facial recognition on individuals without a valid legal ground constitutes a serious infringement, potentially carrying fines of up to **€20 million or 4 % of global annual turnover**.
>
> Similar or stricter rules may apply in other EU/EEA countries, the United Kingdom, Canada, and many other jurisdictions. **The authors and contributors of this project accept no liability for unlawful use.** It is your sole responsibility to obtain any required consent, implement appropriate safeguards, and verify legality before operating this software.

## Tech stack

| Concern | Library |
|---------|---------|
| Web framework | FastAPI + Uvicorn |
| Face detection & recognition | DeepFace (`ArcFace` + `retinaface` backend) |
| Face crop generation | Pillow |
| Embedding clustering | scikit-learn (DBSCAN) |
| Embedding storage | SQLite + sqlite-vec (default) / PostgreSQL + pgvector |
| Job queue | SQLite / PostgreSQL (default) / Redis |
| HTTP client (callbacks) | httpx |
| Config | Pydantic BaseSettings |

## Directory layout

```
Lychee-Facial-Recognition/
├── app/
│   ├── __init__.py
│   ├── config.py          # AppSettings (Pydantic BaseSettings)
│   ├── main.py            # FastAPI app factory & lifespan handler
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py  # API key auth + queue dependency
│   │   ├── routes.py        # /detect, /match, /cluster, /queue, /health
│   │   └── schemas.py       # Pydantic request/response models
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── detector.py    # DeepFace wrapper
│   │   └── cropper.py     # 150×150 JPEG crop generator
│   ├── embeddings/
│   │   ├── __init__.py
│   │   ├── store.py         # Abstract EmbeddingStore protocol
│   │   ├── sqlite_store.py  # SQLite + sqlite-vec implementation
│   │   └── pgvector_store.py # PostgreSQL + pgvector implementation
│   ├── queue/
│   │   ├── __init__.py
│   │   ├── base.py          # Job dataclass + JobQueue protocol
│   │   ├── db_queue.py      # SQLite / PostgreSQL backends
│   │   ├── redis_queue.py   # Redis backend
│   │   ├── factory.py       # create_queue(settings)
│   │   └── worker.py        # Async consumer loop
│   ├── clustering/
│   │   ├── __init__.py
│   │   └── clusterer.py   # DBSCAN clustering
│   └── matching/
│       ├── __init__.py
│       └── matcher.py     # Selfie similarity matching
├── tests/
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_queue.py        # SQLiteJobQueue unit tests
│   ├── test_queue_api.py    # /queue endpoint tests
│   └── ...
├── Dockerfile
├── Makefile
├── pyproject.toml
└── README.md
```

## Environment variables

All variables are prefixed `VISION_FACE_`. Copy `.env.example` to `.env` and fill in the required values. Missing required variables produce a formatted error message at startup instead of a raw traceback.

### Required

| Variable | Description |
|----------|-------------|
| `VISION_FACE_LYCHEE_API_URL` | Lychee base URL for callbacks (no trailing slash) |
| `VISION_FACE_API_KEY` | Shared API key: validated on inbound requests from Lychee and sent on outbound callbacks |

### Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_VERIFY_SSL` | `true` | Verify SSL certificates on Lychee callbacks. Set to `false` for self-signed certs |
| `VISION_FACE_SKIP_LYCHEE_CHECK` | `false` | Skip the Lychee connectivity check at startup (useful for local dev) |

### Model

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_MODEL_NAME` | `ArcFace` | DeepFace recognition model |
| `VISION_FACE_DETECTOR_BACKEND` | `retinaface` | DeepFace detector backend (`retinaface`, `mtcnn`, `opencv`, `ssd`) |
| `VISION_FACE_MODEL_ROOT` | `/root/.deepface` | Root directory for DeepFace model weights (`DEEPFACE_HOME`) |

### Detection & matching

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_DETECTION_THRESHOLD` | `0.5` | Bounding-box confidence filter |
| `VISION_FACE_MATCH_THRESHOLD` | `0.5` | Cosine-similarity cutoff for selfie matching and suggestions |
| `VISION_FACE_RESCAN_IOU_THRESHOLD` | `0.5` | IoU threshold for bounding-box matching on re-scan |
| `VISION_FACE_MAX_FACES_PER_PHOTO` | `10` | Maximum faces included in a callback payload |
| `VISION_FACE_MIN_FACE_SIZE_PIXELS` | `0` | Minimum face size in pixels; `0` = disabled |
| `VISION_FACE_BLUR_THRESHOLD` | `0.5` | Laplacian variance threshold; blurry faces below this are discarded |
| `VISION_FACE_CLUSTER_EPS` | `0.6` | DBSCAN epsilon (max cosine distance) for face clustering |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_STORAGE_BACKEND` | `sqlite` | `sqlite` or `pgvector` |
| `VISION_FACE_STORAGE_PATH` | `/data/embeddings` | SQLite DB directory |
| `VISION_FACE_PG_HOST` | `localhost` | PostgreSQL host (pgvector only) |
| `VISION_FACE_PG_PORT` | `5432` | PostgreSQL port |
| `VISION_FACE_PG_DATABASE` | `ai_vision` | PostgreSQL database |
| `VISION_FACE_PG_USER` | `ai_vision` | PostgreSQL user |
| `VISION_FACE_PG_PASSWORD` | `` | PostgreSQL password |
| `VISION_FACE_PHOTOS_PATH` | `/data/photos` | Shared Docker volume mount for photo files |

### Job queue

Detection and clustering jobs are processed asynchronously via a persistent queue shared across all worker processes. Requests that arrive when the queue is full receive **429 Too Many Requests**.

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_QUEUE_BACKEND` | `database` | `database` (uses `STORAGE_BACKEND`) or `redis` |
| `VISION_FACE_QUEUE_MAX_SIZE` | `100` | Maximum number of pending jobs |
| `VISION_FACE_REDIS_HOST` | `localhost` | Redis host (redis backend only) |
| `VISION_FACE_REDIS_PORT` | `6379` | Redis port |
| `VISION_FACE_REDIS_PASSWORD` | `` | Redis password |
| `VISION_FACE_REDIS_DB` | `0` | Redis logical database index |

The Redis backend requires the optional `redis` extra: `uv sync --extra redis`.

### Concurrency

| Variable | Default | Description |
|----------|---------|-------------|
| `VISION_FACE_THREAD_POOL_SIZE` | `1` | Inference threads (also sets number of queue worker tasks) |
| `VISION_FACE_WORKERS` | `1` | Uvicorn worker processes |

## API endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/detect` | Yes | Enqueue a face-detection job; returns 202 or 429 if queue full |
| `POST` | `/match` | Yes | Synchronous selfie-to-face similarity search |
| `POST` | `/cluster` | Yes | Enqueue a DBSCAN clustering job; returns 202 or 429 if queue full |
| `DELETE` | `/embeddings` | Yes | Delete face embeddings by Lychee Face ID |
| `GET` | `/embeddings/export` | Yes | Export all embeddings with metadata |
| `GET` | `/queue` | Yes | Number of jobs currently pending |
| `DELETE` | `/queue` | Yes | Purge all pending jobs (in-flight jobs are unaffected) |
| `GET` | `/queue/{photo_id}` | Yes | Position of a photo in the queue (`position=0` = processing, 404 = done) |
| `GET` | `/health` | No | Service health and embedding count |
| `GET` | `/config` | Yes | Current runtime configuration (secrets redacted) |

Interactive docs are available at `/docs` when the service is running.

## Development

### Setup

```bash
# Install uv (https://docs.astral.sh/uv/getting-started/installation/)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies (including dev)
uv sync

# Copy and edit the env file — at minimum set VISION_FACE_LYCHEE_API_URL and VISION_FACE_API_KEY
cp .env.example .env
```

### Makefile

```bash
make lint          # ruff check + ruff format --check + ty check
make format        # ruff format + ruff check --fix (auto-fix)
make test          # pytest
make run           # uvicorn with --reload (local dev)
make docker-build  # docker build -t lychee-ai-vision .
make docker-run    # docker run --env-file .env ...
```

The service will be available at http://localhost:8000
- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Running tests with coverage

```bash
uv run pytest --cov=app --cov-report=html
```

## Docker

```bash
# Build (bakes ArcFace + RetinaFace model weights into the image — ~500 MB on first build)
make docker-build

# Run using .env for configuration
make docker-run

# Or manually, mounting photo and embedding volumes
docker run --rm \
  --env-file .env \
  -v /path/to/lychee/public/uploads:/data/photos:ro \
  -v ai-vision-embeddings:/data/embeddings \
  -p 8000:8000 \
  lychee-ai-vision
```

[build-status-shield]: https://img.shields.io/github/actions/workflow/status/LycheeOrg/Lychee-Facial-Recognition/CICD.yaml?branch=master
[codecov-shield]: https://codecov.io/gh/LycheeOrg/Lychee-Facial-Recognition/branch/master/graph/badge.svg
[release-shield]: https://img.shields.io/github/release/LycheeOrg/Lychee-Facial-Recognition.svg
[license-shield]: https://img.shields.io/github/license/LycheeOrg/Lychee-Facial-Recognition.svg
[cii-shield]: https://img.shields.io/cii/summary/2855.svg
[ossf-shield]: https://api.securityscorecards.dev/projects/github.com/LycheeOrg/Lychee-Facial-Recognition/badge
[website-shield]: https://img.shields.io/badge/-Website-informational.svg?logo=data:image/png;base64,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
[docs-shield]: https://img.shields.io/badge/-Documentation-informational.svg?logo=data:image/png;base64,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
[changelog-shield]: https://img.shields.io/badge/-Changelog-informational.svg?logo=data:image/png;base64,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
[discord]: https://discord.gg/JMPvuRQcTf
[discord-shield]: https://img.shields.io/discord/1046911561366765598?logo=discord


---

*Last updated: 2026-06-14*
