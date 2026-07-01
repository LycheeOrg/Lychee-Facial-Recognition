# F-001 · Purge Stale Embeddings

**Status:** Resolved — ready for planning  
**Feature:** F-001 – purge-stale-embeddings  

---

## Goal and motivation

Lychee needs a way to synchronise its face database with the AI Vision service after bulk deletions (e.g. album removal, user data purge). The existing `DELETE /embeddings` endpoint deletes a list of known IDs, but requires Lychee to enumerate every ID to remove. A complementary "purge stale" endpoint accepts the complete set of IDs that **should be kept** and deletes everything else, mirroring a `TRUNCATE … WHERE id NOT IN (…)` semantic.

---

## Scope

### In scope
- New `delete_except(keep_ids: list[str]) -> int` method on the `EmbeddingStore` protocol.
- Implementation in `SQLiteEmbeddingStore` and `PgVectorEmbeddingStore`.
- New API endpoint (`DELETE /embeddings/purge`) that accepts a list of face IDs to retain and deletes all other embeddings.
- Schema additions: request model + response model.
- Route handler implementation.
- Unit tests for the new route and both store implementations.
- Documentation update (`docs/3-reference/api.md`).

### Out of scope
- Deletion of crop image files from disk (consistent with existing `DELETE /embeddings` behaviour).
- Async/background execution.

---

## Functional requirements

1. **FR-1** The endpoint receives a list of `lychee_face_id` strings (`keep_ids`).
2. **FR-2** All stored embeddings whose `lychee_face_id` is **not** in `keep_ids` are deleted.
3. **FR-3** The response body contains the count of deleted embeddings (`deleted: int`).
4. **FR-4** The endpoint is protected by the `X-API-Key` header (same as all other endpoints).
5. **FR-5** If `keep_ids` is empty the behaviour is determined by Q-001 (see Open Questions).
6. **FR-6** The endpoint is idempotent: repeating the same request with the same `keep_ids` deletes 0 rows on the second call.

---

## Non-functional requirements

- **Security:** Same API-key auth as existing endpoints; no additional surface area.
- **Performance:** The database may hold up to 1 million embeddings. Loading all IDs into Python memory and diffing them is not acceptable at that scale. The `EmbeddingStore` protocol must gain a native `delete_except(keep_ids)` method so each backend executes the operation close to the database engine.
  - **SQLite constraint:** `WHERE id NOT IN (?, ?, …)` is limited to `SQLITE_MAX_VARIABLE_NUMBER` bind variables (999 by default). For large keep-sets the `NOT IN` clause would exceed this limit and raise `OperationalError`. The SQLite backend must instead bulk-insert keep IDs into a `TEMPORARY TABLE` (using `executemany`, which has no variable-count limit), then issue a single `DELETE … WHERE id NOT IN (SELECT id FROM _keep_ids)` against that table.
  - **PostgreSQL:** No equivalent bind-variable limit. Use `DELETE … WHERE lychee_face_id != ALL(%s::text[])` with a native array parameter — a single round-trip, no temp table required.
- **Backward compatibility:** Additive change only; no existing endpoint or schema is modified.

---

## Data model / API changes

New endpoint only. No store schema changes.

```
DELETE /embeddings/purge
```

Request body:
```json
{ "keep_ids": ["face-uuid-1", "face-uuid-2"] }
```

Response body:
```json
{ "deleted": 42 }
```

---

## Open Questions

See Decision Cards below.

---

### ❓ Q-001 · Behaviour when `keep_ids` is empty

**Status:** ✅ Resolved — Option A (reject empty list with 422)  
**Feature:** F-001 – purge-stale-embeddings  
**Preferred option:** 🅰️ (**recommended**) Option A – Reject with 422  

**Question**  
What should the endpoint do when the caller sends an empty `keep_ids` list? An empty list could mean "delete everything" (valid for a full wipe) or could indicate a caller bug.

---

#### 🅰️ (**recommended**) Option A – Reject empty list with 422

- **Idea:** Validate `keep_ids` with `min_length=1`; return 422 Unprocessable Entity when the list is empty.
- **Spec impact:** Callers that want to delete all embeddings must continue using `DELETE /embeddings` (delete all) or a future dedicated endpoint.
- **Pros:**
  - ✅ Prevents accidental full wipe due to caller bug or serialisation error.
  - ✅ Consistent with the existing `DeleteEmbeddingsRequest` which also requires `min_length=1`.
  - ✅ Simpler contract — no extra confirmation flag needed.
- **Cons:**
  - ❌ Cannot perform a full wipe in a single call; requires a separate flow.

---

#### 🅱️ Option B – Allow empty list (delete all)

- **Idea:** Accept an empty `keep_ids` list and delete all stored embeddings.
- **Spec impact:** Endpoint becomes a superset of a full-wipe operation.
- **Pros:**
  - ✅ Single endpoint covers all sync scenarios.
- **Cons:**
  - ❌ One serialisation bug on the Lychee side wipes the entire embedding store.
  - ❌ No idempotency guard; hard to recover without re-scanning all photos.

---

#### 🅾️ Option C – Allow empty list only with a confirmation flag

- **Idea:** Add `allow_delete_all: bool = False` to the request. Empty list is accepted only when the flag is `true`.
- **Spec impact:** More complex request schema; Lychee must opt in explicitly.
- **Pros:**
  - ✅ Supports full wipe safely with explicit intent.
- **Cons:**
  - ❌ Adds schema complexity for a rare use-case.
  - ❌ Not needed given `DELETE /embeddings` (or a future `DELETE /embeddings/all`) can cover the wipe case.

---

### ❓ Q-002 · HTTP method for the endpoint

**Status:** ✅ Resolved — Option A (`DELETE /embeddings/purge`)  
**Feature:** F-001 – purge-stale-embeddings  
**Preferred option:** 🅰️ (**recommended**) Option A – `DELETE /embeddings/purge`  

**Question**  
Should the endpoint use `DELETE` (consistent with the existing delete endpoint) or `POST` (more conventional for operations that carry a large body)?

---

#### 🅰️ (**recommended**) Option A – `DELETE /embeddings/purge`

- **Idea:** Use the `DELETE` HTTP method with a JSON body, mirroring the existing `DELETE /embeddings`.
- **Spec impact:** Consistent verb semantics across all embedding-deletion endpoints.
- **Pros:**
  - ✅ Consistent with `DELETE /embeddings` which also takes a JSON body.
  - ✅ Signals destructive intent to readers of the API contract.
- **Cons:**
  - ❌ HTTP `DELETE` with a body is valid but some older proxies or clients may strip the body.

---

#### 🅱️ Option B – `POST /embeddings/purge`

- **Idea:** Use `POST` with a JSON body.
- **Spec impact:** Mixed HTTP verbs for deletion operations (DELETE for the explicit-delete endpoint, POST for the purge endpoint).
- **Pros:**
  - ✅ Universal client compatibility; no proxy issues.
- **Cons:**
  - ❌ `POST` is semantically ambiguous — does not communicate that the operation deletes data.
  - ❌ Inconsistent with the existing `DELETE /embeddings` pattern.

---
