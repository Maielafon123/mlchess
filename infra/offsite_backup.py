"""Stream a PostgreSQL dump to encrypted restic storage and verify a safe restore."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import os
import re
import subprocess
from time import monotonic, sleep
from uuid import uuid4

TAG = "mlchess-postgresql"
ARCHIVE = "mlchess.dump"
PG_IMAGE = "postgres:16@sha256:f9a7b9ebf6f56201f949db745e47bc423c0f0f8294bafe991cc10bf74b029657"
FINGERPRINT = (
    "SELECT json_build_object("
    "'schema',(SELECT version_num FROM alembic_version),"
    "'games',(SELECT count(*) FROM games),"
    "'moves',(SELECT count(*) FROM game_moves),"
    "'events',(SELECT count(*) FROM game_events),"
    "'outbox',(SELECT count(*) FROM outbox_events),"
    "'rating_settlements',(SELECT count(*) FROM rating_settlements),"
    "'learning_profiles',(SELECT count(*) FROM learning_profiles));"
)


def iso_now():
    return datetime.now(timezone.utc).isoformat()


def emit(**result):
    print(json.dumps(result, sort_keys=True))


def command(argv, *, limit=60, quiet=True):
    return subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet else None,
        check=True,
        timeout=limit,
    ).stdout


def ssh(target, *command):
    return [
        "ssh",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=3",
        target,
        *command,
    ]


def make_backup(restic, source):
    before, start = iso_now(), monotonic()
    # --stdin-from-command avoids committing a snapshot if pg_dump/SSH exits
    # nonzero. Neither PowerShell nor a temporary file handles plaintext.
    result = command(
        [
            *restic,
            "backup",
            "--json",
            "--tag",
            TAG,
            "--stdin-filename",
            ARCHIVE,
            "--stdin-from-command",
            "--",
            *ssh(
                source,
                "docker",
                "exec",
                "mlchess-postgres-1",
                "pg_dump",
                "-U",
                "mlchess",
                "-d",
                "mlchess",
                "-Fc",
                "--lock-wait-timeout=5000",
            ),
        ],
        limit=900,
    )
    records = [json.loads(line) for line in result.splitlines()]
    summary = next(
        record
        for record in reversed(records)
        if record.get("message_type") == "summary"
    )
    snapshot = summary.get("snapshot_id", "")
    if not re.fullmatch(r"[0-9a-f]{8,64}", snapshot):
        raise ValueError("Backup did not produce a usable snapshot ID")
    emit(
        status="encrypted_backup_created",
        snapshot=snapshot,
        database_snapshot_window_start=before,
        database_snapshot_window_end=iso_now(),
        elapsed_seconds=round(monotonic() - start, 3),
        source_bytes=summary["total_bytes_processed"],
    )


def restore_drill(restic, destination, snapshot):
    if not re.fullmatch(r"[0-9a-f]{8,64}", snapshot):
        raise ValueError("Pass an explicit snapshot ID")
    matches = json.loads(command([*restic, "snapshots", "--json", "--tag", TAG]))
    (snapshot,) = [row["id"] for row in matches if row["id"].startswith(snapshot)]
    command([*restic, "check", "--read-data"], limit=900)
    name = "mlchess-restore-" + uuid4().hex
    target = ssh(destination)
    start = monotonic()
    container_started = False
    try:
        command(
            [
                *target,
                "docker",
                "run",
                "-d",
                "--rm",
                "--pull=never",
                "--name",
                name,
                "--network",
                "none",
                "--memory",
                "224m",
                "--cpus",
                "0.25",
                "--tmpfs",
                "/var/lib/postgresql/data:size=160m,mode=0700",
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e",
                "POSTGRES_DB=recovery",
                PG_IMAGE,
                "postgres",
                "-c",
                "listen_addresses=''",
            ]
        )
        container_started = True
        # The entrypoint starts a temporary server before switching to the real
        # one. Wait for PID 1's postgres (docker-entrypoint exec) plus readiness.
        ready = (
            f'test "$(docker exec {name} cat /proc/1/comm)" = postgres '
            f"&& docker exec {name} pg_isready -q -U postgres -d recovery"
        )
        for _ in range(30):
            try:
                command([*target, ready], limit=15)
                break
            except subprocess.CalledProcessError:
                sleep(1)
        else:
            raise RuntimeError("Disposable restore container did not become ready")

        with subprocess.Popen(
            [*restic, "dump", snapshot, "/" + ARCHIVE],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as dump:
            try:
                subprocess.run(
                    [
                        *target,
                        "docker",
                        "exec",
                        "-i",
                        name,
                        "pg_restore",
                        "-U",
                        "postgres",
                        "-d",
                        "recovery",
                        "--no-owner",
                        "--no-privileges",
                        "--single-transaction",
                        "--exit-on-error",
                    ],
                    stdin=dump.stdout,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=900,
                    check=True,
                )
            finally:
                dump.stdout.close()
                try:
                    result = dump.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    dump.kill()
                    raise
            if result:
                raise RuntimeError("Restic did not complete the snapshot stream")
        restored = json.loads(
            command(
                [
                    *target,
                    "docker",
                    "exec",
                    name,
                    "psql",
                    "-XqAt",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "postgres",
                    "-d",
                    "recovery",
                    "-c",
                    "'" + FINGERPRINT.replace("'", "'\"'\"'") + "'",
                ]
            )
        )
        if not restored.get("schema") or any(
            restored[key] < 0 for key in restored if key != "schema"
        ):
            raise RuntimeError(
                "Restored application schema or table counts are invalid"
            )
        emit(
            status="encrypted_snapshot_restore_verified",
            snapshot=snapshot,
            restored=restored,
            restore_seconds=round(monotonic() - start, 3),
            scope="disposable network-none PostgreSQL; no production cutover",
        )
    finally:
        if container_started:
            command([*target, "docker", "rm", "-f", name])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restic", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--ssh", dest="target", required=True)
    parser.add_argument("action", choices=("init", "backup", "verify"))
    parser.add_argument("--snapshot")
    args = parser.parse_args()
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+@[A-Za-z0-9][A-Za-z0-9_.-]{0,252}", args.target
    ):
        parser.error("Use a plain user@host for the application server")
    if not os.environ.get("RESTIC_PASSWORD"):
        parser.error("Supply the repository password via the protected wrapper")
    restic = [
        str(args.restic.resolve(strict=True)),
        "-r",
        str(args.repo.resolve()),
        "--no-cache",
    ]
    try:
        if args.action == "init":
            command([*restic, "init"])
            emit(status="encrypted_repository_initialized")
        elif args.action == "backup":
            make_backup(restic, args.target)
        else:
            if args.snapshot is None:
                parser.error("Restore verification requires --snapshot")
            restore_drill(restic, args.target, args.snapshot)
    except (
        OSError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
        KeyError,
        StopIteration,
    ) as error:
        # Do not echo commands, PostgreSQL diagnostics, or encrypted repository internals.
        parser.exit(1, f"Backup operation failed ({type(error).__name__}).\n")


if __name__ == "__main__":
    main()
