"""Typed errors for the tip-safety domain.

All failures on the tip / finality / reorg path raise a subclass of
``TipSafetyError``. Callers must treat any ``TipSafetyError`` as fail-closed:
do not apply the candidate tip, do not advance finality.
"""

from __future__ import annotations


class TipSafetyError(Exception):
    """Base class for tip-safety domain failures.

    Attributes:
        code: Stable machine-readable reason code for metrics and logs.
        message: Human-readable description (also used as ``str(exc)``).
    """

    code: str = "tip_safety_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class TipValidationError(TipSafetyError):
    """Raised when a block reference or tip state violates structural invariants.

    Examples: empty hash, non-hex digest, negative height, finalized above head.
    """

    code = "tip_validation"


class TipAncestryError(TipSafetyError):
    """Raised when parent linkage / ancestry constraints are violated.

    Examples: candidate parent hash does not match current head, unknown parent.
    """

    code = "tip_ancestry"


class TipFinalityRegressError(TipSafetyError):
    """Raised when an operation would move tip or finality below the finalized floor.

    This is the hard safety boundary for reorgs relative to finalized checkpoints.
    """

    code = "tip_finality_regress"


class TipUnknownParentError(TipAncestryError):
    """Raised when a candidate references a parent that is not the known tip head.

    Stage 1 domain does not maintain a full block DAG; unknown parents are
    rejected fail-closed rather than inferred.
    """

    code = "tip_unknown_parent"


class TipDuplicateError(TipSafetyError):
    """Raised when a candidate is identical to the current canonical tip."""

    code = "tip_duplicate"


class TipConflictError(TipSafetyError):
    """Raised when fork-choice cannot pick a single head under policy rules."""

    code = "tip_conflict"
