# Execution Plan

## Milestones

- [x] **M0 setup** *(mvp)* -- Define the product, repository rules, offline checker, and executable skeleton. Acceptance: `python -m unittest discover -s tests -v`
- [x] **M1 SQLite ledger** *(mvp)* -- Add schema and repository operations for synthetic invoices and promises. Acceptance: `python -m unittest discover -s tests -v`
- [x] **M2 mock conversation** *(mvp)* -- Implement local Telegram-style command parsing and ambiguity validation. Acceptance: `python -m unittest discover -s tests -v`
- [x] **M3 commitment monitoring** *(mvp)* -- Identify missed promises against unpaid invoices. Acceptance: `python -m unittest discover -s tests -v`
- [x] **M4 reports** *(mvp)* -- Export the daily collections summary as HTML and CSV. Acceptance: `python -m unittest discover -s tests -v`
- [ ] **M5 demo polish** *(polish)* -- Add seeded demo scenarios, clearer CLI output, and usage examples. Acceptance: `python -m unittest discover -s tests -v`
- [ ] **M6 quality pass** *(polish)* -- Expand edge-case coverage and review documentation. Acceptance: `python -m unittest discover -s tests -v`

## Progress log

- 2026-10-05 -- M0 completed: created product specification, execution plan, repository guidance, checker configuration, and a passing offline skeleton test.
- 2026-10-09 -- M1 completed: added a local SQLite ledger for synthetic invoices and payment promises, including invoice payment updates and persistence coverage.
- 2026-10-10 -- M2 completed: added local Telegram-style invoice, promise, and payment commands with ambiguity validation that leaves the ledger unchanged.
- 2026-10-12 -- M3 completed: added local missed-promise monitoring that excludes paid invoices and distinguishes due-today commitments from missed ones.
- 2026-10-13 -- M4 completed: added local HTML and CSV daily collections exports for unpaid overdue synthetic invoices, including actionable promise states and a mock `/report` command.

## Decision log

- 2026-10-05 -- Use Python 3 standard library and SQLite to keep the prototype offline and portable.
- 2026-10-05 -- Use a mock Telegram-style transport rather than Telegram APIs to ensure synthetic, network-free operation.
- 2026-10-05 -- Treat unclear action requests as validation failures instead of guessing intent.
- 2026-10-09 -- Store promise due dates as ISO 8601 text so SQLite remains portable while Python converts them to `date` values at the repository boundary.
- 2026-10-10 -- Require slash-prefixed commands with fixed positional arguments; incomplete, unknown, or invalid commands ask for clarification instead of inferring an action.
- 2026-10-12 -- Treat a promise as missed only after its due date has passed; accept an explicit as-of date so local monitoring is deterministic and testable without a scheduler.
- 2026-10-13 -- Report one row per unpaid overdue invoice commitment (or one no-promise row) so the daily queue preserves every actionable commitment while still surfacing invoices that need follow-up.
- 2026-10-13 -- Name report files by their explicit as-of date and replace same-date exports, making repeated local report generation predictable.
