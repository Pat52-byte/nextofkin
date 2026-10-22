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
| `POST /owners` | Register an owner and their PayPal Vault permission |
| `GET /owners/{email}` | The owner's plan level and agents |
| `POST /owners/{email}/pause` | Level 1: non-essential agents stop and their held payments are cancelled |
| `POST /owners/{email}/resume` | The owner is back: the plan returns to normal |
| `GET /owners/{email}/events` | Every gate decision, newest first |
| `POST /agents` | Register an agent and return its key, once |
| `POST /agents/{id}/suspend`, `/activate`, `/revoke` | Change one agent without touching the others |
| `POST /gate/pay` | **Agents only**, with `X-Agent-Key`: ask to pay. The money is held on PayPal, not taken. A refusal is a normal `200` answer with `"outcome": "refused"` and the reason |
| `POST /gate/settle` | Complete the held payments that may still go through |

Every endpoint except `/health` and `/gate/pay` requires the header `X-Api-Key`.

## How the gate decides

Agents never see the owner's PayPal permission. They can only ask the gate, which checks, in order: the agent's status, the owner's plan level, whether PayPal is connected, the currency and the agent's spending cap. When the owner stops answering, non-essential agents are refused and their held payments are cancelled, while essential agents such as a utility bills agent keep paying. Every decision is recorded.

## Configuration

Set these in `service/.env` locally and in the Render dashboard in production. Never commit them.

| Variable | Purpose |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | Credentials of the PayPal sandbox app |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` |
| `SERVICE_API_KEY` | Shared secret Zapier sends in `X-Api-Key` |
| `PSEUDONYM_KEY` | Key used to turn people's details into stable codes before the AI sees them |
| `DATABASE_URL` | Postgres connection string (Neon) where the gate keeps owners, agents and held payments |

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
