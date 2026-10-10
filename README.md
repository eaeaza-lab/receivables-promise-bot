# Receivables Promise-to-Pay Bot

An offline Telegram-style prototype for tracking synthetic overdue invoices, recording payment promises, spotting missed commitments, and preparing daily collections reports.

**Status:** work in progress

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

## Current capability

The local SQLite ledger stores synthetic invoices and promise-to-pay records. The
local mock Telegram-style transport accepts the following explicit commands:

```text
/invoice SYN-1001 12500 14
/promise SYN-1001 12500 2026-10-15
/paid SYN-1001
```

Ambiguous or incomplete messages request clarification and never alter the ledger.
The transport is local only: Telegram and every other external integration remain
unavailable. Missed-promise monitoring and report exports are not available yet.
