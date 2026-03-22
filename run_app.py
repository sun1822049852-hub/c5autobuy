from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
DESKTOP_LAUNCHER = PROJECT_ROOT / "main_ui_account_center_desktop.js"


def resolve_node_executable() -> str | None:
    return shutil.which("node")


def launch_desktop(
    node_executable: str,
    launcher_path: Path | None = None,
) -> int:
    launcher = launcher_path or DESKTOP_LAUNCHER
    completed = subprocess.run(
        [node_executable, str(launcher)],
        check=False,
        cwd=str(PROJECT_ROOT),
    )
    return int(completed.returncode)


def main() -> int:
    if not DESKTOP_LAUNCHER.exists():
        sys.stderr.write(
            "未找到桌面启动脚本 main_ui_account_center_desktop.js。\n",
        )
        return 1

    node_executable = resolve_node_executable()
    if not node_executable:
        sys.stderr.write(
            "未找到 Node.js，请先安装 Node.js 或直接使用 node main_ui_account_center_desktop.js。\n",
        )
        return 1

    return launch_desktop(node_executable)


if __name__ == "__main__":
    raise SystemExit(main())
