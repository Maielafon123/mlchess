import { useState } from "react";
import { GameBoard, type MoveRecord } from "./GameBoard";
import { formatScore, type EngineAnalysis } from "../api/analysis";

export function EngineAnalysisPanel({ analysis }: { analysis: EngineAnalysis | null }) {
  const [pvIndex, setPvIndex] = useState(0);

  if (!analysis || analysis.status === "pending") return <section className="analysis-panel" aria-label="Engine analysis"><div className="analysis-status" role="status">Engine analysis pending…</div></section>;
  if (analysis.status === "unavailable") return <section className="analysis-panel" aria-label="Engine analysis"><div className="analysis-status" role="status">Analysis unavailable for this position.</div></section>;

  const currentPv = analysis.pv[pvIndex];
  const pvMoves: MoveRecord[] = analysis.pv.slice(0, pvIndex).map((move, index) => ({ ply: index + 1, san: move.san, uci: move.uci }));
  return (
    <section className="analysis-panel" aria-label="Engine analysis">
      <div className="analysis-header"><h2>Engine analysis</h2><span className={`quality-badge quality-${analysis.quality ?? "none"}`}>{analysis.quality ?? "No quality label"}</span></div>
      <div className="score-row"><div className="score-bar" role="img" aria-label={`Evaluation ${formatScore(analysis.score, analysis.perspective)}`}><span style={{ width: analysis.score?.kind === "cp" ? `${Math.min(100, Math.max(0, 50 + analysis.score.value / 20))}%` : "50%" }} /></div><strong>{formatScore(analysis.score, analysis.perspective)}</strong></div>
      <div className="analysis-lines"><div><span>Best move</span><strong>{analysis.best_move ? `${analysis.best_move.san} · ${analysis.best_move.uci}` : "Unavailable"}</strong></div><div><span>Perspective</span><strong>{analysis.perspective}</strong></div></div>
      <div className="analysis-alternatives"><h3>Alternatives</h3>{analysis.alternatives.length === 0 ? <p>No alternatives returned.</p> : <ol>{analysis.alternatives.map((line) => <li key={line.uci}><span>{line.san} · {line.uci}</span><span>{formatScore(line.score, analysis.perspective)}</span></li>)}</ol>}</div>
      <div className="pv-replay"><div className="analysis-header"><h3>Principal variation</h3><span>{analysis.pv.length === 0 ? "No legal PV" : `${pvIndex + 1}/${analysis.pv.length}`}</span></div>{currentPv && <GameBoard fen={currentPv.fen} moves={pvMoves} disabled onMoveAttempt={() => undefined} />}<div className="pv-controls"><button type="button" onClick={() => setPvIndex((index) => Math.max(0, index - 1))} disabled={pvIndex === 0}>Previous</button><button type="button" onClick={() => setPvIndex((index) => Math.min(analysis.pv.length - 1, index + 1))} disabled={pvIndex >= analysis.pv.length - 1}>Next</button></div></div>
    </section>
  );
}
