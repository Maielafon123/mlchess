from __future__ import annotations

from pathlib import Path

import zstandard as zstd
import numpy as np

from chess_ai.dataset import SelfPlayReplayDataset, SourceMixtureDataset, classify_shard, parse_source_weights


def write_shard(path: Path, event: str, moves: str) -> None:
    pgn = f'''[Event "{event}"]
[Result "1-0"]

{moves} 1-0
'''.encode()
    path.write_bytes(zstd.ZstdCompressor().compress(pgn))


def test_classify_shard_and_parse_weights(tmp_path: Path) -> None:
    lc0 = tmp_path / "lc0.pgn.zst"
    bench = tmp_path / "bench.pgn.zst"
    puzzle = tmp_path / "puzzle.pgn.zst"
    write_shard(lc0, "Lc0 Training Data", "1. e4 e5")
    write_shard(bench, "ChessBench", "1. e4")
    write_shard(puzzle, "40h puzzle", "1. e4 e5")

    assert classify_shard(lc0) == "lc0"
    assert classify_shard(bench) == "chessbench"
    assert classify_shard(puzzle) == "puzzle"
    assert parse_source_weights("lc0=0.7,chessbench=0.2,puzzle=0.1") == {
        "lc0": 0.7,
        "chessbench": 0.2,
        "puzzle": 0.1,
    }


def test_source_mixture_cycles_sources(tmp_path: Path) -> None:
    lc0 = tmp_path / "lc0.pgn.zst"
    puzzle = tmp_path / "puzzle.pgn.zst"
    write_shard(lc0, "Lc0 Training Data", "1. e4 e5")
    write_shard(puzzle, "40h puzzle", "1. d4 d5")
    dataset = SourceMixtureDataset(
        {"lc0": [lc0], "puzzle": [puzzle]},
        {"lc0": 0.5, "puzzle": 0.5},
        shuffle_buffer=1,
        seed=2,
    )
    iterator = iter(dataset)
    sources = [next(iterator).source for _ in range(8)]
    assert set(sources) == {"lc0", "puzzle"}


def test_selfplay_replay_dataset_reads_sparse_policy(tmp_path: Path) -> None:
    np.savez_compressed(
        tmp_path / "game-000000.npz",
        states=np.zeros((1, 20, 8, 8), dtype=np.float16),
        values=np.asarray([1.0], dtype=np.float32),
        policy_offsets=np.asarray([0, 2], dtype=np.int32),
        policy_actions=np.asarray([12, 44], dtype=np.int16),
        policy_visits=np.asarray([2, 5], dtype=np.int16),
    )
    example = next(iter(SelfPlayReplayDataset(tmp_path)))
    assert example.source == "selfplay"
    assert example.policy_action == 44
    assert example.policy_actions.tolist() == [12, 44]
    assert example.policy_weights.tolist() == [2.0, 5.0]
