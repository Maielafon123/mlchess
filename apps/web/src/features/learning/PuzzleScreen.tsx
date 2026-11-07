import { useEffect, useMemo, useState } from "react";
import { GameBoard, type MoveRecord } from "../../components/GameBoard";
import { PuzzleApi, type Puzzle } from "../../api/puzzleApi";

export function PuzzleScreen({ api }: { api?: PuzzleApi }) {
  const [puzzle, setPuzzle] = useState<Puzzle | null>(null); const [attempts, setAttempts] = useState<MoveRecord[]>([]); const [message, setMessage] = useState("Choose a move"); const [hintIndex, setHintIndex] = useState(0); const [replay, setReplay] = useState(false); const resolvedApi = useMemo(() => api ?? PuzzleApi.demo(), [api]);
  useEffect(() => { void resolvedApi.get("back-rank").then(setPuzzle).catch(() => setMessage("Puzzle unavailable — try again later.")); }, [resolvedApi]);
  if (!puzzle) return <div className="status-banner" role="status">Loading puzzle…</div>;
  const currentFen = replay && puzzle.solution.length ? puzzle.solution[puzzle.solution.length - 1].fen : puzzle.fen;
  const submit = async (uci: string) => { const result = await resolvedApi.attempt(puzzle.id, uci, `attempt-${Date.now()}`); if (result.result === "correct") { setMessage("Correct — verified by server."); setAttempts(puzzle.solution.map((move, index) => ({ ply: index + 1, san: move.san, uci: move.uci }))); } else if (result.result === "illegal") setMessage("Illegal move."); else setMessage("Not the verified solution. Try a hint."); };
  return <section className="puzzle-screen" aria-label="Puzzle"><div className="analysis-header"><h2>{puzzle.title}</h2><span className="status-chip">Difficulty {puzzle.difficulty}</span></div><div className="puzzle-layout"><GameBoard fen={currentFen} moves={attempts} disabled={replay} onMoveAttempt={(uci) => void submit(uci)} /><aside className="puzzle-side"><div className="puzzle-message" role="status">{message}</div><div className="hint-stack"><h3>Hints</h3>{puzzle.hints.slice(0, hintIndex).map((hint, index) => <p key={hint}><strong>{index + 1}.</strong> {hint}</p>)}<button className="button button-secondary" type="button" onClick={() => setHintIndex((value) => Math.min(puzzle.hints.length, value + 1))} disabled={hintIndex >= puzzle.hints.length}>Show next hint</button></div><button className="button button-secondary" type="button" onClick={() => setReplay(true)} disabled={!attempts.length}>Replay verified solution</button></aside></div></section>;
}
