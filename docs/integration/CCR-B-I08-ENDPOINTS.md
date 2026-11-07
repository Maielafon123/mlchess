# CCR-B-I08 — Missing composed routes

The current `origin/main` generated contract exposes game creation, snapshots,
moves, takeback, analysis requests/results and `/api/v1/me`. The B UI still has
screens for resign/draw, invitations, matchmaking, coach requests and learning,
but those routes are not present in the composed app or generated A client.

B must not invent response DTOs or claim live support. A should publish and mount
the authoritative routes, schemas, authentication/CSRF rules and idempotency
semantics for:

- game resign/draw/claim actions;
- friend invitations and rated matchmaking;
- coach request/status and learning lesson/puzzle/progress APIs;
- `/ws/v1/games/{game_id}` event delivery.

Until then these screens remain demo/mock boundaries and are excluded from live
acceptance claims. `python -m infra.release_check` is expected to fail with the
missing surface.
