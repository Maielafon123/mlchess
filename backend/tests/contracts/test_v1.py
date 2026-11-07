from __future__ import annotations

import copy
import json

import pytest
import yaml
from jsonschema import ValidationError
from referencing.exceptions import Unresolvable

from contracts.validate import (
    ROOT,
    UniqueKeyLoader,
    check_snapshot_fixture,
    load_registry,
    validate_fixtures,
    validator,
)

BASE = "https://mlchess.local/contracts/"


def sample(path):
    return json.loads((ROOT / "fixtures" / (path + ".json")).read_text())


def validate(name, payload, domain="game"):
    validator(f"{BASE}{domain}/v1.yaml#/$defs/{name}").validate(payload)


def test_all_golden_fixtures_and_local_references():
    assert validate_fixtures() == 36


@pytest.mark.parametrize(
    "domain,name,path",
    [
        ("common", "CurrentUserV1", "common/current-guest"),
        ("common", "ProblemDetailsV1", "common/error-illegal-move"),
        ("game", "CreateGameV1", "game/create-coach"),
        ("game", "GameSnapshotV1", "game/snapshot-coach"),
        ("game", "SubmitMoveV1", "game/submit-move"),
        ("game", "TakebackV1", "game/takeback"),
        ("game", "MoveAcceptedV1", "game/move-accepted"),
    ],
)
def test_required_fields_cannot_be_omitted(domain, name, path):
    payload = sample(path)
    for key in payload:
        changed = copy.deepcopy(payload)
        del changed[key]
        with pytest.raises(ValidationError):
            validate(name, changed, domain)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mode", "rated"),
        ("mode", "learning"),
        ("human_color", None),
        ("human_color", "random"),
        ("ai_profile", "1800"),
        ("ai_profile", None),
        ("fen", "user-chosen-position"),
        ("result", "white"),
        ("time_control", {"initial_ms": -1, "increment_ms": 0}),
        ("time_control", {"initial_ms": 600000, "increment_ms": 0.5}),
        ("engine_path", "/bin/sh"),
        ("engine_budget", {"nodes": 999999999}),
    ],
)
def test_reject_unsafe_create_payload(field, value):
    payload = sample("game/create-coach")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("CreateGameV1", payload)


@pytest.mark.parametrize("field", ["human_color", "ai_profile"])
def test_friend_cannot_set_solo_parameters(field):
    payload = sample("game/create-friend")
    payload[field] = sample("game/create-coach")[field]
    with pytest.raises(ValidationError):
        validate("CreateGameV1", payload)


@pytest.mark.parametrize("mode", ["ai", "coach"])
@pytest.mark.parametrize("color", ["white", "black"])
def test_solo_colors_and_no_clock_are_explicit(mode, color):
    payload = sample("game/create-coach")
    payload.update(mode=mode, human_color=color)
    validate("CreateGameV1", payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("client_move_id", "not-a-uuid"),
        ("client_move_id", "fa4509f2-bc32-14c8-bad7-a09a2bf06914"),
        ("client_move_id", "FA4509F2-BC32-44C8-BAD7-A09A2BF06914"),
        ("expected_version", -1),
        ("expected_version", None),
        ("expected_version", True),
        ("expected_version", 9007199254740992),
        ("uci", "e9e4"),
        ("uci", "e2e4;ls"),
        ("uci", "e4"),
        ("uci", "0000"),
        ("uci", "e7e8k"),
        ("uci", "E2E4"),
        ("fen", "untrusted"),
        ("white_remaining_ms", 1000),
    ],
)
def test_move_command_syntax_and_server_authority(field, value):
    payload = sample("game/submit-move")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("SubmitMoveV1", payload)


@pytest.mark.parametrize("uci", ["e1g1", "e5d6", "a7a8q", "a7a8n", "a2a1r", "a2a1b"])
def test_special_move_wire_notation(uci):
    payload = sample("game/submit-move")
    payload["uci"] = uci
    validate("SubmitMoveV1", payload)


@pytest.mark.parametrize("plies", [0, 3, -1, None, True, 1.5])
def test_invalid_takeback_extent(plies):
    payload = sample("game/takeback")
    payload["plies"] = plies
    with pytest.raises(ValidationError):
        validate("TakebackV1", payload)


@pytest.mark.parametrize("mode", ["friend", "rated"])
@pytest.mark.parametrize("capability", ["can_analyze_now", "can_takeback"])
def test_active_pvp_cannot_expose_analysis_or_takeback(mode, capability):
    payload = sample("game/snapshot-finished")
    payload.update(mode=mode, status="active", result=None, termination=None)
    payload["clock"]["running_side"] = "black"
    payload["capabilities"] = dict(
        can_move=True, can_takeback=False, can_analyze_now=False
    )
    validate("GameSnapshotV1", payload)
    payload["capabilities"][capability] = True
    with pytest.raises(ValidationError):
        validate("GameSnapshotV1", payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fen", "8/8/8/8/8/8/8/8 w - - 0 1"),
        ("fen", "not a FEN"),
        ("fen", None),
        ("result", "white"),
        ("termination", "checkmate"),
        ("schema_version", 2),
        ("status", "unknown"),
        ("revision", -1),
    ],
)
def test_invalid_snapshot_fields(field, value):
    payload = sample("game/snapshot-coach")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("GameSnapshotV1", payload)


@pytest.mark.parametrize(
    "mutation", ["clock", "running", "result", "termination", "players"]
)
def test_snapshot_cross_field_constraints(mutation):
    payload = sample("game/snapshot-finished")
    if mutation == "clock":
        payload["clock"] = None
    elif mutation == "running":
        payload["clock"]["running_side"] = "black"
    elif mutation in {"result", "termination"}:
        payload[mutation] = None
    else:
        payload["players"][1]["side"] = "white"
    with pytest.raises(ValidationError):
        validate("GameSnapshotV1", payload)


@pytest.mark.parametrize("value", [-1, 1.5, True])
def test_clock_milliseconds_are_nonnegative_integers(value):
    payload = sample("game/snapshot-finished")["clock"]
    payload["black_remaining_ms"] = value
    with pytest.raises(ValidationError):
        validate("ClockV1", payload)


@pytest.mark.parametrize(
    "timestamp", ["2026-11-07T14:00:00+03:00", "2026-02-30T14:00:00Z", "yesterday"]
)
def test_clock_requires_real_utc_timestamp(timestamp):
    payload = sample("game/snapshot-finished")["clock"]
    payload["server_now"] = timestamp
    with pytest.raises(ValidationError):
        validate("ClockV1", payload)


def test_problem_code_and_http_status_agree():
    payload = sample("common/error-illegal-move")
    payload["status"] = 409
    with pytest.raises(ValidationError):
        validate("ProblemDetailsV1", payload, "common")


@pytest.mark.parametrize(
    "field,value", [("detail", None), ("traceback", "sensitive"), ("code", "UNKNOWN")]
)
def test_errors_have_no_unstructured_debug_fields(field, value):
    payload = sample("common/error-stale-version")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("ProblemDetailsV1", payload, "common")


@pytest.mark.parametrize("mutation", ["san", "uci", "ply", "fen", "side_to_move"])
def test_fixture_history_is_replayed(mutation):
    payload = sample("game/snapshot-coach")
    if mutation in {"san", "uci", "ply"}:
        payload["moves"][0][mutation] = {"san": "Nf3", "uci": "e2e5", "ply": 2}[
            mutation
        ]
    elif mutation == "fen":
        payload["fen"] = sample("game/snapshot-waiting")["fen"]
    else:
        payload["side_to_move"] = "white"
    with pytest.raises(ValueError):
        check_snapshot_fixture(payload)


def test_duplicate_yaml_keys_fail_lint():
    with pytest.raises(ValueError, match="Duplicate YAML key"):
        yaml.load("type: object\ntype: string\n", Loader=UniqueKeyLoader)


def test_unknown_remote_schema_cannot_trigger_network_fetch():
    registry, _ = load_registry()
    with pytest.raises(Unresolvable):
        registry.resolver().lookup("https://untrusted.invalid/remote.json")


def test_internal_errors_use_sanitized_problem_shape():
    payload = sample("common/error-stale-version")
    payload.update(
        status=500,
        code="INTERNAL_ERROR",
        title="Internal error",
        detail="Request failed.",
    )
    validate("ProblemDetailsV1", payload, "common")
    payload["exception"] = "private internal details"
    with pytest.raises(ValidationError):
        validate("ProblemDetailsV1", payload, "common")


@pytest.mark.parametrize("kind", ["human", "engine"])
def test_solo_has_one_human_and_one_engine(kind):
    payload = sample("game/snapshot-coach")
    for player in payload["players"]:
        player.update(
            kind=kind,
            user_id=payload["players"][0]["user_id"] if kind == "human" else None,
        )
    with pytest.raises(ValidationError):
        validate("GameSnapshotV1", payload)


def test_clock_runs_only_for_side_to_move_in_active_game():
    payload = sample("game/snapshot-finished")
    payload.update(status="active", result=None, termination=None)
    payload["capabilities"]["can_analyze_now"] = False
    payload["clock"]["running_side"] = "black"
    validate("GameSnapshotV1", payload)
    payload["clock"]["running_side"] = "white"
    with pytest.raises(ValidationError):
        validate("GameSnapshotV1", payload)
