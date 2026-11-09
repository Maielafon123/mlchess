import { useEffect, useRef } from "react";
import type { GameSnapshot } from "../../api/gameApi";

export function useTurnVibration(game: GameSnapshot | null | undefined) {
  const previous = useRef<GameSnapshot | null>(null);
  useEffect(() => {
    const before = previous.current;
    previous.current = game ?? null;
    if (game?.status !== "active" || !game.capabilities.can_move || before?.id !== game.id
      || document.visibilityState !== "visible") return;
    const opponentMoved = before.status === "active" && before.side_to_move !== game.side_to_move && game.ply > before.ply;
    if (before.status === "waiting" || opponentMoved) {
      navigator.vibrate?.(45);
    }
  }, [game]);
}
