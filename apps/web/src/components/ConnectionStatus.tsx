import { useConnectionStatus } from "../features/realtime/useConnectionStatus";

export function ConnectionStatus({ state }: { state?: "online" | "offline" | "resyncing" | "out-of-sync" }) {
  const detected = useConnectionStatus();
  const current = state ?? detected;
  if (current === "online") return null;
  const text = current === "offline" ? "Offline — moves will retry safely when connection returns." : current === "resyncing" ? "Resyncing game state…" : "Game state is out of sync. Please wait for resync.";
  return <div className="connection-banner" role="status" aria-live="polite">{text}</div>;
}
