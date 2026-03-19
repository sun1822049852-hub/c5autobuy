from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REMOVED_FILES = [
    PROJECT_ROOT / "c5_layered/presentation/gui/app.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_scan_runtime.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_query_pipeline.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/legacy_bridge.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/pipeline.py",
]


def test_autobuy_reference_file_is_retained():
    assert (PROJECT_ROOT / "autobuy.py").exists()


def test_legacy_scan_runtime_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in REMOVED_FILES
        if path.exists()
    ]

    assert remaining == []
