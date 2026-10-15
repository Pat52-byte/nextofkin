"""NextOfKin service: the only part of the system that talks to PayPal.

Zapier orchestrates the flows; this service makes the PayPal calls and
enforces the fixed safety rules the AI cannot override. This first
version only proves the service runs and can be reached.
"""

from fastapi import FastAPI

app = FastAPI(title="NextOfKin service", version="0.1.0")


@app.get("/health")
def health() -> dict:
    """Liveness check used by Render and by Zapier before each flow."""
    return {"status": "ok", "service": "nextofkin", "version": app.version}
