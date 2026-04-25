from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Callable, Iterable, Mapping
import threading


STARTUP_SLICE_CORE_HOME = "core-home"
STARTUP_SLICE_RUNTIME_FULL = "runtime-full"
STARTUP_SLICE_BROWSER_ACTIONS = "browser-actions"


StartupSliceBuilder = Callable[[], Mapping[str, object]]

_MISSING = object()


@dataclass
class _SliceState:
    name: str
    builder: StartupSliceBuilder
    depends_on: tuple[str, ...] = ()
    lock: threading.Lock = field(default_factory=threading.Lock)
    built: bool = False
    services: dict[str, object] = field(default_factory=dict)


class StartupSliceRegistry:
    """Lazy startup slice registry with per-slice lock/once semantics."""

    def __init__(self) -> None:
        self._slices: dict[str, _SliceState] = {}
        self._services: dict[str, object] = {}
        self._services_lock = threading.Lock()

    def register_slice(
        self,
        name: str,
        builder: StartupSliceBuilder,
        *,
        depends_on: Iterable[str] = (),
    ) -> None:
        if name in self._slices:
            raise ValueError(f"slice already registered: {name}")
        self._slices[name] = _SliceState(
            name=name,
            builder=builder,
            depends_on=tuple(depends_on),
        )

    def ensure_slice(self, name: str) -> Mapping[str, object]:
        return self._ensure_slice(name, stack=())

    def ensure_many(self, names: Iterable[str]) -> dict[str, Mapping[str, object]]:
        return {name: self.ensure_slice(name) for name in names}

    def is_built(self, name: str) -> bool:
        return self._require_slice(name).built

    def get_service(self, key: str, default: object | None = None) -> object | None:
        return self._services.get(key, default)

    def all_services(self) -> Mapping[str, object]:
        return MappingProxyType(dict(self._services))

    def slice_services(self, name: str) -> Mapping[str, object]:
        state = self._require_slice(name)
        return MappingProxyType(dict(state.services))

    def _require_slice(self, name: str) -> _SliceState:
        state = self._slices.get(name)
        if state is None:
            raise KeyError(f"slice not registered: {name}")
        return state

    def _ensure_slice(self, name: str, *, stack: tuple[str, ...]) -> Mapping[str, object]:
        if name in stack:
            chain = " -> ".join((*stack, name))
            raise RuntimeError(f"startup slice dependency cycle detected: {chain}")

        state = self._require_slice(name)
        if state.built:
            return MappingProxyType(dict(state.services))

        with state.lock:
            if state.built:
                return MappingProxyType(dict(state.services))

            next_stack = (*stack, name)
            for dep in state.depends_on:
                self._ensure_slice(dep, stack=next_stack)

            built_services = dict(state.builder() or {})
            with self._services_lock:
                for service_name, service in built_services.items():
                    existing = self._services.get(service_name, _MISSING)
                    if existing is not _MISSING and existing is not service:
                        raise RuntimeError(
                            f"service already provided by another slice: {service_name}"
                        )
                self._services.update(built_services)

            state.services = built_services
            state.built = True
            return MappingProxyType(dict(state.services))
