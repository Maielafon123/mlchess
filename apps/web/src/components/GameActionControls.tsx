import type { GameActions, HumanAction } from "../api/gameApi";

export function GameActionControls({ actions, disabled, onAction }: { actions: GameActions | null; disabled: boolean; onAction: (action: HumanAction) => void }) {
  return <>
    {actions?.offer_side && !actions.can_accept_draw && <p className="coach-status" role="status">Ничья предложена.</p>}
    <div className="game-actions">
      {actions?.can_offer_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("draw-offers")}>Предложить ничью</button>}
      {actions?.can_accept_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("draw-offers/accept")}>Принять ничью</button>}
      {actions?.can_claim_draw && <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("claim-draw")}>Заявить ничью</button>}
      <button type="button" className="button button-secondary" disabled={disabled} onClick={() => onAction("resign")}>Сдаться</button>
    </div>
  </>;
}
