# Level proposal evals (E2)

Once a day, Z6a looks at each owner and decides one of three things: do nothing, pause the non-essential agents (level 1), or ask the trusted contact to confirm. Level 2 needs the trusted contact's confirmation, and level 3 needs that confirmation plus 72 hours without an answer from the owner. No AI is used here. The decision is a plain Python step, so it gives the same answer every time.

- **Scenarios and runner:** [e2_level_proposal.py](e2_level_proposal.py). It has 40 scenarios, including holidays, a broken phone, a hospital stay, a death, owner-chosen timings, different date formats, attacks and badly written data. Run it with `python e2_level_proposal.py`.
- **Run:** 2 November 2026.

## Results

| | Before the fix | After the fix |
|---|---|---|
| Right decision | 37 of 40 (92%) | 40 of 40 (100%) |
| Ever proposes level 2 or 3 by itself | Never | Never |

The target was 90% or more, with level 3 never reached without confirmation.

## What failed, and the fix

| Case | Problem | Fix |
|---|---|---|
| E2-34 | A level written "normal" in lower case was not recognised, so a silent owner was not paused. | The level is read without regard to case. |
| E2-35 | A level written "protection" in lower case was not recognised. A plan already in protection would have asked the trusted contact again. | Same fix. |
| E2-38 | A number of days that wasn't a number stopped the step with an error. | It falls back to the default: 3 days for level 1, 7 days for level 2. |

None of these can happen today, because in Zapier Tables the level is a drop-down list and the days are a number field. We fixed them anyway, so the step doesn't depend on the table always being clean.

## Choices worth knowing

- **Holidays win.** While the owner has said they are away, nothing escalates (E2-11, E2-12). If someone set "away until 2099", the plan would never escalate (E2-31). Only the owner can set that date.
- **When in doubt, do nothing.** A check-in date that can't be read, or that is in the future, never escalates the plan (E2-30, E2-32).
- **A long silence doesn't close anything.** After 90 days of silence, the most Z6a does is ask the trusted contact (E2-10).
