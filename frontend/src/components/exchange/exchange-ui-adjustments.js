/**
 * Exchange UI Adjustments Helper (Frontend)
 * ==========================================
 * 
 * BLOCK E2: Single source of truth for frontend adjustments
 * Symmetric with backend exchange-ui-adjustments.ts
 */

/**
 * Apply adjustments to chart response
 */
export function applyExchangeAdjustments(data) {
  if (!data) return null;

  const raw = data.reliability?.rawConfidence ?? 0;
  const uri = data.reliability?.uriMultiplier ?? 1;
  const calib = data.reliability?.calibrationMultiplier ?? 1;
  const capital = data.reliability?.capitalMultiplier ?? 1;
  const safeMode = data.meta?.safeMode ?? false;

  let finalConfidence = raw * uri * calib * capital;

  if (safeMode) {
    finalConfidence = 0;
  }

  return {
    ...data.forecast,
    confidenceFinal: finalConfidence,
    targetFinal: data.forecast?.targetFinal ?? data.forecast?.entry ?? 0,
    expectedMovePct: data.forecast?.expectedMovePct ?? 0,
  };
}

/**
 * Format percentage for display
 */
export function formatPercent(value, decimals = 2) {
  if (!Number.isFinite(value)) return '0.00%';
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * Get direction color
 */
export function getDirectionColor(direction) {
  if (direction === 'LONG') return '#16a34a'; // green
  if (direction === 'SHORT') return '#dc2626'; // red
  return '#6b7280'; // gray
}

/**
 * Get outcome badge style
 */
export function getOutcomeStyle(outcome) {
  const styles = {
    TP: { bg: '#dcfce7', color: '#16a34a' },
    FP: { bg: '#fee2e2', color: '#dc2626' },
    FN: { bg: '#ffedd5', color: '#ea580c' },
    WEAK: { bg: '#fef9c3', color: '#ca8a04' },
    VOIDED: { bg: '#f3f4f6', color: '#6b7280' },
    PENDING: { bg: '#f3f4f6', color: '#6b7280' },
  };
  return styles[outcome] || styles.PENDING;
}
