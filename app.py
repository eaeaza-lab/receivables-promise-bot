"""Offline entry point for the Receivables Promise-to-Pay Bot."""

from datetime import date

from receivables_bot import LedgerRepository, MockTelegramTransport
from receivables_bot import seed_demo_scenarios


def main() -> None:
    ledger = LedgerRepository()
    transport = MockTelegramTransport(ledger)
    try:
        today = date.today()
        seed_demo_scenarios(ledger, today)
        rows = ledger.list_daily_collections_rows(today)
        status_counts = {
            status: sum(row.status == status for row in rows)
            for status in ("missed", "due today", "upcoming", "needs follow-up")
        }

        print("Receivables Promise-to-Pay Bot — local synthetic demo")
        print(f"Demo date: {today.isoformat()}")
        print(
            "Actionable queue: "
            f"{len(rows)} unpaid overdue invoices — {status_counts['missed']} missed, "
            f"{status_counts['due today']} due today, {status_counts['upcoming']} upcoming, "
            f"{status_counts['needs follow-up']} needing follow-up."
        )
        print("Demo references: DEMO-1001 (missed), DEMO-1002 (due today), "
              "DEMO-1003 (upcoming), DEMO-1004 (no promise).")
        print("Local command formats:")
        print(transport.HELP_TEXT)
        print("Examples: /missed " + today.isoformat())
        print("          /report " + today.isoformat() + " reports")
        print("External integrations are unavailable; no data leaves this process.")
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
