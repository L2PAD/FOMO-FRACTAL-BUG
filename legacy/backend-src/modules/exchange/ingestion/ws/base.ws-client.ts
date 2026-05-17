/**
 * Base WebSocket Client v2 - С health tracking и stale detection
 */
import WebSocket from 'ws';
import { providerHealthTracker } from './provider-health.js';

export abstract class BaseWsClient {
  protected ws: WebSocket | null = null;
  protected reconnectTimer: NodeJS.Timeout | null = null;
  protected pingTimer: NodeJS.Timeout | null = null;
  protected staleTimer: NodeJS.Timeout | null = null;
  protected isShuttingDown = false;
  protected reconnectAttempts = 0;
  protected lastMessageAt: number | null = null;

  constructor(
    protected readonly providerId: string,
    protected readonly name: string,
    protected readonly url: string
  ) {
    providerHealthTracker.init(providerId);
  }

  start() {
    this.isShuttingDown = false;
    this.connect();
  }

  stop() {
    this.isShuttingDown = true;

    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.pingTimer) clearInterval(this.pingTimer);
    if (this.staleTimer) clearInterval(this.staleTimer);

    this.reconnectTimer = null;
    this.pingTimer = null;
    this.staleTimer = null;

    if (this.ws) {
      try {
        this.ws.removeAllListeners();
        this.ws.close();
      } catch {}
    }

    this.ws = null;
  }

  protected connect() {
    console.log(`[${this.name}] connecting ${this.url}`);
    this.ws = new WebSocket(this.url);

    this.ws.on('open', () => {
      this.reconnectAttempts = 0;
      console.log(`[${this.name}] connected`);
      this.onOpen();
      this.startHeartbeat();
      this.startStaleCheck();
    });

    this.ws.on('message', (data) => {
      try {
        this.lastMessageAt = Date.now();
        providerHealthTracker.markMessage(this.providerId);
        this.onMessage(data.toString());
      } catch (error: any) {
        providerHealthTracker.markError(this.providerId);
        console.error(`[${this.name}] message error:`, error?.message);
      }
    });

    this.ws.on('error', (error: any) => {
      providerHealthTracker.markError(this.providerId);
      console.error(`[${this.name}] error:`, error?.message);
    });

    this.ws.on('close', (code, reason) => {
      providerHealthTracker.markError(this.providerId);
      console.warn(
        `[${this.name}] close code=${code} reason=${reason?.toString?.() ?? ''}`
      );

      if (!this.isShuttingDown) {
        this.scheduleReconnect();
      }
    });
  }

  protected scheduleReconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);

    const delay = Math.min(30_000, 1000 * Math.pow(2, this.reconnectAttempts));
    this.reconnectAttempts += 1;

    console.log(`[${this.name}] reconnect in ${delay}ms`);

    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  protected startHeartbeat() {
    if (this.pingTimer) clearInterval(this.pingTimer);

    this.pingTimer = setInterval(() => {
      try {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.sendPing();
        }
      } catch (error: any) {
        providerHealthTracker.markError(this.providerId);
        console.error(`[${this.name}] heartbeat error:`, error?.message);
      }
    }, 15_000);
  }

  protected startStaleCheck() {
    if (this.staleTimer) clearInterval(this.staleTimer);

    this.staleTimer = setInterval(() => {
      if (!this.lastMessageAt) return;

      const age = Date.now() - this.lastMessageAt;
      if (age > 20_000) {
        console.warn(`[${this.name}] stale feed age=${age}ms`);
        providerHealthTracker.markStale(this.providerId);
      }
    }, 5000);
  }

  protected send(data: unknown) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(data));
  }

  protected sendPing() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.ping();
  }

  getLastMessageAt() {
    return this.lastMessageAt;
  }

  protected abstract onOpen(): void;
  protected abstract onMessage(raw: string): void;
}
