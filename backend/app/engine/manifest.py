"""Build-time NNUE export and worker verification for factual engine metadata."""

import argparse
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

from backend.app.engine.adapter import EngineError, UciEngineAdapter, sha256_file


def create_manifest(binary: Path):
    # Export is an upstream Stockfish command, never a client-supplied command.
    with TemporaryDirectory(prefix="mlchess-nnue-") as directory:
        net = Path(directory) / "network.nnue"
        subprocess.run(
            [str(binary), "export_net", str(net)],
            check=True,
            timeout=15,
            capture_output=True,
        )
        if not net.is_file() or not 1_000_000 < net.stat().st_size < 200_000_000:
            raise EngineError("NNUE export is unavailable")
        model_hash = sha256_file(net)
    adapter = UciEngineAdapter(binary)
    try:
        return {
            "name": "stockfish",
            "version": adapter.identity(),
            "model_hash": model_hash,
            "binary_sha256": sha256_file(binary),
        }
    finally:
        adapter.stop()


def load_manifest(path: Path, adapter: UciEngineAdapter):
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        set(data) != {"name", "version", "model_hash", "binary_sha256"}
        or data["name"] != "stockfish"
    ):
        raise EngineError("Invalid engine manifest")
    if any(
        re.fullmatch(r"[a-f0-9]{64}", data[k]) is None
        for k in ("model_hash", "binary_sha256")
    ):
        raise EngineError("Invalid engine manifest hashes")
    if (
        data["binary_sha256"] != sha256_file(adapter.binary)
        or data["version"] != adapter.identity()
    ):
        raise EngineError("Engine manifest does not match the running binary")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--write", required=True, type=Path)
    args = parser.parse_args()
    args.write.write_text(
        json.dumps(create_manifest(args.binary), sort_keys=True), encoding="utf-8"
    )
