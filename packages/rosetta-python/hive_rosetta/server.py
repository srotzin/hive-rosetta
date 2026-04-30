"""
FastAPI/Starlette middleware factory mirroring Node's Express middleware.

v0.1: FastAPI adapter only (Fastify/Hono/Next/MCP/A2A defer to v0.2 per
the narrowing doctrine).

Mirrors rosetta-node/src/server.js.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from .canonical import canonicalize
from .errors import ErrorCode, RosettaError
from .headers import read_payment_signature, write_payment_response
from .registry import assert_recipient, resolve_asset


def server(
    pay_to: str,
    network: str,
    asset: str,
    amount: str | int | Callable,
    facilitator: str,
    free_paths: list[str] | None = None,
    protocol_version: int | str = 2,
    description: str = "",
) -> dict[str, Any]:
    """Create a rosetta server middleware factory.

    Parameters
    ----------
    pay_to:
        EVM address that receives payments.
    network:
        CAIP-2 chain identifier (e.g. 'eip155:8453').
    asset:
        Asset symbol or address (e.g. 'USDC').
    amount:
        Required payment amount (atomic units). May be a callable
        ``(request) -> str|int`` for dynamic pricing.
    facilitator:
        URL of the settlement facilitator.
    free_paths:
        List of paths that bypass the payment gate.
    protocol_version:
        1, 2, or 'both'. Controls emitted header name.
    description:
        Human-readable description of what the payment is for.

    Returns a dict with a ``fastapi()`` method that returns an ASGI
    middleware callable, and a ``middleware_func`` attribute for direct
    use in Starlette/FastAPI add_middleware flows.
    """
    if not pay_to:
        raise RosettaError(ErrorCode["ERR_INVALID_RECIPIENT"], "server() requires pay_to")
    assert_recipient(pay_to)
    resolve_asset(network, asset)  # validate now, fail fast
    if not facilitator:
        raise RosettaError(
            ErrorCode["ERR_FACILITATOR_UNREACHABLE"],
            "server() requires facilitator URL",
        )

    _free_paths = free_paths or []

    def _build_payment_required(path: str, request: Any = None) -> dict[str, Any]:
        dynamic_amount = amount(request) if callable(amount) else amount
        return {
            "x402Version": 2,
            "accepts": [
                {
                    "scheme": "exact",
                    "network": network,
                    "asset": asset,
                    "maxAmountRequired": str(dynamic_amount),
                    "payTo": pay_to,
                    "resource": path,
                    "description": description,
                    "mimeType": "application/json",
                }
            ],
        }

    def fastapi():
        """Return an async ASGI middleware callable for FastAPI/Starlette.

        Usage::

            app = FastAPI()
            pay = server(pay_to=..., network=..., asset=..., amount=..., facilitator=...)
            app.middleware("http")(pay.fastapi())

        Or using add_middleware::

            app.add_middleware(BaseHTTPMiddleware, dispatch=pay.fastapi())
        """
        async def _middleware(request: Any, call_next: Callable) -> Any:
            # Avoid importing Starlette at module level so the package
            # stays installable without FastAPI.
            try:
                from starlette.responses import JSONResponse, Response
            except ImportError:
                raise RosettaError(
                    ErrorCode["ERR_FACILITATOR_UNREACHABLE"],
                    "fastapi/starlette is required for server().fastapi()",
                )

            path = request.url.path if hasattr(request.url, "path") else str(request.url)

            if path in _free_paths:
                return await call_next(request)

            # Read payment signature from request headers
            sig = read_payment_signature(dict(request.headers))
            if sig is None:
                body = _build_payment_required(path, request)
                return Response(
                    content=canonicalize(body),
                    status_code=402,
                    media_type="application/json",
                )

            # Forward signature to facilitator for verify + settle
            try:
                import httpx
            except ImportError:
                raise RosettaError(
                    ErrorCode["ERR_FACILITATOR_UNREACHABLE"],
                    "httpx is required for server facilitator calls",
                )

            facilitator_base = facilitator.rstrip("/")
            payment_reqs = _build_payment_required(path, request)["accepts"][0]
            payload = {"paymentPayload": sig, "paymentRequirements": payment_reqs}
            payload_json = json.dumps(payload)

            async with httpx.AsyncClient() as hc:
                verify_res = await hc.post(
                    facilitator_base + "/verify",
                    content=payload_json,
                    headers={"content-type": "application/json"},
                )
                if not verify_res.is_success:
                    return Response(
                        content=json.dumps(
                            {"error": "facilitator verify rejected", "status": verify_res.status_code}
                        ),
                        status_code=402,
                        media_type="application/json",
                    )

                settle_res = await hc.post(
                    facilitator_base + "/settle",
                    content=payload_json,
                    headers={"content-type": "application/json"},
                )
                try:
                    settlement = settle_res.json()
                except Exception:
                    settlement = {}

            response = await call_next(request)

            if settlement and settlement.get("success") is not False:
                # Mutate response headers if possible
                try:
                    write_payment_response(response.headers, settlement)
                except Exception:
                    pass  # headers may be immutable on some response types

            return response

        return _middleware

    return {
        "fastapi": fastapi,
        "_build_payment_required": _build_payment_required,
    }
