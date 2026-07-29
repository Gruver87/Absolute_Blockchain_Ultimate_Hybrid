"""Handler registry: msg_type → async handler (Step D)."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Iterable, Optional

MessageHandler = Callable[[Any, Any, Any], Awaitable[None]]
"""``(host, peer, data) -> None``."""


class HandlerRegistry:
    """Mutable registry of application message handlers.

    New wire types register here without editing the transport / message loop.
    """

    __slots__ = ("_handlers",)

    def __init__(self, handlers: Optional[Dict[str, MessageHandler]] = None) -> None:
        self._handlers: Dict[str, MessageHandler] = dict(handlers or {})

    def register(self, msg_type: str, handler: MessageHandler) -> None:
        """Register or replace a handler for ``msg_type``."""
        key = str(msg_type or "").strip()
        if not key:
            raise ValueError("msg_type must be non-empty")
        if handler is None or not callable(handler):
            raise TypeError("handler must be callable")
        self._handlers[key] = handler

    def unregister(self, msg_type: str) -> bool:
        """Remove a handler. Returns True if one was present."""
        return self._handlers.pop(str(msg_type), None) is not None

    def get(self, msg_type: str) -> Optional[MessageHandler]:
        """Lookup handler or None."""
        return self._handlers.get(str(msg_type))

    def registered_types(self) -> frozenset[str]:
        """Snapshot of registered wire types."""
        return frozenset(self._handlers)

    def extend(self, items: Iterable[tuple[str, MessageHandler]]) -> None:
        """Bulk-register ``(msg_type, handler)`` pairs."""
        for msg_type, handler in items:
            self.register(msg_type, handler)
