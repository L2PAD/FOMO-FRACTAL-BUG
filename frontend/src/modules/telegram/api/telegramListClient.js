/**
 * Telegram List API Client
 */
import { filtersToQuery } from '../filters/urlCodec';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export async function fetchTelegramList(filters) {
  const params = new URLSearchParams(filtersToQuery(filters));
  const res = await fetch(`${API_BASE}/api/telegram-intel/utility/list?${params.toString()}`);
  if (!res.ok) throw new Error(`List failed: ${res.status}`);
  return res.json();
}

export async function fetchChannelFull(username) {
  const res = await fetch(`${API_BASE}/api/telegram-intel/channel/${encodeURIComponent(username)}/full`);
  if (!res.ok) throw new Error(`Channel failed: ${res.status}`);
  return res.json();
}
