import { useState } from "react";
import { type CoachRequest } from "../../api/coachApi";
import { type GameSnapshot } from "../../api/gameApi";
import { GameSessionScreen } from "../game/GameSessionScreen";
import { CoachHintPanel } from "../../components/CoachHintPanel";

export function CoachGameScreen() {
  const [context, setContext] = useState<Omit<CoachRequest, "schema_version" | "level"> | null>(null);
  const onAcceptedMove = (snapshot: GameSnapshot) => { if (snapshot.analysis_id) setContext({ game_id: snapshot.id, analysis_id: snapshot.analysis_id, revision: snapshot.revision, ply: snapshot.moves.length, language: "ru" }); };
  return <div className="coach-game-layout"><div><GameSessionScreen mode="coach" onAcceptedMove={onAcceptedMove} /></div><CoachHintPanel context={context} /></div>;
}
