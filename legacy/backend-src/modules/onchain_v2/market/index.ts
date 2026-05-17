/**
 * Market Series Layer
 * ====================
 * 
 * PHASE 1: Liquidity & Alt Rotation Engine
 * 
 * Exports for market series module.
 */

export { MarketSeriesModel, MARKET_SERIES_KEYS } from './market.model';
export type { MarketSeriesKey } from './market.model';

export {
  collectMarketSnapshot,
  saveMarketSnapshot,
  getMarketSeries,
  getLatestMarketValue,
  getAllLatestMarketValues,
} from './market.service';

export {
  startMarketJob,
  stopMarketJob,
  forceRunMarketJob,
  getMarketJobStatus,
} from './market.job';

export { marketRoutes } from './market.routes';
