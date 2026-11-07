export type ProblemDetails = {
  type: string;
  title: string;
  status: number;
  code: string;
  detail: string;
  request_id: string;
  /** Optional server snapshot used to roll back a stale optimistic command. */
  snapshot?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function stringField(value: unknown, fallback: string): string {
  return typeof value === "string" && value.length > 0 ? value : fallback;
}

export function decodeProblemDetails(status: number, payload: unknown): ProblemDetails {
  const body = isRecord(payload) ? payload : {};
  return {
    type: stringField(body.type, "about:blank"),
    title: stringField(body.title, "Request failed"),
    status: typeof body.status === "number" ? body.status : status,
    code: stringField(body.code, "HTTP_ERROR"),
    detail: stringField(body.detail, `Request failed with status ${status}`),
    request_id: stringField(body.request_id, "unknown"),
    snapshot: body.snapshot,
  };
}

export class ApiError extends Error {
  readonly problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail);
    this.name = "ApiError";
    this.problem = problem;
  }
}
