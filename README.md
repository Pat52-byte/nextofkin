# NextOfKin

**A legacy contact for your AI agents.** Built on PayPal for the PayPal AI Hackathon 2026.

AI agents now pay on our behalf: groceries, bills, subscriptions. Their permission to pay is tied to a PayPal account, not to whether its owner is still there. If the owner ends up in hospital or dies, the agents keep spending, and nobody has the right to stop them.

NextOfKin is a continuity plan for agents that pay. It checks in with the owner. When the owner stops answering, it steps in gradually and reversibly, and it brings in a trusted contact. Essential bills keep being paid, everything else waits, and the family can see what happened and why.

> **The AI proposes. Fixed rules decide.** Claude classifies payments, prepares grocery orders and answers the family's questions. Every action on money goes through a gate that applies fixed rules and logs each decision.

## The three levels

| Level | When | What happens | Can it be undone? |
|---|---|---|---|
| **1 · Pause** | The owner hasn't answered the check-in for 3 days (the owner picks the number) | Non-essential agents stop and their held payments are cancelled. Essential agents keep paying. | Yes. The owner answers and everything resumes. |
| **2 · Protection** | 7 days of silence (the owner picks the number), and the **trusted contact confirms** an emergency | Non-essential subscriptions are suspended, not cancelled. The emergency fund goes to the PayPal account the owner registered in advance, up to the owner's cap, once every 30 days. | Yes. Subscriptions come back. |
| **3 · Closure** | The trusted contact confirms a death, **and 72 hours pass** without an answer from the owner | All agents lose their permission to pay, and every held payment is cancelled. The family assistant opens. | No. That's why it waits 72 hours. |

**The owner always wins.** At any level before closure, a single answer from the owner puts everything back. That includes a closure that is still waiting.

## How it's built

```
          Owner, trusted contact, family
                       │
         Zapier Interfaces  (forms, tables, pages)
                       │
  Zapier Zaps  ──────  Claude (Anthropic)    proposes: classifies, prepares, explains
       │
       │  X-Api-Key
       ▼
  NextOfKin service  (FastAPI on Render + Postgres on Neon)
       │   the gate: fixed rules, every decision logged
       ▼
  PayPal APIs   Vault · Orders (authorize, void, capture) · Subscriptions · Payouts · Transaction Search
```

- **[service/](service/)** holds the gate. It keeps the owner's PayPal permission (Vault), so agents never see it. Agents can only *ask* to pay. The gate checks the agent's status, the plan level, the currency and the agent's spending cap, then either refuses with a reason or places a PayPal **authorization**. That holds the money without taking it, so the payment can still be cancelled if the owner stops answering.
- **Zapier** runs the plan. Tables store owners, agents, payments, trusted contacts and the action log. Interfaces gives the owner, the trusted contact and the family their pages. Zaps run the daily check-ins and the escalation.
- **Claude** is used in four places, each with a narrow job and tested by evals:

| Where | Model | What it does | Evals |
|---|---|---|---|
| Z1, payment map | Claude Haiku 4.5 | Classifies each recurring payment: essential, subscription, or other; and what to do in an emergency | [E1, E7](docs/evals/e1-e7-results.md) |
| Z10, grocery agent | Claude Haiku 4.5 | Turns a request into an order under a 150 USD cap | [E12](docs/evals/e12-results.md) |
| Z3, rehearsal | Claude Sonnet 5.5 | Explains to the owner what each level would do, without doing it | |
| Z15, family assistant | Claude Sonnet 5.5 | Answers the trusted contact's questions after closure, read-only, from the plan's records only | [E10](docs/evals-family-assistant.md) |

People's names are replaced with stable codes (for example `P-0e85b00c`) before any payment data reaches the AI.

### The Zaps

| Zap | Trigger | What it does |
|---|---|---|
| Z0 · Onboarding | Form | Creates the owner's plan |
| Z1 · Payment map | Daily | Reads the last 30 days from PayPal through the service, and Claude classifies each payment |
| Z2a · Invitation | New trusted contact | Emails the invitation to the trusted contact |
| Z2b · Acceptance | The trusted contact accepts | Records the acceptance in the Trusted contacts table |
| Z3 · Rehearsal | Button | Simulates a level and emails the owner what would happen |
| Z4 · Check-in | Daily, for every owner | Asks the owner "all good?" |
| Z5 · Answer | The owner clicks | Records the check-in and puts the plan back to normal |
| Z6a-loop + Z6a · Escalation | Daily, for every owner | Counts the days of silence and pauses the plan, or asks the trusted contact ([E2](docs/evals/e2-results.md)) |
| Z6b · Confirmation | Trusted contact's form | Level 2 or a level 3 request, from a fixed menu of choices |
| Z9, Z9b · Evals | Button | Run the eval cases through the same prompts as Z1 and Z10 |
| Z10 · Grocery agent | Owner's request | Claude prepares the order. A Code step recomputes the total, and the gate decides. |
| Z11 · Bills agent | Owner's request ("Ask your bills agent" form) | Pays an essential bill through the gate, and keeps paying during an emergency |
| Z12 · Gate log | Every 6 hours | Copies the gate's decisions, refusals included, into the Action log |
| Z13 · Closures | Daily | Closes the plans whose 72 hours have passed |
| Z14 · Demo reset | Button | Puts the demo back to the start |
| Z15 · Family assistant | Trusted contact's form | Answers questions about a closed plan, by email |

## How to test

Everything runs in the PayPal sandbox, so no real money moves. The demo owner is John Doe.

Open the app: **https://cmvggp6wq0049bllc9x0fico9.zapier.app/**. No login is needed.

| Try this | Page | What you should see |
|---|---|---|
| Ask the grocery agent for something under 150 USD, like "milk, eggs and bread" | Ask your grocery agent | Claude prepares the order, and the gate holds the payment on PayPal |
| Paste a bill above the bills agent's 400 USD cap, like "Electricity bill, amount due: 520.00 USD" | Ask your bills agent | The gate refuses it before PayPal is called, and says why: "The amount is above this agent's spending cap of 400.00 USD." |
| Ask the grocery agent for something too big, like "a party for 50 people" | Ask your grocery agent | Claude shrinks the order to fit the 150 USD cap |
| See what the gate stopped, and why | [Activity log](https://cmvggp6wq0049bllc9x0fico9.zapier.app/activity-log) | Every refusal with its reason, such as "The amount is above this agent's spending cap of 150.00 USD" |
| See the owner's plan: payments, agents and their caps | Your plan | What keeps being paid in an emergency, and what waits |
| See what the family would see after a closure | For the family | The payments in the plan, and every decision with who made it |
| Run the evals yourself | Evals | Claude classifies 27 payments and prepares 15 grocery orders, and each case is marked Pass or Fail. Takes 1 to 2 minutes. |

Levels 2 and 3 need a real trusted contact, and the family assistant answers only that person by email. These are shown end to end in the video. To replay them in code, see the [attack tests](docs/evals/attack-tests.md) and the endpoints below. If something looks off, [Reset the demo](https://cmvggp6wq0049bllc9x0fico9.zapier.app/reset-the-demo) puts John back to the start.

## Guardrails

| | Rule | Where it's enforced |
|---|---|---|
| G1 | The AI proposes, a fixed flow executes | Actions on PayPal come only from the service's endpoints |
| G2 | Level 2 and level 3 need a person's confirmation | `confirmed_by` is required. Z6a never goes past asking the trusted contact. |
| G3 | Levels 1 and 2 can be undone | Only holds are cancelled and subscriptions are suspended. Nothing is cancelled for good. |
| G4 | Essential payments keep going | Essential agents pass the gate at levels 1 and 2 |
| G5, G6 | The emergency fund has a cap and a fixed destination | Account and cap are set in advance, frozen during an emergency, and the fund is sent at most once every 30 days |
| G7 | The owner always wins | `resume` undoes any level before closure, including a waiting closure |
| G8 | Level 3 waits 72 hours | `closure_requested_at` + 72 h, checked daily |
| G9 | Every action is logged | `gate_events`: who, what, why, and the PayPal ID |
| G12 | Agents pay only through the gate | Agents get a key to the gate, never the Vault permission |
| G13 | The family assistant is read-only | It can only read the plan, and it opens only after closure |

## Evidence

- **[Evals](docs/evals/):**
  - E1, payment classification: 20 of 20 emergency actions right, 10 of 10 essential payments kept.
  - E7, hidden instructions: 7 of 7 ignored.
  - E2, level proposal: 40 of 40.
  - E12, grocery agent: Claude stayed under the cap 13 of 15 times, and the gate stops the other 2.
  - E10, family assistant: 7 of 7.
- **[Attack tests](docs/evals/attack-tests.md):** a fake death, changing the fund's account, paying above the cap, made-up keys, and asking for the family briefing too early. 14 of 14 stopped.
- **[Known limits](docs/known-limits.md):** what isn't built yet, and where the demo takes shortcuts.

## Service endpoints

Every endpoint except `/health` and `/gate/pay` requires the header `X-Api-Key`.

| Endpoint | What it does |
|---|---|
| `GET /health` | Liveness check, no key needed |
| `GET /map?days=30` | The owner's payments over the last 1–31 days, grouped, with recurring ones marked and people replaced by codes |
| `POST /owners` | Register an owner, their PayPal Vault permission and the emergency fund |
| `GET /owners/{email}` | The plan level, agents and any closure that is waiting |
| `POST /owners/{email}/pause` | Level 1 |
| `POST /owners/{email}/protect` | Level 2: needs `confirmed_by`. Suspends the listed subscriptions and sends the emergency fund. |
| `POST /owners/{email}/closure` | Requests level 3: needs `confirmed_by`. Takes effect after 72 hours. |
| `POST /closures/run` | Closes the plans whose 72 hours have passed |
| `POST /owners/{email}/resume` | The owner is back. Undoes everything that can be undone. |
| `GET /owners/{email}/rehearsal?level=` | What a level would do right now, without doing it |
| `GET /owners/{email}/events`, `GET /events` | The gate's decisions |
| `GET /owners/{email}/family-briefing` | The plan's records for the family assistant. Closed plans only. |
| `POST /agents` | Register an agent and return its key, once |
| `POST /agents/{id}/suspend`, `/activate`, `/revoke` | Change one agent without touching the others |
| `POST /gate/pay` | **Agents only**, with `X-Agent-Key`. Asks to pay. A refusal is a normal `200` answer with `"outcome": "refused"` and the reason. |
| `POST /gate/settle` | Completes the held payments that may still go through |
| `POST /demo/reset`, `POST /demo/skip-closure-wait` | Demo only, demo owner only. See [known limits](docs/known-limits.md). |

## Run the service locally

```bash
cd service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000/health. Run the tests with `python -m pytest`.

Set these in `service/.env` locally and in the Render dashboard in production. Never commit them.

| Variable | Purpose |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | Credentials of the PayPal sandbox app |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` |
| `SERVICE_API_KEY` | Shared secret that Zapier sends in `X-Api-Key` |
| `PSEUDONYM_KEY` | Key that turns people's details into stable codes before the AI sees them |
| `DATABASE_URL` | Postgres connection string (Neon) |

## License

MIT
