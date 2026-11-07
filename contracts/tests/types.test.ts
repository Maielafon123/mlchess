import { createChessClient } from "../client.js";
import type { components } from "../generated/api.js";

const client = createChessClient("https://mlchess.invalid");
const id = "2de40e7e-5241-423e-8fce-2ef1645595dc";
const headers = { "X-CSRF-Token": "fixture-csrf", "Idempotency-Key": id };

// Compiled but not executed: paths, headers, body, and responses come from schemas.
async function examples() {
  const created = await client.POST("/api/v1/games", {
    params: { header: headers },
    body: { mode: "coach", time_control: null, human_color: "black", ai_profile: "club" },
  });
  const gameId: string | undefined = created.data?.id;
  await client.POST("/api/v1/games/{id}/moves", {
    params: { path: { id }, header: { "X-CSRF-Token": "fixture-csrf" } },
    body: { client_move_id: id, expected_version: 0, uci: "e2e4" },
  });
  const analysis = await client.GET("/api/v1/games/{id}/analysis/{ply}", {
    params: { path: { id, ply: 1 } },
  });
  const version: 1 | undefined = analysis.data?.schema_version;
  return { gameId, version };
}
void examples;

// @ts-expect-error rated creation is server-only
const rated: components["schemas"]["CreateGameV1"] = { mode: "rated", time_control: null };
// @ts-expect-error expected_version is mandatory
const noVersion: components["schemas"]["SubmitMoveV1"] = { client_move_id: id, uci: "e2e4" };
// @ts-expect-error evaluation POV is explicitly White
const wrongPov: components["schemas"]["ScoreV1"] = { kind: "mate", value: 1, pov: "black" };
// @ts-expect-error mutating route requires CSRF and idempotency headers
void client.POST("/api/v1/games", { body: { mode: "friend", time_control: null } });
// @ts-expect-error unsupported route cannot be called through typed SDK
void client.POST("/api/v1/engine/arbitrary-fen", { body: { fen: "anything" } });
void [rated, noVersion, wrongPov];
