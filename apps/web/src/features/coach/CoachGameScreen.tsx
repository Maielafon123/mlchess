import { useState } from "react";
import { type CoachRequest } from "../../api/coachApi";
import { type GameSnapshot } from "../../api/gameApi";
import { GameSessionScreen } from "../game/GameSessionScreen";
import { CoachHintPanel } from "../../components/CoachHintPanel";

function analysisId() { return globalThis.crypto?.randomUUID?.() ?? `analysis-${Date.now()}`; }

export function CoachGameScreen() {
  const [context, setContext] = useState<Omit<CoachRequest, "schema_version" | "level"> | null>(null);
  const onAcceptedMove = (snapshot: GameSnapshot) => setContext({ game_id: snapshot.id, analysis_id: analysisId(), revision: snapshot.revision, ply: snapshot.moves.length, language: "ru" });
  return <div className="coach-game-layout"><div><GameSessionScreen onAcceptedMove={onAcceptedMove} /></div><CoachHintPanel context={context} /></div>;
}
