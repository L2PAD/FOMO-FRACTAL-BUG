/**
 * Exchange Admin API Client
 * ==========================
 * 
 * BLOCK E6: API wrapper for Exchange Admin dashboard
 */

import { ExchangeAdminSnapshot } from '../types/exchangeAdmin.types';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

async function safeJson(res: Response) {
  const txt = await res.text();
  try { return JSON.parse(txt); } catch { return { raw: txt }; }
}

async function fetchJSON<T>(url: string): Promise<T> {
  const res = await fetch(`${API_URL}${url}`, { cache: 'no-store' });
  if (!res.ok) {
    const body = await safeJson(res);
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(body).slice(0, 500)}`);
  }
  return (await res.json()) as T;
}

async function postJSON<T>(url: string, body?: any): Promise<T> {
  const res = await fetch(`${API_URL}${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const data = await safeJson(res);
    throw new Error(`HTTP ${res.status}: ${JSON.stringify(data).slice(0, 500)}`);
  }
  return (await res.json()) as T;
}

export async function getExchangeAdminSnapshot(): Promise<ExchangeAdminSnapshot> {
  return fetchJSON<ExchangeAdminSnapshot>('/api/admin/exchange-ml/admin-snapshot');
}

export async function rerunDriftCheck(): Promise<{ ok: boolean; message: string }> {
  return postJSON('/api/admin/exchange-ml/actions/rerun-drift');
}

export async function rerunCalibration(): Promise<{ ok: boolean; message: string }> {
  return postJSON('/api/admin/exchange-ml/actions/rerun-calibration');
}

export async function recomputeCapital(): Promise<{ ok: boolean; message: string }> {
  return postJSON('/api/admin/exchange-ml/actions/recompute-capital');
}

export async function flushEvidence(): Promise<{ ok: boolean; message: string }> {
  return postJSON('/api/admin/exchange-ml/actions/flush-evidence');
}
