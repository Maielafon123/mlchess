import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MatchmakingApi, type MatchPool, type MatchTicket, type RatedGame, type RatingPool } from "../../api/matchmakingApi";
import { GameApi, canAdoptSnapshot, type GameSnapshot } from "../../api/gameApi";
import { ApiError } from "../../api/errors";
import { createIdempotencyKey } from "../../api/client";
import { GameBoard } from "../../components/GameBoard";
import { PlayerClocks } from "../../components/PlayerClocks";
import { GameActionControls } from "../../components/GameActionControls";
import { useGameRealtime } from "../game/useGameRealtime";
import { useHumanGameActions } from "../game/useHumanGameActions";

const labels: Record<RatingPool, string> = { "rapid-10+0": "Рапид 10+0", "blitz-5+0": "Блиц 5+0" };
const ticketIdPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const message = (value: unknown) => value instanceof ApiError && value.problem.status === 409 ? "Сначала завершите текущую партию или отмените поиск." : "Не удалось обновить игру. Повторите попытку.";

export function MatchmakingScreen({ api, gameApi, eligible = false, userId }: { api?: MatchmakingApi; gameApi?: GameApi; eligible?: boolean; userId?: string }) {
  const resolvedApi = useMemo(() => api ?? new MatchmakingApi(), [api]);
  const resolvedGameApi = useMemo(() => gameApi ?? new GameApi(), [gameApi]);
  const [pool, setPool] = useState<RatingPool>("rapid-10+0");
  const [pools, setPools] = useState<MatchPool[]>([]);
  const [ticket, setTicket] = useState<MatchTicket | null>(null);
  const [game, setGame] = useState<GameSnapshot | null>(null);
  const [rating, setRating] = useState<RatedGame | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const busy = useRef(false);
  const queueRevision = useRef(0);
  const joinKey = useRef<{ pool: RatingPool; key: string } | null>(null);
  const cancelKey = useRef<{ id: string; key: string } | null>(null);
  const acceptTicket = useCallback((next: MatchTicket | null) => {
    setTicket(next);
    const query = next ? `?${new URLSearchParams({ ticket: next.ticket_id })}` : "";
    window.history.replaceState(window.history.state, "", `/play/matchmaking${query}`);
  }, []);
  const adopt = useCallback((next: GameSnapshot) => setGame((current) => canAdoptSnapshot(current, next) ? next : current), []);

  useEffect(() => {
    if (!eligible) return;
    const controller = new AbortController();
    const signal = controller.signal;
    const entry = new URLSearchParams(window.location.search).get("ticket");
    const current = () => resolvedApi.current(signal).then((value) => value.ticket);
    const resume = entry && ticketIdPattern.test(entry) ? resolvedApi.get(entry, signal).catch((failure) => {
      if (failure instanceof ApiError && [403, 404].includes(failure.problem.status)) return current();
      throw failure;
    }) : current();
    void Promise.all([resolvedApi.pools(signal), resume]).then(([list, next]) => {
      if (signal.aborted) return;
      setPools(list.items); if (next) setPool(next.pool); acceptTicket(next);
    }).catch((failure) => { if (!signal.aborted) setError(message(failure)); })
      .finally(() => { if (!signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [acceptTicket, eligible, resolvedApi]);

  const ticketId = ticket?.ticket_id;
  const status = ticket?.status;
  useEffect(() => {
    if (!eligible || !ticketId || status !== "searching") return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      if (!busy.current) {
        const revision = queueRevision.current;
        try {
          const next = await resolvedApi.get(ticketId, controller.signal);
          if (controller.signal.aborted) return;
          if (revision === queueRevision.current) {
            acceptTicket(next); setError(null);
            if (next.status !== "searching") return;
          }
        } catch (failure) {
          if (!controller.signal.aborted && revision === queueRevision.current) setError(message(failure));
        }
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, document.hidden ? 4000 : 1000);
    };
    timer = setTimeout(poll, 500);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [acceptTicket, eligible, resolvedApi, status, ticketId]);

  const gameId = ticket?.game_id ?? undefined;
  useEffect(() => {
    if (!eligible || !gameId) return;
    let active = true;
    void resolvedGameApi.get(gameId).then((next) => {
      if (next.id !== gameId || next.mode !== "rated") throw new Error("Invalid game identity");
      if (active) setGame(next);
    }).catch((failure) => { if (active) setError(message(failure)); });
    return () => { active = false; };
  }, [eligible, gameId, resolvedGameApi]);

  const snapshot = game?.id === gameId ? game : null;
  const active = snapshot?.status === "active";
  const version = snapshot?.version;
  const connected = useGameRealtime(active ? gameId : undefined, resolvedGameApi, adopt);
  const actions = useHumanGameActions(snapshot, resolvedGameApi, adopt, pending);
  useEffect(() => {
    if (!eligible || !gameId || !active) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const next = await resolvedGameApi.get(gameId); if (!stopped) adopt(next); }
      catch (failure) { if (!stopped) setError(message(failure)); }
      if (!stopped) timer = setTimeout(poll, connected || document.hidden ? 5000 : 1000);
    };
    timer = setTimeout(poll, connected ? 5000 : 1000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [active, adopt, connected, eligible, gameId, resolvedGameApi]);
  useEffect(() => {
    if (!eligible || !gameId || version === undefined) return;
    const controller = new AbortController();
    void resolvedApi.game(gameId, controller.signal).then((next) => { if (!controller.signal.aborted) setRating(next); })
      .catch((failure) => { if (!controller.signal.aborted) setError(message(failure)); });
    return () => controller.abort();
  }, [eligible, gameId, resolvedApi, version]);

  const join = async () => {
    if (!eligible || busy.current) return;
    busy.current = true; setPending(true); setError(null);
    if (joinKey.current?.pool !== pool) joinKey.current = { pool, key: createIdempotencyKey() };
    try { acceptTicket(await resolvedApi.join(pool, joinKey.current.key)); joinKey.current = null; }
    catch (failure) { setError(message(failure)); }
    finally { busy.current = false; setPending(false); }
  };
  const cancel = async () => {
    if (!ticketId || status !== "searching" || busy.current) return;
    busy.current = true; queueRevision.current += 1; setPending(true); setError(null);
    if (cancelKey.current?.id !== ticketId) cancelKey.current = { id: ticketId, key: createIdempotencyKey() };
    try { acceptTicket(await resolvedApi.cancel(ticketId, cancelKey.current.key)); cancelKey.current = null; }
    catch (failure) {
      try { const next = await resolvedApi.get(ticketId); acceptTicket(next); if (next.status === "searching") setError(message(failure)); }
      catch { setError(message(failure)); }
    } finally { busy.current = false; setPending(false); }
  };
  const another = () => {
    setGame(null); setRating(null); setError(null); acceptTicket(null);
    void resolvedApi.pools().then((value) => setPools(value.items)).catch((failure) => setError(message(failure)));
  };
  const details = rating?.game_id === gameId ? rating : null;
  const side = snapshot?.players.find((player) => player.user_id === userId)?.side ?? details?.side ?? "white";
  const settled = snapshot?.status === "finished" && details && details.version === version ? details.rating_change : null;
  const outcome = snapshot?.result === "draw" ? "Ничья" : snapshot?.result === side ? "Победа" : "Поражение";

  return <section className="matchmaking-screen" aria-label="Rated matchmaking">
    <div className="analysis-header"><h2>Рейтинговая игра</h2><span className="status-chip">Без подсказок</span></div>
    {!eligible && <p>Для рейтинга нужен аккаунт. <a href="/play/friend">Сыграть с другом без регистрации</a></p>}
    {eligible && <>
      {(error || actions.error) && <div className="error-banner" role="alert">{error ?? actions.error} <button type="button" onClick={() => window.location.reload()}>Обновить</button></div>}
      {loading && <p role="status">Загружаем рейтинг…</p>}
      {!loading && !gameId && status !== "searching" && pools.length > 0 && <>
        {status === "expired" && <p role="status">Время поиска истекло. Можно начать заново.</p>}
        {status === "cancelled" && <p role="status">Поиск отменён.</p>}
        <div className="pool-grid">{pools.map((item) => <button key={item.pool} type="button" aria-pressed={pool === item.pool} className={pool === item.pool ? "active" : ""} onClick={() => setPool(item.pool)} disabled={pending}><strong>{labels[item.pool]}</strong>{item.your_rating !== null && <span>Ваш рейтинг {item.your_rating}</span>}</button>)}</div>
        <button className="button button-primary" type="button" disabled={pending} onClick={() => void join()}>Найти соперника</button>
      </>}
      {ticket?.status === "searching" && <><p role="status">Ищем соперника…</p><p className="coach-status">{labels[ticket.pool]} · рейтинг соперника {ticket.rating_min}–{ticket.rating_max}</p><button className="button button-secondary" type="button" disabled={pending} onClick={() => void cancel()}>Отменить поиск</button></>}
      {gameId && !snapshot && !error && <p role="status">Загружаем партию…</p>}
      {snapshot && <div className="rated-game">
        {details && <div className="opponent-row"><strong>{details.opponent_name}</strong><span>Рейтинг {details.opponent_rating}</span></div>}
        {active && <><span className="coach-status" role="status">{connected ? "Связь установлена" : "Проверяем соединение…"}</span><p role="status">{snapshot.capabilities.can_move ? "Ваш ход" : "Ход соперника"}</p></>}
        {snapshot.status === "finished" && <p role="status">Партия завершена: {outcome}{snapshot.termination === "timeout" ? " · время вышло" : ""}</p>}
        {settled && <p className="rating-result" role="status">Рейтинг {settled.before} → {settled.after} ({settled.delta > 0 ? "+" : ""}{settled.delta})</p>}
        <PlayerClocks clock={snapshot.clock} />
        <GameBoard fen={snapshot.fen} moves={snapshot.moves} orientation={side} disabled={actions.pending || !snapshot.capabilities.can_move} onMoveAttempt={actions.move} />
        {active && <GameActionControls actions={actions.capabilities} disabled={actions.pending} onAction={actions.action} />}
        {snapshot.status === "finished" && <button className="button button-primary" type="button" disabled={actions.pending} onClick={another}>Новый поиск</button>}
      </div>}
    </>}
  </section>;
}
