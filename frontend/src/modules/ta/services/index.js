/**
 * modules/ta/services — public surface of the TA service layer.
 *
 * Re-export everything from `taService` so callers can use a single import:
 *
 *     import { taRuntime, taTrace, taAnalytics } from 'modules/ta/services';
 */
export {
  default as taService,
  taRuntime,
  taTrace,
  taAnalytics,
  taLearning,
  taRaw,
  TA_API_ROOT,
} from './taService';
