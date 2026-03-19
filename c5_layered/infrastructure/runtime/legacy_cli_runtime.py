from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class LegacyCliRuntime:
    """Gateway that keeps legacy CLI runnable during migration."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._legacy_cli = project_root / "autobuy.py"

    def launch_legacy_cli_blocking(self) -> int:
        if not self._legacy_cli.exists():
            raise FileNotFoundError(f"Legacy CLI not found: {self._legacy_cli}")
        return subprocess.call(
            [sys.executable, str(self._legacy_cli)],
            cwd=str(self._project_root),
        )

    def launch_legacy_cli_detached(self) -> None:
        if not self._legacy_cli.exists():
            raise FileNotFoundError(f"Legacy CLI not found: {self._legacy_cli}")

        kwargs: dict[str, object] = {"cwd": str(self._project_root)}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE

        subprocess.Popen([sys.executable, str(self._legacy_cli)], **kwargs)

