# Guest challenge links (user priority 2026-11-08)

Explicit user request supersedes the old account-only FRIEND restriction.
Anonymous visitors receive real opaque SQL-backed guest sessions, not fake login.
Guests may play AI/coach and private unrated friend games. Rated remains account
only. Google OAuth remains a later independent feature, not a guest prerequisite.

Additive v1 wire proposal:
- POST /api/v1/auth/guest with empty JSON returns CurrentUserV1 and session/CSRF
  cookies. Reuses a valid existing session. Origin and resource limits apply.
- Existing POST /games accepts friend for a guest (behavior expands; no fields
  removed). POST /invitations {game_id} requires participant+creator ownership,
  CSRF and UUID4 idempotency key; only a waiting friend game is eligible.
- GET /invitations/{UUID} is creator/accepted-player scoped.
- POST /invitations/{UUID}/accept {token} requires a real guest/account session,
  CSRF and UUID4 idempotency key. Game lock + invitation lock atomically seat one
  opponent, start clock and record status event. Creator cannot occupy both seats.
  Same actor/key retries replay; a different actor cannot steal a consumed seat.

InviteSnapshotV1: schema_version, invite_id, game_id, state, expires_at,
created_by_current_user and nullable invite_url. GameSnapshotV1 remains the
source for board, moves, capabilities and clock. No invented online presence.
Share URL: /play/friend?invite=UUID#token=opaque43chars. Fragment prevents raw
tokens appearing in HTTP paths, access logs and Referer. Browser exchanges the
token via CSRF-protected POST only after establishing its guest session; GET
link previews cannot consume it. After join replace URL with game=UUID and
delete token from browser history; reopening with same session resumes the seat.

Only token hashes are stored in invitations. Token is HMAC-SHA256 over random
invitation UUID with a dedicated >=256-bit server secret; command receipts store
non-secret invitation metadata and reconstruct the creator URL at response time.
Rotating that secret invalidates old unused links (existing player sessions
continue working). Never log tokens, response URLs or settings. Link expires24h.
Guest session lasts7days; accepting a link requires no account or login form.

Database migration: existing invitations table is sufficient; transactional
game/player/receipt/event tables already deployed. No destructive schema change.
Compatibility: existing game DTO unchanged; add generated schemas/routes/fixtures.
Frontend B boundary updated explicitly under user's whole-project authorization.

Required tests: expiry, no CSRF/origin, malformed tokens, exact retries, conflicting
keys, own accept, third-user stealing, concurrent accepts, restart persistence,
active PvP coach/takeback denial, two mobile browsers exchanging legal moves and
refreshing without losing the seat. Public preview disables dev auth and serves
static assets via publicly trusted HTTPS on the supplied VPS IP. WireGuard stays
untouched. Full release signoff remains separate from this guest preview.
