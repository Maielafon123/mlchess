import { useEffect, useMemo, useState } from "react";
import { GameApi, type GameSnapshot } from "../../api/gameApi";
import { ensurePublicSession } from "../../auth/guestSession";
import { EngineAnalysisPanel } from "../../components/EngineAnalysisPanel";
import { GameBoard } from "../../components/GameBoard";
import { usePositionAnalysis } from "../coach/useMoveAnalysis";

export function PostGameReview({ gameId }: { gameId: string }) {
  const api = useMemo(() => new GameApi(), []);
  const [snapshot, setSnapshot] = useState<GameSnapshot | null>(null);
  const [error, setError] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [requested, setRequested] = useState(0);
  const analysis = usePositionAnalysis(snapshot?.status === "finished" ? snapshot : null, requested);
  useEffect(() => {
    const controller = new AbortController();
    void ensurePublicSession()
      .then(() => api.get(gameId, controller.signal))
      .then((game) => { if (!controller.signal.aborted && game.id === gameId) setSnapshot(game); })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [api, gameId]);
  if (error) return <p role="alert">Не удалось открыть партию. Разбор доступен её участникам.</p>;
  if (!snapshot) return <p role="status">Загружаем партию…</p>;
  if (snapshot.status !== "finished") return <p role="status">Разбор откроется после завершения партии.</p>;
  const choice = selected ?? snapshot.ply;
  return <section className="post-game-report">
    <p role="status">Партия завершена: {snapshot.result === "draw" ? "ничья" : snapshot.result === "white" ? "победили белые" : snapshot.result === "black" ? "победили чёрные" : "без результата"}.</p>
    <GameBoard fen={snapshot.fen} moves={snapshot.moves} disabled onMoveAttempt={() => undefined} />
    {snapshot.moves.length > 0 && <div className="game-actions report-filters">
      <label>Ход для разбора <select value={choice} onChange={(event) => { setSelected(Number(event.target.value)); setRequested(0); }}>
        {snapshot.moves.map((move) => <option key={move.ply} value={move.ply}>{move.ply}. {move.san}</option>)}
      </select></label>
      <button className="button button-primary" type="button" disabled={analysis.pending || requested === choice} onClick={() => setRequested(choice)}>Разобрать ход</button>
    </div>}
    {analysis.pending && <p role="status">Stockfish анализирует ход…</p>}
    {analysis.error && <div role="alert"><p>{analysis.error}</p><button type="button" onClick={analysis.retry}>Повторить анализ</button></div>}
    {analysis.result && <EngineAnalysisPanel analysis={analysis.result} />}
  </section>;
}
