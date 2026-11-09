"""PostgreSQL game transactions: history, receipt, event and outbox commit together."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import chess
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.games.clocks import ServerClock
from backend.app.games.domain import (
    GameDomain,
    GameError,
    IllegalMove,
    Mode,
    MoveRecord,
)
from backend.app.infra.generated.contracts import GameEventV1, GameSnapshotV1
from backend.app.infra.models import (
    CommandReceipt,
    Game,
    GameEvent,
    GameMove,
    GamePlayer,
    GameState,
    OutboxEvent,
    User,
    WorkerJob,
)
from backend.app.infra.problems import PublicProblem


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def encode_domain(game: GameDomain) -> dict:
    return {
        "mode": game.mode.value,
        "initial_fen": game.initial_fen,
        "moves": [asdict(move) for move in game.moves],
        "version": game.version,
        "result": game.result,
        "termination": game.termination,
        "draw_offer": game.draw_offer,
        "revision": game.revision,
        "archived_lines": [
            [asdict(move) for move in line] for line in game.archived_lines
        ],
    }


def decode_domain(payload: dict) -> GameDomain:
    return GameDomain(
        **{
            **payload,
            "moves": tuple(MoveRecord(**move) for move in payload["moves"]),
            "archived_lines": tuple(
                tuple(MoveRecord(**m) for m in line)
                for line in payload["archived_lines"]
            ),
        }
    )


def decode_clock(
    payload: dict | None, observed_at: datetime | None = None
) -> ServerClock | None:
    if payload is None:
        return None
    return ServerClock(
        **{
            **payload,
            "anchor": datetime.fromisoformat(payload["anchor"])
            if payload["anchor"]
            else None,
            "observed_at": observed_at.replace(tzinfo=timezone.utc)
            if observed_at is not None and observed_at.tzinfo is None
            else observed_at,
        }
    )


def encode_clock(clock: ServerClock | None) -> dict | None:
    if clock is None:
        return None
    # Keep the pre-migration clock JSON shape for rollback and archived lines.
    return {
        "white_remaining_ms": clock.white_remaining_ms,
        "black_remaining_ms": clock.black_remaining_ms,
        "increment_ms": clock.increment_ms,
        "running_side": clock.running_side,
        "anchor": iso(clock.anchor) if clock.anchor else None,
    }


def read_clock(state: GameState) -> ServerClock | None:
    return decode_clock(state.clock, state.clock_observed_at)


def public_clock(clock: ServerClock | None, now: datetime) -> dict | None:
    return (
        None
        if clock is None
        else {
            "white_remaining_ms": clock.remaining(chess.WHITE, now=now),
            "black_remaining_ms": clock.remaining(chess.BLACK, now=now),
            "running_side": None
            if clock.running_side is None
            else ("white" if clock.running_side else "black"),
            "server_now": iso(clock.effective_time(now)),
        }
    )


def fingerprint(operation: str, payload: dict) -> str:
    return hashlib.sha256(
        json.dumps([operation, payload], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class DurableGameService:
    def __init__(self, factory: async_sessionmaker[AsyncSession]):
        self.factory = factory

    @staticmethod
    async def now(session: AsyncSession) -> datetime:
        if session.bind.dialect.name == "postgresql":
            # CURRENT_TIMESTAMP is transaction start time, possibly before a lock wait.
            return await session.scalar(select(func.clock_timestamp()))
        return datetime.now(timezone.utc)

    @staticmethod
    async def lock_actor(session: AsyncSession, actor_id: UUID) -> None:
        user = await session.scalar(
            select(User)
            .where(User.id == actor_id, User.deleted_at.is_(None))
            .with_for_update()
        )
        if user is None:
            raise PublicProblem(401)

    @staticmethod
    async def receipt(
        session: AsyncSession,
        actor_id: UUID,
        key: UUID,
        request_hash: str,
        scope: str = "create",
    ) -> dict | None:
        prior = await session.get(CommandReceipt, (actor_id, scope, key))
        if prior is not None:
            if prior.request_hash != request_hash:
                raise PublicProblem(409)
            return prior.response
        return None

    @staticmethod
    def remember(
        session: AsyncSession,
        actor_id: UUID,
        key: UUID,
        request_hash: str,
        game_id: UUID,
        response: dict,
        scope: str = "create",
    ) -> None:
        session.add(
            CommandReceipt(
                actor_id=actor_id,
                scope=scope,
                command_key=key,
                request_hash=request_hash,
                game_id=game_id,
                response=response,
            )
        )

    @staticmethod
    async def load(
        session: AsyncSession, game_id: UUID, actor_id: UUID, *, lock: bool = False
    ):
        query = select(Game).where(Game.id == game_id)
        game = await session.scalar(query.with_for_update() if lock else query)
        if game is None:
            raise PublicProblem(404)
        players = list(
            (
                await session.scalars(
                    select(GamePlayer)
                    .where(GamePlayer.game_id == game_id)
                    .order_by(GamePlayer.side.desc())
                )
            ).all()
        )
        if actor_id not in {p.user_id for p in players}:
            raise PublicProblem(403)
        state = await session.get(GameState, game_id)
        DurableGameService.checked_domain(game, state)
        return game, state, players

    @staticmethod
    def checked_domain(game, state):
        if state is None:
            # Legacy baseline rows need an audited import, never infer lost history from FEN.
            raise PublicProblem(503)
        domain = decode_domain(state.domain)
        if (domain.mode.value, domain.version, domain.revision, domain.fen) != (
            game.mode,
            game.version,
            game.revision,
            game.fen,
        ):
            raise PublicProblem(503)
        return domain

    @staticmethod
    def snapshot(
        game: Game,
        state: GameState,
        players: list[GamePlayer],
        actor_id: UUID,
        now: datetime,
    ) -> dict:
        domain = decode_domain(state.domain)
        side = "white" if domain.side_to_move else "black"
        own_side = next(p.side for p in players if p.user_id == actor_id)
        active = game.status == "active"
        payload = {
            "schema_version": 1,
            "id": str(game.id),
            "mode": game.mode,
            "status": game.status,
            "version": domain.version,
            "revision": domain.revision,
            "fen": domain.fen,
            "ply": domain.ply,
            "side_to_move": side,
            "players": [
                {
                    "side": p.side,
                    "kind": p.kind,
                    "user_id": str(p.user_id) if p.user_id else None,
                }
                for p in players
            ],
            "moves": [asdict(m) for m in domain.moves],
            "time_control": state.config["time_control"],
            "clock": public_clock(read_clock(state), now),
            "capabilities": {
                "can_move": active and own_side == side,
                "can_takeback": active
                and game.mode in {"ai", "coach"}
                and domain.ply > 0,
                "can_analyze_now": active
                and game.mode in {"ai", "coach"}
                or game.status == "finished",
            },
            "result": domain.result,
            "termination": domain.termination,
        }
        return GameSnapshotV1.model_validate(payload).model_dump(mode="json")

    @staticmethod
    def save(
        game: Game,
        state: GameState,
        domain: GameDomain,
        clock: ServerClock | None,
        now: datetime,
    ) -> None:
        state.domain, state.clock = encode_domain(domain), encode_clock(clock)
        game.version, game.revision, game.fen, game.ply = (
            domain.version,
            domain.revision,
            domain.fen,
            domain.ply,
        )
        game.side_to_move = "white" if domain.side_to_move else "black"
        game.result, game.termination, game.updated_at = (
            domain.result,
            domain.termination,
            now,
        )
        game.status = domain.status
        DurableGameService.clock_projection(game, state, clock, now)

    @staticmethod
    def clock_projection(game, state, clock, now):
        game.clock_deadline_at = (
            clock.deadline if clock and game.status == "active" else None
        )
        state.clock_observed_at = clock.effective_time(now) if clock else None

    @classmethod
    def observe_clock(cls, game, state, now):
        clock = read_clock(state)
        if clock is not None and game.status == "active":
            if clock.running_side != (game.side_to_move == "white"):
                raise PublicProblem(503)
            cls.clock_projection(game, state, clock, now)

    @classmethod
    def expire(cls, session, game, state, domain, clock, now):
        if game.status != "active" or clock is None or clock.deadline is None:
            return False
        now = clock.effective_time(now)
        if now < clock.deadline:
            return False
        if clock.running_side != domain.side_to_move:
            raise PublicProblem(503)
        stopped = clock.stop(now)
        cls.save(game, state, domain.timeout(loser=clock.running_side), stopped, now)
        cls.status_event(session, game, state, stopped, now)
        return True

    @staticmethod
    def event(
        session: AsyncSession,
        game: Game,
        state: GameState,
        kind: str,
        payload: dict,
        now: datetime,
    ) -> None:
        state.event_seq += 1
        event_id = uuid4()
        envelope = GameEventV1.model_validate(
            {
                "schema_version": 1,
                "event_id": str(event_id),
                "game_id": str(game.id),
                "seq": state.event_seq,
                "type": kind,
                "occurred_at": iso(now),
                "payload": payload,
            }
        ).model_dump(mode="json")
        session.add(
            GameEvent(
                id=event_id,
                game_id=game.id,
                seq=state.event_seq,
                event_type=kind,
                payload=envelope,
                created_at=now,
            )
        )
        session.add(
            OutboxEvent(
                id=event_id,
                aggregate_type="game",
                aggregate_id=game.id,
                event_type=kind,
                payload=envelope,
                created_at=now,
            )
        )

    @classmethod
    def status_event(cls, session, game, state, clock, now):
        cls.clock_projection(game, state, clock, now)
        cls.event(
            session,
            game,
            state,
            "game.status_changed",
            {
                "version": game.version,
                "revision": game.revision,
                "status": game.status,
                "result": game.result,
                "termination": game.termination,
                "clock": public_clock(clock, now),
            },
            now,
        )

    @staticmethod
    async def enqueue_engine(session, game, players, now):
        side = game.side_to_move
        if (
            game.status == "active"
            and game.mode in {"ai", "coach"}
            and any(p.side == side and p.kind == "engine" for p in players)
        ):
            event = OutboxEvent(
                id=uuid4(),
                aggregate_type="game",
                aggregate_id=game.id,
                event_type="gameplay.move_requested",
                created_at=now,
                payload={
                    "game_id": str(game.id),
                    "version": game.version,
                    "revision": game.revision,
                },
            )
            session.add(event)
            await session.flush([event])
            session.add(
                WorkerJob(
                    id=event.id,
                    game_id=game.id,
                    queue="gameplay",
                    expected_version=game.version,
                    revision=game.revision,
                    available_at=now,
                    created_at=now,
                )
            )

    async def create(self, actor_id: UUID, key: UUID, payload: dict) -> dict:
        request_hash = fingerprint("create", payload)
        async with self.factory() as session, session.begin():
            await self.lock_actor(session, actor_id)
            cached = await self.receipt(session, actor_id, key, request_hash)
            if cached is not None:
                return cached
            now = await self.now(session)
            # SQL serialization keeps guest resource quotas safe across API replicas.
            if session.bind.dialect.name == "postgresql":
                await session.execute(select(func.pg_advisory_xact_lock(750120261108)))
            own_active = await session.scalar(
                select(func.count())
                .select_from(Game)
                .join(GamePlayer)
                .where(
                    GamePlayer.user_id == actor_id,
                    Game.status.in_(["waiting", "active"]),
                )
            )
            recent_active = await session.scalar(
                select(func.count())
                .select_from(Game)
                .where(
                    Game.status.in_(["waiting", "active"]),
                    Game.created_at > now - timedelta(days=1),
                )
            )
            if own_active >= 20 or recent_active >= 500:
                raise PublicProblem(429)
            mode = Mode(payload["mode"])
            domain = GameDomain.start(mode)
            game = Game(
                id=uuid4(),
                mode=mode.value,
                status="waiting" if mode == Mode.FRIEND else "active",
                version=0,
                revision=0,
                fen=domain.fen,
                ply=0,
                side_to_move="white",
                created_at=now,
                updated_at=now,
            )
            config = {**payload, "clock_history": []}
            tc = payload["time_control"]
            clock = (
                ServerClock(
                    tc["initial_ms"],
                    tc["initial_ms"],
                    tc["increment_ms"],
                    None if mode == Mode.FRIEND else chess.WHITE,
                    now,
                )
                if tc
                else None
            )
            state = GameState(
                game_id=game.id,
                domain=encode_domain(domain),
                config=config,
                clock=encode_clock(clock),
                event_seq=0,
            )
            human_side = payload.get("human_color", "white")
            players = [
                GamePlayer(
                    game_id=game.id,
                    side=human_side,
                    kind="human",
                    user_id=actor_id,
                    joined_at=now,
                )
            ]
            if mode != Mode.FRIEND:
                players.append(
                    GamePlayer(
                        game_id=game.id,
                        side="black" if human_side == "white" else "white",
                        kind="engine",
                        joined_at=now,
                    )
                )
            session.add(game)
            await session.flush()
            session.add_all([state, *players])
            self.status_event(session, game, state, clock, now)
            await self.enqueue_engine(session, game, players, now)
            response = self.snapshot(game, state, players, actor_id, now)
            await session.flush()
            self.remember(session, actor_id, key, request_hash, game.id, response)
        return response

    async def get(self, game_id: UUID, actor_id: UUID) -> dict:
        async with self.factory() as session, session.begin():
            game, state, players = await self.load(
                session, game_id, actor_id, lock=True
            )
            now = await self.now(session)
            self.observe_clock(game, state, now)
            return self.snapshot(game, state, players, actor_id, now)

    async def command(
        self, game_id: UUID, actor_id: UUID, key: UUID, operation: str, payload: dict
    ) -> dict:
        request_hash = fingerprint(operation, {"game_id": str(game_id), **payload})
        timed_out = False
        async with self.factory() as session, session.begin():
            await self.lock_actor(session, actor_id)
            game, state, players = await self.load(
                session, game_id, actor_id, lock=True
            )
            cached = await self.receipt(
                session, actor_id, key, request_hash, str(game_id)
            )
            if cached is not None:
                return cached
            if operation == "takeback" and game.mode not in {"ai", "coach"}:
                raise PublicProblem(403)
            if game.status != "active":
                raise PublicProblem(409)
            now = await self.now(session)
            domain = decode_domain(state.domain)
            clock = read_clock(state)
            if clock:
                now = clock.effective_time(now)
            color = next(p.side == "white" for p in players if p.user_id == actor_id)
            if self.expire(session, game, state, domain, clock, now):
                timed_out = True
            else:
                try:
                    if operation == "move":
                        updated = domain.play(
                            actor=color,
                            uci=payload["uci"],
                            expected_version=payload["expected_version"],
                        )
                    elif operation == "takeback":
                        updated = domain.takeback(
                            actor=color,
                            expected_version=payload["expected_version"],
                            plies=payload["plies"],
                        )
                    else:
                        method = {
                            "resign": domain.resign,
                            "draw-offer": domain.offer_draw,
                            "accept-draw": domain.accept_draw,
                            "claim-draw": domain.claim_draw,
                        }[operation]
                        updated = method(
                            actor=color, expected_version=payload["expected_version"]
                        )
                except IllegalMove:
                    raise PublicProblem(422) from None
                except GameError:
                    raise PublicProblem(409) from None
                config = {
                    **state.config,
                    "clock_history": list(state.config["clock_history"]),
                }
                if operation == "move":
                    config["clock_history"].append(state.clock)
                    if clock:
                        clock = clock.after_legal_move(actor=color, server_now=now)
                    move = updated.moves[-1]
                    session.add(
                        GameMove(
                            game_id=game.id,
                            actor_id=actor_id,
                            client_move_id=key,
                            expected_version=domain.version,
                            version=updated.version,
                            ply=updated.ply,
                            revision=updated.revision,
                            uci=move.uci,
                            san=move.san,
                            fen_after=updated.fen,
                            created_at=now,
                        )
                    )
                elif operation == "takeback":
                    index = len(config["clock_history"]) - payload["plies"]
                    clock = decode_clock(config["clock_history"][index])
                    config["clock_history"] = config["clock_history"][:index]
                    if clock:
                        clock = replace(
                            clock, running_side=updated.side_to_move, anchor=now
                        )
                if updated.result is not None and clock:
                    clock = clock.stop(now)
                state.config = config
                self.save(game, state, updated, clock, now)
                common = {
                    "version": updated.version,
                    "fen": updated.fen,
                    "side_to_move": "white" if updated.side_to_move else "black",
                    "clock": public_clock(clock, now),
                }
                if operation == "move":
                    self.event(
                        session,
                        game,
                        state,
                        "game.move_committed",
                        {
                            **common,
                            "revision": updated.revision,
                            "move": asdict(updated.moves[-1]),
                        },
                        now,
                    )
                elif operation == "takeback":
                    self.event(
                        session,
                        game,
                        state,
                        "game.takeback_applied",
                        {
                            **common,
                            "from_ply": domain.ply,
                            "to_ply": updated.ply,
                            "new_revision": updated.revision,
                        },
                        now,
                    )
                if operation not in {"move", "takeback"} or updated.result is not None:
                    self.status_event(session, game, state, clock, now)
                await self.enqueue_engine(session, game, players, now)
                response = self.snapshot(game, state, players, actor_id, now)
                if operation == "move":
                    response = {
                        "schema_version": 1,
                        "client_move_id": str(key),
                        "move": asdict(updated.moves[-1]),
                        "snapshot": response,
                    }
                self.remember(
                    session,
                    actor_id,
                    key,
                    request_hash,
                    game.id,
                    response,
                    str(game_id),
                )
        if timed_out:
            # Timeout must commit even though the requested command is rejected.
            raise PublicProblem(409)
        return response
