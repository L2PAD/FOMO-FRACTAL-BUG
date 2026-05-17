/**
 * Binding Utils - Helper functions for entity binding
 * ===================================================
 */

export function isBoundActive(entityId, hovered, selected) {
  const active = selected || hovered;
  if (!active || !entityId) return false;

  if (active.id === entityId) return true;
  if (Array.isArray(active.relatedIds) && active.relatedIds.includes(entityId)) return true;

  return false;
}

// Structure entities
export function makeSwingId(swing) {
  return `swing-${swing.time}-${swing.type}`;
}

export function makeEventId(event) {
  return `event-${event.time}-${event.type}-${event.direction}`;
}

// Execution entities
export function makeEntryZoneId(symbol, timeframe) {
  return `entry-zone-${symbol}-${timeframe}`;
}

export function makeRiskZoneId(symbol, timeframe) {
  return `risk-zone-${symbol}-${timeframe}`;
}

export function makeTargetZoneId(symbol, timeframe) {
  return `target-zone-${symbol}-${timeframe}`;
}

// Analysis entities
export function makeBlockerId(slug) {
  return `blocker-${slug}`;
}

// Operational entities
export function makePositionId(positionId) {
  return `position-${positionId}`;
}

export function makeOrderId(orderId) {
  return `order-${orderId}`;
}

export function makeTradeId(tradeId) {
  return `trade-${tradeId}`;
}

export function slugify(value = '') {
  return String(value)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9а-яіїєґ]+/gi, '-')
    .replace(/^-+|-+$/g, '');
}
