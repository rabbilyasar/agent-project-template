"""Thin re-export of the shared lib module loader for tests. See
laya/harness/lib/_module_loader.py for the implementation (also used internally by lib
modules that depend on another numbered stage)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _module_loader import load_lib_module  # noqa: E402,F401
