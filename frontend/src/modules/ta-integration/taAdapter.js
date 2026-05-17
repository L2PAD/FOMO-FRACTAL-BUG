/**
 * TA INTEGRATION LAYER
 *
 * Единственная точка входа MAIN → TA.
 *
 * ❌ Не добавлять бизнес-логику
 * ❌ Не делать вычислений
 * ❌ Не дергать API напрямую (только через taService)
 *
 * Это мост, не мозг.
 */

import { taRuntime, taTrace, taAnalytics } from '../ta/services';

export const taAdapter = {
  getSystemState: () => taRuntime.getState(),
  getLatestTrace: () => taTrace.getLatest({ limit: 30 }),
  getDecisionStats: () => taTrace.getStats(),
  getDaemonStatus: () => taRuntime.daemon.getStatus(),
  getAnalytics: () => taAnalytics.getDecisionQuality(),
  getPendingDecisions: () => taRuntime.decisions.listPending(),
};
