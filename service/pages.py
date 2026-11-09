"""The one page the service renders: the demo owner's gate decisions, for judges.

Plain HTML with inline styles, no scripts and nothing loaded from elsewhere.
Every value from the database is escaped before it reaches the page.
"""

from html import escape

ACTIONS = {
    "pay": "Agent asked to pay",
    "void": "Held payment cancelled",
    "capture": "Payment completed",
    "pause": "Plan paused (level 1)",
    "protect": "Protection (level 2)",
    "suspend_subscription": "Subscription suspended",
    "reactivate_subscription": "Subscription reactivated",
    "emergency_fund": "Emergency fund sent",
    "closure_requested": "Closure requested (level 3)",
    "closure_cancelled": "Closure cancelled",
    "closure": "Plan closed (level 3)",
    "resume": "Owner answered",
    "rehearsal": "Rehearsal",
    "demo_reset": "Demo reset",
    "demo_skip_wait": "Demo: 72-hour wait skipped",
}
# Outcome badge colours: held and done are fine, refused is the gate saying no.
BADGES = {"held": ("#0f766e", "#ccfbf1"), "refused": ("#b91c1c", "#fee2e2"), "error": ("#92400e", "#fef3c7")}
DEFAULT_BADGE = ("#334155", "#e2e8f0")


def _row(event: dict) -> str:
    at = event["at"].strftime("%Y-%m-%d %H:%M") if hasattr(event["at"], "strftime") else str(event["at"])[:16]
    amount = f"{event['amount']} {event['currency'] or ''}".strip() if event["amount"] is not None else ""
    outcome = event["outcome"] or ""
    fg, bg = BADGES.get(outcome, DEFAULT_BADGE)
    cells = [
        escape(at),
        escape(event["agent_id"] or ""),
        escape(ACTIONS.get(event["action"], event["action"])),
        escape(amount),
        f'<span style="color:{fg};background:{bg};padding:2px 8px;border-radius:10px;'
        f'font-weight:600">{escape(outcome)}</span>',
        escape(event["reason"] or ""),
        f'<code>{escape(event["paypal_id"] or "")}</code>',
    ]
    return "<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>"


def activity_page(level: str, events: list[dict]) -> str:
    rows = "\n".join(_row(event) for event in events) or '<tr><td colspan="7">No decisions yet.</td></tr>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NextOfKin gate decisions</title>
<style>
  body {{ margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background: #f8fafc; color: #0f172a; }}
  header {{ background: #0f172a; color: #fff; padding: 24px 16px; }}
  header h1 {{ margin: 0 0 6px; font-size: 24px; }}
  header p {{ margin: 0; color: #cbd5e1; max-width: 900px; line-height: 1.5; }}
  header a {{ color: #2dd4bf; }}
  main {{ padding: 16px; }}
  .level {{ display: inline-block; margin-bottom: 12px; font-weight: 600; }}
  .wrap {{ overflow-x: auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
  th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }}
  th {{ background: #f1f5f9; font-weight: 600; white-space: nowrap; }}
  td:first-child, td:nth-child(4), td:nth-child(7) {{ white-space: nowrap; }}
  code {{ font-size: 13px; }}
</style></head>
<body>
<header>
  <h1>NextOfKin: live gate decisions</h1>
  <p>Every decision the gate made for the demo owner, John Doe (PayPal sandbox), newest first.
  A payment that is <b>held</b> is a PayPal authorization: the money is not taken yet, so it can still be cancelled.
  Email addresses are hidden. Times are UTC.
  <a href="https://github.com/Pat52-byte/nextofkin#how-to-test">How to test</a> ·
  <a href="https://cmvggp6wq0049bllc9x0fico9.zapier.app/">The app</a> ·
  <a href="/demo/activity.json">Raw data</a></p>
</header>
<main>
  <div class="level">Plan level now: {escape(level)}</div>
  <div class="wrap"><table>
    <thead><tr><th>When (UTC)</th><th>Agent</th><th>What happened</th><th>Amount</th><th>Outcome</th><th>Reason</th><th>PayPal ID</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table></div>
</main>
</body></html>"""
