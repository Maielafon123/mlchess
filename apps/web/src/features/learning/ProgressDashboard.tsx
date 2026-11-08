import { useEffect, useMemo, useState } from "react";
import { ProgressApi, type ProgressSnapshot } from "../../api/progressApi";
import { ensurePublicSession } from "../../auth/guestSession";
import type { Language } from "../../api/learningApi";

export function ProgressDashboard({ api, language = "en" }: { api?: ProgressApi; language?: Language }) {
  const resolvedApi = useMemo(() => api ?? new ProgressApi(), [api]);
  const [progress, setProgress] = useState<ProgressSnapshot | null>(null);
  const [due, setDue] = useState<string[]>([]);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  const [pending, setPending] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [epoch, setEpoch] = useState(0);
  const ru = language === "ru";
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      await ensurePublicSession();
      const [snapshot, review, context] = await Promise.all([resolvedApi.get(controller.signal), resolvedApi.review(controller.signal), resolvedApi.context(controller.signal)]);
      if (controller.signal.aborted) return;
      setProgress(snapshot); setDue(review.skills.map((skill) => skill.skill)); setEpoch(context.learning_epoch); setError(false);
    })().catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [resolvedApi, reload]);
  const download = async () => {
    setPending(true); setError(false);
    try {
      const first = await resolvedApi.export();
      const pages = [first];
      let cursor = first.next_cursor;
      while (cursor) {
        const next = await resolvedApi.export(cursor);
        if (next.learning_epoch !== first.learning_epoch || pages.length >= 100) throw new Error("Export changed or exceeded limit");
        pages.push(next); cursor = next.next_cursor;
      }
      const blob = new Blob([JSON.stringify({ ...first, attempts: pages.flatMap((page) => page.attempts), next_cursor: null }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "mlchess-learning.json"; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch { setError(true); }
    finally { setPending(false); }
  };
  const reset = async () => {
    setPending(true); setError(false);
    try { await resolvedApi.reset(epoch); setConfirm(false); setProgress(null); setReload((n) => n + 1); }
    catch { setError(true); }
    finally { setPending(false); }
  };
  return <section className="progress-dashboard" aria-label="Student progress">
    <div className="analysis-header"><h2>{ru ? "Ваш прогресс" : "Student progress"}</h2></div>
    {error && <div className="error-banner" role="alert">{ru ? "Не удалось загрузить или сохранить данные." : "Could not load or save your data."} <button type="button" onClick={() => setReload((n) => n + 1)}>{ru ? "Повторить" : "Retry"}</button></div>}
    {!progress && !error && <p role="status">{ru ? "Загружаем прогресс…" : "Loading progress…"}</p>}
    {progress && <>{progress.skills.length === 0 && <p>{ru ? "Решите первую задачу — здесь появится ваш прогресс." : "Solve your first puzzle to start tracking progress."}</p>}
    <div className="progress-grid">{progress.skills.map((skill) => <article className="progress-card" key={skill.skill}><h3>{skill.skill}</h3><strong>{skill.correct}/{skill.attempts}</strong><span>{skill.hints_used} {ru ? "подсказок · серия" : "hints · streak"} {skill.streak}</span><small>{due.includes(skill.skill) ? (ru ? "Пора повторить" : "Due for review") : skill.due_at ? `${ru ? "Следующее повторение" : "Next review"}: ${new Date(skill.due_at).toLocaleDateString(ru ? "ru-RU" : "en-US")}` : (ru ? "Пока нет попыток" : "No attempts yet")}</small></article>)}</div>
    <p className="coach-status">{ru ? "Гостевой прогресс хранится до истечения сессии. Сохраните файл перед очисткой cookies." : "Guest progress is available while your session is active. Export it before clearing cookies."}</p>
    <div className="game-actions"><button className="button button-secondary" type="button" disabled={pending} onClick={() => void download()}>{ru ? "Скачать данные" : "Export data"}</button><button className="button button-secondary" type="button" disabled={pending} onClick={() => setConfirm(true)}>{ru ? "Сбросить обучение" : "Reset learning"}</button></div>
    {confirm && <div className="status-banner" role="group" aria-label="Confirm reset"><p>{ru ? "Удалить ваши попытки, подсказки и прогресс уроков? Восстановить их будет нельзя. Партии сохранятся." : "Delete your attempts, hints and lesson progress? This cannot be undone. Your games will remain."}</p><button type="button" disabled={pending} onClick={() => void reset()}>{ru ? "Удалить мой прогресс" : "Delete my progress"}</button><button type="button" disabled={pending} onClick={() => setConfirm(false)}>{ru ? "Отмена" : "Cancel"}</button></div>}</>}
  </section>;
}
