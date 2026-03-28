from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_MODULE_NAME = "auto" "buy"
LEGACY_GATEWAY_FILES = [
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_purchase_gateway.py",
    PROJECT_ROOT / "app_backend/infrastructure/purchase/runtime/legacy_inventory_refresh_gateway.py",
]
LEGACY_ATTACH_DEBUG_FILES = [
    PROJECT_ROOT / "app_backend/debug/login_e2e_watch.py",
    PROJECT_ROOT / "app_backend/debug/start_default_profile_attach_login_watch.ps1",
    PROJECT_ROOT / "调试/默认配置附着登录验真.ps1",
]
CODE_SCAN_TARGETS = [
    PROJECT_ROOT / "app_backend",
    PROJECT_ROOT / "app_frontend",
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


def test_attach_debug_helper_files_are_removed():
    remaining = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in LEGACY_ATTACH_DEBUG_FILES
        if path.exists()
    ]

    assert remaining == []


def test_project_dependencies_have_no_selenium_requirement():
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"selenium>=' not in pyproject


def test_readme_has_no_attach_debug_entrypoint():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "附着真实浏览器做登录验真" not in readme
    assert "默认配置附着登录验真.ps1" not in readme
