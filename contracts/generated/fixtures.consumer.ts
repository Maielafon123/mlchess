// Generated fixture/type compatibility examples. Do not edit.
import type { components } from "./api.js";

// common/current-account.json
export const fixture0 = {
  "schema_version": 1,
  "id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8",
  "kind": "account",
  "display_name": "Player",
  "expires_at": "2026-11-08T14:00:00Z"
} satisfies components["schemas"]["CurrentUserV1"];

// common/current-guest.json
export const fixture1 = {
  "schema_version": 1,
  "id": "32a0b81c-a16b-42d7-a4af-86ec5f463f2f",
  "kind": "guest",
  "display_name": null,
  "expires_at": "2026-11-07T15:00:00Z"
} satisfies components["schemas"]["CurrentUserV1"];

// game/create-coach.json
export const fixture2 = {
  "mode": "coach",
  "time_control": null,
  "human_color": "white",
  "ai_profile": "beginner"
} satisfies components["schemas"]["CreateGameV1"];

// game/create-friend.json
export const fixture3 = {
  "mode": "friend",
  "time_control": {
    "initial_ms": 600000,
    "increment_ms": 0
  }
} satisfies components["schemas"]["CreateGameV1"];

// game/snapshot-coach.json
export const fixture4 = {
  "schema_version": 1,
  "id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "mode": "coach",
  "status": "active",
  "version": 1,
  "revision": 0,
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "ply": 1,
  "side_to_move": "black",
  "players": [
    {
      "side": "white",
      "kind": "human",
      "user_id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8"
    },
    {
      "side": "black",
      "kind": "engine",
      "user_id": null
    }
  ],
  "moves": [
    {
      "ply": 1,
      "uci": "e2e4",
      "san": "e4"
    }
  ],
  "time_control": null,
  "clock": null,
  "capabilities": {
    "can_move": false,
    "can_takeback": true,
    "can_analyze_now": true
  },
  "result": null,
  "termination": null
} satisfies components["schemas"]["GameSnapshotV1"];

// game/snapshot-waiting.json
export const fixture5 = {
  "schema_version": 1,
  "id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "mode": "friend",
  "status": "waiting",
  "version": 0,
  "revision": 0,
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "ply": 0,
  "side_to_move": "white",
  "players": [
    {
      "side": "white",
      "kind": "human",
      "user_id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8"
    }
  ],
  "moves": [],
  "time_control": {
    "initial_ms": 600000,
    "increment_ms": 0
  },
  "clock": {
    "white_remaining_ms": 600000,
    "black_remaining_ms": 600000,
    "running_side": null,
    "server_now": "2026-11-07T14:00:00Z"
  },
  "capabilities": {
    "can_move": false,
    "can_takeback": false,
    "can_analyze_now": false
  },
  "result": null,
  "termination": null
} satisfies components["schemas"]["GameSnapshotV1"];

// game/snapshot-finished.json
export const fixture6 = {
  "schema_version": 1,
  "id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "mode": "rated",
  "status": "finished",
  "version": 2,
  "revision": 0,
  "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "ply": 1,
  "side_to_move": "black",
  "players": [
    {
      "side": "white",
      "kind": "human",
      "user_id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8"
    },
    {
      "side": "black",
      "kind": "human",
      "user_id": "32a0b81c-a16b-42d7-a4af-86ec5f463f2f"
    }
  ],
  "moves": [
    {
      "ply": 1,
      "uci": "e2e4",
      "san": "e4"
    }
  ],
  "time_control": {
    "initial_ms": 600000,
    "increment_ms": 0
  },
  "clock": {
    "white_remaining_ms": 600000,
    "black_remaining_ms": 600000,
    "running_side": null,
    "server_now": "2026-11-07T14:00:00Z"
  },
  "capabilities": {
    "can_move": false,
    "can_takeback": false,
    "can_analyze_now": true
  },
  "result": "white",
  "termination": "resignation"
} satisfies components["schemas"]["GameSnapshotV1"];

// game/submit-move.json
export const fixture7 = {
  "client_move_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914",
  "expected_version": 0,
  "uci": "e2e4"
} satisfies components["schemas"]["SubmitMoveV1"];

// game/move-accepted.json
export const fixture8 = {
  "schema_version": 1,
  "client_move_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914",
  "move": {
    "ply": 1,
    "uci": "e2e4",
    "san": "e4"
  },
  "snapshot": {
    "schema_version": 1,
    "id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
    "mode": "coach",
    "status": "active",
    "version": 1,
    "revision": 0,
    "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    "ply": 1,
    "side_to_move": "black",
    "players": [
      {
        "side": "white",
        "kind": "human",
        "user_id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8"
      },
      {
        "side": "black",
        "kind": "engine",
        "user_id": null
      }
    ],
    "moves": [
      {
        "ply": 1,
        "uci": "e2e4",
        "san": "e4"
      }
    ],
    "time_control": null,
    "clock": null,
    "capabilities": {
      "can_move": false,
      "can_takeback": true,
      "can_analyze_now": true
    },
    "result": null,
    "termination": null
  }
} satisfies components["schemas"]["MoveAcceptedV1"];

// game/takeback.json
export const fixture9 = {
  "expected_version": 2,
  "plies": 2,
  "client_action_id": "45e12d64-427a-4a39-80c3-099d8356b48f"
} satisfies components["schemas"]["TakebackV1"];

// common/error-stale-version.json
export const fixture10 = {
  "schema_version": 1,
  "type": "urn:mlchess:problem:stale-game-version",
  "title": "Game version conflict",
  "status": 409,
  "code": "STALE_GAME_VERSION",
  "detail": "Reload the game snapshot before submitting a new command.",
  "request_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914"
} satisfies components["schemas"]["ProblemDetailsV1"];

// common/error-illegal-move.json
export const fixture11 = {
  "schema_version": 1,
  "type": "urn:mlchess:problem:illegal-move",
  "title": "Illegal move",
  "status": 422,
  "code": "ILLEGAL_MOVE",
  "detail": "The move is not legal in the current position.",
  "request_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914"
} satisfies components["schemas"]["ProblemDetailsV1"];

// analysis/request-quick.json
export const fixture12 = {
  "ply": 1,
  "analysis_level": "quick"
} satisfies components["schemas"]["AnalysisRequestV1"];

// analysis/result-cp-white.json
export const fixture13 = {
  "schema_version": 1,
  "analysis_id": "0f65025d-7b3d-40f1-8958-5c236483c8b7",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 1,
  "position_key": "2020a069010f330ac60091b8cca61d8f137c20e93a1e9b836fd57d6f82ad98ae",
  "before_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "after_fen": "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1",
  "played_move_uci": "g1f3",
  "best_move_uci": "e2e4",
  "top_moves": [
    {
      "uci": "e2e4",
      "san": "e4",
      "pv_uci": [
        "e2e4",
        "e7e5",
        "g1f3"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    },
    {
      "uci": "d2d4",
      "san": "d4",
      "pv_uci": [
        "d2d4",
        "d7d5",
        "c2c4"
      ],
      "score": {
        "kind": "cp",
        "value": 25,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 20,
    "pov": "white"
  },
  "quality": "good",
  "quality_method": "cp-loss-v1",
  "cp_loss": 10,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 2,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": false,
    "material_delta": 0,
    "motifs_verified": [],
    "verified_claims": []
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-cp-black.json
export const fixture14 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000001",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 2,
  "position_key": "6a7971e8386a887d1b172524183a94c9d06f9dc74d6028db4af90509904d6958",
  "before_fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
  "after_fen": "rnbqkbnr/1ppppppp/p7/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "played_move_uci": "a7a6",
  "best_move_uci": "e7e5",
  "top_moves": [
    {
      "uci": "e7e5",
      "san": "e5",
      "pv_uci": [
        "e7e5",
        "g1f3",
        "b8c6"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    },
    {
      "uci": "c7c5",
      "san": "c5",
      "pv_uci": [
        "c7c5",
        "g1f3",
        "d7d6"
      ],
      "score": {
        "kind": "cp",
        "value": 40,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 80,
    "pov": "white"
  },
  "quality": "inaccuracy",
  "quality_method": "cp-loss-v1",
  "cp_loss": 50,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 2,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": false,
    "material_delta": 0,
    "motifs_verified": [],
    "verified_claims": []
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-mate.json
export const fixture15 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000002",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 4,
  "position_key": "b7fd99a28a3350aa3d56aa88f4ebfcc97ca73eabfdc6b55fb3eb1b15efccf5ec",
  "before_fen": "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
  "after_fen": "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3",
  "played_move_uci": "d8h4",
  "best_move_uci": "d8h4",
  "top_moves": [
    {
      "uci": "d8h4",
      "san": "Qh4#",
      "pv_uci": [
        "d8h4"
      ],
      "score": {
        "kind": "mate",
        "value": -1,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "mate",
    "value": -1,
    "pov": "white"
  },
  "score_after": {
    "kind": "mate",
    "value": 0,
    "pov": "white"
  },
  "quality": "best",
  "quality_method": "mate-score-v1",
  "cp_loss": null,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": true,
    "captures": false,
    "material_delta": 0,
    "motifs_verified": [
      "checkmate"
    ],
    "verified_claims": [
      {
        "fact_id": "00000000-0000-4000-8000-000000000003",
        "kind": "check",
        "evidence": {
          "uci": "d8h4",
          "after_fen": "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
        }
      },
      {
        "fact_id": "00000000-0000-4000-8000-000000000004",
        "kind": "checkmate",
        "evidence": {
          "uci": "d8h4",
          "after_fen": "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3",
          "winner": "black"
        }
      }
    ]
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/job-pending.json
export const fixture16 = {
  "schema_version": 1,
  "id": "00000000-0000-4000-8000-000000000005",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 1,
  "position_key": "2020a069010f330ac60091b8cca61d8f137c20e93a1e9b836fd57d6f82ad98ae",
  "status": "pending",
  "analysis_id": null,
  "error": null,
  "created_at": "2026-11-07T14:00:00Z",
  "updated_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisJobV1"];

// analysis/job-running.json
export const fixture17 = {
  "schema_version": 1,
  "id": "00000000-0000-4000-8000-000000000005",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 1,
  "position_key": "2020a069010f330ac60091b8cca61d8f137c20e93a1e9b836fd57d6f82ad98ae",
  "status": "running",
  "analysis_id": null,
  "error": null,
  "created_at": "2026-11-07T14:00:00Z",
  "updated_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisJobV1"];

// analysis/job-done.json
export const fixture18 = {
  "schema_version": 1,
  "id": "00000000-0000-4000-8000-000000000005",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 1,
  "position_key": "2020a069010f330ac60091b8cca61d8f137c20e93a1e9b836fd57d6f82ad98ae",
  "status": "done",
  "analysis_id": "0f65025d-7b3d-40f1-8958-5c236483c8b7",
  "error": null,
  "created_at": "2026-11-07T14:00:00Z",
  "updated_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisJobV1"];

// analysis/job-failed.json
export const fixture19 = {
  "schema_version": 1,
  "id": "00000000-0000-4000-8000-000000000005",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 1,
  "position_key": "2020a069010f330ac60091b8cca61d8f137c20e93a1e9b836fd57d6f82ad98ae",
  "status": "failed",
  "analysis_id": null,
  "error": {
    "schema_version": 1,
    "type": "urn:mlchess:problem:service-unavailable",
    "title": "Engine unavailable",
    "status": 503,
    "code": "SERVICE_UNAVAILABLE",
    "detail": "Analysis is temporarily unavailable.",
    "request_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914"
  },
  "created_at": "2026-11-07T14:00:00Z",
  "updated_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisJobV1"];

// analysis/error-active-pvp.json
export const fixture20 = {
  "schema_version": 1,
  "type": "urn:mlchess:problem:forbidden",
  "title": "Analysis is unavailable",
  "status": 403,
  "code": "FORBIDDEN",
  "detail": "Analysis is unavailable for an active friend or rated game.",
  "request_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914"
} satisfies components["schemas"]["ProblemDetailsV1"];

// game/events/snapshot.json
export const fixture21 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000011",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 0,
  "type": "game.snapshot",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "schema_version": 1,
    "id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
    "mode": "coach",
    "status": "active",
    "version": 0,
    "revision": 0,
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "ply": 0,
    "side_to_move": "white",
    "players": [
      {
        "side": "white",
        "kind": "human",
        "user_id": "deafed4a-ab07-41e1-b2f0-d40f2785e8a8"
      },
      {
        "side": "black",
        "kind": "engine",
        "user_id": null
      }
    ],
    "moves": [],
    "time_control": {
      "initial_ms": 600000,
      "increment_ms": 0
    },
    "clock": {
      "white_remaining_ms": 600000,
      "black_remaining_ms": 600000,
      "running_side": "white",
      "server_now": "2026-11-07T14:00:00Z"
    },
    "capabilities": {
      "can_move": true,
      "can_takeback": false,
      "can_analyze_now": true
    },
    "result": null,
    "termination": null
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/move-committed.json
export const fixture22 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000012",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 1,
  "type": "game.move_committed",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "version": 1,
    "revision": 0,
    "move": {
      "ply": 1,
      "uci": "g1f3",
      "san": "Nf3"
    },
    "fen": "rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1",
    "side_to_move": "black",
    "clock": {
      "white_remaining_ms": 599000,
      "black_remaining_ms": 600000,
      "running_side": "black",
      "server_now": "2026-11-07T14:00:00Z"
    }
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/analysis-ready.json
export const fixture23 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000013",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 2,
  "type": "analysis.ready",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "analysis_id": "0f65025d-7b3d-40f1-8958-5c236483c8b7",
    "revision": 0,
    "ply": 1
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/coach-ready.json
export const fixture24 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000014",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 3,
  "type": "coach.ready",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "explanation_id": "00000000-0000-4000-8000-000000000006",
    "analysis_id": "0f65025d-7b3d-40f1-8958-5c236483c8b7",
    "revision": 0,
    "ply": 1
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/clock-sync.json
export const fixture25 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000015",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 4,
  "type": "game.clock_sync",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "version": 1,
    "revision": 0,
    "ply": 1,
    "clock": {
      "white_remaining_ms": 599000,
      "black_remaining_ms": 599000,
      "running_side": "black",
      "server_now": "2026-11-07T14:00:00Z"
    }
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/takeback-applied.json
export const fixture26 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000016",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 5,
  "type": "game.takeback_applied",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "version": 2,
    "from_ply": 1,
    "to_ply": 0,
    "new_revision": 1,
    "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "side_to_move": "white",
    "clock": {
      "white_remaining_ms": 600000,
      "black_remaining_ms": 600000,
      "running_side": "white",
      "server_now": "2026-11-07T14:00:00Z"
    }
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/status-changed.json
export const fixture27 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000017",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 6,
  "type": "game.status_changed",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "version": 3,
    "revision": 1,
    "status": "aborted",
    "result": null,
    "termination": "aborted",
    "clock": {
      "white_remaining_ms": 600000,
      "black_remaining_ms": 600000,
      "running_side": null,
      "server_now": "2026-11-07T14:00:00Z"
    }
  }
} satisfies components["schemas"]["GameEventV1"];

// game/events/resync-required.json
export const fixture28 = {
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000018",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "seq": 6,
  "type": "server.resync_required",
  "occurred_at": "2026-11-07T14:00:00Z",
  "payload": {
    "after_seq": 20,
    "latest_seq": 6,
    "reason": "cursor_ahead"
  }
} satisfies components["schemas"]["GameEventV1"];

// analysis/result-capture.json
export const fixture29 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000024",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 3,
  "position_key": "9b01405924a491897c4e5427ff6ee298c3ac8126277cc7afb40c2bdbd9cdbb72",
  "before_fen": "rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
  "after_fen": "rnbqkbnr/ppp1pppp/8/3P4/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 2",
  "played_move_uci": "e4d5",
  "best_move_uci": "e4d5",
  "top_moves": [
    {
      "uci": "e4d5",
      "san": "exd5",
      "pv_uci": [
        "e4d5"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "quality": "best",
  "quality_method": "cp-loss-v1",
  "cp_loss": 0,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": true,
    "material_delta": 100,
    "motifs_verified": [],
    "verified_claims": [
      {
        "fact_id": "00000000-0000-4000-8000-000000000036",
        "kind": "capture",
        "evidence": {
          "uci": "e4d5",
          "captured_piece": "pawn",
          "square": "d5"
        }
      }
    ]
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-en-passant.json
export const fixture30 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000025",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 5,
  "position_key": "330d01d5c65f5e617c8e6591b92c7831c6587a33feb9b043521e25c41cc1a674",
  "before_fen": "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3",
  "after_fen": "rnbqkbnr/1pp1pppp/p2P4/8/8/8/PPPP1PPP/RNBQKBNR b KQkq - 0 3",
  "played_move_uci": "e5d6",
  "best_move_uci": "e5d6",
  "top_moves": [
    {
      "uci": "e5d6",
      "san": "exd6",
      "pv_uci": [
        "e5d6"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "quality": "best",
  "quality_method": "cp-loss-v1",
  "cp_loss": 0,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": true,
    "material_delta": 100,
    "motifs_verified": [
      "en_passant"
    ],
    "verified_claims": [
      {
        "fact_id": "00000000-0000-4000-8000-000000000036",
        "kind": "capture",
        "evidence": {
          "uci": "e5d6",
          "captured_piece": "pawn",
          "square": "d5"
        }
      }
    ]
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-castling.json
export const fixture31 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000026",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 7,
  "position_key": "d9c852663719c285b5b2d4f0b9f3b99f9d230a3e2c3a42f6438d929fcc36f082",
  "before_fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
  "after_fen": "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 5 4",
  "played_move_uci": "e1g1",
  "best_move_uci": "e1g1",
  "top_moves": [
    {
      "uci": "e1g1",
      "san": "O-O",
      "pv_uci": [
        "e1g1"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "quality": "best",
  "quality_method": "cp-loss-v1",
  "cp_loss": 0,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": false,
    "material_delta": 0,
    "motifs_verified": [
      "castling"
    ],
    "verified_claims": []
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-promotion.json
export const fixture32 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000027",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 9,
  "position_key": "ea9be4ce329bdf6f46a8a293b225c62c67d992f49a9c1ac6d6ed20ebbf17c97b",
  "before_fen": "rnbqkbnr/pPppppp1/8/8/8/8/1PPPPPpP/RNBQKBNR w KQkq - 0 5",
  "after_fen": "Qnbqkbnr/p1ppppp1/8/8/8/8/1PPPPPpP/RNBQKBNR b KQk - 0 5",
  "played_move_uci": "b7a8q",
  "best_move_uci": "b7a8q",
  "top_moves": [
    {
      "uci": "b7a8q",
      "san": "bxa8=Q",
      "pv_uci": [
        "b7a8q"
      ],
      "score": {
        "kind": "cp",
        "value": 30,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": 30,
    "pov": "white"
  },
  "quality": "best",
  "quality_method": "cp-loss-v1",
  "cp_loss": 0,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": true,
    "material_delta": 1300,
    "motifs_verified": [
      "promotion"
    ],
    "verified_claims": [
      {
        "fact_id": "00000000-0000-4000-8000-000000000036",
        "kind": "capture",
        "evidence": {
          "uci": "b7a8q",
          "captured_piece": "rook",
          "square": "a8"
        }
      },
      {
        "fact_id": "00000000-0000-4000-8000-000000000037",
        "kind": "promotion",
        "evidence": {
          "uci": "b7a8q",
          "promoted_piece": "queen"
        }
      }
    ]
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// analysis/result-missed-mate.json
export const fixture33 = {
  "schema_version": 1,
  "analysis_id": "00000000-0000-4000-8000-000000000035",
  "game_id": "2de40e7e-5241-423e-8fce-2ef1645595dc",
  "revision": 0,
  "ply": 4,
  "position_key": "1d4a4b48dd12e1b1e13951c25615467ccf1721200fb6a72cfdb7752517af10e3",
  "before_fen": "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2",
  "after_fen": "rnbqkbnr/pppp1pp1/7p/4p3/6P1/5P2/PPPPP2P/RNBQKBNR w KQkq - 0 3",
  "played_move_uci": "h7h6",
  "best_move_uci": "d8h4",
  "top_moves": [
    {
      "uci": "d8h4",
      "san": "Qh4#",
      "pv_uci": [
        "d8h4"
      ],
      "score": {
        "kind": "mate",
        "value": -1,
        "pov": "white"
      }
    }
  ],
  "score_before": {
    "kind": "mate",
    "value": -1,
    "pov": "white"
  },
  "score_after": {
    "kind": "cp",
    "value": -200,
    "pov": "white"
  },
  "quality": "blunder",
  "quality_method": "mate-score-v1",
  "cp_loss": null,
  "engine": {
    "name": "stockfish",
    "version": "fixture-1",
    "model_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "binary_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
    "limits": {
      "time_ms": 100,
      "nodes": 10000,
      "depth": null
    },
    "multipv": 1,
    "threads": 1,
    "hash_mb": 32
  },
  "facts": {
    "checks": false,
    "captures": false,
    "material_delta": 0,
    "motifs_verified": [],
    "verified_claims": []
  },
  "created_at": "2026-11-07T14:00:00Z"
} satisfies components["schemas"]["AnalysisResultV1"];

// common/health-ok.json
export const fixture34 = {
  "schema_version": 1,
  "status": "ok"
} satisfies components["schemas"]["HealthV1"];

// game/resign.json
export const fixture35 = {
  "expected_version": 1
} satisfies components["schemas"]["GameActionV1"];

// common/error-method-not-allowed.json
export const fixture36 = {
  "schema_version": 1,
  "type": "urn:mlchess:problem:method-not-allowed",
  "title": "Method not allowed",
  "status": 405,
  "code": "METHOD_NOT_ALLOWED",
  "detail": "This HTTP method is not available for this resource.",
  "request_id": "fa4509f2-bc32-44c8-bad7-a09a2bf06914"
} satisfies components["schemas"]["ProblemDetailsV1"];
