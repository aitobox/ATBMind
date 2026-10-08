"""Backend execution layer abstractions and implementations."""

from atbmind_core.harness.backends.protocol import (
    BackendProtocol,
    PathTraversalError,
)
from atbmind_core.harness.backends.local import LocalHostBackend
from atbmind_core.harness.backends.mock import MockBackend

__all__ = [
    "BackendProtocol",
    "PathTraversalError",
    "LocalHostBackend",
    "MockBackend",
]
