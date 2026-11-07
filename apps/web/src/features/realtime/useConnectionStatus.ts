import { useEffect, useState } from "react";
import type { ConnectionState } from "../../api/realtimeResilience";

export function useConnectionStatus() {
  const [state, setState] = useState<ConnectionState>(() => navigator.onLine ? "online" : "offline");
  useEffect(() => { const online = () => setState("online"); const offline = () => setState("offline"); window.addEventListener("online", online); window.addEventListener("offline", offline); return () => { window.removeEventListener("online", online); window.removeEventListener("offline", offline); }; }, []);
  return state;
}
