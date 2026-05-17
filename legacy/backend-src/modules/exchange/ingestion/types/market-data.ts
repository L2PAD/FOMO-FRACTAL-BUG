/**
 * Market Data Types - Production Grade
 */

export type ProviderId =
  | 'HYPERLIQUID'
  | 'BYBIT_USDTPERP'
  | 'BINANCE_USDM'
  | 'COINBASE_SPOT'
  | 'COINGECKO'
  | 'MOCK';

export type ProviderRole =
  | 'perp_primary'
  | 'spot_validation'
  | 'fallback'
  | 'mock';

export interface RawTick {
  providerId: ProviderId;
  providerRole: ProviderRole;
  symbol: string;
  price: number;
  timestamp: number;
  volume24h?: number;
  fundingRate?: number | null;
  openInterest?: number | null;
  sourceType: 'ws' | 'rest' | 'mock';
}

export interface AggregatedTick {
  symbol: string;
  price: number;
  timestamp: number;
  providersUsed: ProviderId[];
  priceSpreadBps?: number;
  fundingRate?: number | null;
  openInterest?: number | null;
  quality: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface IMarketProvider {
  id: ProviderId;
  role: ProviderRole;
  supportsSymbol(symbol: string): boolean;
  getTicker(symbol: string): Promise<RawTick | null>;
}
