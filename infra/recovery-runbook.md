# Recovery rehearsal

Run from the repository root against the local PostgreSQL 16 container:

```powershell
python -m infra.recovery_drill --container mlchess-postgres --user mlchess
```

The command creates two databases with fresh generated names, applies all
Alembic upgrade SQL, inserts a legal four-ply checkmate, backs it up using
`pg_dump -Fc`, restores using `pg_restore --exit-on-error`, and compares the
game result, FEN, complete move history, full domain state, exact command receipt,
game event, users, migration head and pending outbox. It removes only its
generated databases, including after a failure.
It does not connect to the application database or start workers.

The archive exists in process memory for this synthetic drill. It is not an
offsite backup. For deployment, configure encrypted daily backups and continuous
WAL archiving/PITR in the selected PostgreSQL platform, separate backup access
from application credentials, and rehearse restoration monthly in an isolated
environment with worker publishing disabled. Verify the latest restorable
timestamp and measure the complete outage/recovery interval before recording
production RPO/RTO. Record restore evidence without user data or secrets.

After restoring real data, reconcile durable jobs before enabling publishers.
Pending outbox rows survive this drill, but actual Redis redispatch and worker
dedup must be verified by the deployed job pipeline; the script explicitly
reports that check as unverified.

For rollback, first disable affected features and revert the application image
only if it remains compatible with the database schema. Use expand/contract
migrations: add nullable fields and compatible readers, backfill, then enforce
constraints/remove old readers in a later release. A backup restore can lose
writes after its recovery point and is not an automatic substitute for an
application rollback. Rotate application/backup credentials after a compromise,
revoke old sessions and verify access before resuming traffic.
