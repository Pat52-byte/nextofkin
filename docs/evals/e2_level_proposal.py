"""E2: does Z6a propose the right plan level?

Z6a decides once a day, for each owner, whether to do nothing, pause the
non-essential agents (level 1) or ask the trusted contact to confirm (the
step before level 2). Z6A_CODE below is the Python step from Z6a, as it
runs after the 2 November fix. When this script runs it, "now" is fixed,
so the scenarios can be repeated.

Run: python e2_level_proposal.py
"""

from datetime import datetime, timedelta, timezone

Z6A_CODE = r'''
import re
from datetime import datetime, timezone

def parse(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    found = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if found:
        year, month, day = map(int, found.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    found = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", value)
    if found:
        month, day, year = map(int, found.groups())
        return datetime(year, month, day, tzinfo=timezone.utc)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y"):
        try:
            return datetime.strptime(value[:len(value)], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None

now = datetime.now(timezone.utc)
raw_last = input_data.get("last_check_in") or ""
last = parse(raw_last)
away = parse(input_data.get("away_until"))
asked = parse(input_data.get("contact_asked"))
def number(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default

level = (input_data.get("level") or "Normal").strip().capitalize()
l1 = number(input_data.get("l1_days"), 3)
l2 = number(input_data.get("l2_days"), 7)

action, days, reason = "none", 0, ""
if level in ("Protection", "Closure"):
    reason = "The plan is already in protection or closed."
elif away and away.date() >= now.date():
    reason = "The owner said they are away."
elif not last:
    reason = "No check-in recorded yet, so nothing is escalated."
else:
    days = (now - last).days
    if days >= l2 and asked and asked >= last:
        reason = "The trusted contact was already asked. Waiting for their answer."
    elif days >= l2:
        action, reason = "ask_contact", f"No answer for {days} days: the trusted contact is asked to confirm."
    elif days >= l1 and level == "Normal":
        action, reason = "pause", f"No answer for {days} days: non-essential agents are paused."
    else:
        reason = f"Last answer {days} days ago: nothing to do."

output = {"action": action, "days_silent": str(days), "reason": reason, "raw_last_check_in": raw_last}
'''

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
ALLOWED = {"none", "pause", "ask_contact"}


def ago(days=0, hours=0):
    return (NOW - timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ahead(days):
    return (NOW + timedelta(days=days)).strftime("%Y-%m-%d")


def owner(**fields):
    base = {"level": "Normal", "l1_days": "3", "l2_days": "7",
            "last_check_in": "", "away_until": "", "contact_asked": ""}
    base.update(fields)
    return base


# (id, story, owner fields, expected action)
SCENARIOS = [
    ("E2-01", "Answered an hour ago", owner(last_check_in=ago(hours=1)), "none"),
    ("E2-02", "Answered yesterday", owner(last_check_in=ago(1)), "none"),
    ("E2-03", "Silent 2 days 23 hours", owner(last_check_in=ago(2, 23)), "none"),
    ("E2-04", "Silent exactly 3 days", owner(last_check_in=ago(3)), "pause"),
    ("E2-05", "Broken phone, silent 4 days", owner(last_check_in=ago(4)), "pause"),
    ("E2-06", "Broken phone, silent 6 days", owner(last_check_in=ago(6)), "pause"),
    ("E2-07", "In hospital, silent 7 days", owner(last_check_in=ago(7)), "ask_contact"),
    ("E2-08", "In hospital, silent 12 days", owner(last_check_in=ago(12)), "ask_contact"),
    ("E2-09", "Died, silent 30 days", owner(last_check_in=ago(30)), "ask_contact"),
    ("E2-10", "Died, silent 90 days", owner(last_check_in=ago(90)), "ask_contact"),
    ("E2-11", "On holiday for 5 more days, silent 10", owner(last_check_in=ago(10), away_until=ahead(5)), "none"),
    ("E2-12", "Holiday ends today, silent 10", owner(last_check_in=ago(10), away_until=ahead(0)), "none"),
    ("E2-13", "Holiday ended yesterday, silent 10", owner(last_check_in=ago(10), away_until=ahead(-1)), "ask_contact"),
    ("E2-14", "Holiday ended 3 days ago, silent 4", owner(last_check_in=ago(4), away_until=ahead(-3)), "pause"),
    ("E2-15", "Already paused, silent 4", owner(level="Pause", last_check_in=ago(4)), "none"),
    ("E2-16", "Already paused, silent 8", owner(level="Pause", last_check_in=ago(8)), "ask_contact"),
    ("E2-17", "Contact already asked, waiting", owner(last_check_in=ago(9), contact_asked=ago(2)), "none"),
    ("E2-18", "Contact asked in an older episode", owner(last_check_in=ago(8), contact_asked=ago(20)), "ask_contact"),
    ("E2-19", "Already in protection, silent 20", owner(level="Protection", last_check_in=ago(20)), "none"),
    ("E2-20", "Already closed, silent 40", owner(level="Closure", last_check_in=ago(40)), "none"),
    ("E2-21", "New owner, no check-in yet", owner(), "none"),
    ("E2-22", "Owner chose 1 and 2 days, silent 1", owner(l1_days="1", l2_days="2", last_check_in=ago(1)), "pause"),
    ("E2-23", "Owner chose 1 and 2 days, silent 2", owner(l1_days="1", l2_days="2", last_check_in=ago(2)), "ask_contact"),
    ("E2-24", "Owner chose 5 and 10 days, silent 4", owner(l1_days="5", l2_days="10", last_check_in=ago(4)), "none"),
    ("E2-25", "Owner chose 5 and 10 days, silent 6", owner(l1_days="5", l2_days="10", last_check_in=ago(6)), "pause"),
    ("E2-26", "Date written 11/01/2026", owner(last_check_in="11/01/2026"), "none"),
    ("E2-27", "Date written October 20, 2026", owner(last_check_in="October 20, 2026"), "ask_contact"),
    ("E2-28", "Date written 2026-10-30", owner(last_check_in="2026-10-30"), "pause"),
    ("E2-29", "Date written 20 October 2026", owner(last_check_in="20 October 2026"), "ask_contact"),
    ("E2-30", "Attack: check-in date in the future", owner(last_check_in="2026-12-01T00:00:00Z"), "none"),
    ("E2-31", "Away until 2099 (only the owner can set it)", owner(last_check_in=ago(30), away_until="2099-01-01"), "none"),
    ("E2-32", "Unreadable check-in date", owner(last_check_in="yesterday"), "none"),
    ("E2-33", "Level left empty, silent 4", owner(level="", last_check_in=ago(4)), "pause"),
    ("E2-34", "Level written in lower case, silent 4", owner(level="normal", last_check_in=ago(4)), "pause"),
    ("E2-35", "Protection written in lower case, silent 10", owner(level="protection", last_check_in=ago(10)), "none"),
    ("E2-36", "Level 1 days left empty, silent 4", owner(l1_days="", last_check_in=ago(4)), "pause"),
    ("E2-37", "Level 1 days written 3.0, silent 4", owner(l1_days="3.0", last_check_in=ago(4)), "pause"),
    ("E2-38", "Level 1 days not a number: falls back to 3", owner(l1_days="abc", last_check_in=ago(4)), "pause"),
    ("E2-39", "Unreadable 'contact asked' date, silent 8", owner(last_check_in=ago(8), contact_asked="soon"), "ask_contact"),
    ("E2-40", "Unreadable 'away until', silent 8", owner(last_check_in=ago(8), away_until="next week"), "ask_contact"),
]


def run(fields):
    code = Z6A_CODE.replace("now = datetime.now(timezone.utc)", "now = NOW")
    scope = {"input_data": dict(fields), "NOW": NOW}
    try:
        exec(code, scope)
    except Exception as error:  # Z6a would stop with an error: nothing is escalated
        return "error", f"{type(error).__name__}: {error}"
    return scope["output"]["action"], scope["output"]["reason"]


def main():
    passed, never_beyond = 0, True
    for case_id, story, fields, expected in SCENARIOS:
        got, reason = run(fields)
        if got not in ALLOWED and got != "error":
            never_beyond = False
        ok = got == expected
        passed += ok
        print(f"{case_id} {'PASS' if ok else 'FAIL'}  {story}: expected {expected}, got {got}. {reason}")
    print(f"\n{passed} of {len(SCENARIOS)} correct ({passed / len(SCENARIOS):.0%}).")
    print("Never proposes level 2 or 3 by itself:", "yes" if never_beyond else "NO")


if __name__ == "__main__":
    main()
