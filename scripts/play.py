"""Play a terminal game against a trained checkpoint using MCTS."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import chess
import torch

from chess_ai.mcts import MCTS
from chess_ai.model import PolicyValueNet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--human-color", choices=("white", "black"), default="white")
    parser.add_argument("--sims", type=int, default=128, help="MCTS simulations per engine move")
    parser.add_argument("--c-puct", type=float, default=1.5)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def load_model(checkpoint_path: Path, device: torch.device) -> PolicyValueNet:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    args = checkpoint.get("args", {})
    model = PolicyValueNet(width=int(args.get("width", 128)), blocks=int(args.get("blocks", 10))).to(device)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    return model


def parse_human_move(board: chess.Board, text: str) -> chess.Move:
    try:
        return board.parse_uci(text)
    except ValueError:
        return board.parse_san(text)


def main() -> None:
    args = parse_args()
    if args.sims < 1:
        raise SystemExit("--sims must be positive")
    device = torch.device(args.device)
    model = load_model(args.checkpoint, device)
    human = chess.WHITE if args.human_color == "white" else chess.BLACK
    search = MCTS(model, device, c_puct=args.c_puct)
    board = chess.Board()
    print("Введите UCI (e2e4) или SAN (e4, Nf3). Ctrl+C — выход.")

    while not board.is_game_over(claim_draw=True):
        print("\n" + str(board) + f"\nХод: {'белых' if board.turn else 'чёрных'}")
        if board.turn == human:
            while True:
                try:
                    move = parse_human_move(board, input("Ваш ход: ").strip())
                except ValueError as error:
                    print(f"Некорректный ход: {error}")
                    continue
                break
        else:
            move = search.choose_move(board, simulations=args.sims)
            print(f"Ход сети: {board.san(move)} ({move.uci()})")
        board.push(move)
    print("\n" + str(board))
    print("Результат:", board.result(claim_draw=True))


if __name__ == "__main__":
    main()
