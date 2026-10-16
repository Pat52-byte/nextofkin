"""Settings read from environment variables.

In development they come from service/.env; on Render they are set in the
service's Environment page. Secrets never live in the repository.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))


@dataclass(frozen=True)
class Settings:
    paypal_client_id: str
    paypal_client_secret: str
    paypal_base_url: str
    # Shared secret Zapier sends with every call (header X-Api-Key).
    service_api_key: str
    # Key for turning names and emails into stable codes before the AI sees them.
    pseudonym_key: str


def get_settings() -> Settings:
    return Settings(
        paypal_client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
        paypal_client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""),
        paypal_base_url=os.environ.get(
            "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"
        ).rstrip("/"),
        service_api_key=os.environ.get("SERVICE_API_KEY", ""),
        pseudonym_key=os.environ.get("PSEUDONYM_KEY", ""),
    )
