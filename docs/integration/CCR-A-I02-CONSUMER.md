# A-I02 consumer integration correction

Baseline B PR #31: 67b2848f6319d50355911a0800d3e7ecff02de59, merged locally
as 820f6b5. User authorized completing and testing the entire application;
these bounded B-area fixes are recorded explicitly rather than changing DTOs.

Public wire change: none. Migration: none. Generated GameSnapshotV1 stays
authoritative. UI-only profile labels, player orientation and pending-engine
state must be derived from selected options and snapshot.players/capabilities.
Do not require non-schema ai_profile/player_side/engine_pending fields from A.

Existing server profile IDs: beginner/casual/club/strong. They are bounded
Stockfish skill presets; no calibrated human Elo is promised. Readable cookie
mlchess_csrf (path=/, SameSite=Lax, Secure on HTTPS) maps to X-CSRF-Token;
session cookie is HttpOnly. This confirms CCR-B-I01-CSRF without a wire change.

Corrections: decode application/problem+json, retain timeout through body reads,
combine cancellation with timeout in real and test runtimes, use canonical UUID4
commands, poll durable GET while the worker is thinking, fence late replies,
allow solo takeback during engine work, and exclude live tests from mock suite.

Compatibility: no API/WS/schema changes. Existing clients accepting the
generated v1 remain compatible. Example: create returns players with one human
and one engine; side_to_move=engine side means pending until GET advances version.

Validation required: client error/timeout regressions, lint/build/unit suites,
separate mock and live Playwright, live Compose engine reply and takeback.
Status: validated locally: 47 web unit, 3 demo browser, 2 live Compose browser
tests PASS; build/lint PASS. No production signoff implied.

Private Compose uses explicit VITE_AUTH_MODE=development, not fake. It performs
real durable dev-login/me/logout against SQL; each browser login gets a distinct
display name. Both frontend build and backend settings forbid this in production.
The existing fake demo mode remains limited to isolated frontend demo tests.
