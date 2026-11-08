import { backoffDelay } from "./realtimeResilience";
import type { WsEnvelope } from "./wsEnvelope";
import type { GameEventV1 } from "./contracts";
import type { components } from "../../../../contracts/generated/api";

const SERVER_EVENT_TYPES = new Set<GameEventV1["type"]>([
  "game.snapshot",
  "server.resync_required",
  "game.move_committed",
  "game.status_changed",
  "game.clock_sync",
  "game.takeback_applied",
  "analysis.ready",
  "coach.ready",
]);

export type WebSocketLike = Pick<WebSocket, "send" | "close"> & {
  readonly readyState: number;
  addEventListener(type: "open" | "message" | "close" | "error", listener: (event: Event | MessageEvent<string>) => void): void;
  removeEventListener(type: "open" | "message" | "close" | "error", listener: (event: Event | MessageEvent<string>) => void): void;
};

export type GameWebSocketOptions<TPayload> = {
  url: string;
  gameId: string;
  afterSeq: () => number;
  onEnvelope: (event: WsEnvelope<TPayload>) => void;
  onState?: (state: "connecting" | "open" | "closed" | "error") => void;
  socketFactory?: (url: string) => WebSocketLike;
  maxRetries?: number;
};

function isEnvelope<TPayload>(value: unknown): value is WsEnvelope<TPayload> {
  if (!value || typeof value !== "object") return false;
  const item = value as Record<string, unknown>;
  return item.schema_version === 1 && typeof item.event_id === "string" && typeof item.game_id === "string" && typeof item.seq === "number" && Number.isSafeInteger(item.seq) && item.seq >= 0 && typeof item.type === "string" && SERVER_EVENT_TYPES.has(item.type as GameEventV1["type"]) && typeof item.occurred_at === "string" && "payload" in item;
}

export class GameWebSocket<TPayload> {
  private socket: WebSocketLike | null = null;
  private retry = 0;
  private stopped = false;
  private reconnectTimer: number | null = null;
  private readonly options: GameWebSocketOptions<TPayload>;
  private detach: (() => void) | null = null;

  constructor(options: GameWebSocketOptions<TPayload>) {
    this.options = options;
  }

  connect() {
    if (this.socket || this.reconnectTimer !== null) return;
    this.stopped = false;
    this.retry = 0;
    this.open();
  }

  close() {
    this.stopped = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.detach?.();
    this.detach = null;
    this.socket?.close();
    this.socket = null;
    this.options.onState?.("closed");
  }

  private open() {
    if (this.stopped) return;
    this.options.onState?.("connecting");
    const factory = this.options.socketFactory ?? ((url: string) => new WebSocket(url));
    let socket: WebSocketLike;
    try { socket = factory(this.options.url); }
    catch { this.options.onState?.("error"); this.scheduleReconnect(); return; }
    this.socket = socket;
    const current = () => !this.stopped && this.socket === socket;
    const onOpen = () => {
      if (!current()) return;
      const subscription: components["schemas"]["GameSubscribeV1"] = { type: "subscribe", game_id: this.options.gameId, after_seq: this.options.afterSeq() };
      socket.send(JSON.stringify(subscription));
      this.options.onState?.("open");
    };
    const onMessage = (event: Event | MessageEvent<string>) => {
      if (!current() || !(event instanceof MessageEvent) || typeof event.data !== "string") return;
      try {
        const parsed: unknown = JSON.parse(event.data);
        if (isEnvelope<TPayload>(parsed) && parsed.game_id === this.options.gameId) { this.retry = 0; this.options.onEnvelope(parsed); }
      } catch {
        this.options.onState?.("error");
      }
    };
    const onClose = (event: Event) => {
      if (!current()) return;
      this.detach?.(); this.detach = null; this.socket = null;
      this.options.onState?.("closed");
      const code = (event as CloseEvent).code;
      if ([1008, 1009, 4401, 4403].includes(code)) { this.stopped = true; return; }
      this.scheduleReconnect();
    };
    const onError = () => { if (current()) this.options.onState?.("error"); };
    socket.addEventListener("open", onOpen);
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);
    this.detach = () => {
      socket.removeEventListener("open", onOpen);
      socket.removeEventListener("message", onMessage);
      socket.removeEventListener("close", onClose);
      socket.removeEventListener("error", onError);
    };
  }

  private scheduleReconnect() {
    if (this.stopped || this.retry >= (this.options.maxRetries ?? 5)) return;
    const delay = backoffDelay(this.retry);
    this.retry += 1;
    this.reconnectTimer = window.setTimeout(() => { this.reconnectTimer = null; this.open(); }, delay);
  }
}
