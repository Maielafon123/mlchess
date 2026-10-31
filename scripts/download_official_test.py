"""Download the small official test split beside the existing local train split."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = PROJECT_ROOT / "chess_data"


def main() -> None:
    path = snapshot_download(
        repo_id="KeithG33/ChessBot-Dataset",
        repo_type="dataset",
        allow_patterns=["test/*.pgn.zst"],
        local_dir=LOCAL_DIR,
    )
    test_files = sorted((Path(path) / "test").glob("*.pgn.zst"))
    total_bytes = sum(file.stat().st_size for file in test_files)
    print(f"Downloaded {len(test_files)} official test shards ({total_bytes / 1_000_000:.1f} MB) to {Path(path) / 'test'}")


if __name__ == "__main__":
    main()
