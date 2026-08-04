import { WS_BASE } from "./api";
import type { GameEvent, GameView } from "./types";

export interface WsCallbacks {
  onEvents: (events: GameEvent[]) => void;
  onView: (view: GameView) => void;
  onError: (message: string) => void;
  onStatus: (connected: boolean) => void;
}

export interface WsCommand {
  type: string;
  payload?: Record<string, any>;
}

/**
 * 对局 WebSocket 客户端：自动重连、断线补发（last_seq 同步）、request_id 幂等。
 */
export class GameClient {
  private ws: WebSocket | null = null;
  private cb: WsCallbacks;
  private lastSeq = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;
  private retryCount = 0;

  constructor(cb: WsCallbacks) {
    this.cb = cb;
  }

  connect() {
    this.closed = false;
    this.open();
  }

  private open() {
    try {
      this.ws = new WebSocket(`${WS_BASE}/ws/game/current`);
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws.onopen = () => {
      this.retryCount = 0;
      this.cb.onStatus(true);
      // 断线重连：提交最后收到的序号，后端补发缺失事件
      this.sendRaw({ type: "sync", last_seq: this.lastSeq });
    };
    this.ws.onmessage = (e) => this.handleMessage(e.data);
    this.ws.onclose = () => {
      this.cb.onStatus(false);
      this.scheduleReconnect();
    };
    this.ws.onerror = () => {
      /* onclose 会触发重连 */
    };
  }

  private scheduleReconnect() {
    if (this.closed) return;
    const delay = Math.min(1000 * 2 ** this.retryCount, 10000);
    this.retryCount += 1;
    this.reconnectTimer = setTimeout(() => this.open(), delay);
  }

  private handleMessage(raw: string) {
    let msg: any;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }
    if (msg.type === "event") {
      const ev = msg.event as GameEvent;
      if (ev.seq > this.lastSeq) {
        this.lastSeq = ev.seq;
        this.cb.onEvents([ev]);
      }
    } else if (msg.type === "sync_events") {
      const events = (msg.events || []) as GameEvent[];
      const fresh = events.filter((e) => e.seq > this.lastSeq);
      if (fresh.length) {
        this.lastSeq = Math.max(...fresh.map((e) => e.seq));
        this.cb.onEvents(fresh);
      }
    } else if (msg.type === "view") {
      this.cb.onView(msg.view as GameView);
    } else if (msg.type === "error") {
      this.cb.onError(msg.message || "操作失败");
    } else if (msg.type === "pong") {
      /* 心跳 */
    }
  }

  private sendRaw(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendCommand(type: string, payload?: Record<string, any>): string {
    const request_id = typeof crypto !== "undefined" && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random()}`;
    this.sendRaw({ type, request_id, payload: payload || {} });
    return request_id;
  }

  close() {
    this.closed = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) this.ws.close();
  }
}
