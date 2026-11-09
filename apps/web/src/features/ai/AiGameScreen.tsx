import { useMemo, useState } from "react";
import { GameBoard } from "../../components/GameBoard";
import { PlayerClocks } from "../../components/PlayerClocks";
import { GameReviewLink } from "../../components/GameReviewLink";
import { GameActionControls, SoloGameResult } from "../../components/GameActionControls";
import { type AiGameOptions, aiProfiles as profiles } from "../../api/aiGameApi";
import { useAiGameSession } from "./useAiGameSession";

export function AiGameScreen() {
  const [profileId, setProfileId] = useState(() => profiles.find((profile) => profile.id === new URLSearchParams(window.location.search).get("profile"))?.id ?? profiles[1].id);
  const [side, setSide] = useState<AiGameOptions["side"]>(() => new URLSearchParams(window.location.search).get("side") === "black" ? "black" : "white");
  const options = useMemo(() => ({ profile_id: profileId, side }), [profileId, side]);
  const session = useAiGameSession(options);
  const snapshot = session.snapshot;

  return (
    <section className="ai-game-screen" aria-label="AI game">
      <div className="ai-game-toolbar">
        <label>Opponent profile<select value={profileId} onChange={(event) => setProfileId(event.target.value)} disabled={session.pending !== null}>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.label}</option>)}</select></label>
        <label>Your side<select value={side} onChange={(event) => setSide(event.target.value as AiGameOptions["side"])} disabled={session.pending !== null}><option value="white">White</option><option value="black">Black</option><option value="random">Random</option></select></label>
      </div>
      {!snapshot && <div className="status-banner" role="status">{session.error ?? "Creating AI game…"}</div>}
      {snapshot && <>
        {session.pending && <div className="pending-overlay" role="status">{session.pending === "engine" ? "Engine is thinking…" : "Waiting for server…"}</div>}
        {session.error && <div className="error-banner" role="alert">{session.error}</div>}
        <SoloGameResult game={snapshot} />
        <PlayerClocks clock={snapshot.clock} />
        {snapshot.status === "active" && <GameActionControls key={snapshot.id} actions={session.actions.capabilities} disabled={session.pending !== null && session.pending !== "engine"} onAction={session.actions.action} />}
        <GameBoard fen={snapshot.fen} moves={snapshot.moves} orientation={snapshot.player_side} disabled={session.pending !== null || !snapshot.capabilities.can_move} onMoveAttempt={session.move} />
        <div className="game-actions"><span className="status-chip">{snapshot.ai_profile.label}</span><button className="button button-secondary" type="button" onClick={() => void session.takeback()} disabled={(session.pending !== null && session.pending !== "engine") || !snapshot.capabilities.can_takeback}>Take back</button><GameReviewLink game={snapshot} /></div>
      </>}
    </section>
  );
}
