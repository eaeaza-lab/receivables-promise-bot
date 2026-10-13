"""Core types and SQLite storage for an offline, synthetic receivables workflow."""

from dataclasses import dataclass
from datetime import date
import csv
from html import escape
from pathlib import Path
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


@dataclass(frozen=True)
class DailyCollectionsRow:
    """One actionable promise state for an unpaid, overdue synthetic invoice."""

    invoice_reference: str
    invoice_amount_cents: int
    days_overdue: int
    promise_id: int | None
    promise_amount_cents: int | None
    promise_due_on: date | None
    status: str


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

    def list_missed_promises(self, as_of: date) -> list[PromiseToPay]:
        """Return promises due before ``as_of`` whose invoices remain unpaid.

        A commitment due on the as-of date is still due, rather than missed.
        """
        rows = self.connection.execute(
            """
            SELECT promise.id, promise.invoice_reference, promise.amount_cents, promise.due_on
            FROM promises_to_pay AS promise
            JOIN invoices AS invoice ON invoice.reference = promise.invoice_reference
            WHERE promise.due_on < ? AND invoice.paid = 0
            ORDER BY promise.due_on, promise.id
            """,
            (as_of.isoformat(),),
        ).fetchall()
        return [
            PromiseToPay(row["invoice_reference"], row["amount_cents"], date.fromisoformat(row["due_on"]), row["id"])
            for row in rows
        ]

    def list_daily_collections_rows(self, as_of: date) -> list[DailyCollectionsRow]:
        """List actionable states for all unpaid synthetic overdue invoices.

        An invoice without a commitment remains visible as needing follow-up.
        Paid and current invoices are deliberately excluded from the daily queue.
        """
        rows = self.connection.execute(
            """
            SELECT invoice.reference, invoice.amount_cents AS invoice_amount_cents,
                   invoice.days_overdue, promise.id AS promise_id,
                   promise.amount_cents AS promise_amount_cents, promise.due_on
            FROM invoices AS invoice
            LEFT JOIN promises_to_pay AS promise ON promise.invoice_reference = invoice.reference
            WHERE invoice.paid = 0 AND invoice.days_overdue > 0
            ORDER BY invoice.days_overdue DESC, promise.id
            """
        ).fetchall()
        result = []
        for row in rows:
            due_on = date.fromisoformat(row["due_on"]) if row["due_on"] is not None else None
            if due_on is None:
                status = "needs follow-up"
            elif due_on < as_of:
                status = "missed"
            elif due_on == as_of:
                status = "due today"
            else:
                status = "upcoming"
            result.append(
                DailyCollectionsRow(
                    row["reference"],
                    row["invoice_amount_cents"],
                    row["days_overdue"],
                    row["promise_id"],
                    row["promise_amount_cents"],
                    due_on,
                    status,
                )
            )
        return result


def export_daily_collections_summary(
    ledger: LedgerRepository, as_of: date, output_directory: str | Path
) -> tuple[Path, Path]:
    """Write a local daily collection queue in both CSV and HTML formats.

    Files are named from the requested as-of date so rerunning a report replaces
    that date's local snapshot instead of accumulating anonymous exports.
    """
    directory = Path(output_directory)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / f"collections-summary-{as_of.isoformat()}.csv"
    html_path = directory / f"collections-summary-{as_of.isoformat()}.html"
    rows = ledger.list_daily_collections_rows(as_of)

    fieldnames = [
        "report_date",
        "invoice_reference",
        "invoice_amount_cents",
        "days_overdue",
        "promise_id",
        "promise_amount_cents",
        "promise_due_on",
        "status",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(_report_row_values(as_of, row))

    overdue_invoice_count = len({row.invoice_reference for row in rows})
    missed_count = sum(row.status == "missed" for row in rows)
    due_today_count = sum(row.status == "due today" for row in rows)
    html_rows = "\n".join(
        "<tr>"
        f"<td>{escape(str(values['invoice_reference']))}</td>"
        f"<td>{values['invoice_amount_cents']}</td>"
        f"<td>{values['days_overdue']}</td>"
        f"<td>{escape(str(values['promise_id']))}</td>"
        f"<td>{escape(str(values['promise_amount_cents']))}</td>"
        f"<td>{escape(str(values['promise_due_on']))}</td>"
        f"<td>{escape(str(values['status']))}</td>"
        "</tr>"
        for values in (_report_row_values(as_of, row) for row in rows)
    )
    html_path.write_text(
        "<!doctype html>\n"
        "<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Daily collections summary</title></head><body>\n"
        f"<h1>Daily collections summary — {as_of.isoformat()}</h1>\n"
        f"<p>Unpaid overdue invoices: {overdue_invoice_count}; "
        f"actionable rows: {len(rows)}; missed commitments: {missed_count}; "
        f"due today: {due_today_count}.</p>\n"
        "<table><thead><tr><th>Invoice</th><th>Invoice amount (cents)</th>"
        "<th>Days overdue</th><th>Promise ID</th><th>Promise amount (cents)</th>"
        "<th>Promise due</th><th>Status</th></tr></thead>\n"
        f"<tbody>{html_rows}</tbody></table>\n"
        "</body></html>\n",
        encoding="utf-8",
    )
    return html_path, csv_path


def _report_row_values(as_of: date, row: DailyCollectionsRow) -> dict[str, str | int]:
    """Convert an actionable row to the common CSV and HTML representation."""
    return {
        "report_date": as_of.isoformat(),
        "invoice_reference": row.invoice_reference,
        "invoice_amount_cents": row.invoice_amount_cents,
        "days_overdue": row.days_overdue,
        "promise_id": "" if row.promise_id is None else row.promise_id,
        "promise_amount_cents": "" if row.promise_amount_cents is None else row.promise_amount_cents,
        "promise_due_on": "" if row.promise_due_on is None else row.promise_due_on.isoformat(),
        "status": row.status,
    }


class MockTelegramTransport:
    """Handle a small, local subset of Telegram-style collection commands.

    Messages are parsed locally and never leave the process. A message that is
    incomplete or unclear is rejected with the exact command format required;
    it must not create or change a ledger record.
    """

    HELP_TEXT = (
        "Commands: /invoice <reference> <amount_cents> <days_overdue>; "
        "/promise <invoice_reference> <amount_cents> <YYYY-MM-DD>; "
        "/paid <invoice_reference>; /missed <YYYY-MM-DD>; "
        "/report <YYYY-MM-DD> <output_directory>. "
        "All data is synthetic and local."
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
        if command == "/missed":
            return self._list_missed_promises(parts)
        if command == "/report":
            return self._export_daily_report(parts)
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

    def _list_missed_promises(self, parts: list[str]) -> str:
        if len(parts) != 2:
            return self._clarify("/missed <YYYY-MM-DD>")
        try:
            missed = self.ledger.list_missed_promises(date.fromisoformat(parts[1]))
        except ValueError:
            return self._clarify("/missed <YYYY-MM-DD>")
        if not missed:
            return "No missed synthetic promises as of that date."
        references = ", ".join(
            f"#{promise.id} for synthetic invoice {promise.invoice_reference}"
            for promise in missed
        )
        return f"Missed synthetic promises: {references}."

    def _export_daily_report(self, parts: list[str]) -> str:
        if len(parts) != 3:
            return self._clarify("/report <YYYY-MM-DD> <output_directory>")
        try:
            report_date = date.fromisoformat(parts[1])
            html_path, csv_path = export_daily_collections_summary(self.ledger, report_date, parts[2])
        except (OSError, ValueError):
            return self._clarify("/report <YYYY-MM-DD> <writable_output_directory>")
        return f"Saved local daily collections report: {html_path} and {csv_path}."

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
