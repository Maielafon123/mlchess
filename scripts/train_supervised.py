"""Step-based supervised pretraining for the policy/Q/WDL network."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import torch
from torch.utils.data import DataLoader

from chess_ai.dataset import (
    SourceMixtureDataset,
    SelfPlayReplayDataset,
    WeightedIterableDataset,
    StreamingChessDataset,
    group_shards_by_source,
    parse_source_weights,
    shard_paths,
)
from chess_ai.evaluate import evaluate_batches
from chess_ai.model import PolicyValueNet, parameter_count
from chess_ai.training import collate_examples, policy_value_loss


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", type=Path, default=PROJECT_ROOT / "chess_data" / "train")
    parser.add_argument("--test-dir", type=Path, default=PROJECT_ROOT / "chess_data" / "test")
    parser.add_argument("--run-dir", type=Path, default=None, help="Default: runs/<timestamp>")
    parser.add_argument("--steps", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--shuffle-buffer", type=int, default=10_000)
    parser.add_argument(
        "--source-weights",
        default="lc0=0.7,chessbench=0.2,puzzle=0.1",
        help="Empty string disables source balancing; otherwise e.g. lc0=0.7,chessbench=0.2,puzzle=0.1",
    )
    parser.add_argument("--max-games-per-file", type=int, default=None)
    parser.add_argument("--selfplay-dir", type=Path, default=None, help="Directory of self-play .npz replay shards")
    parser.add_argument("--selfplay-ratio", type=float, default=0.0, help="Fraction of each train stream drawn from self-play")
    parser.add_argument("--max-eval-examples", type=int, default=50_000)
    parser.add_argument("--width", type=int, default=128)
    parser.add_argument("--blocks", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--warmup-steps", type=int, default=500)
    parser.add_argument("--eval-every", type=int, default=1_000)
    parser.add_argument("--checkpoint-every", type=int, default=1_000)
    parser.add_argument("--log-every", type=int, default=50)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--no-amp", action="store_true")
    parser.add_argument("--resume", type=Path, default=None)
    parser.add_argument("--init-checkpoint", type=Path, default=None, help="Initialize model weights only; start a new run with a fresh optimizer")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_loader(dataset: object, args: argparse.Namespace) -> DataLoader:
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        num_workers=args.workers,
        pin_memory=args.device.startswith("cuda"),
        collate_fn=collate_examples,
        persistent_workers=args.workers > 0,
    )


def learning_rate(step: int, args: argparse.Namespace) -> float:
    if step < args.warmup_steps:
        return args.lr * (step + 1) / max(args.warmup_steps, 1)
    progress = (step - args.warmup_steps) / max(args.steps - args.warmup_steps, 1)
    return args.lr * 0.5 * (1.0 + np.cos(np.pi * min(progress, 1.0)))


def save_checkpoint(path: Path, model: PolicyValueNet, optimizer: torch.optim.Optimizer, step: int, args: argparse.Namespace) -> None:
    torch.save(
        {
            "step": step,
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "args": vars(args),
        },
        path,
    )


def main() -> None:
    args = parse_args()
    if args.steps < 1:
        raise SystemExit("--steps must be positive")
    if args.resume and args.init_checkpoint:
        raise SystemExit("use either --resume or --init-checkpoint, not both")
    if not 0.0 <= args.selfplay_ratio < 1.0:
        raise SystemExit("--selfplay-ratio must be in [0, 1)")
    if args.selfplay_ratio and args.selfplay_dir is None:
        raise SystemExit("--selfplay-dir is required when --selfplay-ratio is positive")
    set_seed(args.seed)
    device = torch.device(args.device)
    if args.resume and args.run_dir is None:
        run_dir = args.resume.parent.parent
    else:
        run_dir = args.run_dir or PROJECT_ROOT / "runs" / datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.resume:
        if not run_dir.exists():
            raise SystemExit(f"resume run directory does not exist: {run_dir}")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "checkpoints").mkdir()
        (run_dir / "config.json").write_text(json.dumps(vars(args), default=str, indent=2), encoding="utf-8")
    (run_dir / "checkpoints").mkdir(exist_ok=True)

    train_paths = shard_paths(args.train_dir)
    if args.source_weights:
        source_weights = parse_source_weights(args.source_weights)
        source_paths = group_shards_by_source(train_paths)
        manifest = {source: [path.name for path in paths] for source, paths in source_paths.items()}
        (run_dir / "shard_sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        train_dataset = SourceMixtureDataset(
            source_paths,
            source_weights,
            shuffle_buffer=args.shuffle_buffer,
            max_games_per_file=args.max_games_per_file,
            seed=args.seed,
        )
        print("source_shards=" + json.dumps({source: len(paths) for source, paths in source_paths.items()}), flush=True)
    else:
        train_dataset = StreamingChessDataset(
            train_paths,
            shuffle_buffer=args.shuffle_buffer,
            max_games_per_file=args.max_games_per_file,
            seed=args.seed,
        )
    if args.selfplay_ratio:
        train_dataset = WeightedIterableDataset(
            {"supervised": train_dataset, "selfplay": SelfPlayReplayDataset(args.selfplay_dir, seed=args.seed + 31)},
            {"supervised": 1.0 - args.selfplay_ratio, "selfplay": args.selfplay_ratio},
            seed=args.seed + 53,
        )
        print(f"selfplay_ratio={args.selfplay_ratio} selfplay_dir={args.selfplay_dir}", flush=True)
    test_dataset = StreamingChessDataset(
        shard_paths(args.test_dir),
        shuffle_buffer=min(args.shuffle_buffer, 1_000),
        max_games_per_file=args.max_games_per_file,
        seed=args.seed + 1,
    )
    train_loader = make_loader(train_dataset, args)
    model = PolicyValueNet(width=args.width, blocks=args.blocks).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    start_step = 0
    if args.resume:
        checkpoint = torch.load(args.resume, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        start_step = int(checkpoint["step"])
    elif args.init_checkpoint:
        checkpoint = torch.load(args.init_checkpoint, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model"])

    print(f"run_dir={run_dir} device={device} parameters={parameter_count(model):,} start_step={start_step}", flush=True)
    log_path = run_dir / "metrics.jsonl"
    train_iter = iter(train_loader)
    amp = not args.no_amp and device.type == "cuda"
    rolling: list[float] = []

    for step in range(start_step + 1, args.steps + 1):
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)
        batch = batch.to(device)
        lr = learning_rate(step - 1, args)
        for group in optimizer.param_groups:
            group["lr"] = lr

        model.train()
        optimizer.zero_grad(set_to_none=True)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=amp):
            output = model(batch.state)
            loss = policy_value_loss(output, batch)
        loss.total.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        rolling.append(loss.total.item())

        if step % args.log_every == 0:
            payload = {
                "kind": "train",
                "step": step,
                "loss": float(np.mean(rolling)),
                "policy_loss": loss.policy.item(),
                "q_loss": loss.q_value.item(),
                "wdl_loss": loss.wdl.item(),
                "grad_norm": float(grad_norm),
                "lr": lr,
            }
            print(json.dumps(payload), flush=True)
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(payload) + "\n")
            rolling.clear()

        if step % args.eval_every == 0 or step == args.steps:
            eval_loader = make_loader(test_dataset, args)
            batches = []
            seen = 0
            for eval_batch in eval_loader:
                batches.append(eval_batch)
                seen += eval_batch.state.shape[0]
                if seen >= args.max_eval_examples:
                    break
            metrics = evaluate_batches(model, batches, device=device, amp=amp)
            payload = {"kind": "eval", "step": step, **asdict(metrics)}
            print(json.dumps(payload), flush=True)
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(payload) + "\n")

        if step % args.checkpoint_every == 0 or step == args.steps:
            save_checkpoint(run_dir / "checkpoints" / f"step-{step:07d}.pt", model, optimizer, step, args)
            save_checkpoint(run_dir / "checkpoints" / "latest.pt", model, optimizer, step, args)


if __name__ == "__main__":
    main()
