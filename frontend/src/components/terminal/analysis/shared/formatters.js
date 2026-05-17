/**
 * Formatters - Utility functions
 */

export function fmtPct(v) {
  if (v == null) return '—';
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtNum(v, decimals = 2) {
  if (v == null) return '—';
  return v.toFixed(decimals);
}
