import { useEffect, useMemo, useRef, useState } from "react";
import { LearningApi, type Lesson, type Language } from "../../api/learningApi";
import { ensurePublicSession } from "../../auth/guestSession";
import { LessonBoard } from "./LessonBoard";

export function LessonCatalog({ api, language = "en" }: { api?: LearningApi; language?: Language }) {
  const learningApi = useMemo(() => api ?? new LearningApi(), [api]);
  const [items, setItems] = useState<Lesson[]>([]);
  const [selected, setSelected] = useState<Lesson | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [epoch, setEpoch] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const busy = useRef(false);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const openedLesson = useRef<HTMLButtonElement | null>(null);
  const selectedId = selected?.id;
  const ru = language === "ru";
  const labels = ru ? { open: "Открыть урок", done: "Завершить урок", source: "Источник", previous: "Назад", next: "Далее", loading: "Загружаем уроки…", error: "Не удалось сохранить или загрузить урок. Повторите попытку.", retry: "Повторить" } : { open: "Open lesson", done: "Mark completed", source: "Source", previous: "Previous", next: "Next", loading: "Loading lessons…", error: "Could not load or save the lesson. Please retry.", retry: "Retry" };
  const statusLabel = (status: Lesson["status"]) => ru ? ({ "not-started": "Не начат", started: "В процессе", completed: "Завершён" })[status] : status;
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      await ensurePublicSession();
      const result = await learningApi.list(page, 6, language, controller.signal);
      if (controller.signal.aborted) return;
      setItems(result.items); setTotalPages(result.total_pages); setEpoch(result.learning_epoch); setError(null);
    })().catch(() => { if (!controller.signal.aborted) setError(labels.error); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [learningApi, language, page, reload, labels.error]);
  useEffect(() => {
    if (selectedId) detailHeading.current?.focus();
    else if (openedLesson.current?.isConnected) openedLesson.current.focus();
  }, [selectedId]);
  const update = async (lesson: Lesson, status: "started" | "completed") => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError(null);
    try {
      const saved = await learningApi.status(lesson.id, status, epoch, language);
      setSelected(saved); setItems((list) => list.map((item) => item.id === saved.id ? saved : item));
    } catch { setError(labels.error); }
    finally { busy.current = false; setPending(false); }
  };
  return <section className="lesson-catalog" aria-label="Lesson catalog" aria-busy={loading || pending}>
    {error && <div className="error-banner" role="alert">{error} <button type="button" onClick={() => setReload((n) => n + 1)}>{labels.retry}</button></div>}
    {loading && <p role="status">{labels.loading}</p>}
    <div hidden={!!selected}>
      <div className="catalog-grid">{items.map((lesson) => <article className="lesson-card" key={lesson.id}>
        <span className="status-chip">{statusLabel(lesson.status)}</span><h2>{lesson.title}</h2><p>{lesson.summary}</p>
        <div className="lesson-tags">{lesson.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
        <button className="button button-secondary" disabled={pending} type="button" onClick={(event) => {
          openedLesson.current = event.currentTarget;
          setSelected(lesson);
          if (lesson.status === "not-started") void update(lesson, "started");
        }}>{labels.open}</button>
      </article>)}</div>
      <div className="catalog-pagination">
        <button type="button" disabled={page === 1 || loading || pending} onClick={() => { setLoading(true); setPage((n) => n - 1); }}>{labels.previous}</button>
        <span>{page} / {totalPages}</span>
        <button type="button" disabled={page >= totalPages || loading || pending} onClick={() => { setLoading(true); setPage((n) => n + 1); }}>{labels.next}</button>
      </div>
    </div>
    {selected && <article className="lesson-detail" aria-label={ru ? "Урок" : "Lesson detail"}>
      <div className="lesson-navigation"><button className="button button-secondary" type="button" disabled={pending} onClick={() => setSelected(null)}>{ru ? "К списку уроков" : "Back to lessons"}</button></div>
      <div className="analysis-header"><h2 ref={detailHeading} tabIndex={-1}>{selected.title}</h2><span className="status-chip">{statusLabel(selected.status)}</span></div>
      <p>{selected.body}</p>
      <LessonBoard key={selected.id} lessonId={selected.id} language={language} />
      <p className="coach-status">{labels.source}: <a href={selected.source_url} target="_blank" rel="noreferrer">{selected.source_name}</a> · {selected.license}</p>
      <button className="button button-primary" disabled={pending || selected.status === "completed"} type="button" onClick={() => void update(selected, "completed")}>{labels.done}</button>
    </article>}
  </section>;
}
