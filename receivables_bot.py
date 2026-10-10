"""Core types and SQLite storage for an offline, synthetic receivables workflow."""

from dataclasses import dataclass
from datetime import date
import sqlite3


@dataclass(frozen=True)
class Invoice:
    """A synthetic invoice represented in minor currency units."""

    reference: str
    amount_cents: int
    days_overdue: int
    paid: bool = False


@dataclass(frozen=True)
class PromiseToPay:
    """A synthetic commitment to pay all or part of an invoice by a date."""

    invoice_reference: str
    amount_cents: int
    due_on: date
    id: int | None = None


class LedgerRepository:
    """Persist synthetic invoices and payment promises in a local SQLite database.

    This repository deliberately has no network or external-system integration.
    """

    def __init__(self, database_path: str = ":memory:") -> None:
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.connection.close()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS invoices (
                reference TEXT PRIMARY KEY,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                days_overdue INTEGER NOT NULL CHECK (days_overdue >= 0),
                paid INTEGER NOT NULL CHECK (paid IN (0, 1)) DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS promises_to_pay (
                id INTEGER PRIMARY KEY,
                invoice_reference TEXT NOT NULL REFERENCES invoices(reference),
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                due_on TEXT NOT NULL
            );
            """
        )

    def add_invoice(self, invoice: Invoice) -> None:
        """Store one synthetic invoice without replacing an existing record."""
        if not invoice.reference.strip():
            raise ValueError("invoice reference must not be blank")
        if invoice.amount_cents <= 0:
            raise ValueError("invoice amount must be positive")
        if invoice.days_overdue < 0:
            raise ValueError("days overdue must not be negative")
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO invoices (reference, amount_cents, days_overdue, paid)
                VALUES (?, ?, ?, ?)
                """,
                (invoice.reference, invoice.amount_cents, invoice.days_overdue, int(invoice.paid)),
            )

    def get_invoice(self, reference: str) -> Invoice | None:
        """Return an invoice by its synthetic reference, if it exists."""
        row = self.connection.execute(
            """
            SELECT reference, amount_cents, days_overdue, paid
            FROM invoices WHERE reference = ?
            """,
            (reference,),
        ).fetchone()
        if row is None:
            return None
        return Invoice(row["reference"], row["amount_cents"], row["days_overdue"], bool(row["paid"]))

    def mark_invoice_paid(self, reference: str) -> bool:
        """Mark an existing invoice as paid and report whether it was found."""
        with self.connection:
            cursor = self.connection.execute(
                "UPDATE invoices SET paid = 1 WHERE reference = ?", (reference,)
            )
        return cursor.rowcount == 1

    def record_promise(self, promise: PromiseToPay) -> PromiseToPay:
        """Store a promise and return it with its generated local identifier."""
        if not promise.invoice_reference.strip():
            raise ValueError("promise invoice reference must not be blank")
        if promise.amount_cents <= 0:
            raise ValueError("promise amount must be positive")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO promises_to_pay (invoice_reference, amount_cents, due_on)
                VALUES (?, ?, ?)
                """,
                (promise.invoice_reference, promise.amount_cents, promise.due_on.isoformat()),
            )
        return PromiseToPay(promise.invoice_reference, promise.amount_cents, promise.due_on, cursor.lastrowid)

    def list_promises(self, invoice_reference: str | None = None) -> list[PromiseToPay]:
        """List recorded promises, optionally limited to one invoice."""
        statement = "SELECT id, invoice_reference, amount_cents, due_on FROM promises_to_pay"
        parameters: tuple[str, ...] = ()
        if invoice_reference is not None:
            statement += " WHERE invoice_reference = ?"
            parameters = (invoice_reference,)
        rows = self.connection.execute(statement + " ORDER BY id", parameters).fetchall()
        return [
            PromiseToPay(row["invoice_reference"], row["amount_cents"], date.fromisoformat(row["due_on"]), row["id"])
            for row in rows
        ]


class MockTelegramTransport:
    """Handle a small, local subset of Telegram-style collection commands.

    Messages are parsed locally and never leave the process. A message that is
    incomplete or unclear is rejected with the exact command format required;
    it must not create or change a ledger record.
    """

    HELP_TEXT = (
        "Commands: /invoice <reference> <amount_cents> <days_overdue>; "
        "/promise <invoice_reference> <amount_cents> <YYYY-MM-DD>; "
        "/paid <invoice_reference>. All data is synthetic and local."
    )

    def __init__(self, ledger: LedgerRepository) -> None:
        self.ledger = ledger

    def handle_message(self, message: str) -> str:
        """Process one local message and return a concise mock-chat response."""
        parts = message.strip().split()
        if not parts:
            return self._clarify()

        command = parts[0].lower()
        if command == "/help":
            return self.HELP_TEXT if len(parts) == 1 else self._clarify("/help")
        if command == "/invoice":
            return self._add_invoice(parts)
        if command == "/promise":
            return self._record_promise(parts)
        if command == "/paid":
            return self._mark_paid(parts)
        return self._clarify()

    def _add_invoice(self, parts: list[str]) -> str:
        if len(parts) != 4:
            return self._clarify("/invoice <reference> <amount_cents> <days_overdue>")
        try:
            invoice = Invoice(parts[1], int(parts[2]), int(parts[3]))
            self.ledger.add_invoice(invoice)
        except (ValueError, sqlite3.IntegrityError):
            return self._clarify("/invoice <reference> <positive amount_cents> <non-negative days_overdue>")
        return f"Saved synthetic invoice {invoice.reference}."

    def _record_promise(self, parts: list[str]) -> str:
        if len(parts) != 4:
            return self._clarify("/promise <invoice_reference> <amount_cents> <YYYY-MM-DD>")
        try:
            promise = PromiseToPay(parts[1], int(parts[2]), date.fromisoformat(parts[3]))
            saved = self.ledger.record_promise(promise)
        except (ValueError, sqlite3.IntegrityError):
            return self._clarify(
                "/promise <existing invoice_reference> <positive amount_cents> <YYYY-MM-DD>"
            )
        return f"Saved promise #{saved.id} for synthetic invoice {saved.invoice_reference}."

    def _mark_paid(self, parts: list[str]) -> str:
        if len(parts) != 2:
            return self._clarify("/paid <invoice_reference>")
        if not self.ledger.mark_invoice_paid(parts[1]):
            return "No synthetic invoice matches that reference; please check it and try again."
        return f"Marked synthetic invoice {parts[1]} as paid."

    def _clarify(self, format_hint: str | None = None) -> str:
        if format_hint is None:
            return f"I need a complete command before changing the ledger. {self.HELP_TEXT}"
        return f"I need a complete command before changing the ledger. Use {format_hint}."


def invoice_status(invoice: Invoice) -> str:
    """Return the current collection status for a synthetic invoice."""
    if invoice.paid:
        return "paid"
    if invoice.days_overdue > 0:
        return "overdue"
    return "current"
