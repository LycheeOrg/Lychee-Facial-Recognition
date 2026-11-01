# F-002 · Add Python 3.14 Support

**Status:** Implemented — pending review (amended by Q-002-04: Python 3.14 only)  
**Feature:** F-002 – add-python-314-support  

---

## Goal and motivation

The service currently supports only Python 3.13 (`requires-python = ">=3.13,<3.14"`). An attempt to move the Docker image to `python:3.14-slim` (dependabot, 6f399dd) had to be rolled back.

The only blocker is **TensorFlow**: the latest stable release (2.21.0, March 2026) ships wheels for `cp310`–`cp313` only. Every other dependency resolves and passes the test suite on CPython 3.14.10. Only `tf-nightly` (2.23.0.dev) publishes `cp314` wheels today.

**Amendment (2026-11-01):** once the ONNX switch was implemented, the maintainer chose to drop Python 3.13 entirely (Q-002-04). The service now targets Python 3.14 only. Requirements below are written for that end state.

TensorFlow is no longer required by DeepFace. Since 0.0.103 (already in `uv.lock`), DeepFace and `retina-face` treat TensorFlow and PyTorch as optional extras and ship `onnxruntime` as a base dependency. The engine is picked at import time in the order TensorFlow → PyTorch → ONNX, or forced via `DEEPFACE_BACKEND_ENGINE`. We get TensorFlow only because `pyproject.toml` lists `tensorflow` and `tf-keras` directly. `onnxruntime` 1.31.1 ships `cp311`–`cp314` wheels.

### Evidence: TensorFlow vs ONNX parity (2026-11-01)

ArcFace + RetinaFace via `DeepFace.represent()`, run on 6 images from DeepFace's own test set. The two backends were run in separate processes from the same `.venv` (Python 3.13, DeepFace 0.0.103), with the backend forced via `DEEPFACE_BACKEND_ENGINE`:

| Metric | Result |
|---|---|
| Faces detected per image | identical (1/1 on every image) |
| Bounding-box IoU, TF vs ONNX | 1.000 on every face |
| Max \|Δ face_confidence\| | 0.0000 |
| Cosine(TF embedding, ONNX embedding), recognition only (detector skipped) | 1.000000 on every image |
| Cosine(TF embedding, ONNX embedding), full pipeline | 1.000000 on every face |
| Max \|Δ pairwise similarity\| (TF–TF baseline vs ONNX–ONNX and vs stored-TF–new-ONNX) | < 1e-6 |
| Median detect + embed time per image (CPU) | TF 3.57 s · ONNX 1.05 s (≈ 3.4× faster) |

ONNX weights are separate files (`arcface_weights.onnx`, `retinaface.onnx`; 254 MB together, the same as the `.h5` pair).

Side effects of dropping TensorFlow: about **1.9 GB** fewer installed packages (`tensorflow`, `tf_keras`, `keras`, `ml_dtypes`, `h5py`) and a smaller Docker image.

---

## Scope

### In scope
- Run DeepFace on the ONNX Runtime backend on every supported Python version (Q-002-01 🅰️).
- Remove `tensorflow` and `tf-keras` from `[project].dependencies`; raise the floor to `deepface>=0.0.103`, the first version verified on the ONNX backend.
- Add `werkzeug` as a direct dependency (see *Bundled fix* below).
- Set `requires-python` to `">=3.14,<3.15"` (3.13 dropped, Q-002-04) and regenerate `uv.lock`.
- Set ruff `target-version` to `py314`.
- The CI test matrix runs 3.14 only; the coverage upload moves to the 3.14 job.
- A test that imports the real (unmocked) `deepface` package and checks which backend engine is active.
- Log the active DeepFace backend engine when the model loads.
- Remove the `gpu` optional extra (Q-002-02 🅰️).
- Move both Docker stages to `python:3.14-slim` (Q-002-03 🅱️).
- Documentation updates:
  - `AGENTS.md` and `docs/3-reference/coding-conventions.md` (supported Python version);
  - the detector options listed in `README.md`, `docs/3-reference/configuration.md` and the `AppSettings.detector_backend` docstring (see FR-10).

### Out of scope
- Changing the default recognition model (ArcFace) or detector (RetinaFace).
- Python 3.15: still blocked, because `onnxruntime` has no `cp315` wheels.
- Removing the now-redundant `opencv-python` dependency. Follow-up candidate, with a known defect:
  - DeepFace 0.0.103 pulls in `opencv-contrib-python-headless`, and both packages install the `cv2` module, so whichever is installed last wins.
  - Verified 2026-11-01: `cv2.CascadeClassifier` (contrib-only in OpenCV 5) is present in the project's 3.13 `.venv` but missing from a fresh 3.14 sync and from the 3.14 Docker image.
  - As a result, the `opencv` detector fails there; RetinaFace and ArcFace are unaffected.
  - The clash predates this feature: it was introduced by #63.
- Restoring the `ssd` detector. It needs OpenCV < 5, and the lock has `opencv-python` 5.0.0, so it has been broken since the OpenCV 5 upgrade, independently of this feature. Follow-up candidate.
- Validating `VISION_FACE_DETECTOR_BACKEND` and `VISION_FACE_MODEL_NAME` at startup.

### Bundled fix: missing `werkzeug`
Since dependabot #63 (2026-10-30) bumped DeepFace from 0.0.101 to 0.0.103, `import deepface` fails with `ModuleNotFoundError: No module named 'werkzeug'`:

- `deepface/commons/image_utils.py` imports `werkzeug` unconditionally, but it is only installed through the optional `api` (Flask) extra.
- This breaks model loading on `master` today.
- CI does not catch it: unit tests mock DeepFace, and the Docker job builds only the `builder` stage on pull requests.

The fix is to add `werkzeug` as a direct dependency. FR-7 and FR-8 cannot pass without it, so it is the first change of this feature, kept isolated so it can also be cherry-picked to `master` as a hotfix. FR-7 prevents a recurrence.

The same bump also dropped the `mtcnn` package from the lock: DeepFace 0.0.103 moved it into its `tensorflow` extra. So `VISION_FACE_DETECTOR_BACKEND=mtcnn` has also failed since #63, and it cannot return without TensorFlow (FR-10).

---

## Functional requirements

1. **FR-1** The service installs from a single `uv.lock` (`uv sync --frozen`) and runs on CPython 3.14. Python 3.13 is no longer supported.
2. **FR-2** `tensorflow` and `tf-keras` are absent from the resolved runtime dependency set on every supported Python version.
3. **FR-3** DeepFace runs on the `onnx` backend engine on every supported Python version. `FaceDetector.load()` logs the active engine at `INFO`.
4. **FR-4** Detection behaviour is unchanged: same models (ArcFace, RetinaFace), 512-dimensional embeddings, identical API request and response payloads and callback payloads.
5. **FR-5** Embeddings from the new backend are interchangeable with embeddings already stored under TensorFlow. On a reference image set:
   - each image yields the same number of faces;
   - the cosine similarity between each face's TensorFlow and ONNX embeddings is ≥ 0.9999.
   This is a pre-merge verification step, not a runtime check.
6. **FR-6** `make lint` and `make test` pass on Python 3.14 in CI.
7. **FR-7** At least one test imports the real `deepface` package (unmocked) and asserts that the backend engine is `onnx`. A broken transitive import such as the `werkzeug` failure, or TensorFlow coming back through some dependency, must fail CI.
8. **FR-8** The Docker image is based on `python:3.14-slim`, builds, and bakes the ONNX ArcFace and RetinaFace weights at build time. The resulting image loads them with networking disabled (airgapped).
9. **FR-9** The `gpu` optional extra is removed, so no install path re-introduces TensorFlow.
10. **FR-10** Every value documented for `VISION_FACE_DETECTOR_BACKEND` and `VISION_FACE_MODEL_NAME` must run with the locked dependencies:
    - detectors: only `retinaface` (default) is documented. `mtcnn` (needs TensorFlow), `ssd` (needs OpenCV < 5) and `opencv` (needs `cv2.CascadeClassifier`, lost to the `opencv-python` clash; see *Out of scope*) are removed from the docs;
    - models: `ArcFace`, `Facenet512` and `VGG-Face` all have ONNX implementations in DeepFace and stay documented.

---

## Non-functional requirements

- **Backward compatibility:**
  - No re-indexing. Existing SQLite and pgvector data stays valid (see the parity evidence and FR-5).
  - No API changes and no new required environment variables.
  - Deployments that set `VISION_FACE_DETECTOR_BACKEND` to `mtcnn`, `ssd` or `opencv` already fail, or may fail, on `master`; the release notes must say only `retinaface` is supported.
  - Anyone installing with `--extra gpu` gets an error after the upgrade; the release notes must mention the removal.
  - Source installs on Python 3.13 are no longer supported (Q-002-04). The Docker image is unaffected beyond the base-image move (FR-8). Release-note entry required.
- **Operational change:**
  - Non-Docker installs that pre-seeded `~/.deepface/weights/*.h5` will download the `.onnx` weights on first start.
  - Airgapped non-Docker installs must provide `arcface_weights.onnx` and `retinaface.onnx`.
  - Both points go in the release notes.
- **Performance:** CPU inference latency must not regress compared with the TensorFlow baseline (measured ≈ 3.4× faster).
- **Footprint:** The installed environment and the Docker image get smaller (≈ 1.9 GB less in the venv).
- **Thread safety:** Keep the existing lock around `DeepFace.represent()`. ONNX Runtime sessions are safe to run concurrently, but DeepFace's wrapper code makes no such guarantee.
- **Security:** Fewer dependencies means less surface for supply-chain and CVE exposure.

---

## Data model / API changes

None. Storage schema, HTTP API, callback payloads and `AppSettings` are unchanged.

### Dependency changes (`pyproject.toml`)

| Change | Before | After |
|---|---|---|
| `requires-python` | `>=3.13,<3.14` | `>=3.14,<3.15` |
| `deepface` | `>=0.0.93` | `>=0.0.103` |
| `tensorflow` | `>=2.16` | removed |
| `tf-keras` | `>=2.16` | removed |
| `werkzeug` | (not declared) | added |
| `[project.optional-dependencies].gpu` | `tensorflow[and-cuda]` | removed |
| `ruff` `target-version` | `py313` | `py314` |

### Docker base image (`Dockerfile`, both stages)

| Before | After |
|---|---|
| `python:3.13-slim` | `python:3.14-slim` (pinned by digest) |

---

## Open Questions

See Decision Cards below.

---

### ❓ Q-002-01 · Inference backend strategy

**Status:** ✅ Resolved — Option A (ONNX Runtime on all supported versions)  
**Feature:** F-002 – add-python-314-support  
**Preferred option:** 🅰️ (**recommended**) Option A – ONNX Runtime on all supported versions  

**Question**  
Stable TensorFlow cannot be installed on Python 3.14. Which inference backend should DeepFace use?

---

#### 🅰️ (**chosen**) Option A – ONNX Runtime on all supported versions
- **Idea:** Drop `tensorflow` and `tf-keras`. DeepFace falls back to its base `onnxruntime` dependency on both 3.13 and 3.14.
- **Spec impact:** As written above.
- **Pros:**  
  - ✅ One backend everywhere, so 3.13 and 3.14 deployments behave identically  
  - ✅ Parity verified: embeddings interchangeable, no re-indexing needed  
  - ✅ ≈ 3.4× faster on CPU and ≈ 1.9 GB smaller install
- **Cons:**  
  - ❌ Changes the inference runtime of a working production path (mitigated by FR-5 and FR-7)  
  - ❌ GPU acceleration needs a different setup (see Q-002-02)

---

#### 🅱️ Option B – Per-version backends
- **Idea:** Keep `tensorflow` with an environment marker `python_version < "3.14"`. 3.13 keeps running on TensorFlow; 3.14 falls back to ONNX.
- **Spec impact:** FR-2 and FR-3 hold on 3.14 only. CI must exercise both backends.
- **Pros:**  
  - ✅ No runtime change for existing 3.13 deployments
- **Cons:**  
  - ❌ Two inference stacks to test, debug and support  
  - ❌ The backend silently depends on the interpreter version  
  - ❌ Keeps the 1.9 GB TensorFlow footprint on 3.13

---

#### 🅲 Option C – Wait for stable TensorFlow `cp314` wheels
- **Idea:** No change now. Revisit when a stable TensorFlow release publishes `cp314` wheels (currently only `tf-nightly`).
- **Spec impact:** Feature deferred. Only the CI matrix could be prepared.
- **Pros:**  
  - ✅ Zero risk now
- **Cons:**  
  - ❌ No release date; 3.14 support stays blocked on an external project  
  - ❌ Leaves the speed and footprint gains unused

---

**Next action**  
Resolved by the maintainer on 2026-11-01: 🅰️.

---

### ❓ Q-002-02 · Fate of the `gpu` optional extra

**Status:** ✅ Resolved — Option A (drop the extra)  
**Feature:** F-002 – add-python-314-support  
**Preferred option:** 🅰️ (**recommended**) Option A – Drop the extra  

**Question**  
`pyproject.toml` declares `gpu = ["tensorflow[and-cuda]"]`. The docs don't mention it, and neither the Dockerfile nor CI uses it. Installing it would re-introduce TensorFlow, which DeepFace prefers over ONNX, and it cannot be installed on 3.14 at all. What should happen to it?

---

#### 🅰️ (**chosen**) Option A – Drop the extra
- **Idea:** Remove `[project.optional-dependencies].gpu`. The service is CPU-only on ONNX Runtime. GPU support becomes a follow-up feature if anyone needs it.
- **Spec impact:** FR-9 is satisfied by removal. Add a release-note entry.
- **Pros:**  
  - ✅ No way to switch the backend by accident  
  - ✅ Removes an untested, undocumented install path  
  - ✅ The ONNX CPU path is already ≈ 3.4× faster than TensorFlow on CPU
- **Cons:**  
  - ❌ Anyone privately using `--extra gpu` loses it

---

#### 🅱️ Option B – Replace with `onnxruntime-gpu`
- **Idea:** `gpu = ["onnxruntime-gpu"]`.
- **Spec impact:** Needs uv conflict or override configuration and a CUDA test environment. FR-9 requires the CUDA execution provider to actually be selected.
- **Pros:**  
  - ✅ Keeps GPU acceleration available, on the same backend
- **Cons:**  
  - ❌ DeepFace hard-requires `onnxruntime`, and both distributions install the same `onnxruntime` module, so they conflict in one environment  
  - ❌ No GPU runner in CI to verify it

---

#### 🅲 Option C – Keep `tensorflow[and-cuda]` as a 3.13-only extra
- **Idea:** Add the marker `python_version < "3.14"` to the existing extra.
- **Spec impact:** FR-9 must document that installing the extra switches DeepFace to TensorFlow.
- **Pros:**  
  - ✅ Nothing changes for existing GPU users on 3.13
- **Cons:**  
  - ❌ Brings back a second backend through an extra (the Q-002-01 🅱️ problems)  
  - ❌ GPU never available on 3.14

---

**Next action**  
Resolved by the maintainer on 2026-11-01: 🅰️.

---

### ❓ Q-002-03 · Docker base image Python version

**Status:** ✅ Resolved — Option B (move the image to `python:3.14-slim` now)  
**Feature:** F-002 – add-python-314-support  
**Preferred option:** 🅰️ (**recommended**) Option A – Keep `python:3.13-slim` in this feature  

**Question**  
Should this feature also move the published Docker image to Python 3.14?

---

#### 🅰️ (**recommended**) Option A – Keep `python:3.13-slim` in this feature
- **Idea:** Ship the backend switch on the current 3.13 image. 3.14 becomes supported for source installs and is tested in CI. The image moves to 3.14 in a separate change; dependabot's `3.13-slim` → `3.14-slim` PR would then succeed.
- **Spec impact:** FR-8 is verified on 3.13 only.
- **Pros:**  
  - ✅ Separates the backend change from the interpreter change in production, so a regression traces back to exactly one of them  
  - ✅ Each change can be rolled back on its own
- **Cons:**  
  - ❌ The image keeps 3.13 a little longer  
  - ❌ Dependabot's 3.14 image PRs must stay open or be re-raised, not ignored

---

#### 🅱️ (**chosen**) Option B – Move the image to `python:3.14-slim` now
- **Idea:** Update both `FROM` lines in the same PR.
- **Spec impact:** FR-8 is verified on 3.14. The CI Docker job must build the `baked` stage at least once to prove weights load.
- **Pros:**  
  - ✅ 3.14 lands in production in one step
- **Cons:**  
  - ❌ Two runtime changes (inference engine and interpreter) ship together in the image users run

---

**Next action**  
Resolved by the maintainer on 2026-11-01: 🅱️.

---

### ❓ Q-002-04 · Keep Python 3.13 support alongside 3.14?

**Status:** ✅ Resolved — Option A (switch fully to 3.14)  
**Feature:** F-002 – add-python-314-support  
**Preferred option:** 🅰️ (**chosen**) Option A – Python 3.14 only  

**Question**  
With the ONNX switch in place, the service runs on both 3.13 and 3.14. Should it keep supporting 3.13?

---

#### 🅰️ (**chosen**) Option A – Python 3.14 only
- **Idea:** `requires-python = ">=3.14,<3.15"`; CI tests 3.14 only; ruff targets `py314`.
- **Spec impact:** FR-1 and FR-6 cover 3.14 only. Lockfile carries a single interpreter.
- **Pros:**  
  - ✅ One interpreter across development, CI and the Docker image  
  - ✅ Smaller lockfile and CI matrix; 3.14 language features become available
- **Cons:**  
  - ❌ Source installs on 3.13 stop working (release-note entry)

---

#### 🅱️ Option B – Keep 3.13 and 3.14
- **Idea:** Leave `requires-python = ">=3.13,<3.15"` and the two-version CI matrix as first implemented.
- **Spec impact:** None (the original FR-1 and FR-6).
- **Pros:**  
  - ✅ No change for 3.13 source installs
- **Cons:**  
  - ❌ Two interpreters to test, while production (Docker) runs only 3.14

---

**Next action**  
Resolved by the maintainer on 2026-11-01: 🅰️.
