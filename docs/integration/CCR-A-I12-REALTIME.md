# A-I12: authenticated durable game stream

Base: e13d39920d2acc6c87cbff0242e463a530beba1d (learning PR42 in acceptance).
The user authorized finishing A/B integration and browser verification without
waiting for a separate human review. This record covers the B client integration.

Old: events.v1.yaml defines eight server event types, but no live WS endpoint.
Friend games poll REST; GameWebSocket is an unmounted transport helper.

New: `/ws/v1/games/{game_id}` accepts only a same-origin session cookie and a
single bounded `{"type":"subscribe","game_id":"<UUIDv4>","after_seq":0}`
message. The existing event schemas remain unchanged. Commands stay HTTP+CSRF.
No token is accepted in the URL. No migration or destructive transition.

Fresh subscriptions get a viewer-specific snapshot paired with the committed
event cursor under the same game row lock. Retained cursors replay ordered SQL
events in bounded batches, then tail the same durable log. There is no handoff
to a separate volatile fanout that could miss a commit. SQL polling is explicit;
Redis publish/subscribe is not claimed. No engine/provider runs under a lock.

Each batch rechecks the session and participant ACL. Active friend/rated games
never receive analysis/coach references. Personalized coach references remain
private even after a game finishes. If history is unavailable or contains frames
not visible to this viewer, send existing `replay_unavailable` resync control,
without disclosing references or silently skipping a sequence. The client must
reconnect with zero and adopt a new atomic snapshot/cursor pair.

Handshake rejection before accept is HTTP403. Accepted close codes:4401 session
expired/revoked,4403 participant denied,1008 malformed subscription/extra input,
1009 oversized input,1013 capacity,1012 retry from a fresh snapshot after resync,
1011 storage/server failure. Close reasons contain no raw exceptions or secrets.
Per-process caps and send/receive deadlines bound connections and slow clients.

Tests: exact fixture validation, missing/wrong Origin, anonymous/foreign/deleted
users, revoked active session, malformed cursor, ahead cursor, missing history,
private references, takeback revision, replay racing a real PostgreSQL commit,
two-browser live friend delivery, reconnect/reload, bounded resource cleanup.

Frontend handles snapshot/resync controls before durable sequence checks, ignores
duplicates, refreshes authorized REST after a contiguous event and recovers with
zero on a gap. Polling remains a slower fallback while transport reconnects.
Application gateway already proxies WS on /ws/; host/VPN networking is untouched.


The subscription now also has a generated GameSubscribeV1 schema/golden fixture.
The scaffold OpenAPI cookie name differs from the deployed mlchess_session.
Compatibility correctly prevents silently changing this v1 security scheme;
the production prefix migration belongs to A-I16 auth hardening. WS uses the
actual existing cookie and does not change authentication wire behavior here.
Explicit websockets17.4 and Uvicorn websockets protocol prevent
an optional dependency from leaving production without WS support. The maximum
incoming message is2048 bytes with a queue of4, and compression is disabled.
Upstream settings: https://uvicorn.dev/settings/ ; dependency release/security
notes: https://websockets.readthedocs.io/en/stable/project/changelog.html#id1
