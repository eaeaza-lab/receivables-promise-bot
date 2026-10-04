"""Offline entry point for the Receivables Promise-to-Pay Bot."""

from receivables_bot import Invoice, invoice_status


def main() -> None:
    invoice = Invoice(reference="SYN-1001", amount_cents=125_00, days_overdue=14)
    print(f"{invoice.reference}: {invoice_status(invoice)}")
    print("Mock transport only; external integrations are unavailable.")


if __name__ == "__main__":
    main()
