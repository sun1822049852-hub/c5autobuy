from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any, Callable


LOGIN_URL = "https://www.c5game.com/login?return_url=%2Fuser%2Fuser%2F"
SUCCESS_URL_PATTERN = "https://www.c5game.com/user/user/"
DEFAULT_EDGE_PROFILE_DIRECTORY = "Default"


def build_edge_launch_command(
    *,
    edge_path: str,
    port: int,
    user_data_dir: str,
    proxy_url: str | None,
    cleanup_callbacks: list[Callable[[], None]],
    profile_directory: str | None = None,
    include_default_browser_flags: bool = True,
) -> list[str]:
    command = [
        edge_path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
    ]

    if include_default_browser_flags:
        command.extend(
            [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-sync",
                "--new-window",
            ]
        )
    if profile_directory:
        command.append(f"--profile-directory={profile_directory}")

    normalized_proxy = str(proxy_url or "").strip()
    if normalized_proxy and normalized_proxy.lower() != "direct":
        plugin_path = build_proxy_plugin(normalized_proxy)
        if plugin_path is not None:
            cleanup_callbacks.append(lambda path=plugin_path: remove_temp_path(path))
            command.extend(
                [
                    f"--disable-extensions-except={plugin_path}",
                    f"--load-extension={plugin_path}",
                ]
            )
        else:
            pure_proxy = re.sub(r"https?://[^@]*@", "", normalized_proxy)
            pure_proxy = re.sub(r"^https?://", "", pure_proxy)
            command.append(f"--proxy-server={pure_proxy}")

    command.append(LOGIN_URL)
    return command


def reserve_debug_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_debugger_port(
    port: int,
    *,
    process: subprocess.Popen[Any],
    timeout_seconds: float = 15.0,
) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Edge 调试浏览器启动失败")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("等待 Edge 调试端口超时")


def build_proxy_plugin(proxy_url: str) -> str | None:
    pattern = r"^(?:https?://)?(?:(.+?):(.+?)@)?([^:]+)(?::(\d+))?$"
    stripped_proxy = proxy_url.replace("http://", "").replace("https://", "")
    match = re.match(pattern, stripped_proxy)
    if not match:
        return None

    username, password, host, port = match.groups()
    port = port or "80"
    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth",
        "permissions": [
            "proxy", "tabs", "unlimitedStorage", "storage",
            "<all_urls>", "webRequest", "webRequestBlocking"
        ],
        "background": {"scripts": ["background.js"]}
    }
    """

    if username and password:
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{host}",
                    port: parseInt({port})
                }},
                bypassList: ["localhost", "127.0.0.1", "<local>"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        function callbackFn(details) {{
            return {{
                authCredentials: {{
                    username: "{username}",
                    password: "{password}"
                }}
            }};
        }}
        chrome.webRequest.onAuthRequired.addListener(
            callbackFn, {{urls: ["<all_urls>"]}}, ["blocking"]
        );
        """
    else:
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{host}",
                    port: parseInt({port})
                }},
                bypassList: ["localhost", "127.0.0.1", "<local>"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        """

    extension_dir = tempfile.mkdtemp(prefix="proxy_auth_plugin_")
    try:
        Path(extension_dir, "manifest.json").write_text(manifest_json, encoding="utf-8")
        Path(extension_dir, "background.js").write_text(background_js, encoding="utf-8")
    except Exception:
        remove_temp_path(extension_dir)
        raise
    return extension_dir


def remove_temp_path(path: str) -> None:
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif path and os.path.exists(path):
            os.remove(path)
    except Exception:
        return


def terminate_process(process: subprocess.Popen[Any] | None) -> None:
    if process is None:
        return
    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        return
