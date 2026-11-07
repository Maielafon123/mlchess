import { useState } from "react";
import { type CoachRequest } from "../../api/coachApi";
import { type GameSnapshot } from "../../api/gameApi";
import { GameSessionScreen } from "../game/GameSessionScreen";
import { CoachHintPanel } from "../../components/CoachHintPanel";

export function CoachGameScreen() {
  const [context, setContext] = useState<Omit<CoachRequest, "schema_version" | "level"> | null>(null);
  // Coach context is populated only by a real AnalysisResult/coach.ready event;
  // a game snapshot never carries an analysis_id in the generated contract.
  const onAcceptedMove = (_snapshot: GameSnapshot) => { setContext(null); };
  return <div className="coach-game-layout"><div><GameSessionScreen mode="coach" onAcceptedMove={onAcceptedMove} /></div><CoachHintPanel context={context} /></div>;
}
