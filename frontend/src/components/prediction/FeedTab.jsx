/**
 * FeedTab — Live Polymarket Crypto Terminal with Intelligence Overlay.
 *
 * Phase 2: Action-First UX. Each card shows ONE decisive action prominently.
 * Event-based card grid. Three tiers: HOT / ACTIONABLE / ALL
 */
import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Flame, Zap, List, Clock, TrendingUp,
  ChevronDown, ChevronUp, ExternalLink, Target, AlertTriangle,
  ShieldCheck, BarChart3,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const TIERS = [
  { id: 'hot', label: 'Hot', icon: Flame },
  { id: 'actionable', label: 'Actionable', icon: Zap },
  { id: 'all', label: 'All', icon: List },
];

const ASSETS = ['BTC', 'ETH', 'SOL', 'XRP', 'ALT'];
const CATEGORIES = ['price', 'fdv', 'launch', 'direction', 'etf', 'macro'];

export default function FeedTab() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tier, setTier] = useState('hot');
  const [assetFilter, setAssetFilter] = useState(null);
  const [catFilter, setCatFilter] = useState(null);
  const [counts, setCounts] = useState({ hot: 0, actionable: 0, all: 0 });
  const [freshness, setFreshness] = useState(null);
  const [liveHealth, setLiveHealth] = useState(null);
  const [cmSignalMap, setCmSignalMap] = useState({});

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ mode: tier });
      if (assetFilter) params.set('asset', assetFilter);
      if (catFilter) params.set('category', catFilter);
      const res = await fetch(`${API}/api/feed?${params}`);
      const d = await res.json();
      if (d.ok) {
        setEvents(d.events || []);
        setCounts({ hot: d.hot_count || 0, actionable: d.actionable_count || 0, all: d.all_count || 0 });
        setFreshness(d.freshness);
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [tier, assetFilter, catFilter]);

  useEffect(() => { fetchFeed(); }, [fetchFeed]);

  // Fetch cross-market signals for badges
  useEffect(() => {
    fetch(`${API}/api/cross-market/signals`)
      .then(r => r.ok ? r.json() : { signals: [] })
      .then(d => {
        const map = {};
        (d.signals || []).forEach(s => {
          const entity = (s.entity || '').toUpperCase();
          if (!map[entity]) map[entity] = [];
          map[entity].push(s);
        });
        setCmSignalMap(map);
      })
      .catch(() => {});
  }, []);

  // Live polling: refresh every 8s for HOT, 20s for others
  useEffect(() => {
    const interval = tier === 'hot' ? 8000 : 20000;
    const timer = setInterval(() => {
      // Silent refresh (no loading spinner)
      const params = new URLSearchParams({ mode: tier });
      if (assetFilter) params.set('asset', assetFilter);
      if (catFilter) params.set('category', catFilter);
      fetch(`${API}/api/feed?${params}`)
        .then(r => r.json())
        .then(d => {
          if (d.ok) {
            setEvents(d.events || []);
            setCounts({ hot: d.hot_count || 0, actionable: d.actionable_count || 0, all: d.all_count || 0 });
          }
        })
        .catch(() => {});
    }, interval);
    return () => clearInterval(timer);
  }, [tier, assetFilter, catFilter]);

  // Live health poll every 10s
  useEffect(() => {
    const fetchHealth = () => {
      fetch(`${API}/api/live/health`).then(r => r.json()).then(setLiveHealth).catch(() => {});
    };
    fetchHealth();
    const timer = setInterval(fetchHealth, 10000);
    return () => clearInterval(timer);
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    await fetch(`${API}/api/feed/sync`, { method: 'POST' });
    await fetchFeed();
  };

  return (
    <div className="p-6 space-y-5" data-testid="feed-tab">
      {/* Toolbar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-4">
          {/* Tier selector */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1" data-testid="feed-tiers">
            {TIERS.map((t) => {
              const Icon = t.icon;
              const count = counts[t.id] || 0;
              const active = tier === t.id;
              return (
                <button
                  key={t.id}
                  onClick={() => setTier(t.id)}
                  data-testid={`tier-${t.id}`}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
                    active
                      ? 'bg-white text-gray-900 shadow-sm'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {t.label}
                  <span className={`text-xs ${active ? 'text-gray-500' : 'text-gray-400'}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Asset chips */}
          <div className="flex items-center gap-1" data-testid="asset-filters">
            {ASSETS.map((a) => (
              <button
                key={a}
                onClick={() => setAssetFilter(assetFilter === a ? null : a)}
                data-testid={`asset-${a}`}
                className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                  assetFilter === a
                    ? 'bg-gray-900 text-white'
                    : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                }`}
              >
                {a}
              </button>
            ))}
          </div>

          {/* Category chips */}
          <div className="flex items-center gap-1" data-testid="category-filters">
            {CATEGORIES.map((c) => (
              <button
                key={c}
                onClick={() => setCatFilter(catFilter === c ? null : c)}
                data-testid={`cat-${c}`}
                className={`px-2.5 py-1 text-xs font-medium rounded-md capitalize transition-all ${
                  catFilter === c
                    ? 'bg-gray-900 text-white'
                    : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                }`}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Live status indicator */}
          {liveHealth && liveHealth.hot_live > 0 && (
            <div className="flex items-center gap-1.5 text-[11px]" data-testid="live-indicator">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span className="text-emerald-600 font-semibold">LIVE</span>
              <span className="text-gray-400">{liveHealth.total_tracked}</span>
            </div>
          )}
          {freshness && (
            <span className={`text-xs ${freshness.stale ? 'text-red-500' : 'text-gray-400'}`}
                  data-testid="feed-freshness">
              {freshness.stale ? 'STALE' : freshness.label} ({freshness.age_seconds}s)
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={loading}
            data-testid="feed-refresh"
            className="p-2 rounded-lg hover:bg-gray-100 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Card Grid */}
      {loading && !events.length ? (
        <div className="text-center py-16 text-gray-400 text-sm">Loading crypto feed...</div>
      ) : events.length === 0 ? (
        <div className="text-center py-16 text-gray-400 text-sm">No events match filters</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4" data-testid="feed-grid">
          {events.map((ev) => (
            <EventCard key={ev.event_id} event={ev} cmSignals={getCmSignalsForEvent(ev, cmSignalMap)} />
          ))}
        </div>
      )}
    </div>
  );
}


/* ============ CROSS-MARKET HELPERS ============ */

function getCmSignalsForEvent(event, cmSignalMap) {
  const asset = (event.asset_group || '').toUpperCase();
  const title = (event.title || '').toUpperCase();
  const signals = cmSignalMap[asset] || [];
  // Also check if any entity from cmSignalMap matches the event title
  if (signals.length === 0) {
    for (const [entity, sigs] of Object.entries(cmSignalMap)) {
      if (title.includes(entity) || entity.includes(asset)) {
        return sigs;
      }
    }
  }
  return signals;
}


/* ============ EVENT CARD ============ */

function EventCard({ event, cmSignals = [] }) {
  const [expanded, setExpanded] = useState(false);
  const ov = event.overlay || {};
  const bp = ov.best_pick;
  const markets = event.markets || [];
  const isBinary = !event.is_multi && markets.length === 1;
  const isActionable = ov.action === 'BUY_YES' || ov.action === 'BUY_NO';
  const hoursLeft = getHoursLeft(event.end_date);
  const endingSoon = hoursLeft !== null && hoursLeft > 0 && hoursLeft < 48;

  return (
    <div
      className={`bg-white rounded-xl border transition-all shadow-sm overflow-hidden ${
        isActionable
          ? 'border-emerald-200/80 hover:border-emerald-300'
          : 'border-gray-200/80 hover:border-gray-300'
      }`}
      data-testid={`event-${event.event_id}`}
    >
      {/* Action Banner — the most important element */}
      <ActionBanner action={ov.action} urgency={ov.urgency} confidence={ov.confidence}
                    edgePct={bp?.edge_pct} endingSoon={endingSoon} hoursLeft={hoursLeft}
                    sizing={ov.sizing} edgeQuality={ov.edge_quality} ov={ov} />

      {/* Card Header */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded ${tierBadge(event.tier)}`}>
            {event.tier}
          </span>
          {/* LIVE / STALE indicator */}
          {event.live?.state === 'LIVE' && (
            <span className="flex items-center gap-1 text-[10px] text-emerald-600 font-medium" data-testid="card-live-badge">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              LIVE
            </span>
          )}
          {event.live?.state === 'STALE' && (
            <span className="flex items-center gap-1 text-[10px] text-amber-500 font-medium" data-testid="card-stale-badge">
              <AlertTriangle className="w-3 h-3" />
              STALE
            </span>
          )}
          <span className="text-[10px] font-medium text-gray-400 uppercase tracking-wider">
            {event.asset_group}
          </span>
          <span className="text-[10px] text-gray-300">
            {event.event_type}
          </span>
          {ov.outcomes_with_edge > 2 && (
            <span className="text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded"
                  data-testid="opportunity-density">
              {ov.outcomes_with_edge} mispriced
            </span>
          )}
          {cmSignals.length > 0 && (
            <CrossMarketBadge signals={cmSignals} />
          )}
        </div>
        <div className="flex items-start gap-2.5">
          {event.image && (
            <img
              src={event.image}
              alt=""
              className="w-9 h-9 rounded-lg object-cover bg-gray-100 flex-shrink-0 mt-0.5"
              data-testid="event-image"
              loading="lazy"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
          )}
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold text-gray-900 leading-snug">
              {event.title}
            </h3>

            {/* Market info row */}
            <div className="flex items-center gap-3 text-[11px] text-gray-400 mt-1">
              {event.volume_24h > 0 && (
                <span className="flex items-center gap-1">
                  <TrendingUp className="w-3 h-3" />
                  ${fmtK(event.volume_24h)}
                </span>
              )}
              {event.end_date && (
                <span className={`flex items-center gap-1 ${endingSoon ? 'text-amber-600 font-medium' : ''}`}>
                  <Clock className="w-3 h-3" />
                  {endingSoon ? `${Math.round(hoursLeft)}h left` : timeLeft(event.end_date)}
                </span>
              )}
              <span>{event.markets_count} outcome{event.markets_count > 1 ? 's' : ''}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Outcomes */}
      <div className="px-4 pb-3">
        {isBinary ? (
          <BinaryOutcome market={markets[0]} />
        ) : (
          <MultiOutcome markets={markets} maxShow={4} />
        )}
      </div>

      {/* Intelligence Strip — summary + sizing + why */}
      {bp && (
        <div className={`mx-4 mb-3 p-2.5 rounded-lg border ${
          isActionable ? 'bg-emerald-50/50 border-emerald-100' : 'bg-gray-50 border-gray-100'
        }`} data-testid="fomo-overlay">
          {ov.summary && (
            <p className={`text-xs font-medium mb-1.5 ${isActionable ? 'text-gray-800' : 'text-gray-600'}`}>
              {ov.summary}
            </p>
          )}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {bp.edge_pct !== 0 && (
                <span className={`text-xs font-semibold ${bp.edge > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  Edge: {bp.edge > 0 ? '+' : ''}{bp.edge_pct}%
                </span>
              )}
              <span className={`text-[10px] font-medium ${confColor(ov.confidence)}`}>
                {ov.confidence} conf
              </span>
              {ov.edge_quality && (
                <span className={`text-[10px] font-medium ${eqColor(ov.edge_quality)}`}
                      data-testid="edge-quality-badge">
                  {ov.edge_quality} quality
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {ov.sizing?.size_label && ov.sizing.size_label !== 'NONE' && (
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${sizeBadge(ov.sizing.size_label)}`}
                      data-testid="size-badge">
                  {ov.sizing.size_label}
                </span>
              )}
              {bp.execution && (
                <span className={`text-[10px] font-medium ${execColor(bp.execution.style)}`}>
                  {execLabel(bp.execution.style)}
                </span>
              )}
            </div>
          </div>
          {/* Why reasons (first 2) */}
          {ov.why?.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {ov.why.slice(0, 2).map((reason, i) => (
                <p key={i} className={`text-[10px] leading-snug ${
                  reason.startsWith('Risk:') ? 'text-amber-600' : 'text-gray-500'
                }`}>{reason}</p>
              ))}
            </div>
          )}
          {/* Analytics Badge — historical reliability */}
          <AnalyticsBadge analytics={ov.analytics} stability={ov.stability} />
        </div>
      )}

      {/* No Trade message for WATCH/AVOID */}
      {!bp && (ov.action === 'WATCH' || ov.action === 'AVOID') && (
        <div className="mx-4 mb-3 p-2 rounded-lg bg-gray-50 border border-gray-100" data-testid="no-trade">
          <p className="text-xs text-gray-500">
            {ov.action === 'AVOID' ? 'No clear edge — avoid' : 'Market appears fairly priced'}
          </p>
        </div>
      )}

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full py-2 text-xs text-gray-400 hover:text-gray-600 hover:bg-gray-50 flex items-center justify-center gap-1 transition-all border-t border-gray-100"
        data-testid={`expand-${event.event_id}`}
      >
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        {expanded ? 'Less' : 'Detail'}
      </button>

      {/* Detail Drawer */}
      {expanded && <EventDetail event={event} />}
    </div>
  );
}


/* ============ ACTION BANNER ============ */

function ActionBanner({ action, urgency, confidence, edgePct, endingSoon, hoursLeft, sizing, edgeQuality, ov }) {
  const isAction = action === 'BUY_YES' || action === 'BUY_NO';
  const isAvoid = action === 'AVOID';

  if (!isAction && !endingSoon && !isAvoid) return null;

  return (
    <div className={`px-4 py-2 flex items-center justify-between ${actionBannerBg(action)}`}
         data-testid="action-banner">
      <div className="flex items-center gap-2">
        {isAction && (
          <>
            <span className={`text-sm font-bold tracking-tight ${actionBannerText(action)}`}>
              {actionLabel(action)}
              {urgency === 'now' ? ' NOW' : urgency === 'soon' ? ' SOON' : ''}
            </span>
            {edgePct != null && edgePct !== 0 && (
              <span className={`text-xs font-semibold ${actionBannerText(action)} opacity-80`}>
                {edgePct > 0 ? '+' : ''}{edgePct}%
              </span>
            )}
            {sizing?.size_label && sizing.size_label !== 'NONE' && (
              <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${sizeBadge(sizing.size_label)}`}>
                {sizing.size_label}
              </span>
            )}
          </>
        )}
        {isAvoid && (
          <span className="text-xs font-medium text-gray-500">No clear edge</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {endingSoon && (
          <span className="text-[10px] font-bold text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded"
                data-testid="ending-soon-badge">
            {Math.round(hoursLeft)}h LEFT
          </span>
        )}
        {isAction && confidence && (
          <span className={`text-[10px] font-medium ${actionBannerText(action)} opacity-70`}>
            {ov?.analytics?.effective_confidence
              ? `conf ${(ov.analytics.effective_confidence * 1).toFixed(2)}`
              : confidence
            }
          </span>
        )}
        {ov?.stability?.state === 'LOCKED' && (
          <span className="text-[10px] font-bold text-orange-600 bg-orange-50 px-1.5 py-0.5 rounded" data-testid="stability-locked">
            LOCKED
          </span>
        )}
        {ov?.stability?.state === 'UNSTABLE' && (
          <span className="text-[10px] text-gray-400" data-testid="stability-unstable">
            unstable
          </span>
        )}
      </div>
    </div>
  );
}


/* ============ BINARY OUTCOME ============ */

function BinaryOutcome({ market }) {
  if (!market) return null;
  const ov = market.overlay;
  const yes = Math.round(market.yes_price * 100);
  const no = Math.round(market.no_price * 100);
  const fair = ov?.fair_prob ? Math.round(ov.fair_prob * 100) : null;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-emerald-700">YES {yes}%</span>
            <span className="text-xs font-semibold text-red-600">NO {no}%</span>
          </div>
          <div className="h-2 bg-red-100 rounded-full overflow-hidden">
            <div className="h-full bg-emerald-500 rounded-full transition-all"
                 style={{ width: `${yes}%` }} />
          </div>
        </div>
      </div>
      {fair && fair !== yes && (
        <div className="flex items-center justify-between text-[11px]">
          <span className="text-gray-400">Fair: <span className="font-medium text-gray-600">{fair}%</span></span>
          {ov?.edge_pct && (
            <span className={ov.edge > 0 ? 'text-emerald-600 font-medium' : 'text-red-500 font-medium'}>
              {ov.edge > 0 ? '+' : ''}{ov.edge_pct}% edge
            </span>
          )}
        </div>
      )}
    </div>
  );
}


/* ============ MULTI OUTCOME ============ */

function MultiOutcome({ markets, maxShow = 4 }) {
  const sorted = [...markets]
    .filter((m) => m.yes_price > 0)
    .sort((a, b) => b.yes_price - a.yes_price);
  const show = sorted.slice(0, maxShow);
  const rest = sorted.length - maxShow;

  return (
    <div className="space-y-1">
      {show.map((m) => {
        const pct = Math.round(m.yes_price * 100);
        const ov = m.overlay;
        const fair = ov?.fair_prob ? Math.round(ov.fair_prob * 100) : null;
        const label = m.group_title || m.question?.replace(/^will\s+/i, '').slice(0, 35) || m.market_id;
        const hasStructEdge = Math.abs(ov?.structure_edge || 0) > 0.03;

        return (
          <div key={m.market_id} className="flex items-center gap-2 text-xs">
            <span className="w-24 truncate text-gray-700 font-medium" title={label}>{label}</span>
            <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
            </div>
            <span className="w-8 text-right text-gray-600 font-medium">{pct}%</span>
            {fair && fair !== pct && (
              <span className={`w-14 text-right text-[10px] font-medium ${
                ov.edge > 0 ? 'text-emerald-600' : ov.edge < -0.02 ? 'text-red-500' : 'text-gray-400'
              }`}>
                {ov.edge > 0 ? '+' : ''}{ov.edge_pct}%
              </span>
            )}
            {hasStructEdge && (
              <BarChart3 className="w-3 h-3 text-amber-500 flex-shrink-0" title="Structure edge detected" />
            )}
          </div>
        );
      })}
      {rest > 0 && (
        <div className="text-[10px] text-gray-400 mt-1">+{rest} more outcomes</div>
      )}
    </div>
  );
}


/* ============ EVENT DETAIL DRAWER ============ */

function EventDetail({ event }) {
  const ov = event.overlay || {};
  const bp = ov.best_pick;
  const markets = event.markets || [];
  const sz = ov.sizing;

  return (
    <div className="px-4 pb-4 space-y-4 border-t border-gray-100 bg-gray-50/50" data-testid="event-detail">
      {/* 1. Decision */}
      <DetailBlock title="Decision">
        <div className="flex items-center gap-4 flex-wrap">
          <Stat label="Action" value={actionLabel(ov.action)} color={actionColor(ov.action)} />
          <Stat label="Urgency" value={ov.urgency || 'watch'} color={urgencyColor(ov.urgency)} />
          <Stat label="Confidence" value={ov.confidence || 'low'} color={confColor(ov.confidence)} />
          <Stat label="Edge Quality" value={ov.edge_quality || 'low'} color={eqColor(ov.edge_quality)} />
          <Stat label="Outcomes" value={`${ov.outcomes_with_edge || 0} / ${ov.outcomes_analyzed || 0}`} />
          {ov.competition && (
            <Stat label="Competition" value={competitionLabel(ov.competition)} />
          )}
        </div>
      </DetailBlock>

      {/* 2. Position Sizing */}
      {sz && sz.size_label !== 'NONE' && (
        <DetailBlock title="Position Sizing">
          <div className="flex items-center gap-4 flex-wrap mb-2">
            <div className="flex items-center gap-2">
              <span className={`text-sm font-bold px-2 py-0.5 rounded ${sizeBadge(sz.size_label)}`}
                    data-testid="detail-size-label">
                {sz.size_label}
              </span>
              <span className="text-xs text-gray-500">{sz.size_pct}% of risk budget</span>
            </div>
            <Stat label="Edge Quality" value={sz.edge_quality || 'low'} color={eqColor(sz.edge_quality)} />
            <Stat label="Conviction" value={sz.conviction || 'low'} color={confColor(sz.conviction)} />
          </div>
          {sz.caps && Object.keys(sz.caps).length > 0 && (
            <div className="flex items-center gap-3 flex-wrap mb-1.5">
              {Object.entries(sz.caps).map(([k, v]) => (
                <span key={k} className={`text-[10px] ${v < 1 ? 'text-amber-600' : 'text-gray-400'}`}>
                  {k.replace('_', ' ')}: {Math.round(v * 100)}%
                </span>
              ))}
            </div>
          )}
          {sz.reasons?.length > 0 && (
            <div className="space-y-0.5">
              {sz.reasons.map((r, i) => (
                <p key={i} className="text-[10px] text-gray-500">{r}</p>
              ))}
            </div>
          )}
        </DetailBlock>
      )}

      {/* 3. Best Outcomes */}
      {ov.top_outcomes?.length > 0 && (
        <DetailBlock title="Best Outcomes">
          <div className="space-y-2">
            {ov.top_outcomes.map((o, i) => {
              const m = markets.find((x) => x.market_id === o.market_id);
              const label = m?.group_title || m?.question?.slice(0, 40) || o.market_id;
              return (
                <div key={o.market_id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="w-4 text-gray-300 font-mono text-[10px]">#{i + 1}</span>
                    <span className="text-gray-700 font-medium">{label}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400">Mkt {Math.round((o.market_prob || 0) * 100)}%</span>
                    <span className="text-gray-400">Fair {Math.round((o.fair_prob || 0) * 100)}%</span>
                    <span className={`font-medium ${o.edge > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                      {o.edge > 0 ? '+' : ''}{o.edge_pct}%
                    </span>
                    <span className={`text-[10px] ${actionColor(o.action)}`}>{o.action}</span>
                    {o.structure_edge != null && Math.abs(o.structure_edge) > 0.02 && (
                      <BarChart3 className="w-3 h-3 text-amber-500" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </DetailBlock>
      )}

      {/* 4. Why (drivers + risks) */}
      {ov.why?.length > 0 && (
        <DetailBlock title="Why">
          <ul className="space-y-1">
            {ov.why.map((d, i) => {
              const isRisk = d.startsWith('Risk:');
              return (
                <li key={i} className={`text-xs flex items-start gap-1.5 ${isRisk ? 'text-amber-600' : 'text-gray-600'}`}>
                  {isRisk
                    ? <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                    : <Target className="w-3 h-3 text-gray-400 mt-0.5 flex-shrink-0" />
                  }
                  {d}
                </li>
              );
            })}
          </ul>
        </DetailBlock>
      )}

      {/* 4b. Confidence & Analytics */}
      {ov.analytics && (
        <DetailBlock title="Confidence">
          <div className="flex items-center gap-4 flex-wrap mb-2">
            <Stat label="Raw" value={ov.confidence || 'low'} color={confColor(ov.confidence)} />
            {ov.analytics.adjusted_confidence != null && (
              <Stat label="Calibrated" value={ov.analytics.adjusted_confidence.toFixed(2)} />
            )}
            {ov.analytics.effective_confidence != null && (
              <Stat label="Effective" value={ov.analytics.effective_confidence.toFixed(2)}
                    color={ov.analytics.effective_confidence >= 0.6 ? 'text-emerald-600' : ov.analytics.effective_confidence >= 0.5 ? 'text-amber-600' : 'text-red-500'} />
            )}
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            {ov.analytics.family_strength && ov.analytics.family_strength !== 'UNKNOWN' && (
              <Stat label="Family" value={ov.analytics.family_strength}
                    color={ov.analytics.family_strength === 'STRONG' ? 'text-emerald-600' : ov.analytics.family_strength === 'MEDIUM' ? 'text-gray-600' : 'text-red-500'} />
            )}
            {ov.analytics.calibration_state && ov.analytics.calibration_state !== 'UNKNOWN' && (
              <Stat label="Calibration" value={ov.analytics.calibration_state === 'GOOD' ? 'Calibrated' : ov.analytics.calibration_state === 'OVER' ? 'Overconfident' : 'Underconfident'}
                    color={ov.analytics.calibration_state === 'GOOD' ? 'text-emerald-600' : ov.analytics.calibration_state === 'OVER' ? 'text-red-500' : 'text-blue-500'} />
            )}
            {ov.analytics.sample_size > 0 && (
              <Stat label="Samples" value={ov.analytics.sample_size} />
            )}
            {ov.analytics.family_accuracy != null && (
              <Stat label="Family Accuracy" value={`${Math.round(ov.analytics.family_accuracy * 100)}%`}
                    color={ov.analytics.family_accuracy >= 0.6 ? 'text-emerald-600' : ov.analytics.family_accuracy >= 0.5 ? 'text-gray-600' : 'text-red-500'} />
            )}
          </div>
          {ov.gating?.gating_reasons?.length > 0 && (
            <div className="mt-2 space-y-0.5">
              {ov.gating.gating_reasons.map((r, i) => (
                <p key={i} className="text-[10px] text-amber-600 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />{r}
                </p>
              ))}
            </div>
          )}
          {ov.stability && ov.stability.state !== 'STABLE' && (
            <div className="mt-1.5">
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
                ov.stability.state === 'LOCKED' ? 'bg-orange-50 text-orange-700' : 'bg-gray-100 text-gray-500'
              }`}>
                {ov.stability.state === 'LOCKED' ? 'Decision Locked — avoiding noisy flips' : 'Decision Unstable — waiting for confirmation'}
              </span>
            </div>
          )}
        </DetailBlock>
      )}

      {/* 5. Structure Analysis */}
      {ov.structure && (
        <DetailBlock title="Structure">
          <div className="flex items-center gap-4">
            <Stat label="Ladder Quality"
                  value={`${Math.round((ov.structure.ladder_quality || 0) * 100)}%`}
                  color={ov.structure.ladder_quality > 0.8 ? 'text-emerald-600' : ov.structure.ladder_quality > 0.5 ? 'text-amber-600' : 'text-red-500'} />
            <Stat label="Monotonic" value={ov.structure.monotonic ? 'Yes' : 'No'}
                  color={ov.structure.monotonic ? 'text-emerald-600' : 'text-red-500'} />
            {ov.structure.dominant_issue && (
              <div className="flex items-center gap-1 text-xs text-amber-600">
                <AlertTriangle className="w-3 h-3" />
                {ov.structure.dominant_issue}
              </div>
            )}
          </div>
        </DetailBlock>
      )}

      {/* 6. Execution */}
      {bp?.execution && (
        <DetailBlock title="Execution">
          <div className="flex items-center gap-4">
            <Stat label="Style" value={execLabel(bp.execution.style)} color={execColor(bp.execution.style)} />
            <Stat label="Spread" value={`${bp.execution.spread_pct}%`}
                  color={bp.execution.spread_pct > 5 ? 'text-red-500' : bp.execution.spread_pct > 2 ? 'text-amber-500' : 'text-emerald-600'} />
            <Stat label="Slippage" value={bp.execution.slippage_risk} color={slipColor(bp.execution.slippage_risk)} />
          </div>
        </DetailBlock>
      )}

      {/* 7. All outcomes table (for multi) */}
      {markets.length > 1 && (
        <DetailBlock title={`All Outcomes (${markets.length})`}>
          <div className="max-h-48 overflow-y-auto space-y-0.5">
            {markets
              .filter((m) => m.yes_price > 0)
              .sort((a, b) => b.yes_price - a.yes_price)
              .map((m) => {
                const ov2 = m.overlay;
                const label = m.group_title || m.question?.slice(0, 35) || m.market_id;
                return (
                  <div key={m.market_id} className="flex items-center justify-between text-[11px] py-0.5">
                    <span className="text-gray-600 truncate w-32">{label}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-gray-500">{Math.round(m.yes_price * 100)}%</span>
                      {ov2 && (
                        <>
                          <span className="text-gray-400">Fair {Math.round(ov2.fair_prob * 100)}%</span>
                          <span className={`font-medium ${ov2.edge > 0 ? 'text-emerald-600' : ov2.edge < -0.02 ? 'text-red-500' : 'text-gray-400'}`}>
                            {ov2.edge > 0 ? '+' : ''}{ov2.edge_pct}%
                          </span>
                        </>
                      )}
                      <span className="text-gray-300">bid {(m.best_bid * 100).toFixed(1)}%</span>
                      <span className="text-gray-300">ask {(m.best_ask * 100).toFixed(1)}%</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </DetailBlock>
      )}

      {/* Polymarket link */}
      {event.slug && (
        <a
          href={`https://polymarket.com/event/${event.slug}`}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          data-testid="polymarket-link"
        >
          <ExternalLink className="w-3 h-3" />
          View on Polymarket
        </a>
      )}
    </div>
  );
}


/* ============ UI PRIMITIVES ============ */

function DetailBlock({ title, children }) {
  return (
    <div>
      <h4 className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">{title}</h4>
      {children}
    </div>
  );
}

function Stat({ label, value, color = 'text-gray-700' }) {
  return (
    <div className="text-xs">
      <span className="text-gray-400">{label}: </span>
      <span className={`font-medium ${color}`}>{value}</span>
    </div>
  );
}


/* ============ CROSS-MARKET BADGE ============ */

function CrossMarketBadge({ signals }) {
  const high = signals.filter(s => s.severity === 'HIGH');
  const hasMismatch = signals.some(s =>
    s.type === 'STRUCTURE_MISMATCH' || s.type === 'MONOTONIC_BREAK' || s.type === 'EQUIVALENT_DIVERGENCE'
  );
  const hasLadder = signals.some(s => s.type === 'LADDER_VIOLATION' || s.type === 'LADDER_GAP');

  if (hasMismatch) {
    return (
      <span
        className="text-[10px] font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded flex items-center gap-0.5"
        data-testid="cm-badge-mismatch"
        title={`${signals.length} cross-market signal(s)`}
      >
        <AlertTriangle className="w-3 h-3" />
        {high.length > 0 ? 'Ladder mismatch' : 'Structure issue'}
      </span>
    );
  }

  if (hasLadder) {
    return (
      <span
        className="text-[10px] font-medium text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded flex items-center gap-0.5"
        data-testid="cm-badge-ladder"
        title={`${signals.length} cross-market signal(s)`}
      >
        <BarChart3 className="w-3 h-3" />
        Ladder gap
      </span>
    );
  }

  return null;
}


/* ============ HELPERS ============ */

function getHoursLeft(dateStr) {
  if (!dateStr) return null;
  try {
    const end = new Date(dateStr);
    const now = new Date();
    return (end - now) / 3600000;
  } catch { return null; }
}

function fmtK(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(0) + 'K';
  return n.toFixed(0);
}

function timeLeft(dateStr) {
  try {
    const end = new Date(dateStr);
    const now = new Date();
    const h = Math.round((end - now) / 3600000);
    if (h < 0) return 'Ended';
    if (h < 24) return `${h}h left`;
    const d = Math.round(h / 24);
    if (d < 30) return `${d}d left`;
    return `${Math.round(d / 30)}mo left`;
  } catch { return ''; }
}

function tierBadge(t) {
  if (t === 'hot') return 'bg-orange-50 text-orange-600';
  if (t === 'actionable') return 'bg-emerald-50 text-emerald-600';
  return 'bg-gray-50 text-gray-500';
}

function actionLabel(a) {
  const m = { BUY_YES: 'BUY YES', BUY_NO: 'BUY NO', WATCH: 'WATCH', AVOID: 'AVOID' };
  return m[a] || a || 'WATCH';
}
function actionColor(a) {
  if (a === 'BUY_YES') return 'text-emerald-600';
  if (a === 'BUY_NO') return 'text-red-600';
  if (a === 'AVOID') return 'text-red-400';
  return 'text-gray-500';
}

function actionBannerBg(a) {
  if (a === 'BUY_YES') return 'bg-emerald-50';
  if (a === 'BUY_NO') return 'bg-red-50';
  return 'bg-gray-50';
}
function actionBannerText(a) {
  if (a === 'BUY_YES') return 'text-emerald-700';
  if (a === 'BUY_NO') return 'text-red-700';
  return 'text-gray-600';
}

function confColor(c) {
  if (c === 'high') return 'text-emerald-600';
  if (c === 'medium') return 'text-blue-600';
  return 'text-gray-400';
}

function urgencyColor(u) {
  if (u === 'now') return 'text-red-600';
  if (u === 'soon') return 'text-amber-600';
  return 'text-gray-500';
}

function execLabel(s) {
  const m = { MARKET_OK: 'Market OK', LIMIT_PREFERRED: 'Use Limit', LIMIT_ONLY: 'Limit Only' };
  return m[s] || s || '';
}
function execColor(s) {
  if (s === 'MARKET_OK') return 'text-emerald-600';
  if (s === 'LIMIT_PREFERRED') return 'text-blue-600';
  return 'text-amber-600';
}

function slipColor(s) {
  if (s === 'low') return 'text-emerald-600';
  if (s === 'medium') return 'text-amber-600';
  return 'text-red-500';
}

function sizeBadge(s) {
  const m = {
    TINY: 'bg-gray-100 text-gray-600',
    SMALL: 'bg-blue-50 text-blue-700',
    MEDIUM: 'bg-emerald-50 text-emerald-700',
    LARGE: 'bg-amber-50 text-amber-700',
    MAX: 'bg-red-50 text-red-700',
  };
  return m[s] || 'bg-gray-100 text-gray-500';
}

function eqColor(eq) {
  if (eq === 'high') return 'text-emerald-600';
  if (eq === 'medium') return 'text-blue-500';
  return 'text-gray-400';
}

function competitionLabel(c) {
  if (c === 'clear_dominant') return 'Clear dominant';
  if (c === 'no_edge') return 'No edge';
  if (c?.includes('_competing')) return c.replace('_competing', ' competing');
  return c || '';
}


/* ============ ANALYTICS BADGE ============ */

function AnalyticsBadge({ analytics, stability }) {
  if (!analytics) return null;

  const acc = analytics.family_accuracy;
  const strength = analytics.family_strength;
  const calState = analytics.calibration_state;
  const sampleSize = analytics.sample_size || 0;

  return (
    <div className="flex items-center gap-2 mt-1.5 flex-wrap" data-testid="analytics-badge">
      {/* Family accuracy badge */}
      {sampleSize >= 10 && acc != null ? (
        <span
          className={`text-[10px] font-medium flex items-center gap-1 ${
            strength === 'STRONG' ? 'text-emerald-600' :
            strength === 'MEDIUM' ? 'text-gray-500' :
            strength === 'WEAK' ? 'text-red-500' : 'text-gray-400'
          }`}
          title={`Based on ${sampleSize} past predictions`}
        >
          {strength === 'STRONG' && <ShieldCheck className="w-3 h-3" />}
          {strength === 'WEAK' && <AlertTriangle className="w-3 h-3" />}
          {Math.round(acc * 100)}% accuracy
          {strength === 'STRONG' && ' — reliable'}
          {strength === 'WEAK' && ' — weak'}
        </span>
      ) : sampleSize > 0 && sampleSize < 10 ? (
        <span className="text-[10px] text-gray-400">
          Low data ({sampleSize} samples)
        </span>
      ) : null}

      {/* Calibration badge */}
      {calState && calState !== 'UNKNOWN' && (
        <span className={`text-[10px] font-medium ${
          calState === 'GOOD' ? 'text-emerald-500' :
          calState === 'OVER' ? 'text-red-400' : 'text-blue-400'
        }`}>
          {calState === 'GOOD' ? 'calibrated' :
           calState === 'OVER' ? 'overconfident' : 'underconfident'}
        </span>
      )}

      {/* Stability */}
      {stability && stability.state === 'LOCKED' && (
        <span className="text-[10px] font-medium text-orange-600">locked</span>
      )}
    </div>
  );
}
