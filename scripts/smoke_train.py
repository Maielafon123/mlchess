"""Run a bounded end-to-end policy/Q/WDL training smoke test."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import torch
from torch.utils.data import DataLoader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "data_dir", type=Path, help="Directory containing train .pgn.zst shards"
    )
    parser.add_argument("--examples", type=int, default=1024)
    parser.add_argument("--max-games-per-file", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--width", type=int, default=32)
    parser.add_argument("--blocks", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument(
        "--device", default="cuda" if torch.cuda.is_available() else "cpu"
    )
    return parser.parse_args()


def main() -> None:
    project_root = str(Path(__file__).resolve().parents[1])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from chess_ai.model import PolicyValueNet, parameter_count
    from chess_ai.stream import iter_examples
    from chess_ai.training import collate_examples, policy_value_loss

    args = parse_args()
    if min(args.examples, args.batch_size, args.epochs, args.width, args.blocks) < 1:
        raise SystemExit(
            "Examples, batch size, epochs, width and blocks must be positive"
        )
    paths = sorted(args.data_dir.glob("*.pgn.zst"))
    if not paths:
        raise SystemExit(f"No .pgn.zst shards found in {args.data_dir}")
    examples = list(
        iter_examples(
            paths,
            max_games_per_file=args.max_games_per_file,
            max_examples=args.examples,
        )
    )
    if len(examples) < args.batch_size:
        raise SystemExit(
            f"Only {len(examples)} usable examples; lower --batch-size or increase the sample"
        )

    device = torch.device(args.device)
    model = PolicyValueNet(width=args.width, blocks=args.blocks).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    loader = DataLoader(
        examples, batch_size=args.batch_size, shuffle=True, collate_fn=collate_examples
    )
    print(
        f"examples={len(examples)} device={device} parameters={parameter_count(model):,}"
    )

    for epoch in range(1, args.epochs + 1):
        model.train()
        totals = {"loss": 0.0, "policy": 0.0, "q": 0.0, "wdl": 0.0}
        for batch in loader:
            batch = batch.to(device)
            optimizer.zero_grad(set_to_none=True)
            output = model(batch.state)
            loss = policy_value_loss(output, batch)
            if not torch.isfinite(loss.total):
                raise RuntimeError("Smoke training produced a non-finite loss")
            loss.total.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(), max_norm=1.0, error_if_nonfinite=True
            )
            optimizer.step()
            totals["loss"] += loss.total.item()
            totals["policy"] += loss.policy.item()
            totals["q"] += loss.q_value.item()
            totals["wdl"] += loss.wdl.item()
        steps = len(loader)
        print(
            f"epoch={epoch} loss={totals['loss'] / steps:.4f} "
            f"policy={totals['policy'] / steps:.4f} q={totals['q'] / steps:.4f} wdl={totals['wdl'] / steps:.4f}"
        )


if __name__ == "__main__":
    main()
