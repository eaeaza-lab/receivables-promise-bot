# Receivables Promise-to-Pay Bot

An offline Telegram-style prototype for tracking synthetic overdue invoices, recording payment promises, spotting missed commitments, and preparing daily collections reports.

**Status:** work in progress

Built by a supervised autonomous agent pipeline (nightshift).

## Run

Requires Python 3. Run the current skeleton:

```text
python app.py
```

Run tests:

```text
python -m unittest discover -s tests -v
```

All future data is synthetic and the application will not use the network at runtime.
