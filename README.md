# Receivables Promise-to-Pay Bot

An offline Telegram-style prototype for tracking synthetic overdue invoices, recording payment promises, spotting missed commitments, and preparing daily collections reports.

**Status:** polish

Built by a supervised autonomous agent pipeline (nightshift).

## Run

Requires Python 3. Run the local command guide:

```text
python app.py
```

Run tests:

```text
python -m unittest discover -s tests -v
```

All future data is synthetic and the application will not use the network at runtime.

## Demo

Running `python app.py` creates an in-memory, synthetic demo for the current
local date. It presents four unpaid overdue invoices: one missed commitment,
one commitment due today, one upcoming commitment, and one invoice needing a
promise. A fifth, paid synthetic invoice demonstrates that settled work is
excluded from the queue.

Sample output:

```text
Receivables Promise-to-Pay Bot — local synthetic demo
Demo date: 2026-10-14
Actionable queue: 4 unpaid overdue invoices — 1 missed, 1 due today, 1 upcoming, 1 needing follow-up.
Demo references: DEMO-1001 (missed), DEMO-1002 (due today), DEMO-1003 (upcoming), DEMO-1004 (no promise).
```

The command formats printed by the demo are handled by the local
`MockTelegramTransport` in code; they are intentionally not real Telegram
messages. For example, an embedding application can send `/missed 2026-10-14`
or `/report 2026-10-14 reports` to the mock transport. All output remains
local, and external integrations are unavailable.

## Current capability

The local SQLite ledger stores synthetic invoices and promise-to-pay records. The
local mock Telegram-style transport accepts the following explicit commands:

```text
/invoice SYN-1001 12500 14
/promise SYN-1001 12500 2026-10-15
/paid SYN-1001
/missed 2026-10-16
/report 2026-10-16 reports
```

Ambiguous or incomplete messages request clarification and never alter the ledger.
Use `/missed <YYYY-MM-DD>` (exactly hyphenated, for example `2026-10-16`) to list commitments that were due before that date
while their synthetic invoices remain unpaid; commitments due on the supplied
date are not yet missed. The transport is local only: Telegram and every other
external integration remain unavailable.

`/report <YYYY-MM-DD> <output_directory>` writes a daily collections queue to
both `collections-summary-YYYY-MM-DD.html` and
`collections-summary-YYYY-MM-DD.csv`. It includes each unpaid overdue synthetic
invoice, including those with no promise, and labels commitments as missed, due
today, or upcoming. The HTML report escapes synthetic references; the CSV is
ready for spreadsheet review. Re-running a report for the same date replaces
that date's two local files.
