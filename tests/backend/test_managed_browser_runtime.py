from __future__ import annotations

import json
from pathlib import Path


def _write_text(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_from_app_private_dir_normalizes_relative_paths_to_absolute(tmp_path: Path, monkeypatch):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    monkeypatch.chdir(tmp_path)

    runtime = ManagedBrowserRuntime.from_app_private_dir(Path("data/app-private"))

    assert runtime.app_private_dir == tmp_path / "data" / "app-private"
    assert runtime.runtime_root == tmp_path / "data" / "app-private" / "browser-runtime"
    assert runtime.session_root == tmp_path / "data" / "app-private" / "browser-sessions"
    assert runtime.bundle_root == tmp_path / "data" / "app-private" / "account-session-bundles"


def test_resolve_browser_executable_prefers_managed_runtime_over_system_install(
    tmp_path: Path,
    monkeypatch,
):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    managed_executable = runtime.runtime_root / "Application" / "msedge.exe"
    _write_text(managed_executable)

    system_root = tmp_path / "Program Files (x86)" / "Microsoft" / "Edge" / "Application"
    _write_text(system_root / "msedge.exe")
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))

    assert runtime.resolve_browser_executable() == managed_executable


def test_resolve_browser_executable_downloads_when_auto_download_enabled(
    tmp_path: Path,
    monkeypatch,
):
    import shutil

    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    monkeypatch.setenv("C5_EDGE_AUTO_DOWNLOAD", "1")
    monkeypatch.setenv("EDGE_BINARY", "")
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def fake_download_latest(self, **kwargs):
        executable = self.runtime_root / "Application" / "msedge.exe"
        _write_text(executable, "exe")
        return executable

    monkeypatch.setattr(ManagedBrowserRuntime, "download_latest", fake_download_latest)

    assert runtime.resolve_browser_executable() == runtime.runtime_root / "Application" / "msedge.exe"


def test_install_runtime_from_executable_copies_application_and_writes_manifest(tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    source_executable = tmp_path / "Edge" / "Application" / "msedge.exe"
    _write_text(source_executable, "exe")
    _write_text(source_executable.parent / "msedge.dll", "dll")

    installed_executable = runtime.install_from(source_executable)

    assert installed_executable == runtime.runtime_root / "Application" / "msedge.exe"
    assert installed_executable.exists()
    assert (runtime.runtime_root / "Application" / "msedge.dll").exists()

    manifest = json.loads((runtime.runtime_root / ".managed-runtime.json").read_text(encoding="utf-8"))
    assert manifest["executable_relative_path"] == "Application/msedge.exe"
    assert manifest["source_kind"] == "executable"


def test_init_managed_browser_runtime_main_bootstraps_runtime(tmp_path: Path, capsys):
    from app_backend.debug.init_managed_browser_runtime import main

    source_executable = tmp_path / "Edge" / "Application" / "msedge.exe"
    _write_text(source_executable, "exe")

    exit_code = main(
        [
            "--source-path",
            str(source_executable),
            "--app-private-dir",
            str(tmp_path / "app-private"),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "app-private" / "browser-runtime" / "Application" / "msedge.exe").exists()

    stdout = capsys.readouterr().out
    assert "browser-runtime" in stdout
    assert "Application/msedge.exe" in stdout


def test_download_latest_installs_latest_enterprise_release(tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    downloaded_files: dict[str, Path] = {}

    def fake_fetch_json(_url: str):
        return [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "ReleaseId": 123,
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "146.0.3856.78",
                        "PublishedTime": "2026-03-23T20:13:00",
                        "Artifacts": [
                            {
                                "ArtifactName": "msi",
                                "Location": "https://example.test/MicrosoftEdgeEnterpriseX64.msi",
                                "Hash": "dummyhash",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    }
                ],
            }
        ]

    def fake_download_file(url: str, destination: Path) -> None:
        downloaded_files["url"] = Path(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("msi", encoding="utf-8")
        downloaded_files["destination"] = destination

    def fake_hash_file(_path: Path, _algorithm: str) -> str:
        return "dummyhash"

    def fake_extract_embedded_installer(_msi_path: Path, destination: Path) -> Path:
        installer_path = destination / "MicrosoftEdgeInstaller.exe"
        _write_text(installer_path, "installer")
        return installer_path

    installer_calls: list[dict[str, object]] = []

    def fake_run_installer(
        installer_path: Path,
        *,
        tag: str,
        appargs: str,
        install_source: str,
        log_path: Path,
    ) -> None:
        installer_calls.append(
            {
                "installer_path": installer_path,
                "tag": tag,
                "appargs": appargs,
                "install_source": install_source,
                "log_path": log_path,
            }
        )
        _write_text(
            tmp_path / "LocalAppData" / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            "exe",
        )
        _write_text(
            tmp_path / "LocalAppData" / "Microsoft" / "Edge" / "Application" / "msedge.dll",
            "dll",
        )

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))
    try:
        installed_executable = runtime.download_latest(
            fetch_json=fake_fetch_json,
            download_file=fake_download_file,
            hash_file=fake_hash_file,
            extract_embedded_installer=fake_extract_embedded_installer,
            run_installer=fake_run_installer,
            architecture="x64",
        )
    finally:
        monkeypatch.undo()

    assert installed_executable == runtime.runtime_root / "Application" / "msedge.exe"
    assert installed_executable.exists()
    assert downloaded_files["destination"].name == "MicrosoftEdgeEnterpriseX64.msi"
    assert len(installer_calls) == 1
    assert installer_calls[0]["install_source"] == "enterprisemsi"
    assert "needsadmin=False" in str(installer_calls[0]["tag"])

    manifest = json.loads(runtime.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_kind"] == "downloaded-msi"
    assert manifest["channel"] == "Stable"
    assert manifest["release_id"] == 123
    assert manifest["install_scope"] == "user"


def test_init_managed_browser_runtime_main_supports_download_latest(tmp_path: Path, capsys, monkeypatch):
    from app_backend.debug.init_managed_browser_runtime import main
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    def fake_download_latest(self, **kwargs):
        executable = self.runtime_root / "Application" / "msedge.exe"
        _write_text(executable, "exe")
        self.manifest_path.write_text(
            '{"source_kind":"downloaded-msi","executable_relative_path":"Application/msedge.exe"}',
            encoding="utf-8",
        )
        return executable

    monkeypatch.setattr(ManagedBrowserRuntime, "download_latest", fake_download_latest)

    exit_code = main(
        [
            "--download-latest",
            "--app-private-dir",
            str(tmp_path / "app-private"),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "app-private" / "browser-runtime" / "Application" / "msedge.exe").exists()

    stdout = capsys.readouterr().out
    assert "downloaded-msi" in stdout


def test_download_latest_falls_back_to_system_scope_when_user_scope_does_not_materialize(tmp_path: Path, monkeypatch):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")

    def fake_fetch_json(_url: str):
        return [
            {
                "Product": "Stable",
                "Releases": [
                    {
                        "ReleaseId": 123,
                        "Platform": "Windows",
                        "Architecture": "x64",
                        "ProductVersion": "146.0.3856.78",
                        "PublishedTime": "2026-03-23T20:13:00",
                        "Artifacts": [
                            {
                                "ArtifactName": "msi",
                                "Location": "https://example.test/MicrosoftEdgeEnterpriseX64.msi",
                                "Hash": "dummyhash",
                                "HashAlgorithm": "SHA256",
                            }
                        ],
                    }
                ],
            }
        ]

    def fake_download_file(_url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("msi", encoding="utf-8")

    def fake_hash_file(_path: Path, _algorithm: str) -> str:
        return "dummyhash"

    def fake_extract_embedded_installer(_msi_path: Path, destination: Path) -> Path:
        installer_path = destination / "MicrosoftEdgeInstaller.exe"
        _write_text(installer_path, "installer")
        return installer_path

    installer_tags: list[str] = []

    def fake_run_installer(
        _installer_path: Path,
        *,
        tag: str,
        appargs: str,
        install_source: str,
        log_path: Path,
    ) -> None:
        installer_tags.append(tag)
        if "needsadmin=True" in tag:
            _write_text(
                tmp_path / "Program Files (x86)" / "Microsoft" / "Edge" / "Application" / "msedge.exe",
                "exe",
            )
            _write_text(
                tmp_path / "Program Files (x86)" / "Microsoft" / "Edge" / "Application" / "msedge.dll",
                "dll",
            )

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))

    installed_executable = runtime.download_latest(
        fetch_json=fake_fetch_json,
        download_file=fake_download_file,
        hash_file=fake_hash_file,
        extract_embedded_installer=fake_extract_embedded_installer,
        run_installer=fake_run_installer,
        architecture="x64",
    )

    assert installed_executable == runtime.runtime_root / "Application" / "msedge.exe"
    assert installer_tags == [
        "appguid={56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}&appname=Microsoft Edge&needsadmin=False",
        "appguid={56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}&appname=Microsoft Edge&needsadmin=True",
    ]

    manifest = json.loads(runtime.manifest_path.read_text(encoding="utf-8"))
    assert manifest["install_scope"] == "system"


def test_download_latest_reuses_existing_system_edge_before_downloading(tmp_path: Path, monkeypatch):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    runtime = ManagedBrowserRuntime.from_app_private_dir(tmp_path / "app-private")
    system_edge = tmp_path / "Program Files (x86)" / "Microsoft" / "Edge" / "Application" / "msedge.exe"
    _write_text(system_edge, "exe")
    _write_text(system_edge.parent / "msedge.dll", "dll")
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "Program Files (x86)"))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))

    installed_executable = runtime.download_latest(
        fetch_json=lambda _url: (_ for _ in ()).throw(AssertionError("不应触发下载发布查询")),
        force_reset=True,
    )

    assert installed_executable == runtime.runtime_root / "Application" / "msedge.exe"
    manifest = json.loads(runtime.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_kind"] == "existing-install"
    assert manifest["install_scope"] == "system"


def test_run_embedded_installer_builds_silent_install_command(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    captured: dict[str, object] = {}

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return Completed()

    monkeypatch.setattr("subprocess.run", fake_run)

    installer_path = tmp_path / "dir with spaces" / "MicrosoftEdgeInstaller.exe"
    log_path = tmp_path / "logs" / "user install.log"
    ManagedBrowserRuntime._run_embedded_installer(
        installer_path,
        tag="appguid=test-app&appname=Microsoft Edge&needsadmin=False",
        appargs="appguid=test-app&installerdata=%7B%22distribution%22%3A%7B%22msi%22%3Atrue%2C%22system_level%22%3Afalse%2C%22verbose_logging%22%3Atrue%2C%22msi_product_id%22%3A%22test-product%22%2C%22allow_downgrade%22%3Afalse%2C%22do_not_create_desktop_shortcut%22%3Afalse%2C%22do_not_create_taskbar_shortcut%22%3Afalse%7D%7D",
        install_source="enterprisemsi",
        log_path=log_path,
    )

    assert captured["command"] == [
        str(installer_path),
        "/silent",
        "/install",
        "appguid=test-app&appname=Microsoft Edge&needsadmin=False",
        "/installsource",
        "enterprisemsi",
        "/enterprise",
        "/appargs",
        "appguid=test-app&installerdata=%7B%22distribution%22%3A%7B%22msi%22%3Atrue%2C%22system_level%22%3Afalse%2C%22verbose_logging%22%3Atrue%2C%22msi_product_id%22%3A%22test-product%22%2C%22allow_downgrade%22%3Afalse%2C%22do_not_create_desktop_shortcut%22%3Afalse%2C%22do_not_create_taskbar_shortcut%22%3Afalse%7D%7D",
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["text"] is True
    assert captured["kwargs"]["check"] is False


def test_run_embedded_installer_includes_log_path_and_output_on_failure(monkeypatch, tmp_path: Path):
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    class Completed:
        returncode = 1
        stdout = "metainstaller failed"
        stderr = "0x80040c01"

    monkeypatch.setattr("subprocess.run", lambda *_args, **_kwargs: Completed())
    log_path = tmp_path / "logs" / "installer.log"

    try:
        ManagedBrowserRuntime._run_embedded_installer(
            tmp_path / "MicrosoftEdgeInstaller.exe",
            tag="appguid=test-app&appname=Microsoft Edge&needsadmin=False",
            appargs="appguid=test-app&installerdata=%7B%7D",
            install_source="enterprisemsi",
            log_path=log_path,
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "Edge runtime installer 执行失败" in message
        assert "0x80040c01" in message
        assert "metainstaller failed" in message
        assert str(log_path) in message
    else:
        raise AssertionError("预期 _run_embedded_installer 在安装失败时抛错")


def test_run_embedded_installer_times_out_with_close_edge_guidance(monkeypatch, tmp_path: Path):
    import subprocess

    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    def fake_run(*_args, **_kwargs):
        raise subprocess.TimeoutExpired(cmd="MicrosoftEdgeInstaller.exe", timeout=90)

    monkeypatch.setattr("subprocess.run", fake_run)
    log_path = tmp_path / "logs" / "installer.log"

    try:
        ManagedBrowserRuntime._run_embedded_installer(
            tmp_path / "MicrosoftEdgeInstaller.exe",
            tag="appguid=test-app&appname=Microsoft Edge&needsadmin=False",
            appargs="appguid=test-app&installerdata=%7B%7D",
            install_source="enterprisemsi",
            log_path=log_path,
        )
    except RuntimeError as exc:
        message = str(exc)
        assert "超时" in message
        assert "关闭 Edge" in message
        assert str(log_path) in message
    else:
        raise AssertionError("预期 _run_embedded_installer 在超时时抛错")


def test_build_installer_appargs_matches_enterprise_distribution_shape():
    from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime

    appargs = ManagedBrowserRuntime._build_installer_appargs(
        "appguid=test-app&appname=Microsoft Edge&needsadmin=False",
        system_level=False,
        msi_product_id="test-product",
        allow_downgrade=False,
        do_not_create_desktop_shortcut=False,
        do_not_create_taskbar_shortcut=False,
    )

    assert appargs == (
        "appguid=test-app&installerdata=%7B%22distribution%22%3A%7B%22msi%22%3Atrue%2C%22system_level%22%3Afalse%2C"
        "%22verbose_logging%22%3Atrue%2C%22msi_product_id%22%3A%22test-product%22%2C%22allow_downgrade%22%3Afalse%2C"
        "%22do_not_create_desktop_shortcut%22%3Afalse%2C%22do_not_create_taskbar_shortcut%22%3Afalse%7D%7D"
    )

