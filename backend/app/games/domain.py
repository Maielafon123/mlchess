"""Pure standard-chess rules. Storage, identity, jobs and HTTP stay outside this module."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from enum import StrEnum

import chess
import chess.pgn


class Mode(StrEnum):
    FRIEND = "friend"
    RATED = "rated"
    AI = "ai"
    COACH = "coach"


class Result(StrEnum):
    WHITE = "white"
    BLACK = "black"
    DRAW = "draw"


class EndReason(StrEnum):
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    FIVEFOLD_REPETITION = "fivefold_repetition"
    SEVENTYFIVE_MOVES = "seventyfive_moves"
    THREEFOLD_CLAIM = "threefold_claim"
    FIFTY_MOVES_CLAIM = "fifty_moves_claim"
    DRAW_AGREEMENT = "draw_agreement"
    RESIGNATION = "resignation"
    TIMEOUT = "timeout"


class GameError(ValueError):
    """Internal domain errors are mapped to the public error contract by adapters."""


class InvalidHistory(GameError):
    pass


class IllegalMove(GameError):
    pass


class NotYourTurn(GameError):
    pass


class GameNotActive(GameError):
    pass


class StaleVersion(GameError):
    pass


class DrawNotClaimable(GameError):
    pass


class DrawOfferError(GameError):
    pass


class ModeRestriction(GameError):
    pass


@dataclass(frozen=True, slots=True)
class MoveRecord:
    ply: int
    uci: str
    san: str


_UCI = re.compile(r"[a-h][1-8][a-h][1-8][qrbn]?\Z")
_AUTOMATIC = {
    chess.Termination.CHECKMATE: EndReason.CHECKMATE,
    chess.Termination.STALEMATE: EndReason.STALEMATE,
    chess.Termination.INSUFFICIENT_MATERIAL: EndReason.INSUFFICIENT_MATERIAL,
    chess.Termination.FIVEFOLD_REPETITION: EndReason.FIVEFOLD_REPETITION,
    chess.Termination.SEVENTYFIVE_MOVES: EndReason.SEVENTYFIVE_MOVES,
}


def _move(value: str) -> chess.Move:
    if not isinstance(value, str) or _UCI.fullmatch(value) is None:
        raise IllegalMove("A canonical standard-chess UCI move is required")
    try:
        return chess.Move.from_uci(value)
    except ValueError:
        raise IllegalMove("Invalid UCI move") from None


def _initial_board(fen: str) -> chess.Board:
    if not isinstance(fen, str):
        raise InvalidHistory("Initial position must be a FEN string")
    try:
        board = chess.Board(fen, chess960=False)
    except ValueError:
        raise InvalidHistory("Invalid initial position") from None
    if not board.is_valid():
        raise InvalidHistory("Invalid standard-chess position")
    return board


def _natural_result(board: chess.Board) -> tuple[Result | None, EndReason | None]:
    outcome = board.outcome(claim_draw=False)
    if outcome is None:
        return None, None
    result = (
        Result.DRAW
        if outcome.winner is None
        else (Result.WHITE if outcome.winner else Result.BLACK)
    )
    return result, _AUTOMATIC[outcome.termination]


@dataclass(frozen=True, slots=True)
class GameDomain:
    mode: Mode = Mode.FRIEND
    initial_fen: str = chess.STARTING_FEN
    moves: tuple[MoveRecord, ...] = ()
    version: int = 0
    result: Result | None = None
    termination: EndReason | None = None
    draw_offer: chess.Color | None = None
    revision: int = 0
    archived_lines: tuple[tuple[MoveRecord, ...], ...] = ()
    _board: chess.Board = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        try:
            object.__setattr__(self, "mode", Mode(self.mode))
            if self.result is not None:
                object.__setattr__(self, "result", Result(self.result))
            if self.termination is not None:
                object.__setattr__(self, "termination", EndReason(self.termination))
        except ValueError:
            raise InvalidHistory("Invalid mode, result or termination") from None
        if type(self.version) is not int or self.version < 0:
            raise InvalidHistory("Version must be a nonnegative integer")
        if not isinstance(self.moves, tuple) or self.version < len(self.moves):
            raise InvalidHistory(
                "History must be immutable and fit its command version"
            )
        if type(self.revision) is not int or self.revision < 0:
            raise InvalidHistory("Revision must be a nonnegative integer")
        if not isinstance(self.archived_lines, tuple) or any(
            not isinstance(line, tuple) for line in self.archived_lines
        ):
            raise InvalidHistory("Archived lines must be immutable")
        board = _initial_board(self.initial_fen)
        if board.fen() != self.initial_fen:
            raise InvalidHistory("Initial FEN must be canonical")
        for ply, item in enumerate(self.moves, start=1):
            if board.outcome(claim_draw=False) is not None:
                raise InvalidHistory(
                    "History continues after an automatic terminal result"
                )
            if (
                not isinstance(item, MoveRecord)
                or type(item.ply) is not int
                or item.ply != ply
            ):
                raise InvalidHistory("Move history must have contiguous plies")
            try:
                move = _move(item.uci)
            except IllegalMove:
                raise InvalidHistory("History contains an invalid move") from None
            if (
                move not in board.legal_moves
                or board.uci(move, chess960=False) != item.uci
                or board.san(move) != item.san
            ):
                raise InvalidHistory("History contains illegal UCI or inconsistent SAN")
            board.push(move)
        automatic = _natural_result(board)
        if (self.result is None) != (self.termination is None):
            raise InvalidHistory("Result and termination must be set together")
        if automatic[0] is not None:
            if (self.result, self.termination) != automatic:
                raise InvalidHistory("Automatic result disagrees with complete history")
        elif self.result is not None:
            if self.version < len(self.moves) + 1:
                raise InvalidHistory("A manual terminal action must advance version")
            reason = self.termination
            if reason == EndReason.RESIGNATION:
                valid = self.result in {Result.WHITE, Result.BLACK}
            elif reason == EndReason.TIMEOUT:
                valid = self.result in {Result.WHITE, Result.BLACK, Result.DRAW}
            elif reason == EndReason.DRAW_AGREEMENT:
                valid = self.result == Result.DRAW and self.mode in {
                    Mode.FRIEND,
                    Mode.RATED,
                }
            elif reason == EndReason.THREEFOLD_CLAIM:
                valid = self.result == Result.DRAW and board.is_repetition(3)
            elif reason == EndReason.FIFTY_MOVES_CLAIM:
                valid = self.result == Result.DRAW and board.is_fifty_moves()
            else:
                valid = False
            if not valid:
                raise InvalidHistory("Manual result disagrees with game rules")
        if self.draw_offer is not None:
            if (
                type(self.draw_offer) is not bool
                or self.result is not None
                or self.mode not in {Mode.FRIEND, Mode.RATED}
                or self.version < len(self.moves) + 1
            ):
                raise InvalidHistory("Invalid pending draw offer")
        object.__setattr__(self, "_board", board)

    @classmethod
    def start(
        cls, mode: Mode = Mode.FRIEND, *, initial_fen: str = chess.STARTING_FEN
    ) -> GameDomain:
        # Nonstandard starting FEN is only an internal trusted fixture/restore port;
        # the v1 public create API starts from chess.STARTING_FEN.
        return cls.from_history(mode, (), initial_fen=initial_fen)

    @classmethod
    def from_history(
        cls,
        mode: Mode,
        uci_moves: Iterable[str],
        *,
        initial_fen: str = chess.STARTING_FEN,
        version: int | None = None,
    ) -> GameDomain:
        board = _initial_board(initial_fen)
        canonical = board.fen()
        records = []
        for ply, uci in enumerate(uci_moves, start=1):
            if board.outcome(claim_draw=False) is not None:
                raise InvalidHistory(
                    "History continues after an automatic terminal result"
                )
            try:
                move = _move(uci)
            except IllegalMove:
                raise InvalidHistory("History contains an invalid move") from None
            if move not in board.legal_moves or board.uci(move, chess960=False) != uci:
                raise InvalidHistory("History contains an illegal move")
            records.append(MoveRecord(ply, uci, board.san(move)))
            board.push(move)
        result, reason = _natural_result(board)
        return cls(
            mode,
            canonical,
            tuple(records),
            len(records) if version is None else version,
            result,
            reason,
        )

    @property
    def board(self) -> chess.Board:
        return self._board.copy(stack=True)

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def ply(self) -> int:
        return len(self.moves)

    @property
    def side_to_move(self) -> chess.Color:
        return self._board.turn

    @property
    def status(self) -> str:
        return "active" if self.result is None else "finished"

    def _command(self, actor: chess.Color, expected_version: int):
        if type(actor) is not bool:
            raise GameError("Actor must be an authenticated participant color")
        if type(expected_version) is not int or expected_version != self.version:
            raise StaleVersion("Game version is stale")
        if self.result is not None:
            raise GameNotActive("The game has finished")

    def play(
        self, *, actor: chess.Color, uci: str, expected_version: int
    ) -> GameDomain:
        self._command(actor, expected_version)
        if actor != self._board.turn:
            raise NotYourTurn("The other participant must move")
        move = _move(uci)
        if (
            move not in self._board.legal_moves
            or self._board.uci(move, chess960=False) != uci
        ):
            raise IllegalMove("The move is not legal in the current position")
        board = self._board.copy(stack=True)
        record = MoveRecord(self.ply + 1, uci, board.san(move))
        board.push(move)
        result, reason = _natural_result(board)
        offer = self.draw_offer if self.draw_offer == actor and result is None else None
        return replace(
            self,
            moves=(*self.moves, record),
            version=self.version + 1,
            result=result,
            termination=reason,
            draw_offer=offer,
        )

    def resign(self, *, actor: chess.Color, expected_version: int) -> GameDomain:
        self._command(actor, expected_version)
        return replace(
            self,
            version=self.version + 1,
            result=Result.BLACK if actor else Result.WHITE,
            termination=EndReason.RESIGNATION,
            draw_offer=None,
        )

    def claim_draw(self, *, actor: chess.Color, expected_version: int) -> GameDomain:
        self._command(actor, expected_version)
        if actor != self.side_to_move:
            raise NotYourTurn("Only the player to move can claim a draw")
        # can_claim_* also accepts a hypothetical next move, but this v1 command
        # has no intended-move field. Only the current position is claimable.
        board = self.board
        if board.is_repetition(3):
            reason = EndReason.THREEFOLD_CLAIM
        elif board.is_fifty_moves():
            reason = EndReason.FIFTY_MOVES_CLAIM
        else:
            raise DrawNotClaimable("The current position does not permit a draw claim")
        return replace(
            self,
            version=self.version + 1,
            result=Result.DRAW,
            termination=reason,
            draw_offer=None,
        )

    def timeout(self, *, loser: chess.Color) -> GameDomain:
        """Internal server-clock command, never based on a client time value."""
        self._command(loser, self.version)
        winner = not loser
        result = (
            Result.DRAW
            if self.board.has_insufficient_material(winner)
            else (Result.WHITE if winner else Result.BLACK)
        )
        return replace(
            self,
            version=self.version + 1,
            result=result,
            termination=EndReason.TIMEOUT,
            draw_offer=None,
        )

    def offer_draw(self, *, actor: chess.Color, expected_version: int) -> GameDomain:
        self._command(actor, expected_version)
        if self.mode not in {Mode.FRIEND, Mode.RATED}:
            raise ModeRestriction("Draw offers require two human participants")
        if self.draw_offer is not None:
            raise DrawOfferError("A draw offer is already pending")
        return replace(self, version=self.version + 1, draw_offer=actor)

    def accept_draw(self, *, actor: chess.Color, expected_version: int) -> GameDomain:
        self._command(actor, expected_version)
        if self.mode not in {Mode.FRIEND, Mode.RATED}:
            raise ModeRestriction("Draw offers require two human participants")
        if self.draw_offer is None or self.draw_offer == actor:
            raise DrawOfferError("There is no opponent draw offer to accept")
        return replace(
            self,
            version=self.version + 1,
            result=Result.DRAW,
            termination=EndReason.DRAW_AGREEMENT,
            draw_offer=None,
        )

    def takeback(
        self, *, actor: chess.Color, expected_version: int, plies: int
    ) -> GameDomain:
        self._command(actor, expected_version)
        if self.mode not in {Mode.AI, Mode.COACH}:
            raise ModeRestriction("Takeback is available only in solo games")
        if plies not in {1, 2} or plies > len(self.moves):
            raise GameError("Takeback must remove one or two existing plies")
        return replace(
            self,
            moves=self.moves[:-plies],
            version=self.version + 1,
            result=None,
            termination=None,
            draw_offer=None,
            revision=self.revision + 1,
            archived_lines=self.archived_lines + (self.moves,),
        )

    def to_pgn(self) -> str:
        game = chess.pgn.Game()
        game.setup(_initial_board(self.initial_fen))
        game.headers["Result"] = {
            Result.WHITE: "1-0",
            Result.BLACK: "0-1",
            Result.DRAW: "1/2-1/2",
            None: "*",
        }[self.result]
        if self.termination is not None:
            game.headers["Termination"] = self.termination.value
        node = game
        for item in self.moves:
            node = node.add_variation(chess.Move.from_uci(item.uci))
        return game.accept(
            chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        )
