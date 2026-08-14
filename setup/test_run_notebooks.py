from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


def load_runner() -> ModuleType:
    path = Path(__file__).with_name("run_notebooks.py")
    spec = importlib.util.spec_from_file_location("run_notebooks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_marks_default_execution_and_restores_environment() -> None:
    runner = load_runner()
    os.environ.pop(runner.RUNNER_MARKER, None)

    with runner.runner_environment(allow_writes=False):
        assert os.environ[runner.RUNNER_MARKER] == "1"

    assert runner.RUNNER_MARKER not in os.environ


def test_allow_writes_clears_and_restores_existing_marker() -> None:
    runner = load_runner()
    os.environ[runner.RUNNER_MARKER] = "parent-value"
    try:
        with runner.runner_environment(allow_writes=True):
            assert runner.RUNNER_MARKER not in os.environ
        assert os.environ[runner.RUNNER_MARKER] == "parent-value"
    finally:
        os.environ.pop(runner.RUNNER_MARKER, None)


def test_allow_writes_flag_is_opt_in() -> None:
    parser = load_runner().build_parser()

    assert parser.parse_args([]).allow_writes is False
    assert parser.parse_args(["--allow-writes"]).allow_writes is True
