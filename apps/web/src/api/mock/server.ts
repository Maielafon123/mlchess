import { http, HttpResponse } from "msw";
import { mockProblem, mockSnapshot } from "./fixtures";

export const handlers = [
  http.get("*/api/v1/mock/snapshot", () => HttpResponse.json(mockSnapshot)),
  http.get("*/api/v1/mock/problem", () => HttpResponse.json(mockProblem, { status: 422 })),
];
