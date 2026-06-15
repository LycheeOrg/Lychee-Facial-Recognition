# Python Coding Conventions

This document describes the coding standards enforced in this project. All rules are verified by `ruff` and `ty` — pull requests must pass both before merging.

## Python version

**Python 3.13** is the only supported version (`requires-python = ">=3.13,<3.14"`). Use modern syntax freely: `match`, `Self`, `TypeAlias`, `ExceptionGroup`, built-in generics, etc.

## Tooling

| Tool | Purpose | Command |
|---|---|---|
| `ruff check` | Lint (pycodestyle, pyflakes, isort, naming, annotations, bugbear, …) | `make lint` |
| `ruff format` | Auto-format | `make format` |
| `ty check` | Static type checking | `make lint` |
| `pytest` | Tests | `make test` |

Run all three before opening a PR. `ruff format --check` and `ruff check` run in CI and will fail the build.

## Formatting

- **Line length:** 120 characters.
- **Indentation:** 4 spaces (ruff normalises Python files to spaces regardless of `.editorconfig` tab settings).
- **String quotes:** double (`"`).
- **Line endings:** LF.
- **Trailing whitespace:** trimmed.

## Imports

Every module must begin with:

```python
from __future__ import annotations
```

This enables PEP 563 postponed annotation evaluation, which allows forward references and eliminates runtime annotation cost.

Import order (enforced by `ruff I` / isort):

1. Standard library
2. Third-party packages
3. First-party (`app.*`)

Imports used only in type annotations go inside a `TYPE_CHECKING` guard:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from app.detection.detector import FaceDetector
```

This keeps heavy packages (`deepface`, `numpy`, …) out of the runtime import graph when only their types are needed.

## Type annotations

All function parameters and return types must be fully annotated (`ruff ANN`). Unannotated signatures fail CI.

```python
# correct
def detect(self, image_path: Path) -> list[DetectedFace]:

# wrong — missing return type
def detect(self, image_path: Path):
```

`typing.Any` is permitted only where no more precise type exists — specifically numpy arrays and raw DeepFace return values (`ANN401` is suppressed). Do not use `Any` as an escape hatch elsewhere.

Use built-in generic types directly (`list[str]`, `dict[str, int]`, `tuple[str, ...]`) — not `typing.List`, `typing.Dict` (enforced by `ruff UP`).

Apply `@typing.override` when overriding a base class or protocol method:

```python
class _ColorFormatter(logging.Formatter):
    @typing.override
    def format(self, record: logging.LogRecord) -> str:
        ...
```

## Naming

PEP 8 naming enforced by `ruff N`:

| Kind | Convention | Example |
|---|---|---|
| Module | `snake_case` | `sqlite_store.py` |
| Class | `PascalCase` | `FaceDetector`, `EmbeddingStore` |
| Function / method | `snake_case` | `detect_bytes`, `similarity_search` |
| Variable | `snake_case` | `raw_faces`, `photo_id` |
| Module-level private | leading `_` | `_RED`, `_default_lifespan` |
| Instance private | leading `_` | `_loaded`, `_lock` |

Do not shadow Python built-ins (`id`, `list`, `type`, …) — enforced by `ruff A`.

## Docstrings

Use a single-line docstring when the purpose is obvious from the name and signature. Add `Args:` and `Raises:` sections when behaviour or failure modes are non-obvious.

```python
def count(self) -> int:
    """Return the total number of stored embeddings."""

def detect(self, image_path: Path) -> list[DetectedFace]:
    """Detect faces in an image file.

    Args:
        image_path: Absolute path to the image file.

    Returns:
        Detected faces sorted by descending confidence, with normalised
        bounding box coordinates (0.0–1.0) and 512-dim embeddings.

    Raises:
        RuntimeError: If :meth:`load` has not been called.
        ValueError: If the file cannot be decoded as an image.
    """
```

Do not write a docstring that only restates the function name. A docstring must add information beyond what the name and types already express.

## Inline comments

Write a comment only when the **why** is non-obvious from the code. Do not explain what the code does. Do not reference issue numbers or task IDs — those belong in commit messages.

```python
# Avoid division by zero for zero-norm vectors
norms = np.where(norms == 0, 1.0, norms)

# deepface reads DEEPFACE_HOME lazily, not at import time, so setting it here —
# before detector.load() — is reliable even though the module is already imported.
os.environ["DEEPFACE_HOME"] = settings.model_root
```

## Application structure

### Configuration

All settings live in `app/config.py` as a `pydantic-settings` `AppSettings` model. **Never read environment variables directly.** Inject settings in route handlers via `Depends(get_settings)`.

```python
# correct
async def detect(settings: AppSettings = Depends(get_settings)) -> None:
    threshold = settings.detection_threshold

# wrong
threshold = float(os.environ["VISION_FACE_DETECTION_THRESHOLD"])
```

`get_settings()` is cached with `@lru_cache`. Override it in tests with `app.dependency_overrides[get_settings]`.

### FastAPI routes

Routes must be thin: validate the request, delegate to domain modules or background tasks, return. Business logic belongs in `app/detection/`, `app/clustering/`, `app/matching/`, or `app/embeddings/`.

`Depends()` calls in function default arguments are allowed — `B008` is suppressed because FastAPI requires this pattern.

### Interfaces

Use `typing.Protocol` for backend-agnostic interfaces. Concrete implementations satisfy the protocol structurally — no inheritance needed.

```python
@runtime_checkable
class EmbeddingStore(Protocol):
    def add(self, lychee_face_id: str, embedding: list[float], ...) -> None: ...
    def similarity_search(self, embedding: list[float], threshold: float, limit: int) -> list[tuple[str, float]]: ...
```

### CPU-bound work

DeepFace inference is blocking and slow. Always offload it to the `ThreadPoolExecutor` in `app.state.executor`:

```python
loop = asyncio.get_running_loop()
results = await loop.run_in_executor(executor, detector.detect, image_path)
```

Never call blocking functions directly inside `async def` handlers or background tasks.

## Tests

- Test files live in `tests/`, named after the module they cover (`test_api.py`, `test_detection.py`, …).
- `asyncio_mode = "auto"` is set globally — no `@pytest.mark.asyncio` decorator needed.
- Use `respx` to mock `httpx` HTTP calls. Do not patch `httpx` internals.
- Inject fakes via `app.dependency_overrides` instead of monkeypatching globals.
- `--strict-markers` is enabled: any custom marker must be declared under `[tool.pytest.ini_options]` in `pyproject.toml`.
