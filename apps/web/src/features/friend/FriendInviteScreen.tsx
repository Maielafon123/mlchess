import { useCallback, useEffect, useMemo, useState } from "react";
import { InviteApi, type InviteSnapshot, type TimeControl } from "../../api/inviteApi";
import { GameApi, canAdoptSnapshot, type GameSnapshot } from "../../api/gameApi";
import { createIdempotencyKey } from "../../api/client";
import { ApiError } from "../../api/errors";
import { ensurePublicSession } from "../../auth/guestSession";
import { GameBoard } from "../../components/GameBoard";
import { useGameRealtime } from "../game/useGameRealtime";
import { useHumanGameActions } from "../game/useHumanGameActions";
import { PlayerClocks } from "../../components/PlayerClocks";
import { GameReviewLink } from "../../components/GameReviewLink";
import { GameActionControls } from "../../components/GameActionControls";

const controls: Record<string, TimeControl | null> = {
  untimed: null, "1+0": { initial_ms: 60000, increment_ms: 0 },
  "3+2": { initial_ms: 180000, increment_ms: 2000 },
  "5+3": { initial_ms: 300000, increment_ms: 3000 },
  "10+5": { initial_ms: 600000, increment_ms: 5000 },
};

function rememberGame(gameId: string, inviteId: string) {
  const query = new URLSearchParams({ game: gameId, invite: inviteId });
  window.history.replaceState(window.history.state, "", "/play/friend?" + query.toString());
}

export function FriendInviteScreen({ api, gameApi }: { api?: InviteApi; gameApi?: GameApi }) {
  const resolvedApi = useMemo(() => api ?? new InviteApi(), [api]);
  const resolvedGameApi = useMemo(() => gameApi ?? new GameApi(), [gameApi]);
  const acceptKey = useMemo(() => createIdempotencyKey(), []);
  const [entry] = useState(() => ({
    game: new URLSearchParams(window.location.search).get("game"),
    invite: new URLSearchParams(window.location.search).get("invite"),
    token: new URLSearchParams(window.location.hash.slice(1)).get("token"),
  }));
  const [snapshot, setSnapshot] = useState<InviteSnapshot | null>(null);
  const [game, setGame] = useState<GameSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [copied, setCopied] = useState(false);
  const [timeControl, setTimeControl] = useState("untimed");

  useEffect(() => {
    if (!entry.invite && !entry.game) return;
    let cancelled = false;
    setPending(true);
    void (async () => {
      try {
        await ensurePublicSession();
        let invitation: InviteSnapshot | null = null;
        if (entry.invite) {
          try { invitation = await resolvedApi.get(entry.invite); }
          catch (value: unknown) {
            if (entry.token && value instanceof ApiError && value.problem.status === 403) invitation = await resolvedApi.accept(entry.invite, entry.token, acceptKey);
            else throw value;
          }
        }
        const gameId = invitation?.game_id ?? entry.game;
        if (!gameId) throw new Error("В ссылке не найдена партия.");
        const next = await resolvedGameApi.get(gameId);
        if (!cancelled) {
          setSnapshot(invitation);
          setGame(next);
          if (invitation) rememberGame(gameId, invitation.invite_id);
        }
      } catch (value: unknown) {
        if (!cancelled) setError(value instanceof ApiError && [403, 409].includes(value.problem.status) ? "Этот вызов уже принят, истёк или недоступен в этом браузере." : value instanceof Error ? value.message : "Не удалось принять вызов.");
      } finally {
        if (!cancelled) setPending(false);
      }
    })();
    return () => { cancelled = true; };
  }, [acceptKey, entry, resolvedApi, resolvedGameApi]);

  const gameId = game?.id ?? snapshot?.game_id;
  const finished = game?.status === "finished";
  const expired = snapshot?.state === "expired";
  const invitationId = snapshot?.invite_id;
  const adoptSnapshot = useCallback((next: GameSnapshot) => {
    setGame((current) => canAdoptSnapshot(current, next) ? next : current);
  }, []);
  const connected = useGameRealtime(finished ? undefined : gameId, resolvedGameApi, adoptSnapshot);
  const actions = useHumanGameActions(game, resolvedGameApi, adoptSnapshot, pending);
  useEffect(() => {
    if (!gameId || finished || expired) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    let polls = 0;
    const poll = async () => {
      try {
        const next = await resolvedGameApi.get(gameId);
        if (!cancelled) adoptSnapshot(next);
        if (next.status === "waiting" && invitationId && polls++ % 10 === 0) {
          const invitation = await resolvedApi.get(invitationId);
          if (!cancelled) setSnapshot(invitation);
        }
      } catch (value: unknown) {
        if (!cancelled) setError(value instanceof Error ? value.message : "Проверяем соединение…");
      } finally {
        if (!cancelled) timer = setTimeout(poll, document.hidden || connected ? 5000 : 1000);
      }
    };
    timer = setTimeout(poll, 1000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [adoptSnapshot, connected, expired, finished, gameId, invitationId, resolvedApi, resolvedGameApi]);

  const create = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await ensurePublicSession();
      const invitation = await resolvedApi.create(controls[timeControl]);
      setSnapshot(invitation);
      setGame(await resolvedGameApi.get(invitation.game_id));
      rememberGame(invitation.game_id, invitation.invite_id);
    } catch (value: unknown) {
      setError(value instanceof Error ? value.message : "Не удалось создать вызов.");
    } finally { setPending(false); }
  };
  const copy = async () => {
    if (!snapshot?.invite_url) return;
    try {
      await navigator.clipboard.writeText(snapshot.invite_url);
      setCopied(true);
    } catch { setError("Выделите и скопируйте ссылку из поля ниже."); }
  };
  const waiting = game?.status === "waiting" && snapshot?.state !== "expired";
  return <section className="friend-screen" aria-label="Friend game">
    <div className="analysis-header"><h1>Игра с другом</h1><span className="status-chip">Без регистрации</span></div>
    <p className="friend-description">{game?.status === "active" ? "Нажмите фигуру, затем поле для хода. Партия сохраняется автоматически." : "Отправьте ссылку другу. Он сразу займёт второе место; партия сохранится в ваших браузерах."}</p>
    {(error || actions.error) && <div className="error-banner" role="alert">{error ?? actions.error}</div>}
    {!snapshot && !game && !entry.invite && !entry.game && <div className="friend-create"><label>Контроль времени<select value={timeControl} disabled={pending} onChange={(event) => setTimeControl(event.target.value)}><option value="untimed">Без часов</option>{Object.keys(controls).filter((name) => name !== "untimed").map((name) => <option key={name} value={name}>{name.replace("+", " мин + ")} сек</option>)}</select></label><button className="button button-primary" type="button" disabled={pending} onClick={() => void create()}>Создать вызов</button></div>}
    {pending && <div className="status-banner" role="status">Подключаемся…</div>}
    {snapshot?.invite_url && waiting && <div className="invite-row">
      <label className="invite-link-label">Ссылка для друга<input aria-label="Ссылка для друга" readOnly value={snapshot.invite_url} onFocus={(event) => event.currentTarget.select()} /></label>
      <button className="button button-secondary" type="button" onClick={() => void copy()}>{copied ? "Скопировано" : "Копировать ссылку"}</button>
      {typeof navigator.share === "function" && <button className="button button-secondary" type="button" onClick={() => void navigator.share({ title: "Шахматный вызов", url: snapshot.invite_url! }).catch(() => {})}>Поделиться</button>}
    </div>}
    {waiting && <div className="status-banner" role="status">Ожидаем друга… Ссылка действует 24 часа.</div>}
    {snapshot?.state === "expired" && <div className="error-banner">Срок ссылки истёк. <a href="/play/friend">Создать новый вызов</a></div>}
    {game && <>
      {!finished && <span className="coach-status" role="status">{connected ? "Связь установлена" : "Проверяем соединение…"}</span>}
      <div className="friend-game-status" role="status">{finished ? "Партия завершена: " + (game.result === "draw" ? "ничья" : game.result === "white" ? "победили белые" : "победили чёрные") + (game.termination === "timeout" ? " · время вышло" : "") : game.status === "active" ? game.capabilities.can_move ? "Ваш ход" : "Ход соперника" : "Партия ещё не началась"}</div>
      <PlayerClocks clock={game.clock} />
      {game.status === "active" && <GameActionControls actions={actions.capabilities} disabled={pending || actions.pending} onAction={(kind) => { setError(null); actions.action(kind); }} />}
      <GameBoard fen={game.fen} moves={game.moves} orientation={snapshot?.created_by_current_user === false ? "black" : "white"} disabled={pending || actions.pending || !game.capabilities.can_move} onMoveAttempt={(uci) => { setError(null); actions.move(uci); }} />
      {finished && <div className="game-actions"><a className="button button-primary" href="/play/friend">Новая партия</a><GameReviewLink game={game} /></div>}
    </>}
    <p className="friend-description">В этой партии нет подсказок тренера или анализа.</p>
  </section>;
}
