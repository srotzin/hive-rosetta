"""
High-level async client. Drop-in httpx wrapper that handles 402 → sign → retry.

Defaults to v2 headers on emit, accepts v1 + v2 on read. In dual mode
emits both for Hive-internal traffic during the rollover.

Mirrors rosetta-node/src/client.js.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .canonical import canonicalize
from .errors import ErrorCode, RosettaError
from .headers import read_payment_response, read_payment_signature, write_payment_signature


def client(
    signer: dict[str, Any] | None = None,
    facilitator: str | None = None,
    protocol_version: int | str = 2,
    on_sign: Callable | None = None,
    on_settle: Callable | None = None,
    http_client: Any = None,
) -> dict[str, Any]:
    """Create a rosetta client dict with async fetch and preview methods.

    Parameters
    ----------
    signer:
        An eip3009_signer dict (must have a callable ``sign`` coroutine).
    facilitator:
        Facilitator URL for settlement (unused in the basic retry flow).
    protocol_version:
        1, 2, or 'both'. Controls which header name is emitted on retry.
    on_sign:
        Optional async callback called with the signed payload before retry.
    on_settle:
        Optional async callback called with settlement result.
    http_client:
        Optional httpx.AsyncClient instance. If None, a fresh client is
        created per request (simple, good enough for v0.1).
    """

    async def fetch(url: str, **kwargs: Any) -> Any:
        """Fetch *url*, handle 402 by signing and retrying.

        Keyword args are forwarded to httpx.AsyncClient.request. The
        ``method`` kwarg defaults to 'GET'; ``headers`` may be a dict.
        """
        try:
            import httpx
        except ImportError as exc:
            raise RosettaError(
                ErrorCode["ERR_FACILITATOR_UNREACHABLE"],
                "httpx is required for client.fetch — pip install httpx",
            ) from exc

        method = kwargs.pop("method", "GET")
        headers_in: dict = dict(kwargs.pop("headers", {}))

        async with httpx.AsyncClient() as hc:
            first = await hc.request(method, url, headers=headers_in, **kwargs)

            if first.status_code != 402:
                return first

            # Parse the 402 body for accepts list
            payload = _parse_402_body(first)
            accepts = (payload or {}).get("accepts", [])
            if not accepts:
                raise RosettaError(
                    ErrorCode["ERR_NO_ACCEPTABLE_PAYMENT"],
                    "402 response had no accepts list",
                    {"url": url, "status": first.status_code},
                )

            # v0.1 negotiation: first 'exact' entry
            choice = next((a for a in accepts if a.get("scheme") == "exact"), None)
            if choice is None:
                raise RosettaError(
                    ErrorCode["ERR_NO_ACCEPTABLE_PAYMENT"],
                    "No 'exact' scheme in 402 accepts (v0.1 supports exact only)",
                    {"schemes": [a.get("scheme") for a in accepts]},
                )

            if signer is None:
                raise RosettaError(
                    ErrorCode["ERR_SIGNER_FAILED"],
                    "Got 402 but no signer configured on client",
                    {"url": url},
                )

            amount = choice.get("maxAmountRequired") or choice.get("amount")
            signed = await signer["sign"](
                network=choice["network"],
                asset=choice["asset"],
                amount=amount,
                recipient=choice.get("payTo") or choice.get("recipient"),
            )
            if on_sign:
                await on_sign(signed)

            # Retry with payment header
            retry_headers = dict(headers_in)
            write_payment_signature(retry_headers, signed, {"protocol_version": protocol_version})

            retried = await hc.request(method, url, headers=retry_headers, **kwargs)

            settlement = read_payment_response(dict(retried.headers))
            if settlement and on_settle:
                await on_settle(settlement)

            return retried

    async def preview(required: dict[str, Any]) -> dict[str, Any]:
        """Inspect what would be signed without signing.

        Returns dict with ``acceptable``, and if true: scheme/network/amount/canonical.
        """
        accepts = (required or {}).get("accepts", [])
        choice = next((a for a in accepts if a.get("scheme") == "exact"), None)
        if choice is None:
            return {"acceptable": False, "reason": "no exact scheme available"}
        return {
            "acceptable": True,
            "scheme": "exact",
            "network": choice.get("network"),
            "amount": choice.get("maxAmountRequired") or choice.get("amount"),
            "recipient": choice.get("payTo") or choice.get("recipient"),
            "canonical": canonicalize(choice),
        }

    return {"fetch": fetch, "preview": preview}


def _parse_402_body(response: Any) -> dict | None:
    """Try to parse the 402 response body as JSON."""
    ct = response.headers.get("content-type", "")
    try:
        if "application/json" in ct:
            return response.json()
    except Exception:
        pass
    try:
        return json.loads(response.text)
    except Exception:
        return None
