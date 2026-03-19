from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTORED_FILES = [
    PROJECT_ROOT / "autobuy.py",
    PROJECT_ROOT / "c5_layered/bootstrap.py",
    PROJECT_ROOT / "c5_layered/presentation/gui/app.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_scan_runtime.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_query_pipeline.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/legacy_bridge.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/pipeline.py",
]


def test_legacy_scan_runtime_files_are_restored_for_reference():
    missing = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in RESTORED_FILES
        if not path.exists()
    ]

    assert missing == []
