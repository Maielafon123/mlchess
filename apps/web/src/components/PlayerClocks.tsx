import { useEffect, useState } from "react";
import type { GameSnapshot } from "../api/gameApi";

function format(milliseconds: number) {
  const seconds = Math.ceil(Math.max(0, milliseconds) / 1000);
  return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${(seconds % 60).toString().padStart(2, "0")}`;
}

export function PlayerClocks({ clock }: { clock?: GameSnapshot["clock"] }) {
  const [projection, setProjection] = useState<{ sample: GameSnapshot["clock"]; elapsed: number } | null>(null);
  useEffect(() => {
    if (!clock?.running_side) return;
    const received = performance.now();
    const remaining = clock.running_side === "white" ? clock.white_remaining_ms : clock.black_remaining_ms;
    const timer = window.setInterval(() => {
      const elapsed = performance.now() - received;
      setProjection({ sample: clock, elapsed });
      if (elapsed >= remaining) window.clearInterval(timer);
    }, 100);
    return () => window.clearInterval(timer);
  }, [clock]);
  if (!clock) return null;
  const elapsed = projection?.sample === clock ? projection.elapsed : 0;
  return <div className="player-clocks" aria-label="Шахматные часы">
    <div role="timer" aria-label="Часы белых" data-running={clock.running_side === "white"}><span>Белые</span><strong>{format(clock.white_remaining_ms - (clock.running_side === "white" ? elapsed : 0))}</strong></div>
    <div role="timer" aria-label="Часы чёрных" data-running={clock.running_side === "black"}><span>Чёрные</span><strong>{format(clock.black_remaining_ms - (clock.running_side === "black" ? elapsed : 0))}</strong></div>
  </div>;
}
