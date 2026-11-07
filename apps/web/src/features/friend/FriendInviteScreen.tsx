import { useMemo, useState } from "react";
import { InviteApi, type InviteSnapshot } from "../../api/inviteApi";

export function FriendInviteScreen({ api }: { api?: InviteApi }) {
  const resolvedApi = useMemo(() => api ?? new InviteApi(), [api]);
  const [snapshot, setSnapshot] = useState<InviteSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const create = async () => { setError(null); try { setSnapshot(await resolvedApi.create()); } catch (value) { setError(value instanceof Error ? value.message : "Invite unavailable"); } };
  const accept = async () => { if (!snapshot) return; try { setSnapshot(await resolvedApi.accept(snapshot.invite_id)); } catch (value) { setError(value instanceof Error ? value.message : "Invite cannot be accepted"); } };
  const copy = async () => { if (!snapshot) return; try { await navigator.clipboard?.writeText(snapshot.invite_url); setCopied(true); } catch { setError("Clipboard access was denied; copy the invite link manually."); } };
  return <section className="friend-screen" aria-label="Friend game"><div className="analysis-header"><h2>Play with a friend</h2><span className="status-chip">No coach or analysis</span></div>{error && <div className="error-banner" role="alert">{error}</div>}{!snapshot && <button className="button button-primary" type="button" onClick={() => void create()}>Create private invite</button>}{snapshot && <><div className="invite-row"><code>{snapshot.invite_url}</code><button className="button button-secondary" type="button" onClick={() => void copy()}>{copied ? "Copied" : "Copy invite"}</button></div>{snapshot.state === "waiting" && <div className="pending-overlay" role="status">Waiting for your friend…</div>}{snapshot.state === "expired" && <div className="error-banner" role="alert">This invite has expired.</div>}{snapshot.state === "full" && <div className="error-banner" role="alert">This game is already full.</div>}{snapshot.state === "waiting" && <button className="button button-secondary" type="button" onClick={() => void accept()}>Accept invite</button>}{snapshot.state === "active" && <div className="friend-game-status"><span className={snapshot.opponent?.connected ? "presence online" : "presence offline"}>{snapshot.opponent?.connected ? "Opponent online" : "Opponent disconnected"}</span>{snapshot.clocks && <div className="server-clocks"><strong>{Math.ceil(snapshot.clocks.white_ms / 1000)}s</strong><strong>{Math.ceil(snapshot.clocks.black_ms / 1000)}s</strong></div>}</div>}</>}</section>;
}
