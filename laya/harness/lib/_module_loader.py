"""Shared helper for loading numbered-prefix sibling modules by file path -- a filename
starting with a digit cannot be imported with a normal `import` statement. Used by lib
modules that depend on another numbered stage, and by laya/harness/tests/_load_lib.py."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent


def load_lib_module(filename: str, module_name: str | None = None):
    module_name = module_name or filename.rsplit(".", 1)[0]
    spec = importlib.util.spec_from_file_location(module_name, LIB_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # dataclasses needs the module registered before exec
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
