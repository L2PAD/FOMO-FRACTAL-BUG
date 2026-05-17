/**
 * Radar V11 API Client + Data Mapping
 * =====================================
 * Single source of truth for Alt Radar V2 UI.
 * Maps backend DTOs to unified RadarRow type.
 * Supports server-side pagination, filtering, sorting.
 */

const API = process.env.REACT_APP_BACKEND_URL;

// ─── Unified UI Types ───────────────────────────────────────

export const MODES = { SPOT: 'spot', ALPHA: 'alpha', FUTURES: 'futures' };

function feat(key, value, label, hint) {
  return { key, value, label, hint };
}

function mapSpotRow(api) {
  return {
    symbol: api.symbol,
    mode: 'spot',
    venue: api.venue,
    direction: api.direction,
    verdict: api.verdict,
    conviction: api.conviction ?? 0,
    convictionTier: api.convictionTier ?? null,
    horizons: api.horizons ?? null,
    integrity: api.integrity ?? null,
    whyNow: api.explain?.whyNow ?? api.reasons?.[0] ?? '',
    riskLevel: api.risk,
    breakoutProb: api.breakoutProb ?? 0,
    structure: api.structure,
    momentumBuild: api.momentumBuild,
    features: api.features ? [
      feat('compression', api.features.compression, 'Compression', 'Price range tightening before potential move'),
      feat('volumeBuild', api.features.volumeBuild, 'Volume Build', 'Volume increasing without breakout'),
      feat('trendAlignment', api.features.trendAlignment, 'Trend Alignment', 'Multi-timeframe structure agreement'),
      feat('liquidity', api.features.liquidity, 'Liquidity', 'Orderbook depth and tradability'),
      feat('risk', api.features.risk, 'Risk', 'Volatility and structural instability'),
    ] : [],
    explain: {
      whyNow: api.explain?.whyNow ?? '',
      invalidation: api.explain?.invalidation ?? '',
      timeHorizon: api.explain?.timeHorizon ?? '24h',
      oneLiner: api.explain?.oneLiner ?? '',
    },
    reasons: api.reasons ?? [],
    dataQuality: api.dataQuality ?? null,
    venueCount: api.venueCount ?? 1,
    venues: api.venues ?? ['binance'],
    divergenceScore: api.divergenceScore ?? 0,
    divergenceLabel: api.divergenceLabel ?? 'NONE',
    divergenceReasons: api.divergenceReasons ?? [],
  };
}

function mapFuturesRow(api) {
  return {
    symbol: api.symbol,
    mode: 'futures',
    direction: api.direction ?? (api.bias === 'long_build' ? 'long' : api.bias === 'short_build' ? 'short' : 'neutral'),
    verdict: api.verdict,
    conviction: api.conviction ?? 0,
    convictionTier: api.convictionTier ?? null,
    horizons: api.horizons ?? null,
    whyNow: api.explain?.whyNow ?? api.reasons?.[0] ?? '',
    riskLevel: api.risk,
    breakoutProb: api.breakoutProb ?? 0,
    squeezeRisk: api.squeezeRisk,
    squeezeRiskScore: api.squeezeRiskScore ?? 0,
    bias: api.bias,
    oiShift: api.oiShift,
    fundingState: api.fundingState,
    features: api.features ? [
      feat('oiShift', api.features.oiShift, 'Open Interest Shift', 'Expansion or contraction of positions'),
      feat('fundingSkew', api.features.fundingSkew, 'Funding Skew', 'Long/short funding imbalance (-1 to 1)'),
      feat('liquidationDensity', api.features.liquidationDensity, 'Liquidation Density', 'Clustered liquidation levels nearby'),
      feat('volatilityRegime', api.features.volatilityRegime, 'Volatility Regime', 'Market expansion or compression state'),
      feat('risk', api.features.risk, 'Risk', 'Crowded positioning or unstable structure'),
    ] : [],
    explain: {
      whyNow: api.explain?.whyNow ?? '',
      invalidation: api.explain?.invalidation ?? '',
      timeHorizon: api.explain?.timeHorizon ?? '24h',
      oneLiner: api.explain?.oneLiner ?? '',
    },
    reasons: api.reasons ?? [],
    dataQuality: api.dataQuality ?? null,
  };
}

// ─── API Fetchers ───────────────────────────────────────────

export async function fetchUniverse() {
  const [spotRes, futRes] = await Promise.all([
    fetch(`${API}/api/v11/exchange/radar/universe?mode=spot`),
    fetch(`${API}/api/v11/exchange/radar/universe?mode=futures`),
  ]);
  const spot = await spotRes.json();
  const fut = await futRes.json();
  return {
    spotMainCount: spot.spotMainCount ?? 0,
    spotAlphaCount: spot.spotAlphaCount ?? 0,
    futuresCount: fut.futuresCount ?? 0,
    spotMainSymbols: spot.spotMainSymbols ?? [],
    spotAlphaSymbols: spot.spotAlphaSymbols ?? [],
    futuresSymbols: fut.futuresSymbols ?? [],
  };
}

/**
 * Fetch radar data with server-side pagination, filtering, sorting.
 * @param {Object} params
 * @param {string} params.mode - 'spot' | 'alpha' | 'futures'
 * @param {number} params.page - 1-based page number
 * @param {number} params.limit - items per page
 * @param {string} [params.search] - search query
 * @param {string} [params.verdict] - 'buy'|'sell'|'watch'|'neutral'|'all'
 * @param {number} [params.minConv] - minimum conviction threshold
 * @param {string} [params.sort] - 'conviction'|'risk'|'symbol'
 * @returns {{ rows: Array, meta: Object, updatedAt: string }}
 */
export async function fetchRadarData({ mode, page = 1, limit = 20, search, verdict, minConv, sort = 'conviction' }) {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('limit', String(limit));
  if (sort) params.set('sort', sort);
  if (search) params.set('search', search);
  if (verdict && verdict !== 'all') params.set('verdict', verdict);
  if (minConv && minConv > 0) params.set('minConv', String(minConv));

  let url;
  if (mode === 'futures') {
    url = `${API}/api/v11/exchange/radar/futures?${params}`;
  } else {
    const venue = mode === 'alpha' ? 'alpha' : 'main';
    params.set('venue', venue);
    url = `${API}/api/v11/exchange/radar/spot?${params}`;
  }

  const res = await fetch(url);
  const data = await res.json();

  const mapper = mode === 'futures' ? mapFuturesRow : mapSpotRow;
  return {
    rows: (data.rows ?? []).map(mapper),
    meta: data.meta ?? { total: 0, page: 1, pages: 1, limit },
    updatedAt: data.updatedAt ?? '',
  };
}

/**
 * Fetch alpha universe metadata (source, count, scores).
 */
export async function fetchAlphaUniverse() {
  const res = await fetch(`${API}/api/v11/exchange/radar/alpha/universe`);
  return res.json();
}

