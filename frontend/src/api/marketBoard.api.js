/**
 * P2 — Market V2 API
 * Fetches board data from /api/v11/exchange/market/board
 */

const API = process.env.REACT_APP_BACKEND_URL;

export async function fetchMarketBoard(universe = 'alpha') {
  const res = await fetch(`${API}/api/v11/exchange/market/board?universe=${universe}`);
  if (!res.ok) throw new Error(`Market board fetch failed: ${res.status}`);
  return res.json();
}
