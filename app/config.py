"""Application configuration via Pydantic BaseSettings.

All settings are loaded from environment variables prefixed with ``VISION_FACE_``.
Example: the ``api_key`` field maps to the ``VISION_FACE_API_KEY`` env var.
"""

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _pretty_config_error(exc: ValidationError) -> None:
    missing: list[str] = []
    invalid: list[tuple[str, str]] = []

    for error in exc.errors():
        field = str(error["loc"][0])
        env_var = f"VISION_FACE_{field.upper()}"
        if error["type"] == "missing":
            missing.append(env_var)
        else:
            invalid.append((env_var, error["msg"]))

    lines = [
        "",
        f"{_BOLD}{_RED}✗  AI Vision Service failed to start — invalid configuration{_RESET}",
        "",
    ]

    if missing:
        lines.append(f"{_YELLOW}Required environment variables are not set:{_RESET}")
        for var in missing:
            lines.append(f"  {_BOLD}{var}{_RESET}")
        lines.append("")

    if invalid:
        lines.append(f"{_YELLOW}Environment variables have invalid values:{_RESET}")
        for var, msg in invalid:
            lines.append(f"  {_BOLD}{var}{_RESET}  {_DIM}— {msg}{_RESET}")
        lines.append("")

    lines += [
        f"{_DIM}All settings use the VISION_FACE_ prefix.",
        f"Example:  VISION_FACE_LYCHEE_API_URL=http://lychee  VISION_FACE_API_KEY=secret{_RESET}",
        "",
    ]

    print("\n".join(lines), file=sys.stderr)


class AppSettings(BaseSettings):
    """Runtime configuration for the AI Vision Service.

    All values are read from environment variables prefixed ``VISION_FACE_``.
    """

    # --- Required ---
    lychee_api_url: str
    """Lychee instance base URL for callbacks (e.g. ``http://lychee``). No trailing slash."""

    api_key: str
    """Shared API key used in both directions: validated on *inbound* requests from Lychee
    (``X-API-Key`` header) and sent as ``X-API-Key`` on *outbound* callbacks to Lychee.
    Must match ``AI_VISION_FACE_API_KEY`` in the Lychee ``.env``."""

    verify_ssl: bool = True
    """Whether to verify SSL certificates when making callbacks to Lychee.
    Set to ``False`` for development environments with self-signed certificates.
    **WARNING:** Disabling SSL verification in production is a security risk."""

    skip_lychee_check: bool = False
    """Skip the Lychee connectivity check at startup.
    Useful for local development or when Lychee is not yet reachable."""

    # --- Model ---
    model_name: str = "ArcFace"
    """DeepFace recognition model name.  ``ArcFace`` = high-accuracy 512-dim embeddings (default);
    other supported models include ``Facenet512``, ``VGG-Face``, etc."""

    detector_backend: str = "retinaface"
    """DeepFace detector backend.  ``retinaface`` = high-accuracy (default);
    alternatives include ``mtcnn``, ``opencv``, ``ssd``."""

    # --- Detection thresholds ---
    detection_threshold: float = 0.5
    """Bounding-box confidence filter — faces below this score are excluded from the callback payload."""

    match_threshold: float = 0.5
    """Cosine-similarity cutoff for selfie match results and suggestion candidates."""

    rescan_iou_threshold: float = 0.5
    """IoU threshold for bounding-box matching on re-scan (preserves ``person_id``)."""

    max_faces_per_photo: int = 10
    """Maximum faces included in a callback payload (top-N by confidence; rest dropped)."""

    # --- Concurrency ---
    thread_pool_size: int = 1
    """Number of threads in the ``ThreadPoolExecutor`` used for CPU-bound inference."""

    workers: int = 1
    """Number of Uvicorn worker processes."""

    # --- Embedding storage ---
    storage_backend: str = "sqlite"
    """Embedding storage engine: ``sqlite`` or ``pgvector``."""

    storage_path: str = "/data/embeddings"
    """SQLite DB directory (used when ``storage_backend = "sqlite"``)."""

    # --- PostgreSQL (pgvector) ---
    pg_host: str = "localhost"
    """PostgreSQL host (only when ``storage_backend = "pgvector"``)."""

    pg_port: int = 5432
    """PostgreSQL port."""

    pg_database: str = "ai_vision"
    """PostgreSQL database name."""

    pg_user: str = "ai_vision"
    """PostgreSQL username."""

    pg_password: str = ""
    """PostgreSQL password."""

    # --- Photo volume ---
    photos_path: str = "/data/photos"
    """Shared Docker-volume mount point for photo files.

    ``photo_path`` values from Lychee are validated to reside within this prefix
    (path-traversal protection).
    """

    # --- Logging ---
    log_level: str = "info"
    """Uvicorn/application log level."""

    # --- Clustering ---
    cluster_eps: float = 0.6
    """DBSCAN epsilon (max cosine distance) for face clustering.
    Lower values produce tighter, more homogeneous clusters."""

    # --- Quality filtering ---
    min_face_size_pixels: int = 0
    """Minimum face size in pixels. The longest side of the detected bounding box (width or height)
    must be strictly greater than this value. Set to ``0`` to disable (default)."""

    blur_threshold: float = 0.5
    """Laplacian variance threshold for blur detection.
    Face crops with a variance below this value are discarded before embedding."""

    model_root: str = "/root/.deepface"
    """Root directory for DeepFace model weights.  Exposed as ``DEEPFACE_HOME`` when the service starts.
    Defaults to the library's default (``~/.deepface``) but can be overridden to point to a shared
    Docker volume if desired."""

    model_config = SettingsConfigDict(
        env_prefix="VISION_FACE_",
        # Support .env files in development but never require them in production.
        # Load project root .env first (fallback), then working directory .env (override)
        env_file=(
            Path(__file__).parent.parent / ".env",  # Project root (fallback)
            ".env",  # Current working directory (takes precedence)
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields (e.g., from Lychee's .env when running from main project)
    )

    def to_diagnostics_payload(self) -> dict[str, str]:
        """Return settings as a diagnostics-safe mapping.

        Only non-sensitive operational settings are exposed via diagnostics.
        """
        return {
            "blur_threshold": str(self.blur_threshold),
            "cluster_eps": str(self.cluster_eps),
            "detection_threshold": str(self.detection_threshold),
            "detector_backend": str(self.detector_backend),
            "match_threshold": str(self.match_threshold),
            "max_faces_per_photo": str(self.max_faces_per_photo),
            "min_face_size_pixels": str(self.min_face_size_pixels),
            "model_name": str(self.model_name),
            "rescan_iou_threshold": str(self.rescan_iou_threshold),
            "thread_pool_size": str(self.thread_pool_size),
            "verify_ssl": str(self.verify_ssl),
            "workers": str(self.workers),
        }


@lru_cache
def get_settings() -> AppSettings:
    """Return a cached ``AppSettings`` instance.

    Call this function via ``Depends(get_settings)`` in FastAPI route handlers.
    Override ``app.dependency_overrides[get_settings]`` in tests to inject
    mock settings without touching environment variables.
    """
    try:
        return AppSettings()  # ty: ignore
    except ValidationError as exc:
        _pretty_config_error(exc)
        raise SystemExit(1) from None
