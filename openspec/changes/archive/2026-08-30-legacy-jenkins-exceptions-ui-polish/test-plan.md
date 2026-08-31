# Test plan

- `.venv/bin/ruff check .` exits 0.
- `.venv/bin/mypy app` exits 0 and reports success.
- `.venv/bin/pytest -q` exits 0 with all tests passed.
- Extracted inline JavaScript passes `node --check`.
- Playwright desktop/mobile smoke test produces screenshots without overflow.
- Live staged API returns 200 tickets, 4 eras, exact 3-name allowlist, and 100% v4/v5 replay.
