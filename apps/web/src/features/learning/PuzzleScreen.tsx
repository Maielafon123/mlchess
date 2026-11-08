import { useEffect, useMemo, useRef, useState } from "react";
import { GameBoard } from "../../components/GameBoard";
import { PuzzleApi, type Puzzle, type PuzzleState } from "../../api/puzzleApi";
import { createIdempotencyKey } from "../../api/client";
import { ensurePublicSession } from "../../auth/guestSession";
import type { Language } from "../../api/learningApi";

type Action = { kind: "attempt" | "hint" | "restart"; key: string; basis: PuzzleState; uci?: string };
const titles: Record<string, [string, string]> = { "back-rank": ["Мат по последней горизонтали", "Back-rank finish"], "king-diagonal": ["Открытая диагональ", "The open diagonal"], "knight-net": ["Матовая сеть коня", "Knight mating net"], "promotion-finish": ["Решающее превращение", "Promotion finish"] };
export function PuzzleScreen({ api, language = "en" }: { api?: PuzzleApi; language?: Language }) {
  const resolvedApi = useMemo(() => api ?? new PuzzleApi(), [api]);
  const [id, setId] = useState(() => new URLSearchParams(window.location.search).get("puzzle") ?? "back-rank");
  const [items, setItems] = useState<Puzzle[]>([]);
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null);
  const [state, setState] = useState<PuzzleState | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState(false);
  const [recovery, setRecovery] = useState<Action | null>(null);
  const [reload, setReload] = useState(0);
  const [replayPly, setReplayPly] = useState<number | null>(null);
  const busy = useRef(false);
  const alive = useRef(true);
  const ru = language === "ru";
  const title = (slug: string) => titles[slug]?.[ru ? 0 : 1] ?? slug;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      await ensurePublicSession();
      const [list, nextPuzzle, nextState] = await Promise.all([resolvedApi.list(controller.signal), resolvedApi.get(id, controller.signal), resolvedApi.state(id, language, controller.signal)]);
      if (controller.signal.aborted) return;
      setItems(list.items); setPuzzle(nextPuzzle); setState(nextState); setError(false);
    })().catch(() => { if (!controller.signal.aborted) setError(true); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [resolvedApi, id, language, reload]);
  const execute = async (action: Action) => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError(false);
    try {
      let next: PuzzleState;
      if (action.kind === "attempt") {
        const result = await resolvedApi.attempt(id, action.uci!, action.basis, action.key);
        next = await resolvedApi.state(id, language);
        if (alive.current) setMessage(result.result === "correct" || result.result === "completed" ? (ru ? "Верно! Задача решена." : "Correct — verified by server.") : result.result === "illegal" ? (ru ? "Недопустимый ход." : "Illegal move.") : (ru ? "Это не мат. Попробуйте ещё раз или откройте подсказку." : "That is not mate. Try again or request a hint."));
      } else if (action.kind === "hint") {
        await resolvedApi.hint(id, action.basis, language, action.key);
        next = await resolvedApi.state(id, language);
      } else { next = await resolvedApi.restart(id, action.basis, language, action.key); }
      if (!alive.current) return;
      setState(next); setRecovery(null); setReplayPly(null);
      if (action.kind === "restart") setMessage("");
    } catch { if (alive.current) { setError(true); setRecovery(action); } }
    finally { busy.current = false; if (alive.current) setPending(false); }
  };
  const start = (kind: Action["kind"], uci?: string) => { if (state && !recovery) void execute({ kind, uci, key: createIdempotencyKey(), basis: state }); };
  const replay = state?.solution ?? [];
  const fen = replayPly === null ? state?.current_fen : replayPly === 0 ? puzzle?.fen : replay[replayPly - 1]?.fen;
  return <section className="puzzle-screen" aria-label="Puzzle" aria-busy={loading || pending}>
    {items.length > 0 && <label>{ru ? "Задача" : "Puzzle"}<select aria-label="Choose puzzle" value={id} disabled={pending || !!recovery} onChange={(event) => { const selected = event.target.value; setId(selected); setLoading(true); setState(null); setPuzzle(null); setMessage(""); setReplayPly(null); const url = new URL(window.location.href); url.searchParams.set("puzzle", selected); window.history.replaceState(null, "", url); }}>{items.map((item) => <option key={item.id} value={item.id}>{title(item.id)}</option>)}</select></label>}
    {error && <div className="error-banner" role="alert">{ru ? "Не удалось получить ответ. Повторите запрос." : "Could not receive a response. Please retry."} <button type="button" disabled={pending} onClick={() => recovery ? void execute(recovery) : setReload((n) => n + 1)}>{ru ? "Повторить запрос" : "Retry request"}</button>{recovery && <button type="button" onClick={() => window.location.reload()}>{ru ? "Обновить состояние" : "Refresh state"}</button>}</div>}
    {loading && <p role="status">{ru ? "Загружаем задачу…" : "Loading puzzle…"}</p>}
    {!loading && puzzle && state && fen && <><div className="analysis-header"><h2>{title(puzzle.id)}</h2><span className="status-chip">{ru ? "Сложность" : "Difficulty"} {puzzle.difficulty}</span></div>
    <div className="puzzle-layout"><GameBoard key={`${id}:${state.session_number}`} fen={fen} moves={replay.map((move, index) => ({ ply: index + 1, san: move.san, uci: move.uci }))} orientation={puzzle.fen.split(" ")[1] === "b" ? "black" : "white"} disabled={pending || !!recovery || state.completed || replayPly !== null} onMoveAttempt={(uci) => start("attempt", uci)} />
      <aside className="puzzle-side"><div className="puzzle-message" role="status">{message || (state.completed ? (ru ? "Задача решена." : "Puzzle completed.") : (ru ? "Поставьте мат в один ход." : "Find mate in one."))}</div>
      <div className="hint-stack"><h3>{ru ? "Подсказки" : "Hints"}</h3>{state.hints.map((hint, index) => <p key={index}><strong>{index + 1}.</strong> {hint}</p>)}<button className="button button-secondary" type="button" onClick={() => start("hint")} disabled={pending || !!recovery || state.hints.length >= 3 || state.completed}>{ru ? "Следующая подсказка" : "Show next hint"}</button></div>
      {state.completed && <div className="solution-replay"><h3>{ru ? "Ваше решение" : "Your solution"}</h3><button className="button button-secondary" type="button" onClick={() => setReplayPly(0)}>{ru ? "Начальная позиция" : "Starting position"}</button>{replay.map((move, index) => <button className="button button-secondary" key={index} type="button" onClick={() => setReplayPly(index + 1)}>{move.san}</button>)}</div>}
      <button className="button button-secondary" type="button" onClick={() => start("restart")} disabled={pending || !!recovery}>{ru ? "Начать заново" : "Restart puzzle"}</button>
      <p className="coach-status">{ru ? "Источник" : "Source"}: <a href={puzzle.source_url} target="_blank" rel="noreferrer">{puzzle.source_name}</a> · {puzzle.license}</p></aside></div></>}
  </section>;
}
