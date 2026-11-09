"""Coherent SQL snapshot/replay/tail; viewer-private frames never enter a stream."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import select

from backend.app.games.durable import DurableGameService, iso
from backend.app.infra.generated.contracts import GameEventV1
from backend.app.infra.models import Analysis, CoachExplanation, GameEvent


@dataclass(frozen=True)
class Batch:
    frames: list[dict]
    cursor: int
    resync: bool = False
    more: bool = False


def control(game_id, seq, kind, payload, now):
    return GameEventV1.model_validate(
        {
            "schema_version": 1,
            "event_id": str(uuid4()),
            "game_id": str(game_id),
            "seq": seq,
            "type": kind,
            "occurred_at": iso(now),
            "payload": payload,
        }
    ).model_dump(mode="json")


class DurableEventStream:
    def __init__(self, factory, *, batch_size=64):
        if not 1 <= batch_size <= 64:
            raise ValueError("Bounded event batches required")
        self.factory, self.batch_size = factory, batch_size

    async def read(
        self, game_id: UUID, actor_id: UUID, after_seq: int, *, bootstrap=False
    ):
        async with self.factory() as session, session.begin():
            game, state, players = await DurableGameService.load(
                session, game_id, actor_id, lock=True
            )
            now = await DurableGameService.now(session)
            head = state.event_seq
            if bootstrap:
                DurableGameService.observe_clock(game, state, now)
                snapshot = DurableGameService.snapshot(
                    game, state, players, actor_id, now
                )
                return Batch(
                    [control(game_id, head, "game.snapshot", snapshot, now)], head
                )

            def resync(reason):
                return Batch(
                    [
                        control(
                            game_id,
                            head,
                            "server.resync_required",
                            {
                                "after_seq": after_seq,
                                "latest_seq": head,
                                "reason": reason,
                            },
                            now,
                        )
                    ],
                    after_seq,
                    resync=True,
                )

            if after_seq > head:
                return resync("cursor_ahead")
            rows = list(
                await session.scalars(
                    select(GameEvent)
                    .where(
                        GameEvent.game_id == game_id,
                        GameEvent.seq > after_seq,
                        GameEvent.seq <= head,
                    )
                    .order_by(GameEvent.seq)
                    .limit(self.batch_size + 1)
                )
            )
            if after_seq < head and not rows:
                return resync("replay_unavailable")
            frames = []
            cursor = after_seq
            for row in rows[: self.batch_size]:
                if row.seq != cursor + 1:
                    return resync("sequence_gap")
                # Revalidate persisted envelopes and their SQL identity before publishing.
                envelope = GameEventV1.model_validate(row.payload).model_dump(
                    mode="json"
                )
                if (
                    envelope["game_id"],
                    envelope["event_id"],
                    envelope["seq"],
                    envelope["type"],
                ) != (str(game_id), str(row.id), row.seq, row.event_type):
                    return resync("replay_unavailable")
                if row.event_type in {"game.snapshot", "server.resync_required"}:
                    return resync("replay_unavailable")
                if row.event_type in {"analysis.ready", "coach.ready"}:
                    if game.mode in {"friend", "rated"} and game.status != "finished":
                        return resync("replay_unavailable")
                    reference = envelope["payload"]
                    analysis = await session.get(
                        Analysis, UUID(reference["analysis_id"])
                    )
                    if (
                        analysis is None
                        or (
                            analysis.game_id,
                            analysis.revision,
                            analysis.ply,
                            analysis.status,
                        )
                        != (game_id, game.revision, reference["ply"], "done")
                        or reference["revision"] != game.revision
                        or reference["ply"] > game.ply
                    ):
                        return resync("replay_unavailable")
                    if row.event_type == "coach.ready":
                        explanation = await session.get(
                            CoachExplanation,
                            UUID(envelope["payload"]["explanation_id"]),
                        )
                        if explanation is None or (
                            explanation.requester_id,
                            explanation.game_id,
                            explanation.analysis_id,
                            explanation.revision,
                            explanation.ply,
                            explanation.status,
                        ) != (
                            actor_id,
                            game_id,
                            analysis.id,
                            game.revision,
                            analysis.ply,
                            "ready",
                        ):
                            return resync("replay_unavailable")
                frames.append(envelope)
                cursor = row.seq
            if len(rows) <= self.batch_size and cursor < head:
                return resync("sequence_gap")
            return Batch(frames, cursor, more=len(rows) > self.batch_size)
