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

import { taRuntime } from '../ta/services';

export const decisionBridge = {
  approve: (id) => taRuntime.decisions.approve(id),
  reject: (id, reason = 'OPERATOR_REJECTED') =>
    taRuntime.decisions.reject(id, reason),
  note: (id, text) => taRuntime.decisions.note(id, text),
  runCycle: () => taRuntime.runOnce(),
  startEngine: () => taRuntime.start(),
  stopEngine: () => taRuntime.stop(),
};
