"""Guard tests for the real (unmocked) DeepFace installation."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_PROBE = "from deepface import DeepFace; print(DeepFace.backend_engine)"


def test_deepface_imports_and_selects_onnx_engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The installed deepface must import cleanly and pick the ONNX backend engine.

    Runs in a subprocess so the real package is imported fresh: other tests
    inject a stub ``deepface`` into ``sys.modules``, and DeepFace caches its
    engine choice at import time.  Fails if a transitive import is missing or
    if TensorFlow (which DeepFace prefers over ONNX) has been re-introduced.
    """
    monkeypatch.setenv("DEEPFACE_HOME", str(tmp_path))
    monkeypatch.delenv("DEEPFACE_BACKEND_ENGINE", raising=False)

    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "onnx"
