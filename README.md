# NextOfKin

A legacy contact for your AI agents. Built on PayPal for the PayPal AI Hackathon 2026.

AI agents now pay on our behalf. If their owner falls ill, ends up in hospital or dies, the agents keep spending, because nothing ties their payment permission to a person who is still there. NextOfKin checks in with the owner, and when they stop answering it pauses the agents, keeps essential payments running and brings in a trusted contact.

> Work in progress. Full documentation will be added before submission.

## Repository layout

| Path | What it holds |
|---|---|
| `service/` | The service that talks to PayPal and enforces the safety rules |
| `render.yaml` | Deployment settings for Render |

## Run the service locally

```bash
cd service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/health.

## License

MIT
