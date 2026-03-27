from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform as system_platform
import re
import shutil
import subprocess
import urllib.request
import urllib.parse
from uuid import uuid4
from ctypes import wintypes


@dataclass(frozen=True, slots=True)
class RuntimeSourceLayout:
    source_root: Path
    source_kind: str
    executable_relative_path: Path


@dataclass(slots=True)
class ManagedBrowserRuntime:
    APP_PRIVATE_ENV = "C5_APP_PRIVATE_DIR"
    EXPLICIT_EXECUTABLE_ENV = "C5_EDGE_RUNTIME_EXECUTABLE"
    AUTO_DOWNLOAD_ENV = "C5_EDGE_AUTO_DOWNLOAD"
    MANIFEST_FILENAME = ".managed-runtime.json"
    EDGE_ENTERPRISE_RELEASES_URL = "https://edgeupdates.microsoft.com/api/products?view=enterprise"
    DEFAULT_PRODUCT_TAG = "appguid={56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}&appname=Microsoft Edge&needsadmin=True"
    EMBEDDED_INSTALLER_BINARY_NAME = "MicrosoftEdgeInstaller"
    MSI_ERROR_MORE_DATA = 234
    MSI_ERROR_NO_MORE_ITEMS = 259
    MSI_READONLY_OPEN_MODE = "0"

    app_private_dir: Path
    runtime_root: Path
    session_root: Path
    bundle_root: Path

    @classmethod
    def from_environment(cls, *, default_root: Path | None = None) -> "ManagedBrowserRuntime":
        configured_root = os.environ.get(cls.APP_PRIVATE_ENV)
        if configured_root:
            return cls.from_app_private_dir(Path(configured_root))
        if default_root is None:
            default_root = Path("data/app-private")
        return cls.from_app_private_dir(default_root)

    @classmethod
    def from_app_private_dir(cls, app_private_dir: Path) -> "ManagedBrowserRuntime":
        root = Path(app_private_dir)
        layout = cls(
            app_private_dir=root,
            runtime_root=root / "browser-runtime",
            session_root=root / "browser-sessions",
            bundle_root=root / "account-session-bundles",
        )
        layout.ensure_directories()
        return layout

    @property
    def manifest_path(self) -> Path:
        return self.runtime_root / self.MANIFEST_FILENAME

    def ensure_directories(self) -> None:
        self.app_private_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.session_root.mkdir(parents=True, exist_ok=True)
        self.bundle_root.mkdir(parents=True, exist_ok=True)

    def load_manifest(self) -> dict[str, object] | None:
        if not self.manifest_path.exists():
            return None
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def resolve_browser_executable(self, *, allow_auto_download: bool = True) -> Path:
        for candidate in self._candidate_executables():
            if candidate.exists():
                return candidate
        if allow_auto_download and self._is_auto_download_enabled():
            return self.download_latest()
        raise RuntimeError("未找到 Microsoft Edge 可执行文件")

    def install_from(
        self,
        source_path: Path,
        *,
        force_reset: bool = False,
        source_metadata: dict[str, object] | None = None,
    ) -> Path:
        current_executable = self._managed_runtime_executable()
        if current_executable is not None and not force_reset:
            return current_executable

        source_layout = self._resolve_source_layout(Path(source_path))
        staging_root = self.app_private_dir / f".runtime-staging-{uuid4().hex}"
        self._remove_path(staging_root)

        try:
            self._copy_runtime_to_staging(source_layout, staging_root)
            self._write_manifest(
                staging_root,
                source_layout=source_layout,
                source_metadata=source_metadata,
            )
            self._replace_runtime_root(staging_root)
            return self.runtime_root / source_layout.executable_relative_path
        finally:
            self._remove_path(staging_root)

    def download_latest(
        self,
        *,
        channel: str = "Stable",
        platform: str = "Windows",
        architecture: str | None = None,
        force_reset: bool = False,
        fetch_json=None,
        download_file=None,
        hash_file=None,
        extract_embedded_installer=None,
        run_installer=None,
        query_msi_value=None,
    ) -> Path:
        current_executable = self._managed_runtime_executable()
        if current_executable is not None and not force_reset:
            return current_executable

        existing_install_scope, existing_installed_executable = self._locate_preinstalled_msedge()
        if existing_installed_executable is not None:
            return self.install_from(
                existing_installed_executable,
                force_reset=True,
                source_metadata={
                    "source_kind": "existing-install",
                    "install_scope": existing_install_scope,
                    "installed_executable_path": str(existing_installed_executable),
                },
            )

        architecture = architecture or self._default_architecture()
        fetch_json = fetch_json or self._fetch_json
        download_file = download_file or self._download_file
        hash_file = hash_file or self._hash_file
        extract_embedded_installer = extract_embedded_installer or self._extract_embedded_installer
        run_installer = run_installer or self._run_embedded_installer
        query_msi_value = query_msi_value or self._query_msi_value

        releases = fetch_json(self.EDGE_ENTERPRISE_RELEASES_URL)
        release, artifact = self._select_latest_release(
            releases,
            channel=channel,
            platform=platform,
            architecture=architecture,
        )
        artifact_url = str(artifact.get("Location") or "").strip()
        if not artifact_url:
            raise RuntimeError("Edge 发布信息缺少下载地址")

        download_dir = self.app_private_dir / ".runtime-downloads" / uuid4().hex
        installer_dir = self.app_private_dir / ".runtime-installer" / uuid4().hex
        artifact_name = Path(artifact_url).name or "MicrosoftEdgeEnterprise.msi"
        artifact_path = download_dir / artifact_name

        self._remove_path(download_dir)
        self._remove_path(installer_dir)
        try:
            download_dir.mkdir(parents=True, exist_ok=True)
            download_file(artifact_url, artifact_path)
            expected_hash = str(artifact.get("Hash") or "").strip()
            hash_algorithm = str(artifact.get("HashAlgorithm") or "SHA256")
            if expected_hash:
                actual_hash = str(hash_file(artifact_path, hash_algorithm))
                if actual_hash.upper() != expected_hash.upper():
                    raise RuntimeError("下载的 Edge runtime 哈希校验失败")

            installer_dir.mkdir(parents=True, exist_ok=True)
            installer_path = extract_embedded_installer(artifact_path, installer_dir)
            product_tag = self._resolve_product_tag(
                artifact_path,
                channel=channel,
                query_msi_value=query_msi_value,
            )
            msi_product_id = self._query_msi_property(
                artifact_path,
                "ProductCode",
                query_msi_value=query_msi_value,
            )
            allow_downgrade = self._query_msi_property_bool(
                artifact_path,
                "AllowDowngradeSubstitution",
                default=False,
                query_msi_value=query_msi_value,
            )
            do_not_create_desktop_shortcut = self._query_msi_property_bool(
                artifact_path,
                "DONOTCREATEDESKTOPSHORTCUT",
                default=False,
                query_msi_value=query_msi_value,
            )
            do_not_create_taskbar_shortcut = self._query_msi_property_bool(
                artifact_path,
                "DONOTCREATETASKBARSHORTCUT",
                default=False,
                query_msi_value=query_msi_value,
            )

            install_errors: list[str] = []
            for install_scope in ("user", "system"):
                scoped_tag = self._with_needs_admin(
                    product_tag,
                    needs_admin=install_scope == "system",
                )
                log_path = self._default_updater_log_path(scope=install_scope)
                appargs = self._build_installer_appargs(
                    scoped_tag,
                    system_level=install_scope == "system",
                    msi_product_id=msi_product_id,
                    allow_downgrade=allow_downgrade,
                    do_not_create_desktop_shortcut=do_not_create_desktop_shortcut,
                    do_not_create_taskbar_shortcut=do_not_create_taskbar_shortcut,
                )
                try:
                    run_installer(
                        installer_path,
                        tag=scoped_tag,
                        appargs=appargs,
                        install_source="enterprisemsi",
                        log_path=log_path,
                    )
                except RuntimeError as exc:
                    install_errors.append(f"{install_scope}: {exc}")
                    continue

                installed_executable = self._locate_installed_msedge(scope=install_scope)
                if installed_executable is None:
                    install_errors.append(
                        f"{install_scope}: 安装完成但未找到 msedge.exe; log_path={log_path}"
                    )
                    continue

                metadata = {
                    "source_kind": "downloaded-msi",
                    "channel": channel,
                    "platform": platform,
                    "architecture": architecture,
                    "release_id": release.get("ReleaseId"),
                    "product_version": release.get("ProductVersion"),
                    "artifact_url": artifact_url,
                    "artifact_hash": expected_hash,
                    "artifact_hash_algorithm": hash_algorithm,
                    "install_scope": install_scope,
                    "updater_log_path": str(log_path),
                    "installed_executable_path": str(installed_executable),
                }
                return self.install_from(
                    installed_executable,
                    force_reset=True,
                    source_metadata=metadata,
                )

            raise RuntimeError(
                "Edge runtime 安装失败: "
                + " || ".join(install_errors or ["未产生可用的安装结果"])
            )
        finally:
            self._remove_path(download_dir)
            self._remove_path(installer_dir)

    def _candidate_executables(self) -> list[Path]:
        candidates: list[Path] = []

        explicit_candidate = str(os.environ.get(self.EXPLICIT_EXECUTABLE_ENV, "") or "").strip()
        if explicit_candidate:
            candidates.append(Path(explicit_candidate))

        managed_candidate = self._managed_runtime_executable()
        if managed_candidate is not None:
            candidates.append(managed_candidate)

        edge_binary = str(os.environ.get("EDGE_BINARY", "") or "").strip()
        if edge_binary:
            candidates.append(Path(edge_binary))

        for which_name in ("msedge.exe", "msedge"):
            resolved = shutil.which(which_name)
            if resolved:
                candidates.append(Path(resolved))

        candidates.extend(self._installed_executable_candidates())

        unique_candidates: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized = str(candidate)
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_candidates.append(candidate)
        return unique_candidates

    def _managed_runtime_executable(self) -> Path | None:
        manifest = self.load_manifest()
        if manifest:
            relative_path = str(manifest.get("executable_relative_path") or "").strip()
            if relative_path:
                candidate = self.runtime_root / Path(relative_path)
                if candidate.exists():
                    return candidate

        for relative_path in (
            Path("Application") / "msedge.exe",
            Path("msedge.exe"),
            Path("Edge") / "Application" / "msedge.exe",
        ):
            candidate = self.runtime_root / relative_path
            if candidate.exists():
                return candidate
        return None

    def _resolve_source_layout(self, source_path: Path) -> RuntimeSourceLayout:
        if source_path.is_file():
            if source_path.name.lower() != "msedge.exe":
                raise RuntimeError("runtime 来源必须是 msedge.exe 或包含它的目录")
            return RuntimeSourceLayout(
                source_root=source_path.parent,
                source_kind="executable",
                executable_relative_path=Path("Application") / "msedge.exe",
            )

        if source_path.is_dir():
            executable_in_dir = source_path / "msedge.exe"
            if executable_in_dir.exists():
                return RuntimeSourceLayout(
                    source_root=source_path,
                    source_kind="application-dir",
                    executable_relative_path=Path("Application") / "msedge.exe",
                )

            executable_in_application = source_path / "Application" / "msedge.exe"
            if executable_in_application.exists():
                return RuntimeSourceLayout(
                    source_root=source_path,
                    source_kind="runtime-dir",
                    executable_relative_path=Path("Application") / "msedge.exe",
                )

        raise RuntimeError("未找到可导入的 Edge runtime，来源必须包含 msedge.exe")

    def _copy_runtime_to_staging(self, source_layout: RuntimeSourceLayout, staging_root: Path) -> None:
        staging_root.mkdir(parents=True, exist_ok=True)
        if source_layout.source_kind in {"executable", "application-dir"}:
            self._copytree(source_layout.source_root, staging_root / "Application")
            return
        self._copytree(source_layout.source_root, staging_root)

    def _write_manifest(
        self,
        runtime_root: Path,
        *,
        source_layout: RuntimeSourceLayout,
        source_metadata: dict[str, object] | None = None,
    ) -> None:
        manifest = {
            "schema_version": 1,
            "prepared_at": datetime.now().isoformat(timespec="seconds"),
            "source_kind": source_layout.source_kind,
            "executable_relative_path": str(source_layout.executable_relative_path).replace("\\", "/"),
        }
        if source_metadata:
            manifest.update(source_metadata)
        runtime_root.joinpath(self.MANIFEST_FILENAME).write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _replace_runtime_root(self, staging_root: Path) -> None:
        self._remove_path(self.runtime_root)
        staging_root.replace(self.runtime_root)

    @staticmethod
    def _copytree(source: Path, destination: Path) -> None:
        shutil.copytree(source, destination, dirs_exist_ok=True)

    @staticmethod
    def _remove_path(path: Path) -> bool:
        if not path.exists():
            return False
        if path.is_dir():
            shutil.rmtree(path)
            return True
        path.unlink(missing_ok=True)
        return True

    @staticmethod
    def _default_architecture() -> str:
        machine = system_platform.machine().lower()
        if machine in {"arm64", "aarch64"}:
            return "arm64"
        return "x64"

    @staticmethod
    def _fetch_json(url: str) -> object:
        with urllib.request.urlopen(url) as response:
            return json.load(response)

    @staticmethod
    def _download_file(url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)

    @staticmethod
    def _hash_file(path: Path, algorithm: str) -> str:
        digest = hashlib.new(str(algorithm or "SHA256").lower())
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest().upper()

    @classmethod
    def _installed_executable_candidates(cls, *, scope: str | None = None) -> list[Path]:
        candidates: list[Path] = []
        normalized_scope = str(scope or "").strip().lower()

        if normalized_scope in {"", "user"}:
            local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
            if local_app_data:
                candidates.append(
                    Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                )

        if normalized_scope in {"", "system"}:
            program_files_x86 = str(os.environ.get("PROGRAMFILES(X86)", "") or "").strip()
            if program_files_x86:
                candidates.append(
                    Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                )

            program_files = str(os.environ.get("PROGRAMFILES", "") or "").strip()
            if program_files:
                candidates.append(
                    Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
                )

        return candidates

    @classmethod
    def _locate_installed_msedge(cls, *, scope: str | None = None) -> Path | None:
        for candidate in cls._installed_executable_candidates(scope=scope):
            if candidate.exists():
                return candidate
        return None

    @classmethod
    def _locate_preinstalled_msedge(cls) -> tuple[str | None, Path | None]:
        for scope in ("user", "system"):
            candidate = cls._locate_installed_msedge(scope=scope)
            if candidate is not None:
                return scope, candidate
        return None, None

    @classmethod
    def _extract_embedded_installer(
        cls,
        msi_path: Path,
        destination: Path,
        *,
        binary_name: str | None = None,
    ) -> Path:
        installer_name = str(binary_name or cls.EMBEDDED_INSTALLER_BINARY_NAME)
        destination.mkdir(parents=True, exist_ok=True)
        output_path = destination / f"{installer_name}.exe"
        cls._extract_msi_binary_stream(
            msi_path,
            stream_name=installer_name,
            destination=output_path,
        )
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("下载的 Edge runtime 未能提取出有效 installer")
        return output_path

    @staticmethod
    def _run_embedded_installer(
        installer_path: Path,
        *,
        tag: str,
        appargs: str,
        install_source: str,
        log_path: Path,
        timeout_seconds: int = 90,
    ) -> None:
        command = [
            str(installer_path),
            "/silent",
            "/install",
            str(tag),
            "/installsource",
            str(install_source),
            "/enterprise",
            "/appargs",
            str(appargs),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Edge runtime installer 执行超时，请先关闭 Edge、EdgeUpdate、WebView2 相关进程后重试: "
                f"timeout_seconds={timeout_seconds} | updater_log_path={log_path}"
            ) from exc
        if completed.returncode != 0:
            error_parts = [f"returncode={completed.returncode}", f"updater_log_path={log_path}"]
            stdout_text = str(completed.stdout or "").strip()
            stderr_text = str(completed.stderr or "").strip()
            if stdout_text:
                error_parts.append(f"stdout={stdout_text}")
            if stderr_text:
                error_parts.append(f"stderr={stderr_text}")
            raise RuntimeError(
                "Edge runtime installer 执行失败: " + " | ".join(error_parts)
            )

    @classmethod
    def _default_updater_log_path(cls, *, scope: str) -> Path:
        normalized_scope = str(scope or "").strip().lower()
        if normalized_scope == "system":
            program_files_x86 = str(os.environ.get("PROGRAMFILES(X86)", "") or "").strip()
            if program_files_x86:
                return Path(program_files_x86) / "Microsoft" / "EdgeUpdate" / "updater.log"
            program_files = str(os.environ.get("PROGRAMFILES", "") or "").strip()
            if program_files:
                return Path(program_files) / "Microsoft" / "EdgeUpdate" / "updater.log"
            windir = str(os.environ.get("WINDIR", "") or "").strip()
            if windir:
                return Path(windir) / "SystemTemp" / "updater.log"
            return Path("Windows/SystemTemp/updater.log")

        local_app_data = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
        if local_app_data:
            return Path(local_app_data) / "Microsoft" / "EdgeUpdate" / "updater.log"
        temp_dir = str(os.environ.get("TMP", "") or os.environ.get("TEMP", "") or "").strip()
        if temp_dir:
            return Path(temp_dir) / "updater.log"
        return Path("updater.log")

    @classmethod
    def _resolve_product_tag(
        cls,
        msi_path: Path,
        *,
        channel: str,
        query_msi_value,
    ) -> str:
        try:
            product_tag = str(
                query_msi_value(
                    msi_path,
                    "SELECT `Target` FROM `CustomAction` WHERE `Action`='SetProductTagProperty'",
                )
            ).strip()
            if product_tag:
                return product_tag
        except Exception:
            pass

        if str(channel).strip().lower() == "stable":
            return cls.DEFAULT_PRODUCT_TAG
        raise RuntimeError(f"未能从 Edge MSI 解析产品安装 tag: channel={channel}")

    @classmethod
    def _build_installer_appargs(
        cls,
        tag: str,
        *,
        system_level: bool,
        msi_product_id: str | None,
        allow_downgrade: bool,
        do_not_create_desktop_shortcut: bool,
        do_not_create_taskbar_shortcut: bool,
    ) -> str:
        app_guid = cls._extract_tag_value(tag, "appguid")
        if not app_guid:
            raise RuntimeError("Edge installer tag 缺少 appguid，无法构造安装参数")
        installer_data = {
            "distribution": {
                "msi": True,
                "system_level": bool(system_level),
                "verbose_logging": True,
                "msi_product_id": str(msi_product_id or ""),
                "allow_downgrade": bool(allow_downgrade),
                "do_not_create_desktop_shortcut": bool(do_not_create_desktop_shortcut),
                "do_not_create_taskbar_shortcut": bool(do_not_create_taskbar_shortcut),
            }
        }
        encoded_installer_data = urllib.parse.quote(
            json.dumps(installer_data, separators=(",", ":")),
            safe="",
        )
        return f"appguid={app_guid}&installerdata={encoded_installer_data}"

    @classmethod
    def _query_msi_property(
        cls,
        msi_path: Path,
        property_name: str,
        *,
        query_msi_value,
        default: str | None = None,
    ) -> str | None:
        escaped_property_name = str(property_name).replace("'", "''")
        query = (
            "SELECT `Value` FROM `Property` "
            f"WHERE `Property`='{escaped_property_name}'"
        )
        try:
            return str(query_msi_value(msi_path, query)).strip()
        except Exception:
            return default

    @classmethod
    def _query_msi_property_bool(
        cls,
        msi_path: Path,
        property_name: str,
        *,
        default: bool,
        query_msi_value,
    ) -> bool:
        value = cls._query_msi_property(
            msi_path,
            property_name,
            query_msi_value=query_msi_value,
            default=str(default).lower(),
        )
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    @classmethod
    def _with_needs_admin(cls, product_tag: str, *, needs_admin: bool) -> str:
        replacement = f"needsadmin={'True' if needs_admin else 'False'}"
        if re.search(r"(?i)(^|&)needsadmin=(true|false)", product_tag):
            return re.sub(
                r"(?i)(^|&)needsadmin=(true|false)",
                lambda match: f"{match.group(1)}{replacement}",
                product_tag,
                count=1,
            )
        if not product_tag:
            return replacement
        return f"{product_tag}&{replacement}"

    @staticmethod
    def _extract_tag_value(product_tag: str, key: str) -> str | None:
        match = re.search(
            rf"(?i)(?:^|&){re.escape(key)}=([^&]+)",
            str(product_tag or ""),
        )
        if match:
            return match.group(1)
        return None

    @classmethod
    def _query_msi_value(cls, msi_path: Path, query: str, *, field_index: int = 1) -> str:
        db_handle, view_handle, record_handle = cls._open_msi_query(msi_path, query)
        try:
            return cls._msi_record_get_string(record_handle, field_index)
        finally:
            cls._close_msi_handles(record_handle, view_handle, db_handle)

    @classmethod
    def _extract_msi_binary_stream(
        cls,
        msi_path: Path,
        *,
        stream_name: str,
        destination: Path,
    ) -> Path:
        escaped_stream_name = str(stream_name).replace("'", "''")
        query = f"SELECT `Data` FROM `Binary` WHERE `Name`='{escaped_stream_name}'"
        db_handle, view_handle, record_handle = cls._open_msi_query(msi_path, query)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("wb") as handle:
                while True:
                    chunk_size = ctypes.c_uint(64 * 1024)
                    chunk = ctypes.create_string_buffer(chunk_size.value)
                    cls._ensure_msi_success(
                        cls._msi_dll().MsiRecordReadStream(
                            record_handle,
                            1,
                            chunk,
                            ctypes.byref(chunk_size),
                        ),
                        action=f"读取 MSI Binary 流失败: name={stream_name}",
                    )
                    if chunk_size.value == 0:
                        break
                    handle.write(chunk.raw[: chunk_size.value])
            return destination
        finally:
            cls._close_msi_handles(record_handle, view_handle, db_handle)

    @classmethod
    def _open_msi_query(cls, msi_path: Path, query: str) -> tuple[wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE]:
        database_handle = wintypes.HANDLE()
        view_handle = wintypes.HANDLE()
        record_handle = wintypes.HANDLE()
        msi_dll = cls._msi_dll()

        cls._ensure_msi_success(
            msi_dll.MsiOpenDatabaseW(
                str(msi_path),
                cls.MSI_READONLY_OPEN_MODE,
                ctypes.byref(database_handle),
            ),
            action=f"打开 MSI 数据库失败: {msi_path}",
        )
        try:
            cls._ensure_msi_success(
                msi_dll.MsiDatabaseOpenViewW(
                    database_handle,
                    str(query),
                    ctypes.byref(view_handle),
                ),
                action=f"打开 MSI 查询失败: {query}",
            )
            cls._ensure_msi_success(
                msi_dll.MsiViewExecute(view_handle, 0),
                action=f"执行 MSI 查询失败: {query}",
            )
            fetch_result = msi_dll.MsiViewFetch(view_handle, ctypes.byref(record_handle))
            if fetch_result == cls.MSI_ERROR_NO_MORE_ITEMS:
                raise RuntimeError(f"MSI 查询无结果: {query}")
            cls._ensure_msi_success(fetch_result, action=f"读取 MSI 查询结果失败: {query}")
            return database_handle, view_handle, record_handle
        except Exception:
            cls._close_msi_handles(record_handle, view_handle, database_handle)
            raise

    @classmethod
    def _msi_record_get_string(cls, record_handle: wintypes.HANDLE, field_index: int) -> str:
        msi_dll = cls._msi_dll()
        buffer_length = ctypes.c_uint(0)
        result = msi_dll.MsiRecordGetStringW(
            record_handle,
            field_index,
            None,
            ctypes.byref(buffer_length),
        )
        if result not in {0, cls.MSI_ERROR_MORE_DATA}:
            cls._ensure_msi_success(result, action="读取 MSI 文本字段长度失败")
        capacity = max(buffer_length.value + 1, 256)
        while True:
            buffer = ctypes.create_unicode_buffer(capacity)
            length = ctypes.c_uint(capacity)
            result = msi_dll.MsiRecordGetStringW(
                record_handle,
                field_index,
                buffer,
                ctypes.byref(length),
            )
            if result == cls.MSI_ERROR_MORE_DATA:
                capacity = max(capacity * 2, length.value + 1)
                continue
            cls._ensure_msi_success(result, action="读取 MSI 文本字段失败")
            return buffer.value

    @classmethod
    def _ensure_msi_success(cls, result_code: int, *, action: str) -> None:
        if int(result_code) != 0:
            raise RuntimeError(f"{action}: returncode={result_code}")

    @staticmethod
    def _close_msi_handles(*handles: wintypes.HANDLE) -> None:
        close_handle = ManagedBrowserRuntime._msi_dll().MsiCloseHandle
        for handle in handles:
            if handle and getattr(handle, "value", None):
                close_handle(handle)

    @staticmethod
    def _msi_dll():
        msi_dll = ctypes.WinDLL("msi")
        msi_dll.MsiOpenDatabaseW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        msi_dll.MsiOpenDatabaseW.restype = wintypes.UINT
        msi_dll.MsiDatabaseOpenViewW.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCWSTR,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        msi_dll.MsiDatabaseOpenViewW.restype = wintypes.UINT
        msi_dll.MsiViewExecute.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        msi_dll.MsiViewExecute.restype = wintypes.UINT
        msi_dll.MsiViewFetch.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE)]
        msi_dll.MsiViewFetch.restype = wintypes.UINT
        msi_dll.MsiRecordGetStringW.argtypes = [
            wintypes.HANDLE,
            ctypes.c_uint,
            wintypes.LPWSTR,
            ctypes.POINTER(ctypes.c_uint),
        ]
        msi_dll.MsiRecordGetStringW.restype = wintypes.UINT
        msi_dll.MsiRecordReadStream.argtypes = [
            wintypes.HANDLE,
            ctypes.c_uint,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_uint),
        ]
        msi_dll.MsiRecordReadStream.restype = wintypes.UINT
        msi_dll.MsiCloseHandle.argtypes = [wintypes.HANDLE]
        msi_dll.MsiCloseHandle.restype = wintypes.UINT
        return msi_dll

    @staticmethod
    def _select_latest_release(
        releases_payload: object,
        *,
        channel: str,
        platform: str,
        architecture: str,
    ) -> tuple[dict[str, object], dict[str, object]]:
        for product in releases_payload or []:
            if str(product.get("Product") or "") != channel:
                continue
            candidate_releases = [
                release
                for release in (product.get("Releases") or [])
                if str(release.get("Platform") or "") == platform
                and str(release.get("Architecture") or "") == architecture
            ]
            candidate_releases.sort(
                key=lambda item: str(item.get("PublishedTime") or ""),
                reverse=True,
            )
            for release in candidate_releases:
                for artifact in release.get("Artifacts") or []:
                    if str(artifact.get("ArtifactName") or "").lower() == "msi":
                        return release, artifact
        raise RuntimeError("未找到匹配的 Edge 企业版下载发布")

    @staticmethod
    def _locate_extracted_msedge(extract_root: Path) -> Path:
        candidates = sorted(
            extract_root.rglob("msedge.exe"),
            key=lambda item: (len(item.parts), str(item)),
        )
        if not candidates:
            raise RuntimeError("下载的 Edge runtime 解包后未找到 msedge.exe")
        return candidates[0]

    @classmethod
    def _is_auto_download_enabled(cls) -> bool:
        value = str(os.environ.get(cls.AUTO_DOWNLOAD_ENV, "") or "").strip().lower()
        return value in {"1", "true", "yes", "on"}
