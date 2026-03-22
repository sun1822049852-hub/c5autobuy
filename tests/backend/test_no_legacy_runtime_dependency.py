from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MODULE_NAME = "auto" "buy"
LEGACY_GATEWAY_FILES = [
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_purchase_gateway.py",
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_inventory_refresh_gateway.py",
]
CODE_SCAN_TARGETS = [
    PROJECT_ROOT / "app_backend",
    PROJECT_ROOT / "run_app.py",
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


def test_runtime_code_has_no_direct_legacy_module_reference():
    current_file = Path(__file__).resolve()
    referenced_files = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in _iter_python_files()
        if path != current_file
        if FORBIDDEN_MODULE_NAME in path.read_text(encoding="utf-8")
    ]

    assert referenced_files == []


def test_pyui_directory_is_removed():
    assert not (PROJECT_ROOT / "app_frontend").exists()


def test_packaging_has_no_pyui_dependency():
    content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "PySide6" not in content
    assert "app_frontend*" not in content
