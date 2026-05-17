/**
 * paper-api — Phase C client surface for the paper runtime contract.
 *
 * All endpoints are read-only or gated.  The simulate POST returns a
 * structured refusal until the gate opens.
 */
import { mbrainApi, MBRAIN_API_URL } from './mbrain-api';

const API_URL = MBRAIN_API_URL;

async function jget<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${API_URL}${path}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    return (await res.json()) as T;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

async function jpost<T>(path: string, body?: any): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8000);
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return (await res.json()) as T;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

export const paperApi = {
  health: () =>
    jget<{
      ok: boolean;
      gate?: { open: boolean; passing: string[]; requires: string[] };
      collections?: Record<string, number>;
      universe?: string[];
      active?: boolean;
      phase?: string;
      note?: string;
      asOf?: string;
    }>('/api/paper/runtime/health'),
  accounts: () => jget<{ ok: boolean; count: number; items: any[] }>('/api/paper/accounts'),
  positions: () => jget<{ ok: boolean; count: number; items: any[] }>('/api/paper/positions'),
  orders: (limit = 50) => jget<{ ok: boolean; count: number; items: any[] }>(
    `/api/paper/orders?limit=${limit}`,
  ),
  events: (limit = 25) => jget<{ ok: boolean; count: number; items: any[] }>(
    `/api/paper/events?limit=${limit}`,
  ),
  simulate: (payload: { symbol?: string; side?: string; size?: number } = {}) =>
    jpost<{ ok: boolean; reason?: string; requires?: string[]; phase?: string }>(
      '/api/paper/orders/simulate',
      payload,
    ),
};
