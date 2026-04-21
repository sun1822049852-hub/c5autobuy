from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import uuid4


class DeviceIdStore(Protocol):
    def load(self) -> str | None:
        ...

    def save(self, device_id: str) -> None:
        ...

    def load_or_create(self) -> str:
        ...


class FileDeviceIdStore:
    def __init__(self, path: Path):
        self._path = path

    def load(self) -> str | None:
        if not self._path.exists():
            return None
        value = self._path.read_text(encoding="utf-8").strip()
        return value or None

    def save(self, device_id: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(device_id, encoding="utf-8")

    def load_or_create(self) -> str:
        existing = self.load()
        if existing is not None:
            return existing
        generated = str(uuid4())
        self.save(generated)
        return generated


def build_device_id_store(
    app_name: str,
    app_data_root: Path | None = None,
) -> FileDeviceIdStore:
    root = app_data_root or Path.home() / "AppData" / "Roaming"
    return FileDeviceIdStore(root / app_name / "program_access" / "device_id.txt")
