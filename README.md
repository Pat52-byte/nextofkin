# NextOfKin

A legacy contact for your AI agents. Built on PayPal for the PayPal AI Hackathon 2026.

AI agents now pay on our behalf. If their owner falls ill, ends up in hospital or dies, the agents keep spending, because nothing ties their payment permission to a person who is still there. NextOfKin checks in with the owner, and when they stop answering it pauses the agents, keeps essential payments running and brings in a trusted contact.

> Work in progress. Full documentation will be added before submission.

## Repository layout

| Path | What it holds |
|---|---|
| `service/` | The service that talks to PayPal and enforces the safety rules |
| `render.yaml` | Deployment settings for Render |

## Service endpoints

| Endpoint | What it does |
|---|---|
| `GET /health` | Liveness check, no key needed |
| `GET /map?days=30` | The owner's payments over the last 1–31 days: PayPal bookkeeping removed, repeated payments grouped, recurring ones marked, people replaced by stable codes |

Every endpoint except `/health` requires the header `X-Api-Key`.

## Configuration

Set these in `service/.env` locally and in the Render dashboard in production. Never commit them.

| Variable | Purpose |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | Credentials of the PayPal sandbox app |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` |
| `SERVICE_API_KEY` | Shared secret Zapier sends in `X-Api-Key` |
| `PSEUDONYM_KEY` | Key used to turn people's details into stable codes before the AI sees them |

## Run the service locally

```bash
cd service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/health. Run the tests with `python -m pytest`.

## License

MIT
