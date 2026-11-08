import { GameBoard } from "../../components/GameBoard";
import { type GameApi, type GameSnapshot } from "../../api/gameApi";
import { useGameSession } from "./useGameSession";
import { useEffect } from "react";

export function GameSessionScreen({ api, onAcceptedMove, onSnapshot, mode = "ai" }: { api?: GameApi; onAcceptedMove?: (snapshot: GameSnapshot) => void; onSnapshot?: (snapshot: GameSnapshot) => void; mode?: "ai" | "coach" }) {
  const session = useGameSession(api, onAcceptedMove, mode);
  const snapshot = session.snapshot;
  useEffect(() => { if (snapshot) onSnapshot?.(snapshot); }, [onSnapshot, snapshot]);

  if (!snapshot) {
    return <div className="status-banner" role="status">{session.error ?? "Creating game…"}</div>;
  }

  return (
    <div className="game-session" aria-busy={session.pending}>
      {session.pending && <div className="pending-overlay" role="status">Waiting for server…</div>}
      {session.error && <div className="error-banner" role="alert">{session.error}</div>}
      <GameBoard
        fen={snapshot.fen}
        moves={snapshot.moves}
        disabled={session.pending || !snapshot.capabilities.can_move}
        onMoveAttempt={session.move}
      />
      <div className="game-actions">
        <span className="status-chip">Version {snapshot.version}</span>
        <button className="button button-secondary" type="button" onClick={() => void session.resign()} disabled={session.pending || snapshot.status !== "active"}>Resign</button>
      </div>
    </div>
  );
}
