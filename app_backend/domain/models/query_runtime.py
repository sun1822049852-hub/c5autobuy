from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class WindowState:
    in_window: bool
    next_window_start: datetime
    next_window_end: datetime
