"""PyTorch iterable dataset for bounded-memory PGN shard training."""

from __future__ import annotations

import re
import random
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Mapping

from torch.utils.data import IterableDataset, get_worker_info

from .stream import TrainingExample, iter_examples, open_pgn_text


KNOWN_SOURCES = ("lc0", "chessbench", "puzzle", "other")


class StreamingChessDataset(IterableDataset[TrainingExample]):
    """Read examples from shards while keeping only a shuffle buffer in memory.

    Files are first partitioned across DataLoader workers. This avoids every
    worker parsing the same games on Windows and keeps samples reproducible for
    a given seed.
    """

    def __init__(
        self,
        paths: Sequence[str | Path],
        *,
        shuffle_buffer: int = 10_000,
        max_games_per_file: int | None = None,
        standard_only: bool = True,
        seed: int = 17,
    ) -> None:
        super().__init__()
        self.paths = tuple(Path(path) for path in paths)
        if not self.paths:
            raise ValueError("at least one PGN shard is required")
        if shuffle_buffer < 1:
            raise ValueError("shuffle_buffer must be positive")
        self.shuffle_buffer = shuffle_buffer
        self.max_games_per_file = max_games_per_file
        self.standard_only = standard_only
        self.seed = seed

    def _worker_paths(self) -> tuple[Path, ...]:
        worker = get_worker_info()
        if worker is None:
            return self.paths
        selected = self.paths[worker.id :: worker.num_workers]
        if not selected:
            return ()
        return selected

    def __iter__(self) -> Iterator[TrainingExample]:
        worker = get_worker_info()
        worker_id = 0 if worker is None else worker.id
        rng = random.Random(self.seed + worker_id)
        paths = list(self._worker_paths())
        rng.shuffle(paths)
        if not paths:
            return

        buffer: list[TrainingExample] = []
        for example in iter_examples(
            paths,
            max_games_per_file=self.max_games_per_file,
            standard_only=self.standard_only,
        ):
            if len(buffer) < self.shuffle_buffer:
                buffer.append(example)
                continue
            index = rng.randrange(len(buffer))
            yield buffer[index]
            buffer[index] = example

        rng.shuffle(buffer)
        yield from buffer


def shard_paths(directory: str | Path) -> list[Path]:
    paths = sorted(Path(directory).glob("*.pgn.zst"))
    if not paths:
        raise FileNotFoundError(f"No .pgn.zst shards found in {directory}")
    return paths


def classify_shard(path: str | Path) -> str:
    """Classify a shard cheaply from its first PGN headers.

    The classification deliberately happens before full PGN parsing, so a
    30 GB dataset can be indexed in seconds rather than hours.
    """
    with open_pgn_text(path) as text:
        prefix = text.read(16_384)
    event = re.search(r'^\[Event "([^"]*)"\]', prefix, flags=re.MULTILINE)
    event_value = event.group(1).casefold() if event else ""
    if "lc0" in event_value:
        return "lc0"
    if "chessbench" in event_value:
        return "chessbench"
    if "puzzle" in event_value or "[Themes " in prefix:
        return "puzzle"
    return "other"


def group_shards_by_source(paths: Sequence[str | Path]) -> dict[str, list[Path]]:
    groups = {source: [] for source in KNOWN_SOURCES}
    for path in paths:
        path = Path(path)
        groups[classify_shard(path)].append(path)
    return groups


def parse_source_weights(specification: str) -> dict[str, float]:
    """Parse ``lc0=0.7,chessbench=0.2,puzzle=0.1`` and validate it."""
    weights: dict[str, float] = {}
    for entry in specification.split(","):
        key, separator, raw_value = entry.strip().partition("=")
        if not separator:
            raise ValueError(f"invalid source weight entry: {entry!r}")
        if key not in KNOWN_SOURCES:
            raise ValueError(f"unknown source {key!r}; expected one of {KNOWN_SOURCES}")
        value = float(raw_value)
        if value < 0:
            raise ValueError(f"source weight must be non-negative: {entry!r}")
        weights[key] = value
    if not weights or sum(weights.values()) <= 0:
        raise ValueError("at least one positive source weight is required")
    return weights


class SourceMixtureDataset(IterableDataset[TrainingExample]):
    """Infinite weighted mixture of source-specific streaming datasets.

    A source may be smaller than an Lc0 shard (notably puzzles). Once it is
    exhausted, only that source restarts with a fresh file order; other sources
    continue uninterrupted. This implements curriculum weights without
    materialising positions in a replay database.
    """

    def __init__(
        self,
        source_paths: Mapping[str, Sequence[str | Path]],
        weights: Mapping[str, float],
        *,
        shuffle_buffer: int = 10_000,
        max_games_per_file: int | None = None,
        seed: int = 17,
    ) -> None:
        super().__init__()
        self.source_paths = {source: tuple(Path(path) for path in paths) for source, paths in source_paths.items()}
        self.weights = {source: float(weight) for source, weight in weights.items() if weight > 0}
        missing = [source for source in self.weights if not self.source_paths.get(source)]
        if missing:
            raise ValueError(f"weighted sources have no shards: {', '.join(missing)}")
        self.shuffle_buffer = shuffle_buffer
        self.max_games_per_file = max_games_per_file
        self.seed = seed

    def _paths_for_worker(self, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        worker = get_worker_info()
        if worker is None:
            return paths
        return paths[worker.id :: worker.num_workers]

    def __iter__(self) -> Iterator[TrainingExample]:
        worker = get_worker_info()
        worker_id = 0 if worker is None else worker.id
        rng = random.Random(self.seed + worker_id)
        active = [
            source
            for source in self.weights
            if self._paths_for_worker(self.source_paths[source])
        ]
        if not active:
            return
        local_weights = [self.weights[source] for source in active]
        cycles = {source: 0 for source in active}
        iterators: dict[str, Iterator[TrainingExample]] = {}

        def new_iterator(source: str) -> Iterator[TrainingExample]:
            cycles[source] += 1
            return iter(
                StreamingChessDataset(
                    self._paths_for_worker(self.source_paths[source]),
                    shuffle_buffer=self.shuffle_buffer,
                    max_games_per_file=self.max_games_per_file,
                    seed=self.seed + worker_id + cycles[source] * 10_000,
                )
            )

        for source in active:
            iterators[source] = new_iterator(source)

        while True:
            source = rng.choices(active, weights=local_weights, k=1)[0]
            while True:
                try:
                    example = next(iterators[source])
                except StopIteration:
                    iterators[source] = new_iterator(source)
                    continue
                # A header-level group can still contain a rare mixed shard.
                # Never leak a different source into the requested mixture.
                if example.source == source:
                    yield example
                    break


class SelfPlayReplayDataset(IterableDataset[TrainingExample]):
    """Cycle compact `.npz` MCTS games without loading a global replay buffer."""

    def __init__(self, directory: str | Path, *, seed: int = 17) -> None:
        super().__init__()
        self.paths = tuple(sorted(Path(directory).glob("*.npz")))
        if not self.paths:
            raise FileNotFoundError(f"No self-play .npz shards found in {directory}")
        self.seed = seed

    def __iter__(self) -> Iterator[TrainingExample]:
        import numpy as np

        rng = random.Random(self.seed)
        paths = list(self.paths)
        while True:
            rng.shuffle(paths)
            for path in paths:
                with np.load(path) as replay:
                    states = replay["states"].astype(np.float32)
                    values = replay["values"].astype(np.float32)
                    offsets = replay["policy_offsets"]
                    actions = replay["policy_actions"]
                    visits = replay["policy_visits"]
                    for ply, state in enumerate(states):
                        start, end = int(offsets[ply]), int(offsets[ply + 1])
                        policy_actions = actions[start:end].astype(np.int16, copy=False)
                        policy_visits = visits[start:end].astype(np.float32, copy=False)
                        best = int(policy_actions[np.argmax(policy_visits)])
                        value = float(values[ply])
                        yield TrainingExample(
                            state=state,
                            action=best,
                            policy_action=best,
                            legal_actions=policy_actions,
                            value_target=value,
                            wdl_target=int(np.sign(value)),
                            source="selfplay",
                            game_id=path.stem,
                            ply=ply,
                            opening=None,
                            themes=(),
                            rating=None,
                            policy_actions=policy_actions,
                            policy_weights=policy_visits,
                        )


class WeightedIterableDataset(IterableDataset[TrainingExample]):
    """Infinite weighted mixture of arbitrary restartable iterable datasets."""

    def __init__(self, datasets: Mapping[str, IterableDataset[TrainingExample]], weights: Mapping[str, float], *, seed: int = 17) -> None:
        super().__init__()
        self.datasets = dict(datasets)
        self.weights = {name: float(weight) for name, weight in weights.items() if weight > 0}
        if not self.weights or any(name not in self.datasets for name in self.weights):
            raise ValueError("weights must name supplied datasets and include a positive value")
        self.seed = seed

    def __iter__(self) -> Iterator[TrainingExample]:
        rng = random.Random(self.seed)
        names = list(self.weights)
        weights = [self.weights[name] for name in names]
        iterators = {name: iter(self.datasets[name]) for name in names}
        while True:
            name = rng.choices(names, weights=weights, k=1)[0]
            try:
                yield next(iterators[name])
            except StopIteration:
                iterators[name] = iter(self.datasets[name])
                yield next(iterators[name])

