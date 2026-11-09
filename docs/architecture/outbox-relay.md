# Event relay and realtime delivery

Commands append domain events and an outbox row in the same PostgreSQL
transaction. The relay claims a bounded batch of committed unpublished rows
with `SKIP LOCKED`, writes metadata to a bounded Redis stream, and records
acknowledgement in PostgreSQL. Failure leaves the event in the queue.
Publish-before-ack crashes can cause duplicate Redis entries; each still
carries the same event ID. The relay role can read only outbox metadata and
update attempt and acknowledgement fields.

The public API uses the stream to wake a waiting game socket. Redis contains
no moves, engine results, private coach explanations, session or user data.
The socket always reauthorizes and reads the ordered durable SQL events.
Duplicate hints, Redis outages and trimmed streams do not change the public
event order or ACL. SQL polling continues when the stream is unavailable.
Game, clock, analysis and coach jobs remain recoverable from PostgreSQL.

The relay is a separate Compose service with its own connection limit,
health check and database password. The VPS uses the existing private
Redis and PostgreSQL loopback listeners. No new published port is required.
CI stops the isolated Redis container during a two-phone game, checks that
SQL retained unpublished events, restarts Redis and verifies recent
acknowledged event IDs in the transport. It does not restart the VPS broker.
