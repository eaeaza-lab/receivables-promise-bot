# Future-session guide

## Commands

- Run the application: `python app.py`
- Run the test suite: `python -m unittest discover -s tests -v`

## Rules

- Keep all invoices, conversations, users, and organizations synthetic.
- Use Python's standard library and SQLite unless a dependency is explicitly justified.
- Do not add runtime network access, real integrations, secrets, lockfiles, or checksums.
- Preserve the mock transport and clearly communicate unavailable integrations.
- Add or update tests with behavior changes; run the test command before finishing.
- Keep `.nightshift.json` commands within the runner's allowed command prefixes and avoid shell wrappers.
