import { useState } from "react";
import type { GameActions, GameSnapshot, HumanAction } from "../api/gameApi";

export function GameActionControls({ actions, disabled, onAction }: { actions: GameActions | null; disabled: boolean; onAction: (action: HumanAction) => void }) {
  const [confirming, setConfirming] = useState(false);
  return <div className="game-action-panel" role="group" aria-label="Действия в партии">
    {actions?.offer_side && <p className="coach-status" role="status">{actions.can_accept_draw ? "Соперник предлагает ничью." : "Вы предложили ничью."}</p>}
    <div className="game-actions game-action-buttons">
      {actions?.can_offer_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("draw-offers")}>Предложить ничью</button>}
      {actions?.can_accept_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("draw-offers/accept")}>Принять ничью</button>}
      {actions?.can_claim_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("claim-draw")}>Заявить ничью</button>}
      {confirming ? <>
        <button type="button" className="button button-secondary" disabled={disabled} onClick={() => { setConfirming(false); onAction("resign"); }}>Подтвердить сдачу</button>
        <button type="button" className="button button-secondary" onClick={() => setConfirming(false)}>Продолжить игру</button>
      </> : <button type="button" className="button button-secondary" disabled={disabled} onClick={() => setConfirming(true)}>Сдаться</button>}
    </div>
  </div>;
}

export function SoloGameResult({ game }: { game: GameSnapshot }) {
  if (game.status !== "finished") return null;
  const result = game.result === "draw" ? "ничья" : game.result === "white" ? "победили белые" : game.result === "black" ? "победили чёрные" : "без результата";
  const reason = game.termination === "timeout" ? " · время вышло" : game.termination === "resignation" ? " · игрок сдался" : "";
  return <p role="status">Партия завершена: {result}{reason}</p>;
}
