/**
 * Radar Control Bar V4 — Multi-Horizon UI
 * - Mode toggle: Spot | Alpha | Futures
 * - Horizon selector: Auto | Short | Mid | Swing
 * - Filters: Verdict, Conviction, Sort
 * - Search
 */
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { ChevronDown, Search } from 'lucide-react';

const VERDICT_OPTIONS = [
  { value: 'all', label: 'All verdicts' },
  { value: 'buy', label: 'Buy' },
  { value: 'sell', label: 'Sell' },
  { value: 'watch', label: 'Watch' },
  { value: 'neutral', label: 'Neutral' },
  { value: 'data_gap', label: 'Data Gap' },
];

const CONV_OPTIONS = [
  { value: 0, label: 'All conv' },
  { value: 40, label: '\u2265 40' },
  { value: 50, label: '\u2265 50' },
  { value: 60, label: '\u2265 60' },
  { value: 70, label: '\u2265 70' },
];

const HORIZON_OPTIONS = [
  { id: 'auto', label: 'Auto' },
  { id: 'short', label: 'Short' },
  { id: 'mid', label: 'Mid' },
  { id: 'swing', label: 'Swing' },
];

/* Reusable custom dropdown */
function FilterDropdown({ value, options, onChange, testId }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const current = options.find(o => o.value === value) || options[0];

  return (
    <div ref={ref} className="relative" data-testid={testId}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-2.5 text-[13px] font-medium rounded-md cursor-pointer select-none transition-colors"
        style={{
          height: '30px',
          background: 'rgba(15,23,42,0.04)',
          border: '1px solid rgba(15,23,42,0.08)',
          color: '#334155',
        }}
        onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(15,23,42,0.16)'; }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.borderColor = 'rgba(15,23,42,0.08)'; }}
      >
        {current.label}
        <ChevronDown
          className="w-3 h-3 transition-transform"
          style={{ color: '#94a3b8', transform: open ? 'rotate(180deg)' : 'rotate(0)' }}
        />
      </button>

      {open && (
        <div
          className="absolute top-full left-0 mt-1 py-1 rounded-lg shadow-lg z-50"
          style={{
            background: '#fff',
            border: '1px solid rgba(15,23,42,0.1)',
            minWidth: '120px',
          }}
        >
          {options.map(opt => {
            const active = opt.value === value;
            return (
              <button
                key={opt.value}
                data-testid={`${testId}-option-${opt.value}`}
                onClick={() => { onChange(opt.value); setOpen(false); }}
                className="w-full text-left px-3 py-1.5 text-[13px] transition-colors"
                style={{
                  color: active ? '#0f172a' : '#64748b',
                  fontWeight: active ? 600 : 400,
                  background: active ? 'rgba(15,23,42,0.04)' : 'transparent',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = 'rgba(15,23,42,0.04)'; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = active ? 'rgba(15,23,42,0.04)' : 'transparent'; }}
              >
                {opt.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/** Crypto icon from CoinCap */
function CryptoIcon({ symbol, size = 18 }) {
  const base = (symbol || '').replace(/USDT$|USD$/i, '').toLowerCase();
  return (
    <img
      src={`https://assets.coincap.io/assets/icons/${base}@2x.png`}
      alt={base}
      width={size}
      height={size}
      className="rounded-full"
      style={{ minWidth: size }}
      onError={e => { e.target.style.display = 'none'; }}
    />
  );
}

/** Common crypto project names for search */
const CRYPTO_NAMES = {
  BTC:'Bitcoin',ETH:'Ethereum',SOL:'Solana',BNB:'BNB',ADA:'Cardano',AVAX:'Avalanche',
  DOT:'Polkadot',LINK:'Chainlink',UNI:'Uniswap',AAVE:'Aave',MATIC:'Polygon',ARB:'Arbitrum',
  OP:'Optimism',DOGE:'Dogecoin',SHIB:'Shiba Inu',XRP:'Ripple',NEAR:'NEAR Protocol',
  SUI:'Sui',APT:'Aptos',FIL:'Filecoin',ATOM:'Cosmos',FET:'Fetch.ai',RNDR:'Render',
  INJ:'Injective',SEI:'Sei',TIA:'Celestia',JUP:'Jupiter',PENDLE:'Pendle',MKR:'Maker',
  LDO:'Lido',CRV:'Curve',DYDX:'dYdX',GMX:'GMX',SNX:'Synthetix',COMP:'Compound',
  TAO:'Bittensor',WLD:'Worldcoin',PEPE:'Pepe',FLOKI:'Floki',BONK:'Bonk',WIF:'dogwifhat',
  STX:'Stacks',IMX:'Immutable',MANTA:'Manta',SAND:'Sandbox',AXS:'Axie Infinity',
  GALA:'Gala',ENS:'ENS',GRT:'The Graph',ALGO:'Algorand',VET:'VeChain',FTM:'Fantom',
  RUNE:'THORChain',CAKE:'PancakeSwap',SUSHI:'SushiSwap',ONE:'Harmony',ZIL:'Zilliqa',
  EGLD:'MultiversX',FLOW:'Flow',MINA:'Mina',KAVA:'Kava',ROSE:'Oasis',CFX:'Conflux',
  BCH:'Bitcoin Cash',LTC:'Litecoin',ETC:'Ethereum Classic',XLM:'Stellar',TRX:'TRON',
  TON:'Toncoin',KAS:'Kaspa',ICP:'Internet Computer',HBAR:'Hedera',QNT:'Quant',
};

/** Search with autocomplete dropdown */
function SearchWithDropdown({ search, setSearch, universe, mode }) {
  const [focused, setFocused] = useState(false);
  const ref = useRef(null);

  const allSymbols = useMemo(() => {
    if (!universe) return [];
    if (mode === 'futures') return universe.futuresSymbols || [];
    if (mode === 'alpha') return universe.spotAlphaSymbols || [];
    return universe.spotMainSymbols || [];
  }, [universe, mode]);

  const query = (search || '').toLowerCase();
  const suggestions = useMemo(() => {
    if (!query || query.length < 1) return [];
    return allSymbols
      .filter(s => {
        const base = s.replace(/USDT$|USD$/i, '').toLowerCase();
        const name = (CRYPTO_NAMES[base.toUpperCase()] || '').toLowerCase();
        return base.includes(query) || name.includes(query);
      })
      .slice(0, 8);
  }, [allSymbols, query]);

  const showDropdown = focused && query.length >= 1 && suggestions.length > 0;

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setFocused(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const getBase = (sym) => sym.replace(/USDT$|USD$/i, '');

  return (
    <div ref={ref} className="relative flex-shrink-0" style={{ width: '160px' }} data-testid="radar-search-wrap">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: '#94a3b8' }} />
        <input
          data-testid="radar-search"
          type="text"
          placeholder="Search token..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onFocus={() => setFocused(true)}
          className="text-[13px] rounded-md"
          style={{
            height: '30px',
            width: '100%',
            padding: '0 12px 0 30px',
            background: 'rgba(15,23,42,0.04)',
            border: `1px solid ${focused ? 'rgba(15,23,42,0.2)' : 'rgba(15,23,42,0.08)'}`,
            color: '#0f172a',
            outline: 'none',
          }}
        />
      </div>
      {showDropdown && (
        <div
          className="absolute right-0 top-full mt-1 py-1 rounded-lg shadow-lg z-50 overflow-hidden"
          style={{ background: '#fff', border: '1px solid rgba(15,23,42,0.1)', minWidth: '200px' }}
          data-testid="radar-search-dropdown"
        >
          {suggestions.map(sym => {
            const base = getBase(sym);
            const name = CRYPTO_NAMES[base] || '';
            return (
              <button
                key={sym}
                data-testid={`radar-search-item-${sym}`}
                onMouseDown={(e) => { e.preventDefault(); setSearch(base); setFocused(false); }}
                className="w-full flex items-center gap-2.5 px-3 py-1.5 text-left transition-colors"
                style={{ color: '#0f172a' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.04)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
              >
                <span className="text-[13px] font-semibold">{base}</span>
                {name && <span className="text-[11px] ml-auto" style={{ color: '#94a3b8' }}>{name}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const SORT_OPTIONS = [
  { value: 'conviction', label: 'By conviction' },
  { value: 'risk', label: 'By risk' },
  { value: 'symbol', label: 'By symbol' },
];

export default function RadarControlBar({
  mode, setMode, view, horizon, setHorizon,
  search, setSearch,
  verdictFilter, setVerdictFilter,
  minConviction, setMinConviction,
  sort, setSort,
  universe, loading,
  updatedAt, onRefresh,
  alphaMeta, currentMode,
}) {
  const modes = [
    { id: 'spot', label: 'Spot' },
    { id: 'alpha', label: 'Alpha' },
    { id: 'futures', label: 'Futures' },
    { id: 'signals', label: 'Signals' },
  ];

  const isSignals = view === 'signals';

  return (
    <div
      data-testid="radar-control-bar"
      className="flex items-center gap-3 px-4"
      style={{ height: '48px', borderBottom: '1px solid rgba(15,23,42,0.08)' }}
    >
      {/* Mode toggle */}
      <div
        className="flex items-center rounded-md"
        style={{ background: 'rgba(15,23,42,0.04)', padding: '2px' }}
        data-testid="radar-mode-toggle"
      >
        {modes.map(t => {
          const active = (view || mode) === t.id;
          return (
            <button
              key={t.id}
              data-testid={`radar-mode-${t.id}`}
              onClick={() => setMode(t.id)}
              className="px-3 text-[13px] font-medium rounded-[5px] transition-all duration-150"
              style={{
                height: '26px',
                color: active ? '#0f172a' : '#94a3b8',
                background: active ? '#fff' : 'transparent',
                boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                fontWeight: active ? 600 : 500,
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Radar filters — hidden when Signals view is active */}
      {!isSignals && (
        <>
          {/* Divider */}
          <div style={{ width: '1px', height: '20px', background: 'rgba(15,23,42,0.08)' }} />

          {/* Horizon selector */}
          {setHorizon && (
            <div
              className="flex items-center rounded-md"
              style={{ background: 'rgba(15,23,42,0.04)', padding: '2px' }}
              data-testid="radar-horizon-toggle"
            >
              {HORIZON_OPTIONS.map(h => {
                const active = horizon === h.id;
                return (
                  <button
                    key={h.id}
                    data-testid={`radar-horizon-${h.id}`}
                    onClick={() => setHorizon(h.id)}
                    className="px-2.5 text-[12px] font-medium rounded-[5px] transition-all duration-150"
                    style={{
                      height: '24px',
                      color: active ? '#0f172a' : '#94a3b8',
                      background: active ? '#fff' : 'transparent',
                      boxShadow: active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none',
                      fontWeight: active ? 600 : 500,
                    }}
                  >
                    {h.label}
                  </button>
                );
              })}
            </div>
          )}

          {/* Divider */}
          <div style={{ width: '1px', height: '20px', background: 'rgba(15,23,42,0.08)' }} />

          {/* Verdict filter */}
          <FilterDropdown
            value={verdictFilter}
            options={VERDICT_OPTIONS}
            onChange={setVerdictFilter}
            testId="radar-verdict-filter"
          />

          {/* Conviction filter */}
          <FilterDropdown
            value={minConviction}
            options={CONV_OPTIONS}
            onChange={setMinConviction}
            testId="radar-conv-filter"
          />

          {/* Sort */}
          {setSort && (
            <FilterDropdown
              value={sort || 'conviction'}
              options={SORT_OPTIONS}
              onChange={setSort}
              testId="radar-sort-filter"
            />
          )}

          {/* Spacer */}
          <div className="flex-1" />

          {/* Search */}
          <SearchWithDropdown search={search} setSearch={setSearch} universe={universe} mode={mode} />

          {/* Universe counter + time + refresh */}
          <div className="flex items-center gap-2 tabular-nums flex-shrink-0" style={{ color: '#94a3b8' }} data-testid="radar-universe-counts">
            {universe && (
              <span className="text-[10px]">
                {universe.spotMainCount}/{universe.spotAlphaCount ?? 0}/{universe.futuresCount ?? 0}
              </span>
            )}
            {currentMode === 'alpha' && alphaMeta && (
              <span
                className="text-[11px]"
                style={{ color: alphaMeta.source === 'dynamic' ? '#15803d' : '#b45309' }}
                data-testid="alpha-source-badge"
              >
                {alphaMeta.source === 'dynamic' ? 'Dynamic' : 'Static'} {'\u00b7'} avg {alphaMeta.avgScore}
              </span>
            )}
            {updatedAt && (
              <span className="text-[10px]" style={{ color: '#94a3b8' }}>
                {new Date(updatedAt).toLocaleTimeString()}
              </span>
            )}
            {onRefresh && (
              <button
                data-testid="radar-refresh"
                onClick={onRefresh}
                disabled={loading}
                className="p-1 rounded-md transition-colors disabled:opacity-50"
                style={{ color: '#94a3b8' }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.04)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
              >
                <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
                </svg>
              </button>
            )}
            {loading && <span className="w-1.5 h-1.5 rounded-full animate-pulse ml-0.5" style={{ background: '#64748b' }} />}
          </div>
        </>
      )}
    </div>
  );
}
