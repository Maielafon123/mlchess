import { useState } from "react";
import { type CoachRequest } from "../../api/coachApi";
import { type GameSnapshot } from "../../api/gameApi";
import { GameSessionScreen } from "../game/GameSessionScreen";
import { CoachHintPanel } from "../../components/CoachHintPanel";
import { useMoveAnalysis } from "./useMoveAnalysis";
import { useI18n } from "../../i18n/I18nProvider";
import { EngineAnalysisPanel } from "../../components/EngineAnalysisPanel";

export function CoachGameScreen() {
  const [snapshot, setSnapshot] = useState<GameSnapshot | null>(null);
  const analysis = useMoveAnalysis(snapshot);
  const { locale } = useI18n();
  const result = analysis.result;
  const context: Omit<CoachRequest, "schema_version" | "level"> | null = result ? {
    game_id: result.game_id, analysis_id: result.analysis_id, revision: result.revision,
    ply: result.ply, language: locale,
  } : null;
  return <div className="coach-game-layout"><div><GameSessionScreen mode="coach" onSnapshot={setSnapshot} /></div><div>
    {analysis.pending && <p role="status">Движок анализирует ваш ход…</p>}
    {analysis.error && <div role="alert"><p>{analysis.error}</p><button type="button" onClick={analysis.retry}>Повторить анализ</button></div>}
    <CoachHintPanel context={context} language={locale} />
    {result && <details><summary>Разбор движка</summary><EngineAnalysisPanel analysis={result} /></details>}
  </div></div>;
}
