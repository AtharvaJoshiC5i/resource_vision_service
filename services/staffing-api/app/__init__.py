"""Staffing API — make the monorepo ``rv-availability`` package importable for ``uvicorn``."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _rv_src_candidates() -> list[Path]:
    app_dir = Path(__file__).resolve().parent
    staffing_api = app_dir.parent
    repo_root = staffing_api.parent.parent
    paths: list[Path] = [
        repo_root / "packages" / "rv-availability" / "src",
        staffing_api / "packages" / "rv-availability" / "src",
    ]
    extra = os.environ.get("RV_AVAILABILITY_SRC", "").strip()
    if extra:
        paths.insert(0, Path(extra).expanduser().resolve())
    return paths


def ensure_rv_availability() -> None:
    try:
        import rv_availability  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    for src in _rv_src_candidates():
        pkg = src / "rv_availability"
        if not pkg.is_dir():
            continue
        src_s = str(src)
        if src_s not in sys.path:
            sys.path.insert(0, src_s)
        try:
            import rv_availability  # noqa: F401
            return
        except ModuleNotFoundError:
            if src_s in sys.path:
                sys.path.remove(src_s)

    hints = "\n".join(f"  - {p}" for p in _rv_src_candidates())
    raise ModuleNotFoundError(
        "No module named 'rv_availability'. The staffing API requires the "
        "packages/rv-availability library from this repo.\n"
        "Fix options:\n"
        "  1. Run uvicorn from the monorepo clone (auto path: packages/rv-availability/src).\n"
        "  2. pip install -e ../../packages/rv-availability  (from services/staffing-api).\n"
        "  3. Set RV_AVAILABILITY_SRC to the .../packages/rv-availability/src folder.\n"
        f"Checked paths:\n{hints}"
    )


ensure_rv_availability()