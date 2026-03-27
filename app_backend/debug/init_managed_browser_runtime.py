from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from app_backend.infrastructure.browser_runtime.managed_browser_runtime import ManagedBrowserRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入 Edge runtime 到受管 browser-runtime")
    runtime_source_group = parser.add_mutually_exclusive_group(required=True)
    runtime_source_group.add_argument("--source-path")
    runtime_source_group.add_argument("--download-latest", action="store_true")
    parser.add_argument("--app-private-dir")
    parser.add_argument("--channel", default="Stable")
    parser.add_argument("--architecture")
    parser.add_argument("--force", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    runtime = (
        ManagedBrowserRuntime.from_app_private_dir(Path(args.app_private_dir))
        if args.app_private_dir
        else ManagedBrowserRuntime.from_environment()
    )
    if args.download_latest:
        executable_path = runtime.download_latest(
            channel=args.channel,
            architecture=args.architecture,
            force_reset=bool(args.force),
        )
    else:
        executable_path = runtime.install_from(Path(args.source_path), force_reset=bool(args.force))
    manifest = runtime.load_manifest() or {}
    summary = {
        "runtime_root": str(runtime.runtime_root),
        "manifest_path": str(runtime.manifest_path),
        "executable_path": str(executable_path),
        "executable_relative_path": manifest.get("executable_relative_path"),
        "source_kind": manifest.get("source_kind"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

