# Tune Detection Thresholds

All thresholds are environment variables read at startup. Changing them requires a service restart.

## Detection confidence (`VISION_FACE_DETECTION_THRESHOLD`, default `0.5`)

RetinaFace assigns a confidence score (0.0–1.0) to each bounding box. Only faces **above** this value are processed further.

- **Raise** (e.g. `0.7`) to cut false positives — textures or objects that superficially resemble faces in busy backgrounds.
- **Lower** (e.g. `0.3`) to detect more faces in difficult conditions: unusual angles, partial occlusion, small faces.

## Blur filtering (`VISION_FACE_BLUR_THRESHOLD`, default `0.5`)

Laplacian variance measures the sharpness of the face crop region. Higher variance = sharper image.

- Faces with variance **below** this value are discarded before embedding.
- Set to `0.0` to disable blur filtering entirely.
- Laplacian variance values are stored with each embedding and included in callbacks, so you can adjust this threshold and re-cluster without re-scanning photos.

## Minimum face size (`VISION_FACE_MIN_FACE_SIZE_PIXELS`, default `0` — disabled)

The longest side of the bounding box (in pixels) must be **strictly greater** than this value. Discards thumbnails and distant background faces that are unlikely to yield useful embeddings.

Example: `VISION_FACE_MIN_FACE_SIZE_PIXELS=40` rejects any face whose largest dimension is ≤ 40 px.

## Match threshold (`VISION_FACE_MATCH_THRESHOLD`, default `0.5`)

Cosine similarity cutoff used in two places:

1. **Suggestions during detection** — only stored faces above this score are included in the `/detect` callback payload.
2. **Selfie matching** (`POST /match`) — only matches above this score are returned.

- **Raise** (e.g. `0.65`) for stricter matching: fewer suggestions, higher precision.
- **Lower** (e.g. `0.35`) for broader matching: more suggestions, higher recall at the cost of more false positives.

## Clustering epsilon (`VISION_FACE_CLUSTER_EPS`, default `0.6`)

Maximum cosine **distance** (= `1 − similarity`) for two faces to be considered neighbours in DBSCAN. Faces closer than this distance may end up in the same cluster.

- **Lower** (e.g. `0.4`) → tighter, more homogeneous clusters. Equivalent to requiring cosine similarity ≥ 0.6 between neighbours.
- **Higher** (e.g. `0.7`) → broader clusters. More faces grouped together, higher risk of merging distinct people.

A useful reference: `eps = 0.4` means neighbours must have similarity ≥ 0.6; `eps = 0.6` means similarity ≥ 0.4.

## Maximum faces per photo (`VISION_FACE_MAX_FACES_PER_PHOTO`, default `10`)

After filtering, only the top-N faces by detection confidence are included in the callback payload. Useful for very large group photos to cap payload size.

## Suggested starting points

| Scenario | Adjustment |
|---|---|
| Many false-positive faces detected | Raise `DETECTION_THRESHOLD` to 0.7, raise `MIN_FACE_SIZE_PIXELS` to 30 |
| Blurry faces slipping through | Raise `BLUR_THRESHOLD` (try 50–200 range; values depend on image resolution) |
| Suggestions too aggressive (wrong people matched) | Raise `MATCH_THRESHOLD` to 0.65–0.7 |
| Clustering splits the same person into many clusters | Raise `CLUSTER_EPS` to 0.65–0.75 |
| Clustering merges different people into one cluster | Lower `CLUSTER_EPS` to 0.4–0.5 |
