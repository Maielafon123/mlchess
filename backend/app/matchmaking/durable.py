"""SQL-backed rated admission, matching, receipts and participant projections."""

from datetime import timedelta, timezone
from uuid import UUID, uuid4

import chess
from sqlalchemy import and_, func, or_, select

from backend.app.games.clocks import ServerClock
from backend.app.games.domain import GameDomain, Mode
from backend.app.games.durable import (
    DurableGameService,
    encode_clock,
    encode_domain,
    fingerprint,
    iso,
)
from backend.app.infra.generated import contracts as dto
from backend.app.infra.models import (
    Game,
    GamePlayer,
    GameState,
    MatchReceiptRow,
    MatchTicketRow,
    Rating,
    RatingSettlementRow,
    User,
)
from backend.app.infra.problems import PublicProblem
from backend.app.matchmaking.policy import (
    MAX_RATING,
    MIN_RATING,
    POOLS,
    RATING_RADIUS,
    START_RATING,
    TICKET_SECONDS,
)

QUEUE_LOCK = 75012026110915


def aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def ticket_payload(row, now):
    status = (
        "expired"
        if row.status == "searching" and aware(row.expires_at) <= now
        else row.status
    )
    return dto.MatchTicketV1.model_validate(
        {
            "schema_version": 1,
            "ticket_id": str(row.id),
            "pool": row.pool,
            "status": status,
            "queued_at": iso(row.queued_at),
            "expires_at": iso(row.expires_at),
            "game_id": str(row.game_id) if row.game_id else None,
            "rating": row.rating,
            "rating_min": max(MIN_RATING, row.rating - RATING_RADIUS),
            "rating_max": min(MAX_RATING, row.rating + RATING_RADIUS),
        }
    ).model_dump(mode="json")


class DurableMatchmaking:
    def __init__(self, factory):
        self.factory = factory

    @staticmethod
    async def principal(session, actor, *, account=True, lock=False):
        query = select(User).where(User.id == actor, User.deleted_at.is_(None))
        user = await session.scalar(query.with_for_update() if lock else query)
        if user is None:
            raise PublicProblem(401)
        if account and user.kind != "account":
            raise PublicProblem(403)
        return user

    @staticmethod
    async def queue_lock(session):
        if session.bind.dialect.name == "postgresql":
            await session.execute(select(func.pg_advisory_xact_lock(QUEUE_LOCK)))

    @staticmethod
    async def current_ticket(session, actor, now):
        return await session.scalar(
            select(MatchTicketRow)
            .outerjoin(Game, Game.id == MatchTicketRow.game_id)
            .where(
                MatchTicketRow.user_id == actor,
                or_(
                    and_(
                        MatchTicketRow.status == "searching",
                        MatchTicketRow.expires_at > now,
                    ),
                    and_(MatchTicketRow.status == "matched", Game.status == "active"),
                ),
            )
            .order_by(MatchTicketRow.queued_at.desc(), MatchTicketRow.id)
            .limit(1)
        )

    @staticmethod
    async def owned_ticket(session, actor, ticket_id):
        row = await session.get(MatchTicketRow, ticket_id)
        if row is None:
            raise PublicProblem(404)
        if row.user_id != actor:
            raise PublicProblem(403)
        return row

    @staticmethod
    async def receipt(session, actor, key, digest, now):
        row = await session.get(MatchReceiptRow, (actor, key))
        if row is not None:
            if row.request_hash != digest:
                raise PublicProblem(409)
            return row.response
        count = await session.scalar(
            select(func.count())
            .select_from(MatchReceiptRow)
            .where(
                MatchReceiptRow.user_id == actor,
                MatchReceiptRow.created_at >= now - timedelta(hours=1),
            )
        )
        if count >= 60:
            raise PublicProblem(429)
        return None

    async def pools(self, actor):
        async with self.factory() as session:
            user = await self.principal(session, actor, account=False)
            values = {}
            if user.kind == "account":
                values = dict(
                    (
                        await session.execute(
                            select(Rating.pool, Rating.rating).where(
                                Rating.user_id == actor
                            )
                        )
                    ).all()
                )
            return {
                "schema_version": 1,
                "items": [
                    {
                        "pool": pool,
                        "time_control": control,
                        "your_rating": values.get(pool, START_RATING)
                        if user.kind == "account"
                        else None,
                    }
                    for pool, control in POOLS.items()
                ],
            }

    async def current(self, actor):
        async with self.factory() as session:
            await self.principal(session, actor)
            now = await DurableGameService.now(session)
            ticket = await self.current_ticket(session, actor, now)
            return {
                "schema_version": 1,
                "ticket": ticket_payload(ticket, now) if ticket else None,
            }

    async def get(self, actor, ticket_id):
        async with self.factory() as session:
            await self.principal(session, actor)
            row = await self.owned_ticket(session, actor, ticket_id)
            return ticket_payload(row, await DurableGameService.now(session))

    async def cancel(self, actor, key, ticket_id):
        digest = fingerprint("match.cancel", {"ticket_id": str(ticket_id)})
        async with self.factory() as session, session.begin():
            await self.queue_lock(session)
            await self.principal(session, actor, lock=True)
            now = await DurableGameService.now(session)
            prior = await self.receipt(session, actor, key, digest, now)
            if prior is not None:
                return prior
            ticket = await self.owned_ticket(session, actor, ticket_id)
            if ticket.status == "matched":
                raise PublicProblem(409)
            if ticket.status == "searching":
                ticket.status = (
                    "expired" if aware(ticket.expires_at) <= now else "cancelled"
                )
            response = ticket_payload(ticket, now)
            session.add(
                MatchReceiptRow(
                    user_id=actor,
                    command_key=key,
                    request_hash=digest,
                    response=response,
                    created_at=now,
                )
            )
            return response

    async def join(self, actor, key, pool):
        if pool not in POOLS:
            raise PublicProblem(422)
        digest = fingerprint("match.join", {"pool": pool})
        async with self.factory() as session, session.begin():
            await self.queue_lock(session)
            user = await self.principal(session, actor, lock=True)
            now = await DurableGameService.now(session)
            prior = await self.receipt(session, actor, key, digest, now)
            if prior is not None:
                return prior
            ticket = await self.current_ticket(session, actor, now)
            if ticket is not None:
                if ticket.pool != pool:
                    raise PublicProblem(409)
            else:
                ticket = await self.enqueue(session, user, pool, now)
            response = ticket_payload(ticket, now)
            session.add(
                MatchReceiptRow(
                    user_id=actor,
                    command_key=key,
                    request_hash=digest,
                    response=response,
                    created_at=now,
                )
            )
            return response

    async def enqueue(self, session, user, pool, now):
        actor = user.id
        existing = await session.scalar(
            select(MatchTicketRow).where(
                MatchTicketRow.user_id == actor, MatchTicketRow.status == "searching"
            )
        )
        if existing is not None:
            if aware(existing.expires_at) > now:
                raise PublicProblem(409)
            existing.status = "expired"
            await session.flush([existing])
        if await self.active_game(session, actor):
            raise PublicProblem(409)
        recent = await session.scalar(
            select(func.count())
            .select_from(MatchTicketRow)
            .where(
                MatchTicketRow.user_id == actor,
                MatchTicketRow.queued_at >= now - timedelta(hours=1),
            )
        )
        queued = await session.scalar(
            select(func.count())
            .select_from(MatchTicketRow)
            .where(
                MatchTicketRow.status == "searching", MatchTicketRow.expires_at > now
            )
        )
        if recent >= 20 or queued >= 256:
            raise PublicProblem(429)
        rating = await session.scalar(
            select(Rating).where(Rating.user_id == actor, Rating.pool == pool)
        )
        if rating is None:
            rating = Rating(
                user_id=actor,
                pool=pool,
                rating=START_RATING,
                games_count=0,
                updated_at=now,
            )
            session.add(rating)
        if not MIN_RATING <= rating.rating <= MAX_RATING:
            raise PublicProblem(503)
        ticket = MatchTicketRow(
            id=uuid4(),
            user_id=actor,
            pool=pool,
            status="searching",
            rating=rating.rating,
            queued_at=now,
            expires_at=now + timedelta(seconds=TICKET_SECONDS),
        )
        session.add(ticket)
        opponent_in_game = (
            select(GamePlayer.user_id)
            .join(Game, Game.id == GamePlayer.game_id)
            .where(
                Game.mode == "rated",
                Game.status == "active",
                GamePlayer.user_id == MatchTicketRow.user_id,
            )
            .exists()
        )
        candidate = await session.scalar(
            select(MatchTicketRow)
            .join(User, User.id == MatchTicketRow.user_id)
            .where(
                MatchTicketRow.pool == pool,
                MatchTicketRow.status == "searching",
                MatchTicketRow.expires_at > now,
                MatchTicketRow.user_id != actor,
                User.kind == "account",
                User.deleted_at.is_(None),
                MatchTicketRow.rating.between(
                    rating.rating - RATING_RADIUS, rating.rating + RATING_RADIUS
                ),
                ~opponent_in_game,
            )
            .order_by(MatchTicketRow.queued_at, MatchTicketRow.id)
            .limit(1)
        )
        if candidate is not None:
            opponent = await session.scalar(
                select(User)
                .where(
                    User.id == candidate.user_id,
                    User.kind == "account",
                    User.deleted_at.is_(None),
                )
                .with_for_update()
            )
            paired_at = await DurableGameService.now(session)
            if (
                opponent is not None
                and aware(candidate.expires_at) > paired_at
                and aware(ticket.expires_at) > paired_at
            ):
                await self.pair(session, ticket, user, candidate, opponent, paired_at)
        return ticket

    @staticmethod
    async def active_game(session, actor):
        return await session.scalar(
            select(Game.id)
            .join(GamePlayer, GamePlayer.game_id == Game.id)
            .where(
                Game.mode == "rated",
                Game.status == "active",
                GamePlayer.user_id == actor,
            )
            .limit(1)
        )

    @staticmethod
    async def pair(session, first, user, second, opponent, now):
        game_id = uuid4()
        seats = [(first, user), (second, opponent)]
        if game_id.int & 1:
            seats.reverse()
        domain = GameDomain.start(Mode.RATED)
        control = dict(POOLS[first.pool])
        clock = ServerClock(
            control["initial_ms"],
            control["initial_ms"],
            control["increment_ms"],
            chess.WHITE,
            now,
        )
        game = Game(
            id=game_id,
            mode="rated",
            status="active",
            version=0,
            revision=0,
            fen=domain.fen,
            ply=0,
            side_to_move="white",
            created_at=now,
            updated_at=now,
        )
        session.add(game)
        await session.flush([game])
        paired = {}
        for side, (ticket, principal) in zip(("white", "black"), seats, strict=True):
            ticket.status, ticket.game_id = "matched", game_id
            paired[side] = {
                "rating": ticket.rating,
                "name": principal.display_name or "Игрок",
            }
            session.add(
                GamePlayer(
                    game_id=game_id,
                    side=side,
                    kind="human",
                    user_id=principal.id,
                    joined_at=now,
                )
            )
        state = GameState(
            game_id=game_id,
            domain=encode_domain(domain),
            config={
                "mode": "rated",
                "time_control": control,
                "clock_history": [],
                "rating_pool": first.pool,
                "paired": paired,
            },
            clock=encode_clock(clock),
            event_seq=0,
        )
        session.add(state)
        DurableGameService.status_event(session, game, state, clock, now)

    async def rated_game(self, actor, game_id: UUID):
        async with self.factory() as session, session.begin():
            await self.principal(session, actor)
            game, state, players = await DurableGameService.load(
                session, game_id, actor, lock=True
            )
            if game.mode != "rated":
                raise PublicProblem(404)
            side = next(player.side for player in players if player.user_id == actor)
            other = "black" if side == "white" else "white"
            pairing = state.config["paired"]
            settlement = await session.get(RatingSettlementRow, game_id)
            if (game.status == "finished") != (settlement is not None):
                raise PublicProblem(503)
            change = None
            if settlement:
                if (
                    getattr(settlement, side + "_id") != actor
                    or settlement.result != game.result
                    or settlement.pool != state.config["rating_pool"]
                ):
                    raise PublicProblem(503)
                before, after = (
                    getattr(settlement, side + "_before"),
                    getattr(settlement, side + "_after"),
                )
                change = {
                    "before": before,
                    "after": after,
                    "delta": after - before,
                    "games_count": getattr(settlement, side + "_games"),
                    "settled_at": iso(settlement.settled_at),
                }
            return dto.RatedGameV1.model_validate(
                {
                    "schema_version": 1,
                    "game_id": str(game_id),
                    "version": game.version,
                    "status": game.status,
                    "pool": state.config["rating_pool"],
                    "side": side,
                    "opponent_name": pairing[other]["name"],
                    "your_rating": pairing[side]["rating"],
                    "opponent_rating": pairing[other]["rating"],
                    "rating_change": change,
                }
            ).model_dump(mode="json")
