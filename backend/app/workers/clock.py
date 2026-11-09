"""Settle overdue games once, independently of browser or engine traffic."""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import func, select

from backend.app.games.durable import DurableGameService, read_clock
from backend.app.infra.db import create_engine, session_factory
from backend.app.infra.models import Game, GameState
from backend.app.infra.problems import PublicProblem
from backend.app.infra.settings import Settings


class ClockScheduler:
    def __init__(self, factory, *, now=None):
        self.factory, self.override_now = factory, now

    async def run_one(self) -> str | None:
        now = self.override_now or DurableGameService.now
        async with self.factory() as session, session.begin():
            cutoff = (
                func.clock_timestamp()
                if session.bind.dialect.name == "postgresql"
                and self.override_now is None
                else await now(session)
            )
            game = await session.scalar(
                select(Game)
                .where(
                    Game.status == "active",
                    Game.clock_deadline_at.is_not(None),
                    Game.clock_deadline_at <= cutoff,
                )
                .order_by(Game.clock_deadline_at, Game.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if game is None:
                return None
            state = await session.get(GameState, game.id)
            current_time = await now(session)
            try:
                domain = DurableGameService.checked_domain(game, state)
                clock = read_clock(state)
                deadline = clock.deadline if clock else None
                if domain.status != "active" or (
                    clock
                    and clock.running_side is not None
                    and (
                        clock.running_side != domain.side_to_move
                        or game.ply != domain.ply
                    )
                ):
                    raise ValueError("Invalid clock state")
            except (PublicProblem, ValueError, TypeError, KeyError, OverflowError):
                # Exclude a corrupt projection from the due index; never invent a result.
                # The durable board and clock are retained for repair and audit.
                game.clock_deadline_at = None
                return "quarantined"
            if deadline is not None and await DurableGameService.expire(
                session, game, state, domain, clock, current_time
            ):
                return "expired"
            DurableGameService.clock_projection(game, state, clock, current_time)
            return "reindexed"


async def run(settings: Settings, interval: float, once: bool) -> int:
    if not settings.database_url:
        return 1
    engine = create_engine(settings.database_url)
    try:
        scheduler = ClockScheduler(session_factory(engine))
        while True:
            async with asyncio.timeout(5):
                status = await scheduler.run_one()
            if status:
                print(
                    json.dumps({"event": "clock." + status}, separators=(",", ":")),
                    flush=True,
                )
            if once:
                return 0
            if status is None:
                await asyncio.sleep(interval)
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if not 0.05 <= args.poll_seconds <= 2:
        parser.error("poll interval must be 0.05–2 seconds")
    try:
        return asyncio.run(run(Settings(), args.poll_seconds, args.once))
    except KeyboardInterrupt:
        return 0
    except Exception:
        print('{"event":"clock.failed"}', flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
