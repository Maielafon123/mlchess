from __future__ import annotations

import copy
import json

import chess
import pytest
from jsonschema import ValidationError

from contracts.validate import (
    ROOT,
    check_analysis_fixture,
    check_event_fixture,
    check_job_fixture,
    load_registry,
    validator,
)

BASE = "https://mlchess.local/contracts/"


def sample(path):
    return json.loads((ROOT / "fixtures" / (path + ".json")).read_text())


@pytest.fixture(scope="module")
def registry():
    return load_registry()[0]


def validate(name, payload, registry, event=False):
    uri = BASE + ("game/events.v1.yaml" if event else "analysis/v1.yaml")
    validator(uri + "#/$defs/" + name, registry).validate(payload)


@pytest.mark.parametrize(
    "path",
    [
        "cp-white",
        "cp-black",
        "mate",
        "capture",
        "en-passant",
        "castling",
        "promotion",
        "missed-mate",
    ],
)
def test_analysis_examples_have_legal_evidence(path, registry):
    payload = sample("analysis/result-" + path)
    validate("AnalysisResultV1", payload, registry)
    check_analysis_fixture(payload)


@pytest.mark.parametrize(
    "score",
    [
        {"kind": "cp", "value": 50, "pov": "black"},
        {"kind": "mate", "value": 1, "pov": "side_to_move"},
        {"kind": "cp", "value": True, "pov": "white"},
        {"kind": "cp", "value": 0.1, "pov": "white"},
        {"kind": "wdl", "value": 50, "pov": "white"},
        {"kind": "cp", "value": 50},
        {"kind": "cp", "value": 50, "pov": "white", "mate": 2},
    ],
)
def test_scores_cannot_mix_units_or_omit_pov(score, registry):
    with pytest.raises(ValidationError):
        validate("ScoreV1", score, registry)


@pytest.mark.parametrize("value", [0, 100, -100, True])
def test_mate_loss_is_always_null(value, registry):
    payload = sample("analysis/result-mate")
    payload["cp_loss"] = value
    with pytest.raises(ValidationError):
        validate("AnalysisResultV1", payload, registry)


@pytest.mark.parametrize(
    "field,value",
    [("cp_loss", None), ("cp_loss", -1), ("quality_method", "mate-score-v1")],
)
def test_cp_analysis_requires_valid_loss_and_method(field, value, registry):
    payload = sample("analysis/result-cp-black")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("AnalysisResultV1", payload, registry)


@pytest.mark.parametrize(
    "path,loss", [("cp-white", -10), ("cp-black", 0), ("cp-black", 100)]
)
def test_cp_loss_uses_the_mover_pov(path, loss):
    payload = sample("analysis/result-" + path)
    payload["cp_loss"] = loss
    with pytest.raises(ValueError, match="mover POV"):
        check_analysis_fixture(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("fen", "arbitrary"),
        ("engine_path", "/bin/sh"),
        ("nodes", 10000000),
        ("multipv", 3),
        ("revision", 0),
    ],
)
def test_request_accepts_no_client_position_or_worker_options(field, value, registry):
    payload = sample("analysis/request-quick")
    payload[field] = value
    with pytest.raises(ValidationError):
        validate("AnalysisRequestV1", payload, registry)


@pytest.mark.parametrize(
    "limits",
    [
        {"time_ms": None, "nodes": None, "depth": None},
        {"time_ms": 0, "nodes": None, "depth": None},
        {"time_ms": 30001, "nodes": None, "depth": None},
        {"time_ms": None, "nodes": 10000001, "depth": None},
        {"time_ms": None, "nodes": None, "depth": 65},
        {
            "time_ms": 100,
            "nodes": None,
            "depth": None,
            "url": "https://untrusted.invalid",
        },
    ],
)
def test_engine_limits_are_explicit_and_bounded(limits, registry):
    with pytest.raises(ValidationError):
        validate("EngineLimitsV1", limits, registry)


@pytest.mark.parametrize("name", ["time_ms", "nodes", "depth"])
def test_any_one_engine_bound_is_sufficient(name, registry):
    limits = dict(time_ms=None, nodes=None, depth=None)
    limits[name] = 1
    validate("EngineLimitsV1", limits, registry)


@pytest.mark.parametrize(
    "mutation",
    [
        "illegal-pv",
        "wrong-root",
        "san",
        "after",
        "position-key",
        "best",
        "ranking",
        "multipv",
        "duplicate",
        "ply",
    ],
)
def test_inconsistent_analysis_evidence_is_rejected(mutation):
    payload = sample("analysis/result-cp-white")
    if mutation == "illegal-pv":
        payload["top_moves"][0]["pv_uci"][1] = "e7e4"
    elif mutation == "wrong-root":
        payload["top_moves"][0]["pv_uci"][0] = "d2d4"
    elif mutation == "san":
        payload["top_moves"][0]["san"] = "d4"
    elif mutation == "after":
        payload["after_fen"] = payload["before_fen"]
    elif mutation == "position-key":
        payload["position_key"] = "0" * 64
    elif mutation == "best":
        payload["best_move_uci"] = "d2d4"
    elif mutation == "ranking":
        payload["top_moves"][1]["score"]["value"] = 100
    elif mutation == "multipv":
        payload["engine"]["multipv"] = 3
    elif mutation == "duplicate":
        payload["top_moves"][1] = copy.deepcopy(payload["top_moves"][0])
    else:
        payload["ply"] = 2
    with pytest.raises(ValueError):
        check_analysis_fixture(payload)


@pytest.mark.parametrize(
    "mutation",
    [
        "check",
        "capture",
        "material",
        "motif",
        "fact-id",
        "claim-fen",
        "claim-move",
        "winner",
    ],
)
def test_claims_must_have_mechanical_evidence(mutation):
    payload = sample("analysis/result-mate")
    facts = payload["facts"]
    if mutation == "check":
        facts["checks"] = False
    elif mutation == "capture":
        facts["captures"] = True
    elif mutation == "material":
        facts["material_delta"] = 100
    elif mutation == "motif":
        facts["motifs_verified"].append("castling")
    elif mutation == "fact-id":
        facts["verified_claims"][1]["fact_id"] = facts["verified_claims"][0]["fact_id"]
    elif mutation == "claim-fen":
        facts["verified_claims"][0]["evidence"]["after_fen"] = payload["before_fen"]
    elif mutation == "claim-move":
        facts["verified_claims"][0]["evidence"]["uci"] = "h7h6"
    else:
        facts["verified_claims"][1]["evidence"]["winner"] = "white"
    with pytest.raises(ValueError):
        check_analysis_fixture(payload)


def test_en_passant_evidence_names_the_captured_square():
    payload = sample("analysis/result-en-passant")
    payload["facts"]["verified_claims"][0]["evidence"]["square"] = "d6"
    with pytest.raises(ValueError, match="capture claim"):
        check_analysis_fixture(payload)


def test_promotion_claim_matches_the_promoted_piece():
    payload = sample("analysis/result-promotion")
    payload["facts"]["verified_claims"][1]["evidence"]["promoted_piece"] = "knight"
    with pytest.raises(ValueError, match="promotion claim"):
        check_analysis_fixture(payload)


@pytest.mark.parametrize("status", ["pending", "running", "failed"])
def test_only_done_jobs_can_reference_a_result(status, registry):
    payload = sample("analysis/job-" + status)
    payload["analysis_id"] = sample("analysis/result-cp-white")["analysis_id"]
    with pytest.raises(ValidationError):
        validate("AnalysisJobV1", payload, registry)


@pytest.mark.parametrize("status", ["done", "failed"])
def test_terminal_job_requires_result_or_error(status, registry):
    payload = sample("analysis/job-" + status)
    payload["analysis_id" if status == "done" else "error"] = None
    with pytest.raises(ValidationError):
        validate("AnalysisJobV1", payload, registry)


def test_job_timestamps_cannot_run_backwards():
    payload = sample("analysis/job-pending")
    payload["updated_at"] = "2026-11-06T14:00:00Z"
    with pytest.raises(ValueError):
        check_job_fixture(payload)


@pytest.mark.parametrize(
    "kind", ["matchmaking.matched", "game.submit_move", "analysis.secret", "unknown"]
)
def test_unknown_or_command_events_are_not_game_stream_events(kind, registry):
    payload = sample("game/events/analysis-ready")
    payload["type"] = kind
    with pytest.raises(ValidationError):
        validate("GameEventV1", payload, registry, event=True)


@pytest.mark.parametrize("name", ["analysis-ready", "coach-ready"])
def test_ready_event_has_no_evaluation_or_prose_channel(name, registry):
    payload = sample("game/events/" + name)
    payload["payload"]["pv_uci"] = ["e2e4"]
    payload["payload"]["summary"] = "Untrusted prose"
    with pytest.raises(ValidationError):
        validate("GameEventV1", payload, registry, event=True)


@pytest.mark.parametrize("mutation", ["seq", "schema", "game", "revision", "payload"])
def test_event_discriminator_and_envelope_are_strict(mutation, registry):
    payload = sample("game/events/analysis-ready")
    if mutation == "seq":
        payload["seq"] = 0
    elif mutation == "schema":
        payload["schema_version"] = 2
    elif mutation == "game":
        payload["game_id"] = None
    elif mutation == "revision":
        payload["payload"]["revision"] = -1
    else:
        payload["type"] = "game.move_committed"
    with pytest.raises(ValidationError):
        validate("GameEventV1", payload, registry, event=True)


@pytest.mark.parametrize("mutation", ["envelope", "reason", "cursor"])
def test_resync_cursors_are_consistent(mutation):
    payload = sample("game/events/resync-required")
    if mutation == "envelope":
        payload["seq"] = 7
    elif mutation == "reason":
        payload["payload"]["reason"] = "replay_unavailable"
    else:
        payload["payload"]["after_seq"] = 0
    with pytest.raises(ValueError):
        check_event_fixture(payload)


def test_bootstrap_and_durable_sequence_replay_to_current_branch(registry):
    bootstrap = sample("game/events/snapshot")
    check_event_fixture(bootstrap)
    board = chess.Board(bootstrap["payload"]["fen"])
    revision, version, seq = 0, 0, bootstrap["seq"]
    for name in [
        "move-committed",
        "analysis-ready",
        "coach-ready",
        "clock-sync",
        "takeback-applied",
        "status-changed",
    ]:
        frame = sample("game/events/" + name)
        validate("GameEventV1", frame, registry, event=True)
        check_event_fixture(frame)
        assert frame["game_id"] == bootstrap["game_id"]
        assert frame["seq"] == seq + 1
        seq = frame["seq"]
        payload = frame["payload"]
        if frame["type"] == "game.move_committed":
            board.push_uci(payload["move"]["uci"])
            assert board.fen() == payload["fen"]
        elif frame["type"] == "game.takeback_applied":
            assert payload["from_ply"] == board.ply()
            for _ in range(payload["from_ply"] - payload["to_ply"]):
                board.pop()
            assert board.fen() == payload["fen"]
            assert payload["new_revision"] == revision + 1
            revision = payload["new_revision"]
        if "revision" in payload:
            assert payload["revision"] == revision
        if "version" in payload and frame["type"] != "game.clock_sync":
            assert payload["version"] == version + 1
            version = payload["version"]
    assert board == chess.Board()
    assert (seq, revision, version) == (6, 1, 3)


def test_fixture_ids_and_ready_scope_are_consistent():
    result = sample("analysis/result-cp-white")
    for name in ["analysis-ready", "coach-ready"]:
        frame = sample("game/events/" + name)
        assert frame["game_id"] == result["game_id"]
        assert frame["payload"]["analysis_id"] == result["analysis_id"]
        assert frame["payload"]["revision"] == result["revision"]
        assert frame["payload"]["ply"] == result["ply"]
