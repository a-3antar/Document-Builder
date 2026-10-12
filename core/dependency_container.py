"""Minimal lazy dependency container (explicit DI, no globals)."""
from __future__ import annotations

from typing import Any, Callable, TypeVar

T = TypeVar("T")


class Container:
    """Register factories; instances are created once on first use."""

    def __init__(self) -> None:
        self._factories: dict[type, Callable[[], Any]] = {}
        self._instances: dict[type, Any] = {}

    def register(self, key: type[T], factory: Callable[[], T]) -> None:
        self._factories[key] = factory
        self._instances.pop(key, None)

    def resolve(self, key: type[T]) -> T:
        if key not in self._instances:
            if key not in self._factories:
                raise KeyError(f"No registration for {key.__name__}")
            self._instances[key] = self._factories[key]()
        return self._instances[key]
