import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createChessClient } from "../client.ts";

const load = async (path) => JSON.parse(await readFile(new URL(path, import.meta.url), "utf8"));

test("SDK sends typed create body, same-origin cookies, CSRF and idempotency", async () => {
  const snapshot = await load("../fixtures/game/snapshot-waiting.json");
  const body = await load("../fixtures/game/create-friend.json");
  const key = "fa4509f2-bc32-44c8-bad7-a09a2bf06914";
  let seen;
  const client = createChessClient("https://mlchess.invalid", async (request) => {
    seen = request;
    return new Response(JSON.stringify(snapshot), { status: 201, headers: { "Content-Type": "application/json" } });
  });
  const result = await client.POST("/api/v1/games", {
    params: { header: { "X-CSRF-Token": "csrf-fixture", "Idempotency-Key": key } }, body,
  });
  assert.equal(seen.url, "https://mlchess.invalid/api/v1/games");
  assert.equal(seen.method, "POST");
  assert.equal(seen.credentials, "same-origin");
  assert.equal(seen.headers.get("X-CSRF-Token"), "csrf-fixture");
  assert.equal(seen.headers.get("Idempotency-Key"), key);
  assert.deepEqual(await seen.json(), body);
  assert.deepEqual(result.data, snapshot);
  assert.equal(result.error, undefined);
});

test("SDK preserves structured conflict errors without treating them as success", async () => {
  const problem = await load("../fixtures/common/error-stale-version.json");
  const client = createChessClient("https://mlchess.invalid", async () => new Response(JSON.stringify(problem), {
    status: 409, headers: { "Content-Type": "application/problem+json" },
  }));
  const result = await client.GET("/api/v1/games/{id}", { params: { path: { id: "2de40e7e-5241-423e-8fce-2ef1645595dc" } } });
  assert.equal(result.data, undefined);
  assert.deepEqual(result.error, problem);
  assert.equal(result.response.status, 409);
});
