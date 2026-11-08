import { useMemo, useState } from "react";
import { GameBoard } from "./GameBoard";
import { formatScore, replayPv, type EngineAnalysis } from "../api/analysis";

export function EngineAnalysisPanel({ analysis }: { analysis: EngineAnalysis | null }) {
  if (!analysis) return <section className="analysis-panel" aria-label="Engine analysis"><p role="status">Engine analysis pending…</p></section>;
  return <VerifiedAnalysis key={analysis.analysis_id} analysis={analysis} />;
}

function VerifiedAnalysis({ analysis }: { analysis: EngineAnalysis }) {
  const [index, setIndex] = useState(0);
  const frames = useMemo(() => {
    try { return replayPv(analysis.before_fen, analysis.top_moves[0].pv_uci); }
    catch { return []; }
  }, [analysis]);
  const ply = Math.min(index, frames.length);
  const fen = ply === 0 ? analysis.before_fen : frames[ply - 1].fen;
  return <section className="analysis-panel" aria-label="Engine analysis">
    <div className="analysis-header"><h2>Engine analysis</h2><span className={`quality-badge quality-${analysis.quality}`}>{analysis.quality}</span></div>
    <p>Before: {formatScore(analysis.score_before)} · After: {formatScore(analysis.score_after)}</p>
    <p>Best move before the played move: {analysis.top_moves[0].san} · {analysis.best_move_uci}</p>
    <ol>{analysis.top_moves.map((line) => <li key={line.uci}>{line.san} · {formatScore(line.score)}</li>)}</ol>
    <details><summary>Principal variation</summary>{frames.length > 0 ? <>
      <p>{ply}/{frames.length}</p><GameBoard fen={fen} moves={frames.slice(0, ply)} disabled onMoveAttempt={() => undefined} />
      <div className="pv-controls"><button type="button" onClick={() => setIndex((value) => Math.max(0, value - 1))} disabled={ply === 0}>Previous</button><button type="button" onClick={() => setIndex((value) => Math.min(frames.length, value + 1))} disabled={ply >= frames.length}>Next</button></div>
    </> : <p>Variation unavailable.</p>}</details>
    <small>{analysis.engine.version} · White POV</small>
  </section>;
}
