import { useEffect, useMemo, useState } from "react";
import { DEFAULT_POSITION } from "chess.js";
import { GameApi, type GameSnapshot } from "../../api/gameApi";
import { replayPv } from "../../api/analysis";
import type { AnalysisResult } from "../../api/analysisApi";
import type { CoachRequest } from "../../api/coachApi";
import { ensurePublicSession } from "../../auth/guestSession";
import { EngineAnalysisPanel } from "../../components/EngineAnalysisPanel";
import { GameBoard } from "../../components/GameBoard";
import { usePositionAnalysis } from "../coach/useMoveAnalysis";
import { rememberMistake } from "../learning/mistakePractice";
import { SoloGameResult } from "../../components/GameActionControls";
import { CoachHintPanel } from "../../components/CoachHintPanel";
import { CoachAvatar } from "../../components/CoachAvatar";
import { moveQuality } from "../../api/analysis";
import { useI18n } from "../../i18n/I18nProvider";

export function PostGameReview({ gameId }: { gameId: string }) {
  const api = useMemo(() => new GameApi(), []);
  const [snapshot, setSnapshot] = useState<GameSnapshot | null>(null);
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [error, setError] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void ensurePublicSession()
      .then(async (user) => {
        const game = await api.get(gameId, controller.signal);
        if (controller.signal.aborted || game.id !== gameId) return;
        setOrientation(game.players.find((player) => player.user_id === user?.id)?.side ?? "white");
        setSnapshot(game);
      })
      .catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [api, gameId]);
  if (error) return <p role="alert">Не удалось открыть партию. Разбор доступен её участникам.</p>;
  if (!snapshot) return <p role="status">Загружаем партию…</p>;
  if (snapshot.status !== "finished") return <p role="status">Разбор откроется после завершения партии.</p>;
  return <GameConclusion game={snapshot} orientation={orientation} defaultReview />;
}

const termination: Record<NonNullable<GameSnapshot["termination"]>, string> = {
  checkmate: "Мат", stalemate: "Пат", insufficient_material: "Недостаточно фигур",
  fivefold_repetition: "Пятикратное повторение", seventyfive_moves: "Правило 75 ходов",
  threefold_claim: "Троекратное повторение", fifty_moves_claim: "Правило 50 ходов",
  draw_agreement: "Ничья по соглашению", resignation: "Сдача", timeout: "Время вышло", aborted: "Партия прервана",
};

export function GameConclusion({ game, orientation = "white", defaultReview = false, showCoach = false }: {
  game: GameSnapshot; orientation?: "white" | "black"; defaultReview?: boolean; showCoach?: boolean;
}) {
  const [review, setReview] = useState(defaultReview);
  const [choice, setChoice] = useState(game.ply);
  const [requested, setRequested] = useState(0);
  const [results, setResults] = useState<Record<number, AnalysisResult>>({});
  const { locale } = useI18n();
  const analysis = usePositionAnalysis(review ? game : null, requested);
  const result = analysis.result;
  const inspected = results[choice];
  const ru = locale === "ru";
  const quality = inspected ? moveQuality[inspected.quality][ru ? 0 : 1] : null;
  const coachContext = useMemo<Omit<CoachRequest, "schema_version" | "level"> | null>(() => inspected ? {
    game_id: inspected.game_id, analysis_id: inspected.analysis_id, revision: inspected.revision,
    ply: inspected.ply, language: locale,
  } : null, [inspected, locale]);
  const frame = useMemo(() => {
    if (!review || choice === game.ply) return game.fen;
    try { return replayPv(DEFAULT_POSITION, game.moves.slice(0, choice).map((move) => move.uci)).at(-1)?.fen ?? DEFAULT_POSITION; }
    catch { return null; }
  }, [choice, game, review]);
  useEffect(() => {
    if (!result) return;
    setResults((previous) => ({ ...previous, [result.ply]: result }));
    void ensurePublicSession().then((user) => {
      if (user) rememberMistake(game, result, user.id);
    }).catch(() => {});
  }, [game, result]);
  const select = (ply: number) => { setChoice(ply); setRequested(0); };
  const openAnalysis = () => {
    setReview(true);
    if (choice > 0 && !results[choice]) setRequested(choice);
  };
  const score = game.result === "white" ? "1–0" : game.result === "black" ? "0–1" : game.result === "draw" ? "½–½" : "—";
  const mistakes = Object.values(results).filter((item) => item.quality === "mistake" || item.quality === "blunder").length;
  return <section className={showCoach ? "game-conclusion conclusion-with-coach" : "game-conclusion"} aria-label="Сводка партии">
    <div className="section-kicker"><span>Партия завершена</span><span>{game.termination && termination[game.termination]}</span></div>
    <div className="academy-topics" role="group" aria-label="После партии">
      <button type="button" className="button button-secondary" aria-pressed={!review} onClick={() => { setReview(false); setRequested(0); }}>Сводка</button>
      {game.moves.length > 0 && <button type="button" className="button button-secondary" aria-pressed={review} onClick={openAnalysis}>Анализ</button>}
    </div>
    {showCoach && <aside className="conclusion-coach"><CoachAvatar title={ru ? "ИИ-тренер" : "AI coach"}>{quality ?? (analysis.pending
      ? (ru ? "Проверяю ваш последний ход движком." : "The engine is checking your last move.")
      : (ru ? "Партия завершена. Откройте анализ — разберём ключевые решения и найдём, что потренировать." : "The game is over. Open the analysis to review key decisions and choose what to practice."))}</CoachAvatar></aside>}
    <div className="conclusion-content">{!review ? <>
      <p className="conclusion-score">{score}</p>
      <SoloGameResult game={game} />
      <div className="conclusion-metrics">
        <span><strong>{game.moves.length}</strong> полуходов</span>
        <span><strong>{Object.keys(results).length}</strong> разобрано</span>
        <span><strong>{Object.keys(results).length ? mistakes : "—"}</strong> ошибок в разборе</span>
      </div>
    </> : <div className="post-game-layout">
      {frame && <GameBoard fen={frame} moves={game.moves.slice(0, choice)} orientation={orientation} disabled showHistory={false} onMoveAttempt={() => undefined}
        feedback={inspected && inspected.quality !== "unclassified" ? {
          uci: inspected.played_move_uci,
          tone: inspected.quality === "good" || inspected.quality === "best" ? "good" : "bad",
        } : undefined} />}
      <div className="post-game-tools">
        {game.moves.length > 0 && <div className="report-filters">
          <label>Ход для разбора <select value={choice} onChange={(event) => select(Number(event.target.value))}>
            <option value={0}>Начальная позиция</option>
            {game.moves.map((move) => <option key={move.ply} value={move.ply}>{Math.ceil(move.ply / 2)}{move.ply % 2 ? "." : "…"} {move.san}</option>)}
          </select></label>
          <div className="academy-topics">
            <button className="button button-secondary" type="button" disabled={choice <= 0} onClick={() => select(choice - 1)} aria-label="Предыдущий полуход">←</button>
            <button className="button button-secondary" type="button" disabled={choice >= game.ply} onClick={() => select(choice + 1)} aria-label="Следующий полуход">→</button>
          </div>
          <button className="button button-primary" type="button" disabled={!choice || analysis.pending || !!results[choice] || requested === choice} onClick={() => setRequested(choice)}>{ru ? "Разобрать выбранный ход" : "Analyze selected move"}</button>
        </div>}
        {analysis.pending && requested > 0 && <p role="status">Stockfish анализирует ход…</p>}
        {analysis.error && requested > 0 && <div role="alert"><p>{analysis.error}</p><button type="button" onClick={analysis.retry}>Повторить анализ</button></div>}
        {inspected && <>
          <EngineAnalysisPanel analysis={inspected} />
          <CoachHintPanel key={inspected.analysis_id} context={coachContext} autoObservation={false} language={locale} />
        </>}
      </div>
    </div>}</div>
  </section>;
}
