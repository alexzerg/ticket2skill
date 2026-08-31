# Test plan

- Ruff, mypy, pytest, JavaScript parse, and git diff checks pass.
- All three exact allowlist names route to CONTROLLED_EXCEPTION.
- jenkins-london and case-changed jenkins-nyc route to CURRENT_DEFAULT.
- Invalid controller syntax returns HTTP 422.
- Desktop and mobile browser interactions render without overflow.
- Live Cloud Run rebuild reaches replay 100% before router calls.
