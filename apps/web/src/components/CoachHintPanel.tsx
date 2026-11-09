import { useCallback, useEffect, useMemo } from "react";
import { type CoachLevel, type CoachRequest } from "../api/coachApi";
import { useCoachFeedback } from "../features/coach/useCoachFeedback";

const levels: Array<{ id: CoachLevel; label: string; ru: string }> = [
  { id: "observation", label: "1 · Observation", ru: "1 · Наблюдение" },
  { id: "direction", label: "2 · Direction", ru: "2 · Направление" },
  { id: "idea", label: "3 · Idea", ru: "3 · Идея" },
  { id: "candidates", label: "4 · Candidates", ru: "4 · Кандидаты" },
  { id: "solution", label: "5 · Solution", ru: "5 · Решение" },
];

export function CoachHintPanel({ context, onRequest, autoObservation = true, language = "en" }: { context: Omit<CoachRequest, "schema_version" | "level"> | null; onRequest?: (level: CoachLevel) => void; autoObservation?: boolean; language?: "ru" | "en" }) {
  const ru = language === "ru";
  const feedback = useCoachFeedback();
  const { requestFeedback, invalidate } = feedback;
  const requestLevel = useCallback((level: CoachLevel) => { if (context) { onRequest?.(level); void requestFeedback(context, level); } }, [context, onRequest, requestFeedback]);
  useEffect(() => { invalidate(); if (autoObservation && context) requestLevel("observation"); }, [autoObservation, context, invalidate, requestLevel]);
  const explanation = context && feedback.explanation?.game_id === context.game_id && feedback.explanation.analysis_id === context.analysis_id && feedback.explanation.revision === context.revision && feedback.explanation.ply === context.ply && feedback.explanation.language === context.language ? feedback.explanation : null;
  const activeLevel = explanation?.level;
  const title = useMemo(() => feedback.pending ? (ru ? "Тренер готовит подсказку…" : "Coach is preparing a grounded hint…") : feedback.error ?? (ru ? "Запросите подсказку тренера" : "Ask the coach for a hint"), [feedback.error, feedback.pending, ru]);
  return <section className="coach-panel" aria-label="Coach hints"><div className="analysis-header"><h2>{ru ? "Тренер" : "Coach"}</h2><span className="status-chip">{ru ? "По данным движка" : "Grounded feedback"}</span></div><p className="coach-status" role={feedback.pending || feedback.error ? "status" : undefined}>{title}</p><div className="hint-ladder">{levels.map((level) => <button key={level.id} type="button" data-hint-level={level.id} className={activeLevel === level.id ? "active" : ""} onClick={() => requestLevel(level.id)} disabled={!context || feedback.pending}>{ru ? level.ru : level.label}</button>)}</div>{explanation && <div className="coach-explanation"><h3>{explanation.summary}</h3><p>{explanation.why}</p><p><strong>{ru ? "Вопрос:" : "Question:"}</strong> {explanation.question}</p>{explanation.fallback_used && <span className="status-chip">{explanation.model_id === "verified-rules-v1" ? (ru ? "Локальное объяснение" : "Local explanation") : (ru ? "Объяснение временно недоступно" : "Explanation unavailable")}</span>}</div>}</section>;
}
