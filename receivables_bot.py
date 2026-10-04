"""Core types for an offline, synthetic receivables workflow."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Invoice:
    """A synthetic invoice represented in minor currency units."""

    reference: str
    amount_cents: int
    days_overdue: int
    paid: bool = False


def invoice_status(invoice: Invoice) -> str:
    """Return the current collection status for a synthetic invoice."""
    if invoice.paid:
        return "paid"
    if invoice.days_overdue > 0:
        return "overdue"
    return "current"
