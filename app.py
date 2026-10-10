"""Offline entry point for the Receivables Promise-to-Pay Bot."""

from receivables_bot import LedgerRepository, MockTelegramTransport


def main() -> None:
    ledger = LedgerRepository()
    transport = MockTelegramTransport(ledger)
    try:
        print("Receivables Promise-to-Pay Bot (local mock transport)")
        print(transport.HELP_TEXT)
        print("External integrations are unavailable.")
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
