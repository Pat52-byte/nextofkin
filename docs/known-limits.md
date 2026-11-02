# Known limits and what's not built yet

NextOfKin was built in four weeks for the PayPal AI Hackathon. This page lists what it doesn't do yet and where the demo takes shortcuts. Each item explains why.

## By design

- **It only protects payments that go through NextOfKin.** An agent that holds its own card or PayPal permission can still pay without asking the gate. The protection works because the owner's PayPal permission (Vault) stays in the service and is never handed to the agents.
- **If the service is down, nothing happens.** No pause, no closure, no payment. A plan never escalates because of a failure.
- **"Away until" always wins.** While the owner says they are away, the plan never escalates. Only the owner can set that date.
- **Level 3 is the only step that can't be undone.** That's why it needs the trusted contact's confirmation and then 72 hours without an answer from the owner. Payments that were held when the plan closed are cancelled for good.

## Demo shortcuts

- **PayPal sandbox only.** Every account, payment and subscription is a sandbox one.
- **Demo-only endpoints.** `POST /demo/reset` and `POST /demo/skip-closure-wait` exist so a judge can replay the story in minutes instead of 72 hours. They only work on the demo owner, and a real deployment would remove them.
- **The family assistant knows the owner's name from its prompt.** The name "John" is written into the prompt, because the demo has one owner. With more owners, the name would come from the Owners table.
- **A trusted contact for two owners is matched to the first one.** The Zaps look up trusted contacts by email and take the first match.
- **The service sleeps when idle.** It runs on Render's free plan, so the first call after a quiet period can take about a minute.
- **The Action log updates every 6 hours.** Zap Z12 copies the gate's decisions on a schedule, so a refusal can take a few hours to appear in Interfaces. The service's own log (`GET /events`) is immediate.

## Planned, not built

| Item | What it would do | Why it waited |
|---|---|---|
| Z7, PayPal alerts | Verify PayPal webhook signatures, and alert the owner if an agent tries to pay while the plan is paused | The gate already refuses these payments and logs them. Z7 would add a push alert. |
| Z8, new recurring payments | Each week, ask the owner how to classify a payment that started recently | Z1 already maps all payments. Z8 would ask only about new ones. |
| Two trusted contacts | Both must confirm before level 2 (S2) | One contact plus the 72-hour wait was enough for the demo. |
| A PIN for check-ins | Protects against a stolen phone answering the check-in (S3) | |
| A notice to payees | An optional, neutral message to people who keep getting paid (U10) | |
| Data retention | Delete the log and the family assistant's conversations after a set time or on request (P6, P10) | |
| What heirs may see | The owner chooses, while alive, what the family can see. Under Italian privacy law (art. 2-terdecies) this needs a lawyer's review. (P7) | |

## Evals we ran, and those we didn't

Ran (results in [docs/evals](evals/)):
- E1, payment classification;
- E2, level proposal;
- E7, hidden instructions;
- E10, family assistant;
- E12, grocery agent;
- 14 attack tests.

Not run yet:
- **E3**, ambiguous messages from the trusted contact. Today the contact answers through a form with fixed choices, so there is no free text to misread.
- **E4**, checking every number in a report against PayPal.
- **E5**, tone and empathy rated by two people.
- **E8**, false alarms over 90 simulated days.
- **E9**, the same scenario repeated 5 times. The level decision (E2) is plain code, so it's repeatable by construction. The AI steps were not tested this way.
- **E11**, 10 legal and tax questions to the family assistant. E10 included one ("Is it legal to keep it?"), and the assistant gave no legal advice.

E6, suspicious activity, is covered by the [attack tests](evals/attack-tests.md).
