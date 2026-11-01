# F-002 · Add Python 3.14 Support — Implementation Plan

**Spec:** [spec.md](spec.md)  
**Decisions:** Q-002-01 🅰️ (ONNX everywhere) · Q-002-02 🅰️ (drop `gpu` extra) · Q-002-03 🅱️ (Docker on `python:3.14-slim`) · Q-002-04 🅰️ (Python 3.14 only)

---

## Approach

No inference code changes. DeepFace 0.0.103 already selects its backend engine at import time and falls back to its base `onnxruntime` dependency when TensorFlow is not installed. Removing `tensorflow` and `tf-keras` from `pyproject.toml` is therefore enough to move the service onto ONNX Runtime. The rest of the work makes the switch observable, guards it in CI, and widens the supported interpreter range.

The work is ordered so that each step can be verified on its own, and so that the `werkzeug` fix stays separable as a hotfix for `master`.

## Steps

### 1. Guard tests first (FR-7, FR-3)

- **New `tests/test_deepface_backend.py`.** In a subprocess, it imports the real `deepface` package with `DEEPFACE_BACKEND_ENGINE` unset and `DEEPFACE_HOME` pointed at `tmp_path`, then asserts that the selected engine is `onnx`.
  - *Why a subprocess:* other tests inject a stub `deepface` into `sys.modules`; the subprocess keeps the real import isolated from them, and lets DeepFace's import-time engine selection run fresh.
  - *Expected result before step 2:* fails, because `werkzeug` is missing (import error). After `werkzeug` alone it still fails, now because TensorFlow is selected.
- **`tests/test_detection.py`.** New test that `FaceDetector.load()` logs the engine reported by the `DeepFace` module (stubbed as `"onnx"`).

### 2. Bundled fix: add `werkzeug` (hotfix-able)

- `pyproject.toml`: add `werkzeug` to `[project].dependencies`, with a comment explaining why (DeepFace imports it unconditionally but only declares it in its `api` extra).
- `uv lock`.
- This change stands alone: it can be cherry-picked to `master` without the rest of the feature.

### 3. Switch to ONNX and widen the interpreter range (FR-1, FR-2, FR-9)

- `pyproject.toml`:
  - `requires-python = ">=3.13,<3.15"`;
  - remove `tensorflow` and `tf-keras`;
  - `deepface>=0.0.103`;
  - remove `[project.optional-dependencies]` (`gpu` is its only entry).
- `uv lock` with the project's own uv, so the lockfile format stays readable by every uv in use; then `uv sync`.
- Check that the lock contains no `tensorflow`, `tf-keras` or `keras` packages.

### 4. Log the backend engine (FR-3)

- `app/detection/detector.py`: after the warm-up call in `load()`, log `DeepFace.backend_engine` at `INFO`.
  - *Why this attribute:* it is a module global that DeepFace sets at import (`DeepFace.backend_engine = backend_utils.get_backend_engine()`), and reading it works with the existing `sys.modules` stubs. The alternative, importing `deepface.commons.backend_utils`, would fail under those stubs because a `MagicMock` is not a package.

### 5. CI matrix (FR-6)

- `.github/workflows/CICD.yaml`: add `"3.14"` to `test.strategy.matrix.python-version`. Coverage upload stays on 3.13 only.

### 6. Docker image (FR-8)

- `Dockerfile`: both `FROM` lines move to `python:3.14-slim`, pinned to the digest the tag currently resolves to.
- No other Dockerfile changes are needed. The bake step calls `DeepFace.represent()`, which now downloads `arcface_weights.onnx` and `retinaface.onnx` instead of the `.h5` files.

### 7. Documentation (FR-10)

- `AGENTS.md`, `docs/3-reference/coding-conventions.md`: supported versions are 3.13 and 3.14, and code must stay 3.13-compatible.
- `README.md`, `docs/3-reference/configuration.md`, the `AppSettings.detector_backend` docstring: list only `retinaface` as a detector option. `opencv` was dropped during verification: the `opencv-python` clash removes `cv2.CascadeClassifier` (see the spec).

### 8. Verification

- `make lint` and `make test` on 3.13 (project `.venv`).
- Lint and tests on 3.14, in a separate environment synced from the frozen lock.
- FR-5: run the parity harness on the 3.14 environment (ONNX only) and compare against the TensorFlow baseline recorded on 3.13 before the switch.
- FR-8: `docker build` the full image, then run DeepFace inside it with `--network none`.

### 9. Amendment: drop Python 3.13 (Q-002-04)

Applied after steps 1–8, which ran with 3.13 and 3.14 both supported.

- `pyproject.toml`: `requires-python = ">=3.14,<3.15"`; ruff `target-version = "py314"`. ty follows `requires-python`.
- `uv lock`: only the 3.13 wheel entries and markers drop out; the package set and versions must stay unchanged.
- `.github/workflows/CICD.yaml`: test matrix `["3.14"]`; coverage upload condition moves to `'3.14'`. The single-entry matrix is kept so another version can be added later without restructuring the job.
- `AGENTS.md`, `coding-conventions.md`: Python 3.14 is the only supported version.
- Re-verify: lint, ty and tests on 3.14; Docker rebuild from the new lock.

---

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Force `DEEPFACE_BACKEND_ENGINE=onnx` in the Dockerfile or at startup | Unnecessary once TensorFlow is not installed: auto-selection is deterministic. It would also hide a TensorFlow re-introduction instead of letting the FR-7 test catch it. |
| Import the real `deepface` in-process in the guard test | Conflicts with the `sys.modules` stubs used by `test_detection.py`. DeepFace also caches its engine choice at import, so the result would depend on test order. |
| CI Docker job builds the `baked` stage on pull requests | Downloads ~254 MB of weights on every PR. Import breakage is already caught by FR-7 on both interpreters; the bake is verified locally for this change (step 8) and runs in CI on every push to `master`. |
| Keep the `opencv-python` comment and dependency cleanup in this feature | Out of scope per the spec; tracked as a follow-up. |
| Validate detector and model names in `AppSettings` | Out of scope per the spec. A documentation correction is enough to stop advertising unsupported values. |
