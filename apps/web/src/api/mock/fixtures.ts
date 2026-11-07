/** Temporary B-004 fixture; replace with A-001/A-003 generated common fixtures. */
export const mockSnapshot = {
  schema_version: 1,
  id: "mock-game-0001",
  status: "active",
  revision: 0,
  version: 1,
  seq: 1,
  capabilities: { can_move: false, can_analyze_now: false, can_takeback: false },
} as const;

export const mockProblem = {
  type: "https://mlchess.dev/problems/mock-validation",
  title: "Mock validation failed",
  status: 422,
  code: "MOCK_VALIDATION_ERROR",
  detail: "This deterministic fixture represents a server-side validation error.",
  request_id: "mock-request-0001",
} as const;
