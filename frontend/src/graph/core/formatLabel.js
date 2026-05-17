/**
 * Address Label Formatting - ЕДИНЫЙ СТАНДАРТ
 * 
 * ЖЁСТКИЕ ПРАВИЛА:
 * - Формат: 0xABCD…1234 (4 символа + … + 4 символа)
 * - Anchor entities → resolved label (Binance, Uniswap, etc.)
 * - Если не влезает — уменьшаем font-size, НЕ меняем формат
 */

import { resolveNodeLabel } from '../utils/nodeLabelResolver';

/**
 * Сокращение адреса: 0xABCD…1234
 */
export function formatAddressLabel(addr, head = 6, tail = 4) {
  if (!addr) return '';
  if (addr.length <= head + tail + 3) return addr;
  return `${addr.slice(0, head)}…${addr.slice(-tail)}`;
}

/**
 * Получить label для ноды графа
 * 
 * Priority:
 * 1. Anchor entity resolution (address → known label)
 * 2. Known protocol names in text
 * 3. Address shortening 0xABCD…1234
 * 4. Truncation fallback
 */
export function getNodeLabel(node) {
  if (!node) return '';

  // Use the unified label resolver (checks anchor entities, known names, address shortening)
  return resolveNodeLabel(node);
}

export default { formatAddressLabel, getNodeLabel };
