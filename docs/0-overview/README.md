# Overview

Lychee AI Vision is a Python microservice that adds facial recognition to the [Lychee](https://github.com/LycheeOrg/Lychee) photo gallery. It runs as a sidecar Docker container and communicates with Lychee exclusively over HTTP.

## What it does

When Lychee processes a new photo it sends the photo path to this service. The service:

1. Detects all faces using DeepFace (RetinaFace detector + ArcFace model by default).
2. Filters out low-confidence, too-small, and blurry faces.
3. Generates a 150×150 JPEG crop for each surviving face.
4. Computes a 512-dimensional embedding vector for each face.
5. Searches stored embeddings for similar faces to produce suggestions.
6. POSTs results (bounding boxes, crops, embeddings, suggestions) back to Lychee as a callback.
7. Persists embeddings under the stable `Face.id` values returned by Lychee.

Beyond detection, the service also handles:

- **Selfie matching** (`POST /match`) — upload a selfie to find the closest stored faces. Used by Lychee to let a user claim photos of themselves.
- **Clustering** (`POST /cluster`) — run DBSCAN over all stored embeddings to group unknown faces by likely identity.
- **Embedding management** — delete individual embeddings or export all metadata for re-synchronisation.

## Integration model

```
Lychee (PHP)  ──POST /detect──────────────────► AI Vision Service
                                                        │
                                              detect · embed · crop
                                                        │
              ◄──POST /api/v2/FaceDetection/results────
                  {photo_id, faces[]}                   │
              ──200 {face mappings}────────────────────►
                                                        │
                                              persist embeddings
```

Both directions use the same shared API key (`X-API-Key` header).

## Key design decisions

| Decision | Rationale |
|---|---|
| `202 Accepted` + async background task | Detection takes 1–10 s per photo. Returning immediately keeps Lychee's HTTP lifecycle short. |
| Callback instead of polling | Lychee receives results as soon as they are ready; no long-polling or WebSocket needed. |
| Embeddings stored here, not in Lychee | PHP has no vector similarity engine. The service owns the store and exposes a similarity-search API. |
| ArcFace + RetinaFace defaults | High-accuracy combination suited for personal libraries with varied lighting and poses. |
| Pluggable storage (SQLite / pgvector) | SQLite requires no extra infrastructure for small libraries; pgvector scales without code changes. |
| Shared API key in both directions | Lychee authenticates inbound requests; the service authenticates its outbound callbacks to Lychee. |
| Idempotent detection | If faces are already stored for a `photo_id`, the service sends an empty success callback and returns — no redundant work. |
