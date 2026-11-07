import { useEffect, useMemo } from "react";
import { type CoachLevel, type CoachRequest } from "../api/coachApi";
import { useCoachFeedback } from "../features/coach/useCoachFeedback";

const levels: Array<{ id: CoachLevel; label: string }> = [
  { id: "observation", label: "1 · Observation" },
  { id: "direction", label: "2 · Direction" },
  { id: "idea", label: "3 · Idea" },
  { id: "candidates", label: "4 · Candidates" },
  { id: "solution", label: "5 · Solution" },
];

export function CoachHintPanel({ context, onRequest, autoObservation = true }: { context: Omit<CoachRequest, "schema_version" | "level"> | null; onRequest?: (level: CoachLevel) => void; autoObservation?: boolean }) {
  const feedback = useCoachFeedback();
  const requestLevel = (level: CoachLevel) => { if (context) { onRequest?.(level); void feedback.requestFeedback(context, level); } };
  useEffect(() => { if (autoObservation && context) requestLevel("observation"); }, [autoObservation, context]);
  const activeLevel = feedback.explanation?.level;
  const title = useMemo(() => feedback.pending ? "Coach is preparing a grounded hint…" : feedback.error ?? "Ask the coach for a hint", [feedback.error, feedback.pending]);
  return <section className="coach-panel" aria-label="Coach hints"><div className="analysis-header"><h2>Coach</h2><span className="status-chip">Grounded feedback</span></div><p className="coach-status" role={feedback.pending || feedback.error ? "status" : undefined}>{title}</p><div className="hint-ladder">{levels.map((level) => <button key={level.id} type="button" className={activeLevel === level.id ? "active" : ""} onClick={() => requestLevel(level.id)} disabled={!context || feedback.pending}>{level.label}</button>)}</div>{feedback.explanation && <div className="coach-explanation"><h3>{feedback.explanation.summary}</h3><p>{feedback.explanation.why}</p><p><strong>Question:</strong> {feedback.explanation.question}</p>{feedback.explanation.fallback_used && <span className="status-chip">Fallback</span>}</div>}</section>;
}
