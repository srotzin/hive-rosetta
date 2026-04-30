"""
Structured errors with stable codes.
Mirrors rosetta-node/src/errors.js exactly.

Adding codes is non-breaking; renaming or renumbering existing codes is
breaking — never do it.
"""
from __future__ import annotations

from types import MappingProxyType
from typing import Any


# Frozen dict of error codes — mirrors Node's Object.freeze({...}).
ErrorCode = MappingProxyType({
    # protocol shape
    "ERR_INVALID_VERSION": "ERR_INVALID_VERSION",
    "ERR_MISSING_HEADER": "ERR_MISSING_HEADER",
    "ERR_MALFORMED_HEADER": "ERR_MALFORMED_HEADER",

    # chains & networks
    "ERR_UNSUPPORTED_NETWORK": "ERR_UNSUPPORTED_NETWORK",
    "ERR_UNSUPPORTED_ASSET": "ERR_UNSUPPORTED_ASSET",
    "ERR_INVALID_RECIPIENT": "ERR_INVALID_RECIPIENT",

    # schemes
    "ERR_AMOUNT_MISMATCH": "ERR_AMOUNT_MISMATCH",
    "ERR_VALIDBEFORE_TOO_LOW": "ERR_VALIDBEFORE_TOO_LOW",

    # signing
    "ERR_SIGNER_FAILED": "ERR_SIGNER_FAILED",
    "ERR_INVALID_PRIVATE_KEY": "ERR_INVALID_PRIVATE_KEY",

    # facilitator
    "ERR_FACILITATOR_UNREACHABLE": "ERR_FACILITATOR_UNREACHABLE",
    "ERR_FACILITATOR_REJECTED": "ERR_FACILITATOR_REJECTED",

    # negotiation
    "ERR_NO_ACCEPTABLE_PAYMENT": "ERR_NO_ACCEPTABLE_PAYMENT",
})


class RosettaError(Exception):
    """Structured error with a stable code, optional context, and remediation hint.

    The message is prefixed with ``[code]`` so that stack traces and log lines
    identify which condition fired without needing to inspect ``.code``.
    """

    def __init__(
        self,
        code: str,
        message: str,
        context: dict[str, Any] | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(f"[{code}] {message}")
        self.name = "RosettaError"
        self.code = code
        self.context: dict[str, Any] = context if context is not None else {}
        if remediation is not None:
            self.remediation: str | None = remediation
        else:
            self.remediation = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict matching Node's toJSON() shape."""
        d: dict[str, Any] = {
            "code": self.code,
            "message": str(self),
            "context": self.context,
        }
        if self.remediation:
            d["remediation"] = self.remediation
        return d

    # Alias for API symmetry with Node's toJSON
    def toJSON(self) -> dict[str, Any]:  # noqa: N802
        return self.to_dict()
