import unittest
from datetime import date
import csv
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from receivables_bot import (
    Invoice,
    LedgerRepository,
    MockTelegramTransport,
    PromiseToPay,
    export_daily_collections_summary,
    invoice_status,
    seed_demo_scenarios,
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

    def test_missed_promises_only_include_past_commitments_on_unpaid_invoices(self) -> None:
        self.ledger.add_invoice(Invoice("SYN-3003", 60_00, 4))
        self.ledger.add_invoice(Invoice("SYN-3004", 70_00, 5))
        self.ledger.add_invoice(Invoice("SYN-3005", 80_00, 6))
        missed = self.ledger.record_promise(
            PromiseToPay("SYN-3003", 60_00, date(2026, 10, 10))
        )
        self.ledger.record_promise(
            PromiseToPay("SYN-3003", 60_00, date(2026, 10, 12))
        )
        self.ledger.record_promise(
            PromiseToPay("SYN-3004", 70_00, date(2026, 10, 10))
        )
        self.ledger.record_promise(
            PromiseToPay("SYN-3005", 80_00, date(2026, 10, 13))
        )
        self.ledger.mark_invoice_paid("SYN-3004")

        self.assertEqual(self.ledger.list_missed_promises(date(2026, 10, 12)), [missed])


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

    def test_missed_command_lists_only_past_promises_on_unpaid_invoices(self) -> None:
        self.transport.handle_message("/invoice SYN-4003 10000 8")
        self.transport.handle_message("/invoice SYN-4004 10000 8")
        self.transport.handle_message("/promise SYN-4003 10000 2026-10-10")
        self.transport.handle_message("/promise SYN-4003 10000 2026-10-12")
        self.transport.handle_message("/promise SYN-4004 10000 2026-10-10")
        self.transport.handle_message("/paid SYN-4004")

        self.assertEqual(
            self.transport.handle_message("/missed 2026-10-12"),
            "Missed synthetic promises: #1 for synthetic invoice SYN-4003.",
        )

    def test_invalid_missed_command_requests_clarification(self) -> None:
        response = self.transport.handle_message("/missed 12-10-2026")

        self.assertIn("/missed <YYYY-MM-DD>", response)

    def test_report_command_exports_both_local_formats(self) -> None:
        self.transport.handle_message("/invoice SYN-4005 10000 8")
        with TemporaryDirectory() as output_directory:
            response = self.transport.handle_message(f"/report 2026-10-12 {output_directory}")

            self.assertIn("Saved local daily collections report:", response)
            self.assertTrue((Path(output_directory) / "collections-summary-2026-10-12.csv").exists())
            self.assertTrue((Path(output_directory) / "collections-summary-2026-10-12.html").exists())


class DailyCollectionsReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = LedgerRepository()
        self.addCleanup(self.ledger.close)

    def test_export_contains_actionable_unpaid_overdue_invoices_in_csv_and_html(self) -> None:
        self.ledger.add_invoice(Invoice("SYN-<5001>", 12_500, 9))
        self.ledger.add_invoice(Invoice("SYN-5002", 8_000, 4))
        self.ledger.add_invoice(Invoice("SYN-5003", 6_000, 3))
        self.ledger.add_invoice(Invoice("SYN-5004", 7_000, 0))
        self.ledger.record_promise(PromiseToPay("SYN-<5001>", 12_500, date(2026, 10, 10)))
        self.ledger.record_promise(PromiseToPay("SYN-5002", 8_000, date(2026, 10, 12)))
        self.ledger.mark_invoice_paid("SYN-5003")

        with TemporaryDirectory() as output_directory:
            html_path, csv_path = export_daily_collections_summary(
                self.ledger, date(2026, 10, 12), output_directory
            )

            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                report_rows = list(csv.DictReader(csv_file))
            html = html_path.read_text(encoding="utf-8")

        self.assertEqual(
            report_rows,
            [
                {
                    "report_date": "2026-10-12",
                    "invoice_reference": "SYN-<5001>",
                    "invoice_amount_cents": "12500",
                    "days_overdue": "9",
                    "promise_id": "1",
                    "promise_amount_cents": "12500",
                    "promise_due_on": "2026-10-10",
                    "status": "missed",
                },
                {
                    "report_date": "2026-10-12",
                    "invoice_reference": "SYN-5002",
                    "invoice_amount_cents": "8000",
                    "days_overdue": "4",
                    "promise_id": "2",
                    "promise_amount_cents": "8000",
                    "promise_due_on": "2026-10-12",
                    "status": "due today",
                },
            ],
        )
        self.assertIn(
            "Unpaid overdue invoices: 2; actionable rows: 2; missed commitments: 1; due today: 1.",
            html,
        )
        self.assertIn("SYN-&lt;5001&gt;", html)
        self.assertNotIn("SYN-5003", html)
        self.assertNotIn("SYN-5004", html)

    def test_export_keeps_unpromised_overdue_invoice_visible_for_follow_up(self) -> None:
        self.ledger.add_invoice(Invoice("SYN-5005", 9_000, 2))

        with TemporaryDirectory() as output_directory:
            _, csv_path = export_daily_collections_summary(
                self.ledger, date(2026, 10, 12), output_directory
            )
            with csv_path.open(newline="", encoding="utf-8") as csv_file:
                report_rows = list(csv.DictReader(csv_file))

        self.assertEqual(report_rows[0]["status"], "needs follow-up")
        self.assertEqual(report_rows[0]["promise_id"], "")


class DemoScenarioTests(unittest.TestCase):
    def test_seeded_demo_covers_queue_states_and_excludes_paid_work(self) -> None:
        ledger = LedgerRepository()
        self.addCleanup(ledger.close)
        as_of = date(2026, 10, 14)

        seed_demo_scenarios(ledger, as_of)

        self.assertEqual(
            [(row.invoice_reference, row.status) for row in ledger.list_daily_collections_rows(as_of)],
            [
                ("DEMO-1001", "missed"),
                ("DEMO-1002", "due today"),
                ("DEMO-1003", "upcoming"),
                ("DEMO-1004", "needs follow-up"),
            ],
        )
        self.assertTrue(ledger.get_invoice("DEMO-1005").paid)


if __name__ == "__main__":
    unittest.main()
