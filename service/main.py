"""NextOfKin service: the only part of the system that talks to PayPal.

Zapier orchestrates the flows; this service makes the PayPal calls and
enforces the fixed safety rules the AI cannot override.
"""

import hmac
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

from config import get_settings
from mapping import build_map
from paypal import PayPalClient, PayPalError

app = FastAPI(title="NextOfKin service", version="0.2.0")


@lru_cache
def paypal() -> PayPalClient:
    return PayPalClient(get_settings())


def require_api_key(x_api_key: str = Header(default="")) -> None:
    """Every call except /health must carry the shared key Zapier holds (control S6).

    With no key configured the service refuses everything rather than run open.
    """
    expected = get_settings().service_api_key
    if not expected or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or wrong X-Api-Key header.")


@app.exception_handler(PayPalError)
def paypal_error(_, error: PayPalError):
    return JSONResponse(
        status_code=502,
        content={
            "error": "paypal_error",
            "paypal_status": error.status,
            "paypal_name": error.name,
            "message": error.message,
            "debug_id": error.debug_id,
        },
    )


@app.get("/health")
def health() -> dict:
    """Liveness check used by Render and by Zapier before each flow."""
    return {"status": "ok", "service": "nextofkin", "version": app.version}


@app.get("/map", dependencies=[Depends(require_api_key)])
def payment_map(days: int = Query(30, ge=1, le=31)) -> dict:
    """The owner's payments over the last `days` days, grouped, with people
    replaced by codes. PayPal can take a few hours to list new transactions."""
    settings = get_settings()
    if not settings.pseudonym_key:
        raise HTTPException(status_code=503, detail="PSEUDONYM_KEY is not configured.")
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=days)
    stamp = "%Y-%m-%dT%H:%M:%SZ"
    transactions = paypal().search_transactions(start.strftime(stamp), end.strftime(stamp))
    return {
        "period": {"start": start.strftime(stamp), "end": end.strftime(stamp)},
        **build_map(transactions, settings.pseudonym_key),
    }
