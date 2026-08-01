# F-001 · Purge Stale Embeddings

**Status:** Resolved — ready for planning  
**Feature:** F-001 – purge-stale-embeddings  

---

## Goal and motivation

Lychee needs a way to synchronise its face database with the AI Vision service after bulk deletions (e.g. album removal, user data purge). Because the complete set of surviving face IDs may be arbitrarily large, the sync is split across two phases:

1. **Mark phase** — Lychee sends the surviving IDs in one or more batches via `DELETE /embeddings/sync`. Each embedding is flagged `is_present = TRUE` if its ID appears in any batch, and everything is reset to `FALSE` at the start of the first batch (`batch == 0`).
2. **Purge phase** — Lychee calls `DELETE /embeddings/purge` once all batches are sent. The service deletes every embedding still flagged `is_present = FALSE`.

This two-step approach avoids constructing a single giant `NOT IN (…)` clause and keeps each individual request small.

---

## Scope

### In scope
- New `is_present` boolean column on both the SQLite and PgVector embedding stores (`DEFAULT TRUE`).
- New `DELETE /embeddings/sync` endpoint: mark-present batch operation (additive; existing `DELETE /embeddings` is unchanged).
- New `sync_batch(face_ids: list[str], batch: int) -> int` method on the `EmbeddingStore` protocol.
- New `DELETE /embeddings/purge` endpoint: deletes all rows where `is_present = FALSE`.
- New `purge_absent() -> int` method on the `EmbeddingStore` protocol.
- Schema migrations for both backends (SQLite `ALTER TABLE`, PgVector `ALTER TABLE`).
- Updated request/response Pydantic models.
- Route handler implementation for both endpoints.
- Unit tests for the new route and both store implementations.
- Documentation update (`docs/3-reference/api.md`).

### Out of scope
- Deletion of crop image files from disk (consistent with prior behaviour).
- Async/background execution.
- Any rollback or undo mechanism if the purge is called prematurely.

---

## Functional requirements

### `DELETE /embeddings/sync` — Mark-present batch

1. **FR-1** The request body contains `face_ids: list[str]` and `batch: int` (≥ 0).
2. **FR-2** When `batch == 0`, the service first sets `is_present = FALSE` on **all** stored embeddings, then sets `is_present = TRUE` for every embedding whose `lychee_face_id` appears in `face_ids`.
3. **FR-3** When `batch > 0`, the service sets `is_present = TRUE` only for the embeddings in `face_ids`; all other rows are left unchanged.
4. **FR-4** The response body confirms the number of IDs marked present in this batch (`marked: int`).
5. **FR-5** The endpoint is protected by the `X-API-Key` header.
6. **FR-6** Sending the same `face_ids` and `batch > 0` again is idempotent (re-sets the same rows to `TRUE`; no error).
7. **FR-7** `face_ids` may be an empty list. For `batch == 0` this resets all embeddings to `is_present = FALSE` and marks none as present (valid when all faces have been deleted). For `batch > 0` it is a no-op.

### `DELETE /embeddings/purge` — Purge absent embeddings

8. **FR-8** The endpoint accepts no request body.
9. **FR-9** All embeddings where `is_present = FALSE` are permanently deleted.
10. **FR-10** The response body contains the count of deleted embeddings (`deleted: int`).
11. **FR-11** The endpoint is protected by the `X-API-Key` header.
12. **FR-12** Calling the purge before any batch 0 has been sent is safe: since `is_present` defaults to `TRUE`, no rows will be deleted.

---

## Non-functional requirements

- **Security:** Same API-key auth as all existing endpoints; no additional surface area.
- **Performance:** The database may hold up to 1 million embeddings.
  - The batch-0 full reset (`UPDATE … SET is_present = FALSE`) touches every row. Both backends must execute this as a single bulk `UPDATE` — no Python-level iteration.
  - SQLite `UPDATE … SET is_present = TRUE WHERE lychee_face_id IN (?, …)` is limited to `SQLITE_MAX_VARIABLE_NUMBER` (999) bind variables. Large `face_ids` lists must be chunked into batches of ≤ 999 IDs and applied with multiple statements inside a single transaction.
  - PostgreSQL has no equivalent bind-variable limit. Use `UPDATE … SET is_present = TRUE WHERE lychee_face_id = ANY(%s::text[])` with a native array — a single round-trip.
- **Backward compatibility:** Additive change only. `DELETE /embeddings` (delete-by-ID) is unchanged. Two new endpoints are added: `DELETE /embeddings/sync` and `DELETE /embeddings/purge`.
- **Default value:** `is_present` defaults to `TRUE` so that existing embeddings written before the migration do not get purged on the first sync cycle.

---

## Data model / API changes

### Store schema

New column added to both backends:

```sql
ALTER TABLE embeddings ADD COLUMN is_present BOOLEAN NOT NULL DEFAULT TRUE;
```

### `EmbeddingStore` protocol additions

```python
def sync_batch(self, face_ids: list[str], batch: int) -> int:
    """Mark face_ids as present. If batch == 0, reset all rows first.
    Returns the number of rows marked TRUE in this call."""
    ...


def purge_absent(self) -> int:
    """Delete all rows where is_present = FALSE. Returns the deleted count."""
    ...
```

### `DELETE /embeddings/sync` (new)

Request body:
```json
{ "face_ids": ["face-uuid-1", "face-uuid-2"], "batch": 0 }
```

An empty `face_ids` list is permitted (e.g. `{ "face_ids": [], "batch": 0 }` when all faces have been deleted).

Response body:
```json
{ "marked": 2 }
```

### `DELETE /embeddings/purge` (new)

No request body.

Response body:
```json
{ "deleted": 42 }
```

---

## Open Questions

See Decision Cards below.

---

### ❓ Q-001 · Behaviour when `face_ids` is empty in a batch request

**Status:** ✅ Resolved — Option B (allow empty list)  
**Feature:** F-001 – purge-stale-embeddings  
**Preferred option:** 🅱️ Option B – Allow empty `face_ids`  

**Question**  
What should `DELETE /embeddings/sync` do when `face_ids` is an empty list?

---

#### 🅰️ Option A – Reject empty `face_ids` with 422

- **Idea:** Validate `face_ids` with `min_length=1`; return 422 Unprocessable Entity when the list is empty.
- **Pros:**
  - ✅ Prevents accidental full wipe caused by a serialisation bug in Lychee.
- **Cons:**
  - ❌ Lychee cannot express "all faces have been deleted" — a legitimate state that must be representable.

---

#### 🅱️ (**chosen**) Option B – Allow empty `face_ids`

- **Idea:** Accept an empty list. For `batch == 0` this resets all rows to `is_present = FALSE` with none marked present (correct when all faces have been deleted). For `batch > 0` it is a no-op.
- **Pros:**
  - ✅ Covers the valid "deleted everything" scenario without a separate code path in Lychee.
  - ✅ Lychee can page through face IDs and send an empty first batch if the DB is already empty.
- **Cons:**
  - ❌ An accidental empty `batch == 0` call marks everything for deletion; the caller must follow up with `DELETE /embeddings/purge` to materialise the wipe.

---

### ❓ Q-002 · Endpoint naming — new endpoint vs. modifying `DELETE /embeddings`

**Status:** ✅ Resolved — Option B (new endpoint)  
**Feature:** F-001 – purge-stale-embeddings  
**Preferred option:** 🅱️ Option B – New `DELETE /embeddings/sync` endpoint  

**Question**  
Should the mark-present logic replace the existing `DELETE /embeddings` endpoint, or live on a new endpoint?

---

#### 🅰️ Option A – Replace `DELETE /embeddings`

- **Pros:** ✅ Fewer endpoints.
- **Cons:** ❌ Breaking change; older Lychee clients that call `DELETE /embeddings` to delete specific IDs would silently misbehave.

---

#### 🅱️ (**chosen**) Option B – New `DELETE /embeddings/sync` endpoint

- **Idea:** Leave `DELETE /embeddings` (delete-by-ID) completely unchanged. Add `DELETE /embeddings/sync` for the mark-present batch operation.
- **Pros:**
  - ✅ No breaking change; both deletion workflows coexist.
  - ✅ Explicit delete-by-ID remains available for targeted operations.
- **Cons:**
  - ❌ Slightly more endpoints to maintain.

---

### ❓ Q-003 · Concurrency — overlapping sync sessions

**Status:** ✅ Resolved — Option A (no protection)  
**Feature:** F-001 – purge-stale-embeddings  
**Preferred option:** 🅰️ Option A – No protection  

**Question**  
Should the service guard against two concurrent sync sessions clobbering each other's `is_present` flags?

---

#### 🅰️ (**chosen**) Option A – No protection (document as single-writer assumption)

- **Idea:** Document that the sync workflow is intended to be run as a single sequential operation from Lychee. Concurrent syncs produce undefined results.
- **Pros:**
  - ✅ No implementation complexity.
  - ✅ Matches Lychee's operational model — sync is triggered as one atomic job.
- **Cons:**
  - ❌ Silent misbehaviour if the assumption is ever violated.

---

#### 🅱️ Option B – Session token

- **Idea:** `batch == 0` returns a `sync_token`. Subsequent calls require the token; stale tokens are rejected with 409.
- **Pros:** ✅ Safe under concurrency.
- **Cons:** ❌ Requires server-side session state; adds a new failure mode.

---
