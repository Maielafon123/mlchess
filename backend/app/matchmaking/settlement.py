"""One immutable Elo settlement in the same transaction as a rated result."""

from sqlalchemy import select

from backend.app.infra.models import GamePlayer, Rating, RatingSettlementRow
from backend.app.infra.problems import PublicProblem
from backend.app.matchmaking.policy import POOLS, MIN_RATING, MAX_RATING, bounded_delta


async def settle_rated(session, game, state, now):
    """The caller holds the game row lock and owns commit/rollback."""
    if game.mode != "rated" or game.status != "finished":
        return None
    pool = state.config.get("rating_pool")
    if pool not in POOLS or game.result not in {"white", "black", "draw"}:
        raise PublicProblem(503)
    prior = await session.get(RatingSettlementRow, game.id)
    if prior is not None:
        if prior.pool != pool or prior.result != game.result:
            raise PublicProblem(503)
        return prior
    players = list(
        await session.scalars(select(GamePlayer).where(GamePlayer.game_id == game.id))
    )
    if len(players) != 2 or any(
        p.kind != "human" or p.user_id is None for p in players
    ):
        raise PublicProblem(503)
    seats = {p.side: p.user_id for p in players}
    if set(seats) != {"white", "black"} or seats["white"] == seats["black"]:
        raise PublicProblem(503)
    ratings = {}
    for actor in sorted(seats.values()):
        row = await session.scalar(
            select(Rating)
            .where(Rating.user_id == actor, Rating.pool == pool)
            .with_for_update()
        )
        if (
            row is None
            or not MIN_RATING <= row.rating <= MAX_RATING
            or row.games_count < 0
        ):
            raise PublicProblem(503)
        ratings[actor] = row
    white, black = ratings[seats["white"]], ratings[seats["black"]]
    before_white, before_black = white.rating, black.rating
    delta = bounded_delta(before_white, before_black, game.result)
    white.rating, black.rating = before_white + delta, before_black - delta
    white.games_count += 1
    black.games_count += 1
    white.updated_at = black.updated_at = now
    settlement = RatingSettlementRow(
        game_id=game.id,
        pool=pool,
        result=game.result,
        white_id=white.user_id,
        black_id=black.user_id,
        white_before=before_white,
        black_before=before_black,
        white_after=white.rating,
        black_after=black.rating,
        white_games=white.games_count,
        black_games=black.games_count,
        settled_at=now,
    )
    session.add(settlement)
    return settlement
