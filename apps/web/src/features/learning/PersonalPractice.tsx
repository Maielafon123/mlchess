import { useEffect, useMemo, useState } from "react";
import { AnalysisApi, type AnalysisResult } from "../../api/analysisApi";
import { replayPv } from "../../api/analysis";
import { GameApi } from "../../api/gameApi";
import type { Language } from "../../api/learningApi";
import { ensurePublicSession } from "../../auth/guestSession";
import { GameBoard } from "../../components/GameBoard";
import { CoachAvatar } from "../../components/CoachAvatar";
import { CoachHintPanel } from "../../components/CoachHintPanel";
import { isOwnMistake, mistakeReferences, type MistakeReference } from "./mistakePractice";

export function PersonalPractice({ language }: { language: Language }) {
  const [references, setReferences] = useState<MistakeReference[] | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [index, setIndex] = useState(0);
  const [solved, setSolved] = useState<number[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  const ru = language === "ru";
  const reference = references?.[index];
  useEffect(() => {
    let active = true;
    void ensurePublicSession().then((user) => {
      if (!active) return;
      setUserId(user?.id ?? null);
      setReferences(mistakeReferences(user?.id));
    }).catch(() => { if (active) { setUnavailable(true); setReferences([]); } });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!reference || !userId) return;
    const controller = new AbortController();
    void Promise.all([
      new GameApi().get(reference.gameId, controller.signal),
      new AnalysisApi().get(reference.gameId, reference.ply, controller.signal),
    ]).then(([game, result]) => {
      if (controller.signal.aborted) return;
      if (!("top_moves" in result) || !isOwnMistake(game, result, userId) || result.ply !== reference.ply) throw new Error();
      if (!replayPv(result.before_fen, [result.best_move_uci]).length) throw new Error();
      setAnalysis(result);
    }).catch(() => { if (!controller.signal.aborted) setUnavailable(true); });
    return () => controller.abort();
  }, [reference, userId]);

  if (references?.length === 0) return <p role="status">{unavailable
    ? (ru ? "Не удалось загрузить персональные задачи." : "Could not load personal puzzles.")
    : (ru ? "Разберите свой ход после партии. Подтверждённые ошибки появятся здесь для повторения." : "Review your moves after a game. Verified mistakes will appear here for practice.")}</p>;
  return <section className="personal-practice">
    {references && <label>{ru ? "Позиция" : "Position"} <select value={index} onChange={(event) => {
      setIndex(Number(event.target.value)); setAnalysis(null); setUnavailable(false);
    }}>{references.map((item, number) => <option key={`${item.gameId}:${item.ply}`} value={number}>{number + 1} · {ru ? "полуход" : "ply"} {item.ply}</option>)}</select></label>}
    {unavailable && <p role="alert">{ru ? "Разбор этой позиции недоступен." : "Analysis for this position is unavailable."}</p>}
    {!unavailable && !analysis && <p role="status">{ru ? "Проверяем позицию…" : "Verifying position…"}</p>}
    {analysis && reference && <VerifiedPractice key={analysis.analysis_id} analysis={analysis} language={language} phase={reference.phase}
      progress={solved.length} total={references?.length ?? 0} onSolved={() => setSolved((items) => items.includes(index) ? items : [...items, index])} />}
  </section>;
}

const practiceThemes = { opening: ["Дебют", "Opening"], tactics: ["Тактика", "Tactics"], endgame: ["Эндшпиль", "Endgame"] };

function VerifiedPractice({ analysis, language, phase, progress, total, onSolved }: {
  analysis: AnalysisResult; language: Language; phase: MistakeReference["phase"]; progress: number; total: number; onSolved: () => void;
}) {
  const [attempt, setAttempt] = useState<string | null>(null);
  const [hint, setHint] = useState(false);
  const ru = language === "ru";
  const coachContext = useMemo(() => ({
    game_id: analysis.game_id, analysis_id: analysis.analysis_id, revision: analysis.revision,
    ply: analysis.ply, language,
  }), [analysis, language]);
  const best = replayPv(analysis.before_fen, [analysis.best_move_uci])[0];
  const alternatives = analysis.top_moves.filter((move) => move.score.kind === analysis.top_moves[0].score.kind
    && move.score.value === analysis.top_moves[0].score.value).map((move) => move.uci);
  const correct = attempt !== null && (attempt === best.uci || alternatives.includes(attempt));
  const played = correct && attempt ? replayPv(analysis.before_fen, [attempt])[0] : null;
  return <div className="puzzle-layout">
    <GameBoard fen={played?.fen ?? analysis.before_fen} moves={played ? [played] : []} showHistory={false}
      orientation={analysis.before_fen.split(" ")[1] === "w" ? "white" : "black"} disabled={correct}
      feedback={attempt ? { uci: attempt, tone: correct ? "good" : "bad" } : undefined}
      onMoveAttempt={(uci) => { setAttempt(uci); if (uci === best.uci || alternatives.includes(uci)) onSolved(); }} />
    <aside className="puzzle-side">
      <div className="section-kicker"><span>{ru ? "Из вашей партии" : "From your game"}</span><span>{progress} / {total}</span></div>
      <h2>{ru ? "Исправьте ошибку" : "Correct the mistake"}</h2>
      <span className="status-chip">{practiceThemes[phase][ru ? 0 : 1]}</span>
      <p>{ru ? "Найдите лучший ход по оценке Stockfish." : "Find Stockfish’s best move."}</p>
      <button className="button button-secondary" type="button" disabled={hint || correct} onClick={() => setHint(true)}>{ru ? "Получить подсказку" : "Get a hint"}</button>
      {hint && !correct && <p role="status">{ru ? "Посмотрите на фигуру на поле" : "Look at the piece on"} {best.uci.slice(0, 2)}.</p>}
      {attempt && <p className="puzzle-message" role="status">{correct ? (ru ? "Верно!" : "Correct!") : (ru ? "Есть более сильный ход. Попробуйте снова." : "There is a stronger move. Try again.")}</p>}
      {correct && <>
        <CoachAvatar title={ru ? "Объяснение тренера" : "Coach explanation"}>
          {ru ? `Stockfish рекомендует ${best.san}. В партии было сыграно ${replayPv(analysis.before_fen, [analysis.played_move_uci])[0].san}.${analysis.cp_loss === null ? "" : ` Потеря оценки в пешках — ${(analysis.cp_loss / 100).toLocaleString(language)}.`}`
            : `Stockfish recommends ${best.san}. The original move was ${replayPv(analysis.before_fen, [analysis.played_move_uci])[0].san}.`}
        </CoachAvatar>
        <details><summary>{ru ? "Подробнее с ИИ-тренером" : "Explore with the AI coach"}</summary>
          <CoachHintPanel context={coachContext} autoObservation={false} language={language} />
        </details>
      </>}
    </aside>
  </div>;
}
