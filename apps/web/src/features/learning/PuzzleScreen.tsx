import { useEffect, useMemo, useRef, useState } from "react";
import { GameBoard } from "../../components/GameBoard";
import { PuzzleApi, type Puzzle, type PuzzleState } from "../../api/puzzleApi";
import { createIdempotencyKey } from "../../api/client";
import { ensurePublicSession } from "../../auth/guestSession";
import type { Language } from "../../api/learningApi";
import { CoachAvatar } from "../../components/CoachAvatar";
import { PersonalPractice } from "./PersonalPractice";

type Action = { kind: "attempt" | "hint" | "restart"; key: string; basis: PuzzleState; uci?: string };
const titles: Record<string, [string, string]> = { "back-rank": ["Мат по последней горизонтали", "Back-rank finish"], "king-diagonal": ["Открытая диагональ", "The open diagonal"], "knight-net": ["Матовая сеть коня", "Knight mating net"], "promotion-finish": ["Решающее превращение", "Promotion finish"] };
const explanations: Record<string, [string, string]> = {
  "back-rank": ["Ладья перекрывает последнюю горизонталь, а собственные пешки лишают короля полей отступления.", "The rook controls the back rank and the king’s own pawns block its escape."],
  "king-diagonal": ["Ферзь даёт шах по открытой диагонали h4–e1. Король не может уйти, взять ферзя или перекрыть диагональ.", "The queen checks along the open h4–e1 diagonal. The king cannot escape, capture the queen or block the check."],
  "knight-net": ["Шах конём нельзя перекрыть. Свои фигуры закрывают королю поля для отхода.", "A knight’s check cannot be blocked, and the king’s own pieces cover its escape squares."],
  "promotion-finish": ["После превращения новая фигура даёт шах по последней горизонтали. Свои пешки закрывают королю выход.", "The promoted piece checks along the back rank while the king’s own pawns block its escape."],
};

export function PuzzleScreen({ api, language = "en" }: { api?: PuzzleApi; language?: Language }) {
  const [mode, setMode] = useState(() => new URLSearchParams(window.location.search).get("mode") === "personal" ? "personal" : "catalog");
  const [personalOpened, setPersonalOpened] = useState(mode === "personal");
  const ru = language === "ru";
  return <>
    <div className="academy-topics" role="group" aria-label={ru ? "Тип тренировки" : "Practice type"}>
      <button className="button button-secondary" type="button" aria-pressed={mode === "catalog"} onClick={() => setMode("catalog")}>{ru ? "Обычные задачи" : "Standard puzzles"}</button>
      <button className="button button-secondary" type="button" aria-pressed={mode === "personal"} onClick={() => { setPersonalOpened(true); setMode("personal"); }}>{ru ? "Из моих ошибок" : "From my mistakes"}</button>
    </div>
    <div hidden={mode !== "catalog"}><CatalogPractice api={api} language={language} /></div>
    {personalOpened && <div hidden={mode !== "personal"}><PersonalPractice language={language} /></div>}
  </>;
}

function CatalogPractice({ api, language }: { api?: PuzzleApi; language: Language }) {
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
  const [solved, setSolved] = useState<string[]>([]);
  const [attempt, setAttempt] = useState<{ uci: string; correct: boolean } | null>(null);
  const busy = useRef(false);
  const alive = useRef(true);
  const ru = language === "ru";
  const title = (slug: string) => titles[slug]?.[ru ? 0 : 1] ?? slug;
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      await ensurePublicSession();
      const list = await resolvedApi.list(controller.signal);
      if (controller.signal.aborted) return;
      setItems(list.items);
      if (!list.items.some((item) => item.id === id)) {
        if (!list.items[0]) throw new Error("Empty puzzle catalog");
        setId(list.items[0].id);
        return;
      }
      const [nextPuzzle, nextState] = await Promise.all([resolvedApi.get(id, controller.signal), resolvedApi.state(id, language, controller.signal)]);
      if (controller.signal.aborted) return;
      setPuzzle(nextPuzzle); setState(nextState); setError(false);
      if (nextState.completed) setSolved((previous) => previous.includes(id) ? previous : [...previous, id]);
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
        if (alive.current) {
          const correct = result.result === "correct" || result.result === "completed";
          setAttempt({ uci: action.uci!, correct });
          setMessage(correct ? (ru ? "Верно! Задача решена." : "Correct — verified by server.") : result.result === "illegal" ? (ru ? "Недопустимый ход." : "Illegal move.") : (ru ? "Это не мат. Попробуйте ещё раз или откройте подсказку." : "That is not mate. Try again or request a hint."));
        }
      } else if (action.kind === "hint") {
        await resolvedApi.hint(id, action.basis, language, action.key);
        next = await resolvedApi.state(id, language);
      } else { next = await resolvedApi.restart(id, action.basis, language, action.key); }
      if (!alive.current) return;
      setState(next); setRecovery(null); setReplayPly(null);
      if (next.completed) setSolved((previous) => previous.includes(id) ? previous : [...previous, id]);
      if (action.kind === "restart") { setMessage(""); setAttempt(null); }
    } catch { if (alive.current) { setError(true); setRecovery(action); } }
    finally { busy.current = false; if (alive.current) setPending(false); }
  };
  const start = (kind: Action["kind"], uci?: string) => { if (state && !recovery) void execute({ kind, uci, key: createIdempotencyKey(), basis: state }); };
  const replay = state?.solution ?? [];
  const fen = replayPly === null ? state?.current_fen : replayPly === 0 ? puzzle?.fen : replay[replayPly - 1]?.fen;
  const choose = (selected: string) => {
    if (selected === id) return;
    setId(selected);
    setLoading(true);
    setState(null);
    setPuzzle(null);
    setMessage("");
    setAttempt(null);
    setReplayPly(null);
    const url = new URL(window.location.href);
    url.searchParams.set("puzzle", selected);
    window.history.replaceState(window.history.state, "", url);
  };
  const selector = items.length > 0 && <label>{ru ? "Задача" : "Puzzle"}
    <select aria-label="Choose puzzle" value={id} disabled={pending || !!recovery} onChange={(event) => choose(event.target.value)}>
      {items.map((item) => <option key={item.id} value={item.id}>{title(item.id)}</option>)}
    </select>
  </label>;
  const nextPuzzle = items.find((item) => item.id !== id && !solved.includes(item.id));
  const coachMessage = attempt?.correct
    ? (ru ? "Лучший ход в этой задаче. Мат подтверждён шахматной позицией." : "Best move for this exercise. Checkmate confirmed on the board.")
    : attempt
      ? (ru ? "Ошибка в решении: этот ход не выполняет цель задачи. Попробуйте другой ход." : "That move does not solve the puzzle. Try another move.")
      : state?.completed && puzzle && explanations[puzzle.id]
        ? explanations[puzzle.id][ru ? 0 : 1]
        : (ru ? "Сделайте ход фигурой на доске — я проверю решение." : "Play a move on the board and I’ll check your solution.");
  return <section className="puzzle-screen" aria-label="Puzzle" aria-busy={loading || pending}>
    {!loading && !puzzle && selector}
    {error && <div className="error-banner" role="alert">{ru ? "Не удалось получить ответ. Повторите запрос." : "Could not receive a response. Please retry."} <button type="button" disabled={pending} onClick={() => recovery ? void execute(recovery) : setReload((n) => n + 1)}>{ru ? "Повторить запрос" : "Retry request"}</button>{recovery && <button type="button" onClick={() => window.location.reload()}>{ru ? "Обновить состояние" : "Refresh state"}</button>}</div>}
    {loading && <p role="status">{ru ? "Загружаем задачу…" : "Loading puzzle…"}</p>}
    {!loading && puzzle && state && fen && <div className="puzzle-layout"><div className="puzzle-coach"><CoachAvatar title={ru ? "ИИ-тренер" : "AI coach"}>{coachMessage}</CoachAvatar></div><GameBoard key={`${id}:${state.session_number}`} fen={fen} moves={replay.slice(0, replayPly ?? replay.length).map((move, index) => ({ ply: index + 1, san: move.san, uci: move.uci }))} showHistory={false} orientation={puzzle.fen.split(" ")[1] === "b" ? "black" : "white"} disabled={pending || !!recovery || state.completed || replayPly !== null} feedback={replayPly === null && attempt ? { uci: attempt.uci, tone: attempt.correct ? "good" : "bad" } : undefined} onMoveAttempt={(uci) => start("attempt", uci)} />
      <aside className="puzzle-side">
      <div className="section-kicker"><span>{ru ? "Текущая тренировка" : "Current practice"}</span><span>{solved.length} / {items.length}</span></div>
      <h2>{title(puzzle.id)}</h2>
      {selector}
      <span className="status-chip">{ru ? "Сложность" : "Difficulty"} {puzzle.difficulty}</span>
      <p>{ru ? (puzzle.fen.split(" ")[1] === "b" ? "Ход чёрных. Поставьте мат в один ход." : "Ход белых. Поставьте мат в один ход.") : "Find mate in one."}</p>
      <div className="puzzle-message" role="status">{message || (state.completed ? (ru ? "Задача решена." : "Puzzle completed.") : (ru ? "Сделайте ход фигурой на доске." : "Play a move on the board."))}</div>
      <div className="hint-stack"><h3>{ru ? "Подсказки" : "Hints"}</h3>{state.hints.map((hint, index) => <p key={index}><strong>{index + 1}.</strong> {hint}</p>)}<button className="button button-secondary" type="button" onClick={() => start("hint")} disabled={pending || !!recovery || state.hints.length >= 3 || state.completed}>{ru ? "Следующая подсказка" : "Show next hint"}</button></div>
      {state.completed && <div className="solution-replay"><h3>{ru ? "Ваше решение" : "Your solution"}</h3><button className="button button-secondary" type="button" onClick={() => setReplayPly(0)}>{ru ? "Начальная позиция" : "Starting position"}</button>{replay.map((move, index) => <button className="button button-secondary" key={index} type="button" onClick={() => setReplayPly(index + 1)}>{move.san}</button>)}</div>}
      {state.completed && nextPuzzle && <button className="button button-primary" type="button" disabled={pending || !!recovery} onClick={() => choose(nextPuzzle.id)}>{ru ? "Следующая задача" : "Next puzzle"}</button>}
      <button className="button button-secondary" type="button" onClick={() => start("restart")} disabled={pending || !!recovery}>{ru ? "Начать заново" : "Restart puzzle"}</button>
      <p className="coach-status">{ru ? "Источник" : "Source"}: <a href={puzzle.source_url} target="_blank" rel="noreferrer">{puzzle.source_name}</a> · {puzzle.license}</p></aside></div>}
  </section>;
}
