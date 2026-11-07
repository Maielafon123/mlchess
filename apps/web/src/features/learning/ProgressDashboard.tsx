import { useEffect, useMemo, useState } from "react";
import { ProgressApi, type ProgressSnapshot } from "../../api/progressApi";

export function ProgressDashboard({ api }: { api?: ProgressApi }) {
  const resolvedApi = useMemo(() => api ?? new ProgressApi(), [api]); const [progress, setProgress] = useState<ProgressSnapshot | null>(null);
  useEffect(() => { void resolvedApi.get().then(setProgress); }, [resolvedApi]);
  if (!progress) return <div className="status-banner" role="status">Loading progress…</div>;
  return <section className="progress-dashboard" aria-label="Student progress"><div className="analysis-header"><h2>Student progress</h2><span className="status-chip">Demo data — not server persisted</span></div><div className="progress-grid">{progress.skills.map((skill) => <article className="progress-card" key={skill.skill}><h3>{skill.skill}</h3><strong>{skill.correct}/{skill.attempts}</strong><span>{skill.hints_used} hints · streak {skill.streak}</span><small>{skill.due_at && new Date(skill.due_at) <= new Date() ? "Due for review" : `Next review ${skill.due_at ? new Date(skill.due_at).toLocaleDateString() : "—"}`}</small></article>)}</div></section>;
}
