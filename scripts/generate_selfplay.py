"""Generate policy-target replay games from a supervised checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import torch

from chess_ai.mcts import MCTS
from chess_ai.selfplay import play_selfplay_game, save_selfplay_game
from scripts.play import load_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--games", type=int, default=1)
    parser.add_argument("--sims", type=int, default=64)
    parser.add_argument("--max-plies", type=int, default=512)
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "artifacts" / "selfplay")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--live-file", type=Path, default=PROJECT_ROOT / "artifacts" / "live" / "latest.json")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.games < 1:
        raise SystemExit("--games must be positive")
    device = torch.device(args.device)
    model = load_model(args.checkpoint, device)
    search = MCTS(model, device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.live_file.parent.mkdir(parents=True, exist_ok=True)
    for index in range(args.games):
        def publish(event: dict) -> None:
            event["game"] = index
            temporary = args.live_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(event), encoding="utf-8")
            temporary.replace(args.live_file)

        game = play_selfplay_game(search, simulations=args.sims, max_plies=args.max_plies, seed=args.seed + index, on_move=publish)
        path = args.output_dir / f"game-{index:06d}.npz"
        save_selfplay_game(game, path)
        result = "draw" if game.winner is None else ("white" if game.winner else "black")
        print(f"game={index} plies={len(game.moves)} winner={result} path={path}", flush=True)


if __name__ == "__main__":
    main()
