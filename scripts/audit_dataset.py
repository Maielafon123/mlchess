"""Audit a bounded sample of compressed PGN shards before training."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

# Allow `python scripts/audit_dataset.py ...` without requiring an editable
# package installation first.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from chess_ai.stream import game_source, is_standard_game, iter_examples_from_game, iter_games


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_dir", type=Path, help="Directory containing *.pgn.zst shards")
    parser.add_argument("--max-files", type=int, default=3)
    parser.add_argument("--max-games-per-file", type=int, default=200)
    parser.add_argument("--max-examples", type=int, default=50_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = sorted(args.data_dir.glob("*.pgn.zst"))[: args.max_files]
    if not paths:
        raise SystemExit(f"No .pgn.zst shards found in {args.data_dir}")

    summary: dict[str, object] = {
        "files": [path.name for path in paths],
        "games": 0,
        "standard_games": 0,
        "skipped_variants": 0,
        "examples": 0,
        "sources": Counter(),
        "value_annotations": 0,
        "wdl_targets": 0,
        "themes": Counter(),
        "openings": Counter(),
    }
    value_ranges: dict[str, list[float]] = defaultdict(list)

    for path in paths:
        for game_index, game in enumerate(iter_games(path, max_games=args.max_games_per_file)):
            summary["games"] = int(summary["games"]) + 1
            if not is_standard_game(game):
                summary["skipped_variants"] = int(summary["skipped_variants"]) + 1
                continue
            summary["standard_games"] = int(summary["standard_games"]) + 1
            source = game_source(game)
            summary["sources"][source] += 1  # type: ignore[index]
            for example in iter_examples_from_game(game, game_id=f"{path.name}:{game_index}"):
                summary["examples"] = int(summary["examples"]) + 1
                if example.value_target not in (-1.0, 0.0, 1.0):
                    summary["value_annotations"] = int(summary["value_annotations"]) + 1
                if example.wdl_target is not None:
                    summary["wdl_targets"] = int(summary["wdl_targets"]) + 1
                value_ranges[example.source].append(example.value_target)
                summary["themes"].update(example.themes)  # type: ignore[index]
                if example.opening:
                    summary["openings"][example.opening] += 1  # type: ignore[index]
                if int(summary["examples"]) >= args.max_examples:
                    break
            if int(summary["examples"]) >= args.max_examples:
                break
        if int(summary["examples"]) >= args.max_examples:
            break

    output = {
        **summary,
        "sources": dict(summary["sources"]),
        "themes_top10": summary["themes"].most_common(10),
        "openings_top10": summary["openings"].most_common(10),
        "value_ranges": {
            source: {"min": min(values), "max": max(values), "count": len(values)}
            for source, values in value_ranges.items()
        },
    }
    output.pop("themes")
    output.pop("openings")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

