import { backoffDelay } from "./realtimeResilience";
import type { WsEnvelope } from "./wsEnvelope";
import type { GameEventV1 } from "./contracts";

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
  return item.schema_version === 1 && typeof item.event_id === "string" && typeof item.game_id === "string" && typeof item.seq === "number" && Number.isInteger(item.seq) && item.seq >= 0 && typeof item.type === "string" && SERVER_EVENT_TYPES.has(item.type as GameEventV1["type"]) && typeof item.occurred_at === "string" && "payload" in item;
}

export class GameWebSocket<TPayload> {
  private socket: WebSocketLike | null = null;
  private retry = 0;
  private stopped = false;
  private reconnectTimer: number | null = null;
  private readonly options: GameWebSocketOptions<TPayload>;

  constructor(options: GameWebSocketOptions<TPayload>) {
    this.options = options;
  }

  connect() {
    this.stopped = false;
    this.open();
  }

  close() {
    this.stopped = true;
    if (this.reconnectTimer !== null) window.clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
    this.socket?.close();
    this.socket = null;
    this.options.onState?.("closed");
  }

  private open() {
    if (this.stopped) return;
    this.options.onState?.("connecting");
    const factory = this.options.socketFactory ?? ((url: string) => new WebSocket(url));
    const socket = factory(this.options.url);
    this.socket = socket;
    const onOpen = () => {
      this.retry = 0;
      socket.send(JSON.stringify({ type: "subscribe", game_id: this.options.gameId, after_seq: this.options.afterSeq() }));
      this.options.onState?.("open");
    };
    const onMessage = (event: Event | MessageEvent<string>) => {
      if (!(event instanceof MessageEvent) || typeof event.data !== "string") return;
      try {
        const parsed: unknown = JSON.parse(event.data);
        if (isEnvelope<TPayload>(parsed) && parsed.game_id === this.options.gameId) this.options.onEnvelope(parsed);
      } catch {
        this.options.onState?.("error");
      }
    };
    const onClose = () => {
      this.options.onState?.("closed");
      this.scheduleReconnect();
    };
    const onError = () => this.options.onState?.("error");
    socket.addEventListener("open", onOpen);
    socket.addEventListener("message", onMessage);
    socket.addEventListener("close", onClose);
    socket.addEventListener("error", onError);
  }

  private scheduleReconnect() {
    if (this.stopped || this.retry >= (this.options.maxRetries ?? 5)) return;
    const delay = backoffDelay(this.retry);
    this.retry += 1;
    this.reconnectTimer = window.setTimeout(() => { this.reconnectTimer = null; this.open(); }, delay);
  }
}
