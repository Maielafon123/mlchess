# MLChess release runbook

## Local demo

```powershell
cd C:\Users\proebaldiplom\PycharmProjects\ML_course\PythonProject\chess\apps\web
pnpm install
pnpm dev
```

Demo routes:

- `/learn` — provenance-backed lesson catalog with local demo progress.
- `/learn/puzzles` — deterministic puzzle, progressive hints and verified replay.
- `/learn/progress` — progress dashboard demo.
- `/play`, `/play/ai`, `/play/coach`, `/play/friend`, `/play/matchmaking` — play-mode boundaries.

## Verification gates

```powershell
pnpm run typecheck
pnpm run test
pnpm run build
pnpm run test:e2e
python -m pytest -q
```

Backend-dependent modes must be checked again against A staging after generated
contracts, router mounting, auth, queues and persistence are deployed.

## Cloud coach privacy notice

Before enabling a cloud provider, tell the user that the coach request may send
position-derived data (FEN, move references, verified analysis facts, language
and selected learning level) to the configured provider. Do not send passwords,
access tokens, email addresses or raw private PGN annotations. The user must be
able to continue with deterministic fallback/local mode when cloud processing is
disabled. Provider model, prompt version, timeout and fallback status may be
visible in support diagnostics, but secrets must never be logged.

## Known limitations

- A staging two-browser smoke test is pending until A-015/A-016 and realtime
  game contracts are available.
- Demo progress is local and must be replaced by authenticated persistence.
- Temporary frontend types must be replaced by generated contract packages.
