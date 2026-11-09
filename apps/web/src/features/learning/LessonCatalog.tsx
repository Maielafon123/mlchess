import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LearningApi, type Lesson, type Language } from "../../api/learningApi";
import { ProgressApi } from "../../api/progressApi";
import { ensurePublicSession } from "../../auth/guestSession";
import { LessonBoard } from "./LessonBoard";
import { mistakeReferences, type MistakeReference } from "./mistakePractice";
import { CoachAvatar } from "../../components/CoachAvatar";

const categories = [
  { id: "tactics", label: ["Тактика", "Tactics"], tags: ["mate", "checks", "captures", "knight"] },
  { id: "strategy", label: ["Стратегия", "Strategy"], tags: ["king-safety", "castling", "en-passant"] },
  { id: "opening", label: ["Дебюты", "Openings"], tags: ["opening", "development"] },
  { id: "endgame", label: ["Эндшпиль", "Endgame"], tags: ["endgame", "promotion", "draw"] },
] as const;
const matches = (lesson: Lesson, category: typeof categories[number]) => lesson.tags.some((tag) => category.tags.some((key) => key === tag));

export function LessonCatalog({ api, language = "en", academy = false }: { api?: LearningApi; language?: Language; academy?: boolean }) {
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
  const [mistakes, setMistakes] = useState<MistakeReference[]>([]);
  const [resume, setResume] = useState<{ key: string; id: string | null } | null>(null);
  const [category, setCategory] = useState<string | null>(null);
  const [failed, setFailed] = useState<{ lesson: Lesson; status: "started" | "completed" } | null>(null);
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
      const user = await ensurePublicSession();
      const size = academy ? 24 : 6;
      const result = await learningApi.list(page, size, language, controller.signal);
      const all = [...result.items];
      if (academy) for (let index = 2; index <= result.total_pages; index += 1) {
        const next = await learningApi.list(index, size, language, controller.signal);
        all.push(...next.items);
      }
      if (controller.signal.aborted) return;
      setItems(all); setTotalPages(result.total_pages); setEpoch(result.learning_epoch); setError(null);
      setMistakes(mistakeReferences(user?.id));
      if (academy && user?.id) {
        const key = `mlchess-lesson:${user.id}`;
        let id = null;
        try { id = localStorage.getItem(key); } catch { /* Fall back to server progress. */ }
        setResume({ key, id });
      }
    })().catch(() => { if (!controller.signal.aborted) setError(labels.error); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [academy, learningApi, language, page, reload, labels.error]);
  useEffect(() => {
    if (selectedId) detailHeading.current?.focus();
    else if (openedLesson.current?.isConnected) openedLesson.current.focus();
  }, [selectedId]);
  const update = async (lesson: Lesson, status: "started" | "completed") => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError(null); setFailed(null);
    const applySaved = (saved: Lesson) => {
      setSelected(saved);
      setItems((list) => list.map((item) => item.id === saved.id ? saved : item));
    };
    try {
      applySaved(await learningApi.status(lesson.id, status, epoch, language));
    } catch {
      if (!api) {
        try {
          await ensurePublicSession();
          const context = await new ProgressApi().context();
          setEpoch(context.learning_epoch);
          const saved = await learningApi.detail(lesson.id, language);
          applySaved(saved);
          if (saved.status === "completed" || saved.status === status) return;
        } catch { /* A retry remains available if recovery also fails. */ }
      }
      setFailed({ lesson, status });
      setError(labels.error);
    }
    finally { busy.current = false; setPending(false); }
  };
  const open = (lesson: Lesson, button: HTMLButtonElement) => {
    openedLesson.current = button;
    setError(null);
    setFailed(null);
    setSelected(lesson);
    if (resume && lesson.status !== "completed") {
      setResume({ key: resume.key, id: lesson.id });
      try { localStorage.setItem(resume.key, lesson.id); } catch { /* Server progress is still saved. */ }
    }
    if (lesson.status === "not-started") void update(lesson, "started");
  };
  const completed = items.filter((lesson) => lesson.status === "completed").length;
  const focus = categories.find((group) => group.id === mistakes[0]?.phase);
  const current = items.find((lesson) => lesson.id === resume?.id && lesson.status === "started")
    ?? items.find((lesson) => lesson.status === "started")
    ?? items.find((lesson) => lesson.status !== "completed" && focus && matches(lesson, focus))
    ?? items.find((lesson) => lesson.status !== "completed");
  const filter = categories.find((group) => group.id === category);
  const languageIndex = ru ? 0 : 1;
  return <section className="lesson-catalog" aria-label="Lesson catalog" aria-busy={loading || pending}>
    {error && <div className="error-banner" role="alert">{error} <button type="button" disabled={pending} onClick={() => failed ? void update(failed.lesson, failed.status) : setReload((n) => n + 1)}>{labels.retry}</button></div>}
    {loading && <p role="status">{labels.loading}</p>}
    <div hidden={!!selected}>
      {academy && <div className="academy-plan">
        <section>
          <div className="section-kicker"><span>{ru ? "Персональный план" : "Personal plan"}</span><span>{ru ? "Текущий урок" : "Current lesson"}</span></div>
          {current ? <>
            <h2>{current.title}</h2>
            <p>{current.summary}</p>
            <p className="coach-status">{statusLabel(current.status)}</p>
            <button className="button button-primary" type="button" disabled={pending} onClick={(event) => open(current, event.currentTarget)}>{ru ? "Продолжить обучение" : "Continue learning"} <span aria-hidden="true">→</span></button>
          </> : !loading && !error && <h2>{items.length
            ? (ru ? "План пройден" : "Plan complete")
            : (ru ? "Уроки пока недоступны" : "No lessons available yet")}</h2>}
        </section>
        <aside>
          <div className="section-kicker">{ru ? "Общий прогресс" : "Overall progress"}</div>
          <p className="academy-tally"><strong>{completed}</strong> / {items.length} {ru ? "уроков" : "lessons"}</p>
          {items.length > 0 && <progress aria-label={ru ? "Пройдено уроков" : "Completed lessons"} value={completed} max={items.length} />}
          <CoachAvatar title={ru ? "Рекомендация ИИ-тренера" : "AI coach recommendation"}>
            {focus ? (ru ? `В разобранной партии найдена ошибка. Начните с раздела «${focus.label[0]}» и повторите позицию.` : `A reviewed game revealed a mistake. Start with ${focus.label[1]} and retry that position.`)
              : (ru ? "Разберите ход из завершённой партии. Когда Stockfish подтвердит ошибку, я предложу, что повторить." : "Analyze a move from a completed game. When Stockfish verifies a mistake, I’ll suggest what to practice.")}
          </CoachAvatar>
          {focus && <Link className="button button-secondary" to="/learn/puzzles?mode=personal">{ru ? "Повторить позицию" : "Retry the position"}</Link>}
        </aside>
      </div>}
      {academy && <div className="academy-topics" role="group" aria-label={ru ? "Темы обучения" : "Learning topics"}>
        {[{ id: null, label: [ru ? "Все темы" : "All topics", "All topics"] }, ...categories].map((group) =>
          <button key={group.id ?? "all"} type="button" className="button button-secondary" aria-pressed={category === group.id} onClick={() => setCategory(group.id)}>{group.label[languageIndex]}</button>)}
      </div>}
      <div className={academy ? "academy-lessons" : "catalog-grid"}>{items.filter((lesson) => !filter || matches(lesson, filter)).map((lesson) => <article className="lesson-card" key={lesson.id}>
        <span className="status-chip">{statusLabel(lesson.status)}</span><h2>{lesson.title}</h2><p>{lesson.summary}</p>
        {!academy && <div className="lesson-tags">{lesson.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
        <button className="button button-secondary" disabled={pending} type="button" onClick={(event) => open(lesson, event.currentTarget)}>{labels.open}</button>
      </article>)}</div>
      {!academy && <div className="catalog-pagination">
        <button type="button" disabled={page === 1 || loading || pending} onClick={() => { setLoading(true); setPage((n) => n - 1); }}>{labels.previous}</button>
        <span>{page} / {totalPages}</span>
        <button type="button" disabled={page >= totalPages || loading || pending} onClick={() => { setLoading(true); setPage((n) => n + 1); }}>{labels.next}</button>
      </div>}
    </div>
    {selected && <article className="lesson-detail" aria-label={ru ? "Урок" : "Lesson detail"}>
      <div className="lesson-navigation"><button className="button button-secondary" type="button" disabled={pending} onClick={() => { setSelected(null); setError(null); setFailed(null); }}>{ru ? "К списку уроков" : "Back to lessons"}</button></div>
      <div className="analysis-header"><h2 ref={detailHeading} tabIndex={-1}>{selected.title}</h2><span className="status-chip">{statusLabel(selected.status)}</span></div>
      <p>{selected.body}</p>
      <LessonBoard key={selected.id} lessonId={selected.id} language={language} completed={selected.status === "completed"} disabled={pending}
        onComplete={() => void update(selected, "completed")} />
      <p className="coach-status">{labels.source}: <a href={selected.source_url} target="_blank" rel="noreferrer">{selected.source_name}</a> · {selected.license}</p>
      <button className="button button-primary" disabled={pending || selected.status === "completed"} type="button" onClick={() => void update(selected, "completed")}>{labels.done}</button>
      {selected.status === "completed" && <p role="status">{ru ? "Урок завершён. Прогресс сохранён." : "Lesson completed. Progress saved."}</p>}
    </article>}
  </section>;
}
