import type { GameSnapshot } from "../api/gameApi";

export function GameReviewLink({ game }: { game: GameSnapshot }) {
  if (game.status !== "finished" || !game.moves.length) return null;
  return <a className="button button-secondary" href={`/play/report?game=${encodeURIComponent(game.id)}`}>Разобрать партию</a>;
}
