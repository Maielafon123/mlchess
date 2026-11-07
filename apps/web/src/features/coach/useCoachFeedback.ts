import { useCallback, useMemo, useRef, useState } from "react";
import { CoachApi, type CoachExplanation, type CoachLevel, type CoachRequest } from "../../api/coachApi";

export type CoachFeedbackState = { explanation: CoachExplanation | null; pending: boolean; error: string | null };

export function useCoachFeedback(api?: CoachApi) {
  const resolvedApi = useMemo(() => api ?? new CoachApi(), [api]);
  const requestId = useRef(0);
  const [state, setState] = useState<CoachFeedbackState>({ explanation: null, pending: false, error: null });

  const invalidate = useCallback(() => {
    requestId.current += 1;
    setState({ explanation: null, pending: false, error: null });
  }, []);

  const requestFeedback = useCallback(async (input: Omit<CoachRequest, "schema_version" | "level">, level: CoachLevel) => {
    const id = ++requestId.current;
    setState({ explanation: null, pending: true, error: null });
    try {
      const job = await resolvedApi.request({ ...input, schema_version: 1, level });
      const ready = job.status === "ready" ? job : await resolvedApi.get(job.job_id);
      if (id !== requestId.current) return;
      if (!ready.explanation || ready.explanation.revision !== input.revision) {
        setState({ explanation: null, pending: false, error: "Coach feedback is stale for this position." });
        return;
      }
      setState({ explanation: ready.explanation, pending: false, error: null });
    } catch (error: unknown) {
      if (id === requestId.current) setState({ explanation: null, pending: false, error: error instanceof Error ? error.message : "Coach feedback unavailable" });
    }
  }, [resolvedApi]);

  return useMemo(() => ({ ...state, requestFeedback, invalidate }), [invalidate, requestFeedback, state]);
}
