"""Storage domain ports (ADR 0006).

Protocols only — no engine / SQLite / keycodec / CF imports.
Domain (`core/`, `consensus/`, `sync/`) must depend on these ports, not on
native engine types or column-family labels.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from storage.types import AccountRecord, BlockRecord, TipMeta

__all__ = [
    "BlockStorePort",
    "StateStorePort",
    "MetaStorePort",
    "StorageUnitOfWorkPort",
    "StorageHealthPort",
    "StoragePort",
]


@runtime_checkable
class BlockStorePort(Protocol):
    """Canonical block body / tip reads (no CF / raw keys / WriteBatch)."""

    def tip_height(self) -> int:
        ...

    def tip_hash(self) -> str:
        ...

    def has_hash(self, block_hash: str) -> bool:
        ...

    def get_by_height(self, height: int) -> Optional[BlockRecord]:
        ...

    def get_by_hash(self, block_hash: str) -> Optional[BlockRecord]:
        ...

    def iterate_heights(self, from_height: int, to_height: int) -> Sequence[BlockRecord]:
        ...

    def reorg_truncate_above(self, height: int) -> None:
        """Drop bodies/indexes above ``height`` and rewind tip (domain passes height only)."""
        ...


@runtime_checkable
class StateStorePort(Protocol):
    """Account / state-root façade (adapter owns encoding policy)."""

    def get_account(self, address: str) -> Optional[AccountRecord]:
        ...

    def get_state_root(self) -> str:
        ...

    def get_state_root_baseline(self) -> int:
        ...


@runtime_checkable
class MetaStorePort(Protocol):
    """Non-block meta the node already persists (validators, checkpoints, …)."""

    def get_validators(self) -> Sequence[Mapping[str, Any]]:
        ...

    def get_checkpoint(self, epoch: int) -> Optional[Mapping[str, Any]]:
        ...

    def put_checkpoint(self, epoch: int, data: Mapping[str, Any]) -> None:
        ...


@runtime_checkable
class StorageUnitOfWorkPort(Protocol):
    """Single atomic block + state delta + tip commit (all-or-nothing).

    Contract::

        uow = storage.begin_block_commit(expected_parent=..., expected_tip_height=...)
        uow.write_block(block)
        uow.write_state_delta(accounts...)
        uow.set_tip(TipMeta(...))
        uow.commit()   # durable all-or-nothing
        # on failure before/at commit: abort(); domain sees StorageError subclass
    """

    def write_block(self, block: BlockRecord | Mapping[str, Any]) -> None:
        ...

    def write_transactions(self, transactions: Sequence[Mapping[str, Any]]) -> None:
        ...

    def write_state_delta(
        self,
        accounts: Sequence[AccountRecord] | Mapping[str, Mapping[str, Any]],
    ) -> None:
        ...

    def set_tip(self, tip: TipMeta) -> None:
        ...

    def commit(self) -> None:
        """Durably apply staged writes or raise a ``StorageError`` subclass."""
        ...

    def abort(self) -> None:
        """Drop staged writes; tip unchanged."""
        ...


@runtime_checkable
class StorageHealthPort(Protocol):
    """Ops / status surface (no engine internals)."""

    def ping(self) -> bool:
        ...

    def approximate_size(self) -> int:
        ...

    def last_flush_ok(self) -> bool:
        ...


@runtime_checkable
class StoragePort(Protocol):
    """Composite storage boundary used by domain services."""

    @property
    def blocks(self) -> BlockStorePort:
        ...

    @property
    def state(self) -> StateStorePort:
        ...

    @property
    def meta(self) -> MetaStorePort:
        ...

    @property
    def health(self) -> StorageHealthPort:
        ...

    def begin_block_commit(
        self,
        *,
        expected_parent: str = "",
        expected_tip_height: int = -1,
    ) -> StorageUnitOfWorkPort:
        """Start a CAS-aware unit of work for one canonical tip advance."""
        ...
