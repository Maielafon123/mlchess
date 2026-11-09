import { GameBoard, type GameBoardProps } from "../../components/GameBoard";
import { PlayerClocks } from "../../components/PlayerClocks";
import { GameReviewLink } from "../../components/GameReviewLink";
import { GameActionControls } from "../../components/GameActionControls";
import { GameConclusion } from "./PostGameReview";
import { useTurnVibration } from "./useTurnVibration";
import { type GameApi, type GameSnapshot } from "../../api/gameApi";
import { useGameSession } from "./useGameSession";
import { useEffect } from "react";

export function GameSessionScreen({ api, onAcceptedMove, onSnapshot, mode = "ai", feedback }: {
  api?: GameApi; onAcceptedMove?: (snapshot: GameSnapshot) => void; onSnapshot?: (snapshot: GameSnapshot) => void;
  mode?: "ai" | "coach"; feedback?: GameBoardProps["feedback"];
}) {
  const session = useGameSession(api, onAcceptedMove, mode);
  const snapshot = session.snapshot;
  useTurnVibration(snapshot);
  useEffect(() => { if (snapshot) onSnapshot?.(snapshot); }, [onSnapshot, snapshot]);

  if (!snapshot) {
    return <div className="status-banner" role="status">{session.error ?? "Creating game…"}</div>;
  }

  return (
    <div className="game-session" aria-busy={session.pending}>
      {session.pending && <div className="pending-overlay" role="status">Waiting for server…</div>}
      {session.error && <div className="error-banner" role="alert">{session.error}</div>}
      {snapshot.status === "finished" ? <GameConclusion key={snapshot.id} game={snapshot} showCoach={mode === "coach"} /> : <>
      <PlayerClocks clock={snapshot.clock} />
      {snapshot.status === "active" && <GameActionControls key={snapshot.id} actions={session.actions.capabilities} disabled={session.pending} onAction={session.actions.action} />}
      <GameBoard feedback={feedback}
        fen={snapshot.fen}
        moves={snapshot.moves}
        disabled={session.pending || !snapshot.capabilities.can_move}
        onMoveAttempt={session.move}
      /></>}
      {snapshot.status === "finished" && <div className="game-actions"><GameReviewLink game={snapshot} /></div>}
    </div>
  );
}
