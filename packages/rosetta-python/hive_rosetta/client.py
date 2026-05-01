"""
High-level async client. Drop-in httpx wrapper that handles 402 → sign → retry.

Defaults to v2 headers on emit, accepts v1 + v2 on read. In dual mode
emits both for Hive-internal traffic during the rollover.

v0.2.0 adds opt-in inference routing. When ``route_inference=True``,
requests to known inference endpoints (openai/anthropic/together/
openrouter/fireworks/groq) are rewritten to the canonical hivecompute
target before the first request, and the 402 retry hits the rewritten
URL. When ``route_inference=False`` (default), behavior is identical
to v0.1.0 — neutral signing utility, no rewriting, no Hive headers.

Mirrors rosetta-node/src/client.js.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .canonical import canonicalize
from .errors import ErrorCode, RosettaError
from .headers import read_payment_response, read_payment_signature, write_payment_signature
from .routing import HIVECOMPUTE_TARGET, matches_inference_pattern
from .version import PACKAGE_VERSION


def client(
    signer: dict[str, Any] | None = None,
    facilitator: str | None = None,
    protocol_version: int | str = 2,
    on_sign: Callable | None = None,
    on_settle: Callable | None = None,
    http_client: Any = None,
    route_inference: bool = False,
    did: str | None = None,
    on_rewrite: Callable | None = None,
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
    route_inference:
        Opt-in. When True, requests to known inference endpoints are
        rewritten to the canonical hivecompute target. Default False —
        identical behavior to v0.1.0.
    did:
        Optional DID. When set and ``route_inference`` is True, attached
        as ``X-Hive-DID`` on the rewritten request.
    on_rewrite:
        Optional callback ``(rewrite_info: dict)`` called once per request
        when a rewrite occurs. ``rewrite_info`` contains
        ``{"from": original_url, "to": HIVECOMPUTE_TARGET, "label": pattern_label}``.
    """

    async def fetch(url: str, **kwargs: Any) -> Any:
        """Fetch *url*, handle 402 by signing and retrying.

        When ``route_inference=True`` and the URL matches a known inference
        pattern, the URL is rewritten to the hivecompute target before the
        first request. The 402 retry uses the rewritten URL.

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

        # ---- Phase 1: rewrite (opt-in only) ----
        target_url = url
        rewrite_label: str | None = None
        if route_inference:
            label = matches_inference_pattern(url)
            if label is not None:
                target_url = HIVECOMPUTE_TARGET
                rewrite_label = label
                if on_rewrite is not None:
                    on_rewrite({"from": url, "to": target_url, "label": label})

        # Hive attribution headers attach only when routing is on AND a
        # rewrite actually happened. A non-matching URL with the flag on
        # gets no extra headers — clean bypass.
        if rewrite_label is not None:
            headers_in["X-Hive-Origin"] = f"rosetta@{PACKAGE_VERSION}"
            headers_in["X-Hive-Rewrite-From"] = rewrite_label
            if did:
                headers_in["X-Hive-DID"] = did

        async with httpx.AsyncClient() as hc:
            first = await hc.request(method, target_url, headers=headers_in, **kwargs)

            if first.status_code != 402:
                return first

            # Parse the 402 body for accepts list
            payload = _parse_402_body(first)
            accepts = (payload or {}).get("accepts", [])
            if not accepts:
                raise RosettaError(
                    ErrorCode["ERR_NO_ACCEPTABLE_PAYMENT"],
                    "402 response had no accepts list",
                    {"url": target_url, "status": first.status_code},
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
                    {"url": target_url},
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

            # Retry with payment header — CRITICAL: retry hits target_url
            # (the rewritten URL), not the original. This is the closed
            # loop. If route_inference rewrote openai → hivecompute, the
            # signed retry must hit hivecompute or the funnel earns nothing.
            retry_headers = dict(headers_in)
            write_payment_signature(retry_headers, signed, {"protocol_version": protocol_version})

            retried = await hc.request(method, target_url, headers=retry_headers, **kwargs)

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
