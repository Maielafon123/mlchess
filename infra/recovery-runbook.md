# PostgreSQL backup and recovery

Use the encrypted repository on a machine separate from the VPS. The Windows
wrapper creates a random restic repository password and protects it with DPAPI
under the current Windows user. Its default directory is
`%LOCALAPPDATA%\MLChess\Backups`. Restic encrypts every snapshot; pg_dump streams
through SSH and is never written as plaintext to the Windows filesystem.
Restrict access to the directory. Recovery on a different Windows profile needs
an independently recoverable repository password; arrange a second key in an
approved password vault before treating this as disaster recovery for loss of
both machines.

Install an official restic version with `--stdin-from-command` support and
verify its release checksum. With an already trusted SSH host key:

```powershell
$backupTool = 'C:\path\to\restic.exe'
$appServer = 'root@APP_HOST'
./infra/offsite_backup.ps1 -Action init -ResticPath $backupTool -SshTarget $appServer
./infra/offsite_backup.ps1 -Action backup -ResticPath $backupTool -SshTarget $appServer
./infra/offsite_backup.ps1 -Action verify -ResticPath $backupTool -SshTarget $appServer -Snapshot SNAPSHOT_ID
```

Initialize only once. Take a snapshot before every migration; take regular
additional snapshots according to the deployment's recovery objective.
The verify command runs a full authenticated repository check, streams the
chosen snapshot into an isolated disposable PostgreSQL 16 instance with no
network or ports and verifies application schema and aggregate counts. It never
restores into the live DB. Use a trusted restore host with the pinned
PostgreSQL image available; the drill is sized for this small installation.

Measured on 2026-11-09 UTC: production PostgreSQL snapshot window
01:02:08.611–01:02:12.488, about 3.9 s to encrypt and transfer 230,969 bytes;
15.1 s to launch the disposable database, restore and check migration 0007,
82 games, 168 moves, 373 events, 510 outbox records and 13 learning profiles.
This is a successful restore of a real off-VPS copy. The time measures the
database drill and excludes detection, DNS, application startup and cutover.

`python -m infra.pitr_drill` separately proves that PostgreSQL can restore a
physical base backup and archived WAL to an exact named restore point; it
creates only its own disposable containers and volume. Production continuous
PITR still requires a durable encrypted WAL target and independent retention.
Keep the archive target separate from the VPS, monitor successful archived WAL
and backup age, and prove recovery from a fresh machine before committing to an
RPO/RTO. Do not enable archiving to a single local disk with no remote consumer:
an outage in the archive command can make WAL exhaust the disk. A manual
snapshot window is evidence of snapshot age, not a continuous RPO.
