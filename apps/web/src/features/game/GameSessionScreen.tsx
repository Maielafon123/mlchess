import { GameBoard } from "../../components/GameBoard";
import { PlayerClocks } from "../../components/PlayerClocks";
import { GameReviewLink } from "../../components/GameReviewLink";
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
      {snapshot.termination === "timeout" && <p role="status">Партия завершена: время вышло.</p>}
      <PlayerClocks clock={snapshot.clock} />
      <GameBoard
        fen={snapshot.fen}
        moves={snapshot.moves}
        disabled={session.pending || !snapshot.capabilities.can_move}
        onMoveAttempt={session.move}
      />
      <div className="game-actions">
        <button className="button button-secondary" type="button" onClick={() => void session.resign()} disabled={session.pending || snapshot.status !== "active"}>Resign</button>
        <GameReviewLink game={snapshot} />
      </div>
    </div>
  );
}
