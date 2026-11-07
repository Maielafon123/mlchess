import { GameBoard } from "../../components/GameBoard";
import { type GameApi, type GameSnapshot } from "../../api/gameApi";
import { useGameSession } from "./useGameSession";

export function GameSessionScreen({ api, onAcceptedMove }: { api?: GameApi; onAcceptedMove?: (snapshot: GameSnapshot) => void }) {
  const session = useGameSession(api, onAcceptedMove);
  const snapshot = session.snapshot;

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
        <button className="button button-secondary" type="button" onClick={() => void session.resign()} disabled={session.pending || !snapshot.capabilities.can_resign}>Resign</button>
      </div>
    </div>
  );
}
