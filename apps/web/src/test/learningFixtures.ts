import { vi } from "vitest";
import { ApiClient } from "../api/client";
import { LearningApi, type Lesson } from "../api/learningApi";
import { PuzzleApi, type Puzzle, type PuzzleState } from "../api/puzzleApi";
import { ProgressApi } from "../api/progressApi";

export const lesson: Lesson = { schema_version: 1, id: "opening-center", title: "Центр в дебюте", summary: "Control the center.", body: "Develop your pieces.", language: "en", status: "not-started", tags: ["opening"], source_name: "MLChess original", source_url: "https://example.org/curriculum", license: "CC BY 4.0" };
export const puzzle: Puzzle = { schema_version: 1, id: "back-rank", fen: "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", difficulty: 1, tags: ["mate"], source_name: "MLChess original", source_url: "https://example.org/curriculum", license: "CC BY 4.0" };
export const initialState: PuzzleState = { schema_version: 1, learning_epoch: 0, puzzle_id: puzzle.id, session_number: 0, current_fen: puzzle.fen, next_ply: 0, completed: false, hints: [] };
export function learningTransport() {
  let state: PuzzleState = structuredClone(initialState);
  let status = lesson.status;
  const fetchImpl = vi.fn<typeof fetch>(async (input, init) => {
    const url = new URL(String(input), "http://test.local");
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    const method = init?.method;
    let payload: unknown;
    if (url.pathname.endsWith("/context")) payload = { schema_version: 1, learning_epoch: 0 };
    else if (url.pathname.endsWith("/lessons")) payload = { schema_version: 1, learning_epoch: 0, page: 1, total_pages: 1, items: [{ ...lesson, status }] };
    else if (url.pathname.endsWith("/status")) { status = body.status; payload = { ...lesson, status }; }
    else if (url.pathname.endsWith("/puzzles")) payload = { schema_version: 1, items: [puzzle] };
    else if (url.pathname.endsWith("/state")) payload = state;
    else if (url.pathname.endsWith("/hints")) { state = { ...state, hints: ["Consider the king’s escape squares."] }; payload = { schema_version: 1, puzzle_id: puzzle.id, session_number: 0, hint_index: 1, text: state.hints[0], has_more: true }; }
    else if (url.pathname.endsWith("/attempts")) { state = { ...state, current_fen: "3R2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 1 1", next_ply: 1, completed: true, solution: [{ uci: "d1d8", san: "Rd8#", fen: "3R2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 1 1" }] }; payload = { schema_version: 1, attempt_id: body.attempt_id, result: "correct", completed: true, next_ply: 1 }; }
    else if (url.pathname.endsWith("/restart")) { state = { ...initialState, session_number: state.session_number + 1 }; payload = state; }
    else if (url.pathname.endsWith("/progress") || url.pathname.endsWith("/review-queue")) payload = { schema_version: 1, student_id: "00000000-0000-4000-8000-000000000001", skills: [] };
    else if (url.pathname.endsWith("/back-rank")) payload = puzzle;
    else throw new Error(`Unexpected ${method} ${url.pathname}`);
    return new Response(JSON.stringify(payload), { headers: { "Content-Type": "application/json" } });
  });
  const client = new ApiClient({ fetchImpl, csrfTokenProvider: () => "test-csrf" });
  return { fetchImpl, learning: new LearningApi(client), puzzles: new PuzzleApi(client), progress: new ProgressApi(client) };
}
