# Learning service boundary

The gateway sends `/api/v1/learning/*` to a separate ASGI process. In Compose
the core API does not mount those routes. The browser keeps a single origin
and the existing cookie, CSRF and public contracts. No data export or browser
storage migration is required.

Learning owns the catalog reads and mutations of learning progress. PostgreSQL
is shared for this stage so the current catalog and progress stay in place.
The dedicated `mlchess_learning` database login can read the two catalog
tables and read/write seven progress tables. It cannot list sessions or users,
read gameplay, issue a login, or access the Google secret. Authentication
uses a fixed, parameterized database function that returns an active principal
for a single known session hash. Expired, revoked and deleted principals are
rejected. A learning-scoped transaction lock serializes progress, receipt and
reset operations without locking gameplay rows.

The learning service has separate readiness, a connection pool capped at
five, a memory/CPU limit, and its own release override
(`MLCHESS_LEARNING_IMAGE_TAG`). Both service processes currently ship from the
same versioned Python image to share generated contracts and framework policy.
The gateway exposes no private port. In the VPS overlay learning listens only
on loopback port 58120. No new host firewall, bridge, VPN or published port is
needed.

Learning can be restarted or upgraded separately. A learning outage returns
a gateway error for learning routes while auth and games stay available.
CI proves this by stopping the disposable learning service and verifying
the core API, then restoring learning and checking authorization. Production
does not use the in-process learning fallback; standalone Python tests and
the loopback harness may use it. An application rollback can restore the
previous gateway and inline API while retaining the additive migration.

The core still owns auth, matchmaking and game commands, with independent
gameplay, clock, analysis and coach worker processes. This boundary does not
claim separate PostgreSQL servers or a production event broker.
