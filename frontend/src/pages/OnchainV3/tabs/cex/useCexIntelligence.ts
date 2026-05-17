import { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export interface ExchangePressure {
  deposits: number;
  deposits_fmt: string;
  withdrawals: number;
  withdrawals_fmt: string;
  net_flow: number;
  net_fmt: string;
  bias: string;
  active_exchanges: number;
  total_transfers: number;
  top_deposit_txs?: TransactionRef[];
  top_withdrawal_txs?: TransactionRef[];
}

export interface StablecoinPower {
  usdt_in: number;
  usdc_in: number;
  dai_in: number;
  total_in: number;
  total_out: number;
  net_power: number;
  bias: string;
  usdt_top_wallets?: { wallet: string; usd_fmt: string }[];
  usdc_top_wallets?: { wallet: string; usd_fmt: string }[];
  dai_top_wallets?: { wallet: string; usd_fmt: string }[];
}

export interface TransactionRef {
  direction: string;
  token?: string;
  usd_fmt: string;
  from_address: string;
  to_address: string;
  tx_hash: string;
  exchange?: string;
}

export interface ExchangeFlow {
  entityId: string;
  entityName: string;
  inflow_usd: number;
  outflow_usd: number;
  net_usd: number;
  net_fmt: string;
  tx_count: number;
  market_share: number;
  dominant_direction: string;
  behavior_label: string;
  wallet_addresses?: string[];
  top_transactions?: TransactionRef[];
}

export interface LargestTransfer {
  direction: string;
  token: string;
  usd: number;
  usd_fmt: string;
  exchange: string;
  impact_label: string;
  significance: string;
  volume_share: number;
  from_address?: string;
  to_address?: string;
  tx_hash?: string;
}

export interface ExchangeRotation {
  from_exchange: string;
  to_exchange: string;
  total_usd: number;
  total_fmt: string;
  top_token: string;
  count: number;
}

export interface RotationFallback {
  from_exchange: string;
  to_exchange: string;
  total_usd: number;
  total_fmt: string;
  top_token: string;
  count: number;
  time_ago: string;
}

export interface PumpSetup {
  token: string;
  pump_probability: number;
  dump_risk: number;
  drivers: string[];
  confidence_band: {
    low: number;
    high: number;
    spread: number;
    level: string;
  };
  components: {
    smart_flow: number;
    exchange_supply: number;
    stablecoin: number;
    timing: number;
    regime: number;
  };
  top_transactions?: TransactionRef[];
}

export interface Indicators {
  sell_pressure: number;
  liquidity: number;
  confidence: number;
}

export interface MarketLiquidity {
  buy_power: number;
  buy_power_fmt: string;
  sell_supply: number;
  sell_supply_fmt: string;
  net_liquidity: number;
  net_liquidity_fmt: string;
  bias: string;
  interpretation: string;
}

// Sprint B types
export interface InventoryPerExchange {
  exchange: string;
  deposits: number;
  withdrawals: number;
  net: number;
  net_fmt: string;
}

export interface ExchangeInventoryItem {
  token: string;
  deposits: number;
  deposits_fmt: string;
  withdrawals: number;
  withdrawals_fmt: string;
  net_change: number;
  net_change_fmt: string;
  change_pct: number;
  state: string;
  interpretation: string;
  per_exchange: InventoryPerExchange[];
  top_transactions?: TransactionRef[];
}

export interface FlowCompositionItem {
  type: string;
  label: string;
  usd: number;
  usd_fmt: string;
  percentage: number;
  tx_count: number;
  top_transactions?: TransactionRef[];
}

export interface FlowClassification {
  composition: FlowCompositionItem[];
  dominant_type: string;
  dominant_label: string;
  dominant_pct: number;
  interpretation: string;
  total_classified: number;
  total_classified_fmt: string;
}

export interface ShockExchangeDriver {
  exchange: string;
  contribution: number;
  contribution_fmt: string;
  dominant_factor: string;
  wallet_addresses?: string[];
}

export interface LiquidityShock {
  state: string;
  label: string;
  buy_power: number;
  buy_power_fmt: string;
  sell_supply: number;
  sell_supply_fmt: string;
  net: number;
  net_fmt: string;
  ratio: number;
  interpretation: string;
  drivers: string[];
  exchange_drivers: ShockExchangeDriver[];
}

// Sprint C types

// Sprint A Polish types
export interface HeroDominantVenue {
  exchange: string;
  volume_fmt: string;
  share: number;
  net_fmt: string;
  bias: string;
}

export interface HeroDominantAsset {
  token: string;
  volume_fmt: string;
  share: number;
  net_fmt: string;
  bias: string;
}

export interface BehaviorMapPoint {
  exchange: string;
  entity_id: string;
  x: number;
  y: number;
  volume: number;
  volume_fmt: string;
  quadrant: string;
  quadrant_label: string;
  net_flow_fmt: string;
}

export interface BehaviorMapDominant {
  exchange: string;
  quadrant_label: string;
  volume_fmt: string;
  share: number;
}

export interface BehaviorMap {
  points: BehaviorMapPoint[];
  dominant_venue: BehaviorMapDominant | null;
  quadrant_summary: Record<string, { count: number; total_volume: number; exchanges: string[] }>;
}

export interface LiquidityTokenItem {
  token: string;
  buy_power: number;
  buy_power_fmt: string;
  sell_supply: number;
  sell_supply_fmt: string;
  net_liquidity: number;
  net_liquidity_fmt: string;
  buy_pct: number;
  state: string;
  interpretation: string;
}

export interface LiquidityEngine {
  tokens: LiquidityTokenItem[];
  aggregate: {
    total_buy_power: number;
    total_buy_power_fmt: string;
    total_sell_supply: number;
    total_sell_supply_fmt: string;
    net: number;
    net_fmt: string;
    state: string;
  };
}

export interface CexContextData {
  market_bias: string;
  confidence: string;
  narrative_lines: string[];
  drivers: string[];
  offsetting_factors: string[];
  indicators: Indicators | null;
  dominant_venue: HeroDominantVenue | null;
  dominant_asset: HeroDominantAsset | null;
  exchange_pressure: ExchangePressure | null;
  stablecoin_power: StablecoinPower | null;
  market_liquidity: MarketLiquidity | null;
  exchange_inventory: ExchangeInventoryItem[];
  flow_classification: FlowClassification | null;
  liquidity_shock: LiquidityShock | null;
  behavior_map: BehaviorMap | null;
  liquidity_engine: LiquidityEngine | null;
  top_exchanges: ExchangeFlow[];
  largest_transfers: LargestTransfer[];
  exchange_rotation: ExchangeRotation[];
  rotation_fallback: RotationFallback[];
  pump_setups: PumpSetup[];
  loading: boolean;
  error: string | null;
}

type WindowKey = '24h' | '7d' | '30d';

export function useCexIntelligence(chainId: number, window: WindowKey): CexContextData & { refresh: () => void } {
  const [data, setData] = useState<CexContextData>({
    market_bias: 'neutral',
    confidence: 'low',
    narrative_lines: [],
    drivers: [],
    offsetting_factors: [],
    indicators: null,
    dominant_venue: null,
    dominant_asset: null,
    exchange_pressure: null,
    stablecoin_power: null,
    market_liquidity: null,
    exchange_inventory: [],
    flow_classification: null,
    liquidity_shock: null,
    behavior_map: null,
    liquidity_engine: null,
    top_exchanges: [],
    largest_transfers: [],
    exchange_rotation: [],
    rotation_fallback: [],
    pump_setups: [],
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 45000);
      const res = await fetch(
        `${API}/api/onchain/cex/context?chainId=${chainId}&window=${window}`,
        { signal: controller.signal }
      );
      clearTimeout(timeout);
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || 'Failed to load');
      setData({
        market_bias: json.market_bias || 'neutral',
        confidence: json.confidence || 'low',
        narrative_lines: json.narrative_lines || [],
        drivers: json.drivers || [],
        offsetting_factors: json.offsetting_factors || [],
        indicators: json.indicators || null,
        dominant_venue: json.dominant_venue || null,
        dominant_asset: json.dominant_asset || null,
        exchange_pressure: json.exchange_pressure || null,
        stablecoin_power: json.stablecoin_power || null,
        market_liquidity: json.market_liquidity || null,
        exchange_inventory: json.exchange_inventory || [],
        flow_classification: json.flow_classification || null,
        liquidity_shock: json.liquidity_shock || null,
        behavior_map: json.behavior_map || null,
        liquidity_engine: json.liquidity_engine || null,
        top_exchanges: json.top_exchanges || [],
        largest_transfers: json.largest_transfers || [],
        exchange_rotation: json.exchange_rotation || [],
        rotation_fallback: json.rotation_fallback || [],
        pump_setups: json.pump_setups || [],
        loading: false,
        error: null,
      });
    } catch (e: any) {
      setData(prev => ({ ...prev, loading: false, error: e?.message || 'Failed' }));
    }
  }, [chainId, window]);

  useEffect(() => { load(); }, [load]);
  return { ...data, refresh: load };
}
