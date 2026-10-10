import unittest
from datetime import date
import sqlite3

from receivables_bot import (
    Invoice,
    LedgerRepository,
    MockTelegramTransport,
    PromiseToPay,
    invoice_status,
)


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


class MockTelegramTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = LedgerRepository()
        self.addCleanup(self.ledger.close)
        self.transport = MockTelegramTransport(self.ledger)

    def test_complete_commands_update_the_local_ledger(self) -> None:
        self.assertEqual(
            self.transport.handle_message("/invoice SYN-4001 12500 14"),
            "Saved synthetic invoice SYN-4001.",
        )
        self.assertEqual(
            self.transport.handle_message("/promise SYN-4001 12500 2026-10-15"),
            "Saved promise #1 for synthetic invoice SYN-4001.",
        )
        self.assertEqual(
            self.transport.handle_message("/paid SYN-4001"),
            "Marked synthetic invoice SYN-4001 as paid.",
        )
        self.assertTrue(self.ledger.get_invoice("SYN-4001").paid)

    def test_ambiguous_or_invalid_messages_do_not_change_the_ledger(self) -> None:
        response = self.transport.handle_message("record a payment promise")
        self.assertIn("I need a complete command", response)
        self.assertEqual(self.ledger.list_promises(), [])

        response = self.transport.handle_message("/invoice SYN-4002 9000")
        self.assertIn("/invoice <reference> <amount_cents> <days_overdue>", response)
        self.assertIsNone(self.ledger.get_invoice("SYN-4002"))

    def test_invalid_promise_for_unknown_invoice_requests_clarification(self) -> None:
        response = self.transport.handle_message("/promise SYN-MISSING 1000 2026-10-15")

        self.assertIn("existing invoice_reference", response)
        self.assertEqual(self.ledger.list_promises(), [])


if __name__ == "__main__":
    unittest.main()
