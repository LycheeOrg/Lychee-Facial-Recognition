# F-002 · Add Python 3.14 Support — Tasks

**Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)

## Tests first

- [x] Add `tests/test_deepface_backend.py`: a subprocess imports the real `deepface` and asserts the `onnx` engine (FR-7)
- [x] Add a `test_detection.py` test that `FaceDetector.load()` logs the DeepFace backend engine (FR-3)
- [x] Confirm both new tests fail before the implementation

## Bundled fix (hotfix-able)

- [x] Add `werkzeug` to `[project].dependencies` with an explanatory comment
- [x] `uv lock` and confirm `werkzeug` is in the lock

## ONNX switch and interpreter range

- [x] `requires-python = ">=3.13,<3.15"`
- [x] Remove `tensorflow` and `tf-keras`; set `deepface>=0.0.103`
- [x] Remove the `gpu` optional extra
- [x] `uv lock` + `uv sync`; confirm no `tensorflow`, `tf-keras` or `keras` in the lock

## Implementation

- [x] Log `DeepFace.backend_engine` in `FaceDetector.load()`
- [x] Add `"3.14"` to the CI test matrix
- [x] Move both `Dockerfile` stages to `python:3.14-slim` (pinned digest)

## Documentation

- [x] `AGENTS.md` and `coding-conventions.md`: supported versions 3.13 and 3.14
- [x] Detector options reduced to `retinaface` in `README.md`, `configuration.md` and the `AppSettings.detector_backend` docstring

## Verification

- [x] `make lint` and `make test` pass on 3.13
- [x] Lint and tests pass on 3.14 (environment synced from the frozen lock)
- [x] FR-5 parity: ONNX on 3.14 vs the TensorFlow baseline recorded on 3.13
- [x] FR-8: full `docker build`; DeepFace loads the baked weights with `--network none`
- [x] Tick the spec status to *Implemented*

## Amendment: Python 3.14 only (Q-002-04)

- [x] `requires-python = ">=3.14,<3.15"`; ruff `target-version = "py314"`
- [x] `uv lock`; confirm package set and versions unchanged
- [x] CI test matrix 3.14 only; coverage upload on 3.14
- [x] `AGENTS.md` and `coding-conventions.md`: Python 3.14 only
- [x] Lint (`ruff check`, `ruff format --check`, `ty`) and tests pass on 3.14
- [x] Docker image rebuilds from the 3.14-only lock and passes the offline `/health` check
