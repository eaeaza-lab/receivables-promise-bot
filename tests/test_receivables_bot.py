import unittest
from datetime import date
import sqlite3

from receivables_bot import Invoice, LedgerRepository, PromiseToPay, invoice_status


class InvoiceStatusTests(unittest.TestCase):
    def test_unpaid_overdue_invoice_is_overdue(self) -> None:
        invoice = Invoice(reference="SYN-2001", amount_cents=50_00, days_overdue=3)

        self.assertEqual(invoice_status(invoice), "overdue")


class LedgerRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = LedgerRepository()
        self.addCleanup(self.ledger.close)

    def test_invoice_round_trip_and_paid_update(self) -> None:
        invoice = Invoice(reference="SYN-3001", amount_cents=125_00, days_overdue=14)
        self.ledger.add_invoice(invoice)

        self.assertEqual(self.ledger.get_invoice("SYN-3001"), invoice)
        self.assertTrue(self.ledger.mark_invoice_paid("SYN-3001"))
        self.assertTrue(self.ledger.get_invoice("SYN-3001").paid)
        self.assertFalse(self.ledger.mark_invoice_paid("SYN-UNKNOWN"))

    def test_promise_is_linked_to_invoice_and_retrievable(self) -> None:
        self.ledger.add_invoice(Invoice("SYN-3002", 80_00, 5))
        saved = self.ledger.record_promise(
            PromiseToPay("SYN-3002", 40_00, date(2026, 10, 15))
        )

        self.assertIsNotNone(saved.id)
        self.assertEqual(self.ledger.list_promises("SYN-3002"), [saved])

    def test_promise_requires_an_existing_invoice(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.ledger.record_promise(
                PromiseToPay("SYN-MISSING", 10_00, date(2026, 10, 15))
            )


if __name__ == "__main__":
    unittest.main()
