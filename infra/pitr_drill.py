"""Prove PostgreSQL 16 WAL recovery at a named point in isolated CI containers."""

from __future__ import annotations

import json
import subprocess
from time import monotonic, sleep
from uuid import uuid4

from infra.offsite_backup import PG_IMAGE

RESTORE_POINT = "mlchess_rehearsal"


def docker(*args):
    return subprocess.run(
        ["docker", *args], check=True, capture_output=True, timeout=90, text=True
    ).stdout.strip()


def ready(name):
    for _ in range(30):
        try:
            if docker("exec", name, "cat", "/proc/1/comm") == "postgres":
                docker("exec", name, "pg_isready", "-q", "-U", "postgres")
                return
        except subprocess.CalledProcessError:
            pass
        sleep(1)
    raise RuntimeError("PostgreSQL did not become ready")


def sql(name, value):
    return docker(
        "exec",
        name,
        "psql",
        "-XqAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-c",
        value,
    )


def main():
    identity = uuid4().hex
    source, target = (
        f"mlchess-pitr-source-{identity}",
        f"mlchess-pitr-target-{identity}",
    )
    wal = f"mlchess-pitr-wal-{identity}"
    containers = []
    docker("volume", "create", wal)
    common = (
        "--network",
        "none",
        "--tmpfs",
        "/var/lib/postgresql/data:size=256m,mode=0700",
        "-e",
        "POSTGRES_HOST_AUTH_METHOD=trust",
        "--memory",
        "512m",
    )
    try:
        docker(
            "run",
            "-d",
            "--name",
            source,
            *common,
            "-v",
            wal + ":/wal",
            PG_IMAGE,
            "postgres",
            "-c",
            "listen_addresses=",
            "-c",
            "wal_level=replica",
            "-c",
            "archive_mode=on",
            "-c",
            "archive_command=test -f /wal/%f || (cp %p /wal/%f.partial && mv /wal/%f.partial /wal/%f)",
        )
        containers.append(source)
        ready(source)
        docker("exec", "-u", "root", source, "chown", "postgres:postgres", "/wal")
        sql(source, "CREATE TABLE recovery_marker (value text PRIMARY KEY);")
        sql(source, "INSERT INTO recovery_marker VALUES ('before-base');")
        backup_start = monotonic()
        docker(
            "exec",
            "-u",
            "postgres",
            source,
            "pg_basebackup",
            "-U",
            "postgres",
            "-D",
            "/wal/base",
            "-X",
            "stream",
            "--checkpoint=fast",
        )
        backup_seconds = monotonic() - backup_start
        sql(source, "INSERT INTO recovery_marker VALUES ('after-base-before-target');")
        sql(source, f"SELECT pg_create_restore_point('{RESTORE_POINT}');")
        sql(source, "INSERT INTO recovery_marker VALUES ('after-target');")
        segment = sql(source, "SELECT pg_walfile_name(pg_current_wal_lsn());")
        sql(source, "SELECT pg_switch_wal();")
        for _ in range(30):
            try:
                docker("exec", source, "test", "-s", "/wal/" + segment)
                break
            except subprocess.CalledProcessError:
                sleep(1)
        else:
            raise RuntimeError("Target WAL segment was not archived")

        recovery_start = monotonic()
        startup = """
set -e
chown postgres:postgres "$PGDATA"
cp -a /wal/base/. "$PGDATA/"
cat >> "$PGDATA/postgresql.auto.conf" <<'EOF'
restore_command = 'cp /wal/%f %p'
recovery_target_name = 'mlchess_rehearsal'
recovery_target_action = 'promote'
EOF
touch "$PGDATA/recovery.signal"
chown postgres:postgres "$PGDATA/recovery.signal"
exec gosu postgres postgres -c listen_addresses= -c archive_mode=off
"""
        docker(
            "run",
            "-d",
            "--name",
            target,
            *common,
            "-v",
            wal + ":/wal:ro",
            "--entrypoint",
            "sh",
            PG_IMAGE,
            "-ec",
            startup,
        )
        containers.append(target)
        ready(target)
        for _ in range(30):
            if sql(target, "SELECT pg_is_in_recovery();") == "f":
                break
            sleep(1)
        else:
            raise RuntimeError(
                "Target never reached and promoted at the requested point"
            )
        result = sql(
            target,
            "SELECT json_build_object('promoted',NOT pg_is_in_recovery(),"
            "'markers',(SELECT json_agg(value ORDER BY value) FROM recovery_marker));",
        )
        restored = json.loads(result)
        if restored != {
            "promoted": True,
            "markers": ["after-base-before-target", "before-base"],
        }:
            raise RuntimeError("PITR failed to restore the exact named point")
        print(
            json.dumps(
                {
                    "status": "pitr_rehearsal_passed",
                    "scope": "disposable PostgreSQL WAL; not production offsite WAL or RPO",
                    "base_backup_seconds": round(backup_seconds, 3),
                    "restore_seconds": round(monotonic() - recovery_start, 3),
                    "restored": restored,
                }
            )
        )
    finally:
        for name in reversed(containers):
            docker("rm", "-f", name)
        docker("volume", "rm", wal)


if __name__ == "__main__":
    main()
