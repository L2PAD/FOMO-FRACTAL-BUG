/**
 * Telegram Filters - Single source of truth
 */

export const DEFAULT_FILTERS = {
  q: '',
  lang: [],
  tier: [],
  lifecycle: [],
  group: [],
  type: [],
  segment: [],
  minMembers: null,
  maxMembers: null,
  minReach: null,
  maxReach: null,
  minGrowth7: null,
  maxGrowth7: null,
  minPostsPerDay: null,
  maxPostsPerDay: null,
  maxFraud: null,
  minCrypto: null,
  sort: 'utility',
  order: 'desc',
  page: 1,
  limit: 50,
};

export function clampNum(v, min, max) {
  return Math.max(min, Math.min(max, v));
}
