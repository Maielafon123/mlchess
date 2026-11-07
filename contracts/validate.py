"""Offline schema lint and golden-fixture validation for A-owned contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import chess
import chess.engine
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent
CHECKER = FormatChecker()


@CHECKER.checks("chess-fen", raises=ValueError)
def is_canonical_fen(value: Any) -> bool:
    if not isinstance(value, str):
        return True  # The schema's type keyword handles non-strings.
    board = chess.Board(value)
    return board.is_valid() and board.fen() == value


class UniqueKeyLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently discarding a constraint."""


def unique_mapping(loader: UniqueKeyLoader, node: Any) -> dict:
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if key in result:
            raise ValueError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def load_registry(root: Path = ROOT) -> tuple[Registry, dict[str, dict]]:
    schemas = {}
    required = [
        root / name
        for name in (
            "common/v1.yaml",
            "game/v1.yaml",
            "game/events.v1.yaml",
            "analysis/v1.yaml",
        )
    ]
    for path in required:
        if not path.is_file():
            raise ValueError(f"Required schema missing: {path}")
    for path in sorted(root.glob("*/*.yaml")):
        if path.name == "http.v1.yaml":
            continue
        schema = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
        Draft202012Validator.check_schema(schema)
        if schema["$id"] in schemas:
            raise ValueError(f"Duplicate schema id: {schema['$id']}")
        schemas[schema["$id"]] = schema
    # No retrieve callback: unknown references fail locally, with no network access.
    registry = Registry().with_resources(
        (uri, Resource.from_contents(schema)) for uri, schema in schemas.items()
    )
    resolver = registry.resolver()

    def check_references(value: Any) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                resolver.lookup(value["$ref"])
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    for schema in schemas.values():
        check_references(schema)
    return registry, schemas


def validator(
    schema_uri: str, registry: Registry | None = None
) -> Draft202012Validator:
    if registry is None:
        registry, _ = load_registry()
    return Draft202012Validator(
        {"$ref": schema_uri}, registry=registry, format_checker=CHECKER
    )


def check_snapshot_fixture(snapshot: dict) -> None:
    """Check golden examples against chess rules; not a production game service."""
    board = chess.Board()
    for ply, item in enumerate(snapshot["moves"], start=1):
        if item["ply"] != ply:
            raise ValueError("Fixture moves must have contiguous plies")
        move = chess.Move.from_uci(item["uci"])
        if move not in board.legal_moves:
            raise ValueError(f"Illegal fixture move at ply {ply}")
        if board.san(move) != item["san"]:
            raise ValueError(f"Incorrect fixture SAN at ply {ply}")
        board.push(move)
    if snapshot["ply"] != len(board.move_stack) or snapshot["fen"] != board.fen():
        raise ValueError("Fixture history does not match ply/FEN")
    if snapshot["side_to_move"] != ("white" if board.turn else "black"):
        raise ValueError("Fixture side_to_move disagrees with FEN")


PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def check_analysis_fixture(result: dict) -> None:
    """Verify chess evidence in synthetic examples; engine evaluations are fixtures."""
    before = chess.Board(result["before_fen"])
    move = chess.Move.from_uci(result["played_move_uci"])
    if move not in before.legal_moves:
        raise ValueError("Played analysis move is illegal")
    after = before.copy()
    after.push(move)
    if after.fen() != result["after_fen"] or after.ply() != result["ply"]:
        raise ValueError("Analysis before/after FEN or ply mismatch")
    position_key = hashlib.sha256(
        (before.fen() + "|" + move.uci()).encode("utf-8")
    ).hexdigest()
    if result["position_key"] != position_key:
        raise ValueError("Analysis position_key mismatch")
    seen = set()
    previous_score = None
    for candidate in result["top_moves"]:
        candidate_move = chess.Move.from_uci(candidate["uci"])
        if candidate_move not in before.legal_moves or candidate["uci"] in seen:
            raise ValueError("Duplicate or illegal analysis candidate")
        seen.add(candidate["uci"])
        if before.san(candidate_move) != candidate["san"]:
            raise ValueError("Candidate SAN mismatch")
        if not candidate["pv_uci"] or candidate["pv_uci"][0] != candidate["uci"]:
            raise ValueError("PV must start with its candidate move")
        line = before.copy()
        for uci in candidate["pv_uci"]:
            pv_move = chess.Move.from_uci(uci)
            if pv_move not in line.legal_moves:
                raise ValueError("Analysis PV contains an illegal move")
            line.push(pv_move)
        score = candidate["score"]
        typed_score = (
            chess.engine.Cp(score["value"])
            if score["kind"] == "cp"
            else chess.engine.Mate(score["value"])
        )
        mover_score = chess.engine.PovScore(typed_score, chess.WHITE).pov(before.turn)
        if previous_score is not None and previous_score < mover_score:
            raise ValueError("Candidates are not ranked from mover POV")
        previous_score = mover_score
    first = result["top_moves"][0]
    if (
        result["best_move_uci"] != first["uci"]
        or result["score_before"] != first["score"]
    ):
        raise ValueError("Best move / score_before must match the first candidate")
    if len(result["top_moves"]) != min(
        result["engine"]["multipv"], before.legal_moves.count()
    ):
        raise ValueError("Top moves do not match effective MultiPV")
    scores = (result["score_before"], result["score_after"])
    if any(score["kind"] == "mate" for score in scores):
        if result["cp_loss"] is not None:
            raise ValueError("Mate positions cannot have centipawn loss")
    else:
        sign = 1 if before.turn == chess.WHITE else -1
        loss = max(0, (scores[0]["value"] - scores[1]["value"]) * sign)
        if result["cp_loss"] != loss:
            raise ValueError("Centipawn loss has incorrect mover POV")
    if (
        result["score_after"] == {"kind": "mate", "value": 0, "pov": "white"}
        and not after.is_checkmate()
    ):
        raise ValueError("Mate zero requires a checkmated board")
    facts = result["facts"]
    if facts["checks"] != after.is_check() or facts["captures"] != before.is_capture(
        move
    ):
        raise ValueError("Check/capture facts disagree with the played move")

    def balance(board: chess.Board) -> int:
        return sum(
            value
            * (
                len(board.pieces(piece, before.turn))
                - len(board.pieces(piece, not before.turn))
            )
            for piece, value in PIECE_VALUES.items()
        )

    if facts["material_delta"] != balance(after) - balance(before):
        raise ValueError("Material delta disagrees with the played move")
    motifs = set()
    if after.is_checkmate():
        motifs.add("checkmate")
    if move.promotion:
        motifs.add("promotion")
    if before.is_en_passant(move):
        motifs.add("en_passant")
    if before.is_castling(move):
        motifs.add("castling")
    if not set(facts["motifs_verified"]).issubset(motifs):
        raise ValueError("Unsupported or false verified motif")
    fact_ids = set()
    for claim in facts["verified_claims"]:
        if claim["fact_id"] in fact_ids:
            raise ValueError("Duplicate verified fact_id")
        fact_ids.add(claim["fact_id"])
        kind, evidence = claim["kind"], claim["evidence"]
        if evidence["uci"] != move.uci():
            raise ValueError("Claim refers to another move")
        if kind in {"check", "checkmate"}:
            if evidence["after_fen"] != after.fen() or not after.is_check():
                raise ValueError("Unverified check claim")
            if kind == "checkmate" and (
                not after.is_checkmate()
                or evidence["winner"] != ("white" if before.turn else "black")
            ):
                raise ValueError("Unverified checkmate claim")
        elif kind == "capture":
            square = move.to_square
            if before.is_en_passant(move):
                square += -8 if before.turn else 8
            captured = before.piece_at(square)
            if (
                not before.is_capture(move)
                or captured is None
                or evidence["square"] != chess.square_name(square)
                or evidence["captured_piece"] != chess.piece_name(captured.piece_type)
            ):
                raise ValueError("Unverified capture claim")
        elif kind == "promotion":
            if move.promotion is None or evidence["promoted_piece"] != chess.piece_name(
                move.promotion
            ):
                raise ValueError("Unverified promotion claim")
        else:
            raise ValueError("Unsupported verified claim kind")


def check_event_fixture(event: dict) -> None:
    payload, kind = event["payload"], event["type"]
    if kind == "game.snapshot":
        if payload["id"] != event["game_id"]:
            raise ValueError("Snapshot game_id differs from envelope")
        check_snapshot_fixture(payload)
    elif kind in {"game.move_committed", "game.takeback_applied"}:
        board = chess.Board(payload["fen"])
        if payload["side_to_move"] != ("white" if board.turn else "black"):
            raise ValueError("Event turn differs from FEN")
        if kind == "game.move_committed" and payload["move"]["ply"] != board.ply():
            raise ValueError("Committed move ply differs from FEN")
        if kind == "game.takeback_applied" and (
            payload["from_ply"] - payload["to_ply"] not in {1, 2}
            or payload["to_ply"] != board.ply()
        ):
            raise ValueError("Invalid takeback ply range")
        if payload["clock"] is not None and payload["clock"]["running_side"] not in {
            None,
            payload["side_to_move"],
        }:
            raise ValueError("Event clock runs for the wrong side")
    elif kind == "server.resync_required":
        if event["seq"] != payload["latest_seq"]:
            raise ValueError("Resync envelope cursor differs from latest_seq")
        if (
            payload["reason"] == "cursor_ahead"
            and payload["after_seq"] <= payload["latest_seq"]
        ):
            raise ValueError("cursor_ahead requires a cursor beyond the server head")
        if (
            payload["reason"] != "cursor_ahead"
            and payload["after_seq"] >= payload["latest_seq"]
        ):
            raise ValueError("Replay gaps require a cursor before the server head")


def check_job_fixture(job: dict) -> None:
    if datetime.fromisoformat(job["updated_at"]) < datetime.fromisoformat(
        job["created_at"]
    ):
        raise ValueError("Job updated_at precedes created_at")


def validate_fixtures(root: Path = ROOT) -> int:
    registry, _ = load_registry(root)
    fixtures = root / "fixtures"
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    paths = [entry["path"] for entry in manifest]
    # Manifest paths use stable POSIX separators on every platform.
    actual = {
        path.relative_to(fixtures).as_posix() for path in fixtures.rglob("*.json")
    }
    actual.discard("manifest.json")
    if len(paths) != len(set(paths)) or set(paths) != actual:
        raise ValueError("Fixture manifest must list every fixture exactly once")
    analyses = {}
    ready_events = []
    for entry in manifest:
        path = (fixtures / entry["path"]).resolve()
        if not path.is_relative_to(fixtures.resolve()):
            raise ValueError("Fixture path escapes fixture directory")
        payload = json.loads(path.read_text(encoding="utf-8"))
        validator(entry["schema"], registry).validate(payload)
        name = entry["schema"].rsplit("/", 1)[-1]
        if name == "GameSnapshotV1":
            check_snapshot_fixture(payload)
        elif name == "MoveAcceptedV1":
            check_snapshot_fixture(payload["snapshot"])
            if payload["move"] != payload["snapshot"]["moves"][-1]:
                raise ValueError("Accepted move differs from snapshot's last move")
        elif name == "AnalysisResultV1":
            check_analysis_fixture(payload)
            analyses[payload["analysis_id"]] = payload
        elif name == "AnalysisJobV1":
            check_job_fixture(payload)
        elif name == "GameEventV1":
            check_event_fixture(payload)
            if payload["type"] in {"analysis.ready", "coach.ready"}:
                ready_events.append(payload)
    for event in ready_events:
        result = analyses.get(event["payload"]["analysis_id"])
        if (
            result is None
            or any(event["payload"][key] != result[key] for key in ("revision", "ply"))
            or event["game_id"] != result["game_id"]
        ):
            raise ValueError("Ready event does not identify its analysis result")
    return len(manifest)


if __name__ == "__main__":
    count = validate_fixtures()
    print(f"Contract schemas and references valid; {count} golden fixtures passed.")
