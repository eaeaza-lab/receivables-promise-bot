# Receivables Promise-to-Pay Bot — Specification

## Problem

Collections teams need a lightweight way to see which synthetic overdue invoices need attention, capture a customer's stated payment commitment, identify commitments that have passed without payment, and share a short daily summary. This project demonstrates that workflow offline through a Telegram-style mock transport.

## Target user

A collections specialist or operations lead evaluating a small internal workflow tool or SaaS prototype.

## MVP scope

- Store synthetic overdue invoices and promise-to-pay records in SQLite.
- Accept a small set of mock Telegram-style commands locally.
- Ask for clarification rather than creating an action from an ambiguous request.
- Detect promises past their due date when the associated invoice remains unpaid.
- Produce a concise daily collections report in HTML and CSV.
- State clearly when a requested external integration is unavailable; runtime network access is never used.

## Explicit non-goals

- Connecting to Telegram, accounting systems, payment gateways, CRMs, email, or any other external service.
- Handling real customer, company, account, invoice, or payment data.
- Authentication, multi-user permissions, background scheduling, or production deployment.
- Predicting payment outcomes or automating collection messages.

## Acceptance criteria

- The repository contains the required product documents and offline checker configuration. Check: `python -m unittest discover -s tests -v`
- The domain skeleton can classify an overdue synthetic invoice. Check: `python -m unittest discover -s tests -v`
- The project runs without third-party packages or network access. Check: `python app.py`
- The configured Nightshift check uses only an allowed command. Check: `python -m unittest discover -s tests -v`
