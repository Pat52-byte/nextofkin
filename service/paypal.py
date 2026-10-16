"""A small PayPal REST client: gets and reuses the access token, makes calls,
and turns PayPal errors into one exception type."""

import base64
import time

import httpx

from config import Settings

# Refresh the token this many seconds before PayPal says it expires.
TOKEN_MARGIN_SECONDS = 60


class PayPalError(Exception):
    def __init__(self, status: int, name: str, message: str, debug_id: str | None):
        super().__init__(f"PayPal {status} {name}: {message}")
        self.status = status
        self.name = name
        self.message = message
        self.debug_id = debug_id


class PayPalClient:
    def __init__(self, settings: Settings, http: httpx.Client | None = None):
        self._settings = settings
        self._http = http or httpx.Client(base_url=settings.paypal_base_url, timeout=30)
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expires_at:
            return self._token
        credentials = f"{self._settings.paypal_client_id}:{self._settings.paypal_client_secret}"
        response = self._http.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()},
        )
        body = self._json_or_raise(response)
        self._token = body["access_token"]
        self._token_expires_at = time.monotonic() + body.get("expires_in", 0) - TOKEN_MARGIN_SECONDS
        return self._token

    def request(self, method: str, path: str, **kwargs) -> dict:
        headers = {"Authorization": f"Bearer {self._access_token()}", **kwargs.pop("headers", {})}
        response = self._http.request(method, path, headers=headers, **kwargs)
        if response.status_code == 204:
            return {}
        return self._json_or_raise(response)

    def search_transactions(self, start: str, end: str) -> list[dict]:
        """All transactions between two ISO dates (PayPal allows at most 31 days)."""
        transactions: list[dict] = []
        page = 1
        while True:
            body = self.request(
                "GET",
                "/v1/reporting/transactions",
                params={
                    "start_date": start,
                    "end_date": end,
                    "fields": "all",
                    "page_size": 500,
                    "page": page,
                },
            )
            transactions.extend(body.get("transaction_details", []))
            if page >= body.get("total_pages", 1):
                return transactions
            page += 1

    @staticmethod
    def _json_or_raise(response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.is_success:
            return body
        raise PayPalError(
            status=response.status_code,
            name=body.get("name") or body.get("error") or "UNKNOWN",
            message=body.get("message") or body.get("error_description") or response.reason_phrase,
            debug_id=body.get("debug_id"),
        )
