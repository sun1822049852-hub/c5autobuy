from __future__ import annotations

import argparse
from pathlib import Path

from c5_layered.bootstrap import build_container
from c5_layered.presentation.gui import run_gui


def main() -> int:
    parser = argparse.ArgumentParser(description="C5 分层架构入口")
    parser.add_argument(
        "--mode",
        choices=("gui", "cli"),
        default="gui",
        help="gui: 图形界面（默认）；cli: 运行旧版 CLI",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    container = build_container(project_root)

    if args.mode == "cli":
        return container.cli_runtime.launch_legacy_cli_blocking()

    run_gui(container.app.dashboard, container.app.scan, container.cli_runtime)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
