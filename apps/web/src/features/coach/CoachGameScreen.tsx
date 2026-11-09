import { useMemo, useState } from "react";
import { type CoachRequest } from "../../api/coachApi";
import { type GameSnapshot } from "../../api/gameApi";
import { GameSessionScreen } from "../game/GameSessionScreen";
import { CoachHintPanel } from "../../components/CoachHintPanel";
import { useMoveAnalysis } from "./useMoveAnalysis";
import { useI18n } from "../../i18n/I18nProvider";
import { EngineAnalysisPanel } from "../../components/EngineAnalysisPanel";
import { CoachAvatar } from "../../components/CoachAvatar";
import { moveQuality } from "../../api/analysis";

export function CoachGameScreen() {
  const [snapshot, setSnapshot] = useState<GameSnapshot | null>(null);
  const analysis = useMoveAnalysis(snapshot?.status === "active" ? snapshot : null);
  const { locale } = useI18n();
  const result = analysis.result;
  const context = useMemo<Omit<CoachRequest, "schema_version" | "level"> | null>(() => result ? {
    game_id: result.game_id, analysis_id: result.analysis_id, revision: result.revision,
    ply: result.ply, language: locale,
  } : null, [result, locale]);
  const ru = locale === "ru";
  const quality = result ? moveQuality[result.quality][ru ? 0 : 1] : null;
  const tone = result?.quality === "best" || result?.quality === "good" ? "good" : "bad";
  const feedback = result && result.quality !== "unclassified" ? { uci: result.played_move_uci, tone } as const : undefined;
  const finished = snapshot?.status === "finished";
  return <div className={finished ? "coach-game-layout coach-game-finished" : "coach-game-layout"}>
    {!finished && <aside className="coach-intro" aria-live="polite">
      <CoachAvatar title={ru ? "ИИ-тренер" : "AI coach"}>{quality ?? (analysis.pending
        ? (ru ? "Смотрю, как этот ход изменил позицию." : "I’m checking how this move changed the position.")
        : (ru ? "Сделайте ход. Мы разберём его вместе." : "Play a move. We’ll review it together."))}</CoachAvatar>
    </aside>}
    <div className="coach-board"><GameSessionScreen mode="coach" onSnapshot={setSnapshot} feedback={feedback} /></div>
    {!finished && <aside className="coach-tools">
    {analysis.pending && <p role="status">Движок анализирует ваш ход…</p>}
    {analysis.error && <div role="alert"><p>{analysis.error}</p><button type="button" onClick={analysis.retry}>Повторить анализ</button></div>}
    <CoachHintPanel context={context} language={locale} />
    {result && <details><summary>Разбор движка</summary><EngineAnalysisPanel analysis={result} /></details>}
  </aside>}</div>;
}
