"""Needs the NPU and a running OVMS with both MIRA models (Start-MIRA.ps1 or scripts\\start-ovms.ps1).

    pytest -m hardware tests/hardware
"""
import os
from pathlib import Path

import pytest

from mira.check import run_check
from mira.config import get_settings

pytestmark = pytest.mark.hardware


def test_models_on_npu_answer_with_sources_and_say_dont_know():
    models = Path(os.environ.get("MIRA_MODELS", "models"))
    assert models.is_dir(), f"OVMS model folder not found: {models} (set MIRA_MODELS)"
    report = run_check(get_settings(), models)
    failed = [f"{s['step']}: {s['detail']}" for s in report["steps"] if not s["ok"]]
    assert report["ok"], failed
    assert {s["device"] for s in report["steps"] if s["step"] in ("LLM model", "embedding model")} == {"NPU"}
