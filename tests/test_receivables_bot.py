import unittest

from receivables_bot import Invoice, invoice_status


class InvoiceStatusTests(unittest.TestCase):
    def test_unpaid_overdue_invoice_is_overdue(self) -> None:
        invoice = Invoice(reference="SYN-2001", amount_cents=50_00, days_overdue=3)

        self.assertEqual(invoice_status(invoice), "overdue")


if __name__ == "__main__":
    unittest.main()
