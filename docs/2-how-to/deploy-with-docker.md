# Deploy with Docker

## Prerequisites

- Docker (or Docker Compose)
- A running Lychee instance reachable from the container
- Lychee photo files accessible on the Docker host

## Build the image

```bash
docker build -t lychee-ai-vision .
```

The Dockerfile bakes the ArcFace and RetinaFace model weights into the image. Expect a ~500 MB download on the first build.

## Minimal run

```bash
docker run --rm \
  -e VISION_FACE_LYCHEE_API_URL=http://lychee \
  -e VISION_FACE_API_KEY=your-shared-secret \
  -v /path/to/lychee/photos:/data/photos:ro \
  -v ai-vision-embeddings:/data/embeddings \
  -p 8000:8000 \
  lychee-ai-vision
```

| Mount | Purpose |
|---|---|
| `/data/photos` | Read-only mount of Lychee's photo storage. Must match the path Lychee uses internally. |
| `/data/embeddings` | Persistent embedding database. Use a named volume so data survives container restarts. |

## Using an env file

Copy `.env.example` to `.env` and set the required values:

```
VISION_FACE_LYCHEE_API_URL=https://lychee.example.com
VISION_FACE_API_KEY=a-long-random-string
```

Then run:

```bash
docker run --rm --env-file .env \
  -v /path/to/photos:/data/photos:ro \
  -v ai-vision-embeddings:/data/embeddings \
  -p 8000:8000 \
  lychee-ai-vision
```

## Docker Compose example

```yaml
services:
  ai-vision:
    image: lychee-ai-vision
    env_file: .env
    volumes:
      - lychee_uploads:/data/photos:ro
      - ai_embeddings:/data/embeddings
    ports:
      - "8000:8000"
    restart: unless-stopped

volumes:
  lychee_uploads:
    external: true   # the volume Lychee already uses for uploads
  ai_embeddings:
```

## Verify the service is running

```bash
curl http://localhost:8000/health
```

Expected response when ready:

```json
{"status": "ok", "model_loaded": true, "embedding_count": 0}
```

## Common configuration overrides

**Self-signed SSL certificate on Lychee:**

```
VISION_FACE_VERIFY_SSL=false
```

Do not disable SSL verification in production when certificates are valid.

**Skip startup connectivity check** (useful when Lychee starts after this service):

```
VISION_FACE_SKIP_LYCHEE_CHECK=true
```

**Use pgvector instead of SQLite:**

```
VISION_FACE_STORAGE_BACKEND=pgvector
VISION_FACE_PG_HOST=postgres
VISION_FACE_PG_DATABASE=ai_vision
VISION_FACE_PG_USER=ai_vision
VISION_FACE_PG_PASSWORD=secret
```

See [Configuration](../3-reference/configuration.md) for the full list of variables.
