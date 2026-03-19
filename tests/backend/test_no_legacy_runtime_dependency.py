from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MODULE_NAME = "auto" "buy"
LEGACY_GATEWAY_FILES = [
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_purchase_gateway.py",
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_inventory_refresh_gateway.py",
]
LEGACY_ROOT_FILES = [
    PROJECT_ROOT / "autobuy.py",
]
LEGACY_SCAN_COMPAT_FILES = [
    PROJECT_ROOT / "c5_layered/bootstrap.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_scan_runtime.py",
    PROJECT_ROOT / "c5_layered/infrastructure/runtime/legacy_query_pipeline.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/legacy_bridge.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/pipeline.py",
]
LEGACY_QUERY_COMPAT_FILES = [
    PROJECT_ROOT / "app_backend/infrastructure/query/runtime/legacy_scanner_adapter.py",
]
LAYERED_QUERY_TRANSITION_FILES = [
    PROJECT_ROOT / "c5_layered/infrastructure/query/__init__.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/coordinator_adapter.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/group_runner.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/query_group_policy.py",
    PROJECT_ROOT / "c5_layered/infrastructure/query/scanner_factory.py",
]
CODE_SCAN_TARGETS = [
    PROJECT_ROOT / "app_backend",
    PROJECT_ROOT / "app_frontend",
    PROJECT_ROOT / "c5_layered",
    PROJECT_ROOT / "run_app.py",
    PROJECT_ROOT / "tests",
]


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for target in CODE_SCAN_TARGETS:
        if target.is_file():
            files.append(target)
            continue
        files.extend(
            path
            for path in target.rglob("*.py")
            if "__pycache__" not in path.parts
        )
    return files


def test_legacy_runtime_gateway_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LEGACY_GATEWAY_FILES
        if path.exists()
    ]

    assert remaining == []


def test_legacy_root_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LEGACY_ROOT_FILES
        if path.exists()
    ]

    assert remaining == []


def test_legacy_scan_compat_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LEGACY_SCAN_COMPAT_FILES
        if path.exists()
    ]

    assert remaining == []


def test_legacy_query_compat_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LEGACY_QUERY_COMPAT_FILES
        if path.exists()
    ]

    assert remaining == []


def test_layered_query_transition_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LAYERED_QUERY_TRANSITION_FILES
        if path.exists()
    ]

    assert remaining == []


def test_c5_layered_package_has_no_python_sources_left():
    layered_root = PROJECT_ROOT / "c5_layered"
    if not layered_root.exists():
        return

    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in layered_root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]

    assert remaining == []


def test_runtime_code_has_no_direct_legacy_module_reference():
    current_file = Path(__file__).resolve()
    referenced_files = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in _iter_python_files()
        if path != current_file
        if FORBIDDEN_MODULE_NAME in path.read_text(encoding="utf-8")
    ]

    assert referenced_files == []


def test_query_runtime_package_does_not_reexport_legacy_scanner_adapter():
    from app_backend.infrastructure.query import runtime as runtime_package

    assert not hasattr(runtime_package, "LegacyScannerAdapter")
    assert "LegacyScannerAdapter" not in getattr(runtime_package, "__all__", [])
