/**
 * News Intelligence Tab v2 — Product-grade UI
 * =============================================
 * Breaking strip (top 3 fallback) → Compact cluster cards → Quick scan UX.
 * "User should understand the market in 5 seconds."
 * 
 * Rules:
 *  - 1 card = 1 cluster (never raw events)
 *  - HIGH/BREAKING = always visible
 *  - LOW = collapsed by default
 *  - Strong visual badges, compact layout
 */

import React, { useState, useEffect, useCallback, memo, useMemo, useRef } from 'react';
import {
  X, RefreshCw, Globe, Zap, Activity, BarChart2,
  Newspaper, ExternalLink, Clock, Loader2, AlertTriangle,
  ChevronDown, ChevronUp, TrendingUp, TrendingDown, Minus, Flame, Eye, Bell,
  Link2, Sparkles, Info, RotateCcw, AlertCircle, CheckCircle,
  Gauge, FileText, ArrowLeft
} from 'lucide-react';
import { toast } from 'sonner';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ── Colors ──────────────────────────────────────────────────────
const cl = {
  bg: '#ffffff', surface: '#f8fafc', border: '#e2e8f0',
  text: '#0f172a', textSec: '#475569', textMuted: '#94a3b8',
  accent: '#6366f1', accentSoft: '#eef2ff',
  high: '#dc2626', highSoft: '#fef2f2',
  med: '#d97706', medSoft: '#fffbeb',
  low: '#6b7280', lowSoft: '#f9fafb',
  bullish: '#16a34a', bullishSoft: '#dcfce7',
  bearish: '#dc2626', bearishSoft: '#fee2e2',
  breaking: '#ef4444',
};

// ── Event type config ───────────────────────────────────────────
const TYPE_CFG = {
  regulation: { bg: '#fef3c7', color: '#92400e', label: 'Regulation' },
  etf:        { bg: '#d1fae5', color: '#065f46', label: 'ETF' },
  hack:       { bg: '#fee2e2', color: '#991b1b', label: 'Hack' },
  funding:    { bg: '#d1fae5', color: '#065f46', label: 'Funding' },
  listing:    { bg: '#dbeafe', color: '#1e40af', label: 'Listing' },
  macro:      { bg: '#e0e7ff', color: '#3730a3', label: 'Macro' },
  price:      { bg: '#f3f4f6', color: '#374151', label: 'Price' },
  partnership:{ bg: '#fce7f3', color: '#9d174d', label: 'Partnership' },
  whale:      { bg: '#ede9fe', color: '#5b21b6', label: 'Whale' },
  market:     { bg: '#f3f4f6', color: '#374151', label: 'Market' },
  launch:     { bg: '#ede9fe', color: '#5b21b6', label: 'Launch' },
  adoption:   { bg: '#d1fae5', color: '#065f46', label: 'Adoption' },
};

const SENTIMENT_FILTERS = ['all', 'positive', 'neutral', 'negative'];
const EVENT_FILTERS = ['all', 'regulation', 'etf', 'macro', 'funding', 'listing', 'hack', 'price', 'whale'];

// ── Helpers ─────────────────────────────────────────────────────
function timeAgo(d) {
  if (!d) return '';
  const ms = Date.now() - new Date(d).getTime();
  if (ms < 60000) return 'just now';
  if (ms < 3600000) return `${Math.floor(ms / 60000)}m`;
  if (ms < 86400000) return `${Math.floor(ms / 3600000)}h`;
  return `${Math.floor(ms / 86400000)}d`;
}

function sentimentIcon(hint) {
  if (hint === 'bullish') return { Icon: TrendingUp, color: '#16a34a', label: 'Bullish' };
  if (hint === 'bearish') return { Icon: TrendingDown, color: '#dc2626', label: 'Bearish' };
  return { Icon: Minus, color: '#6366f1', label: 'Neutral' };
}

function mapSentiment(hint) {
  if (hint === 'bullish') return 'positive';
  if (hint === 'bearish') return 'negative';
  return 'neutral';
}

function bandColor(band) {
  if (band === 'high') return { bg: cl.highSoft, color: cl.high, border: '#fecaca' };
  if (band === 'medium') return { bg: cl.medSoft, color: cl.med, border: '#fde68a' };
  return { bg: cl.lowSoft, color: cl.low, border: cl.border };
}

// ── Sentiment Analysis Modal ────────────────────────────────────
const AnalysisModal = memo(function AnalysisModal({ data, extraction, onClose }) {
  if (!data) return null;

  const { label, score, confidence, meta } = data;
  const pct = Math.round(score * 100);
  const confPct = Math.round((confidence || meta?.confidenceScore || 0.5) * 100);

  const labelCfg = {
    POSITIVE: { color: cl.bullish, bg: '#dcfce7', text: 'Positive' },
    NEGATIVE: { color: cl.breaking, bg: '#fee2e2', text: 'Negative' },
    NEUTRAL: { color: cl.med, bg: '#fef3c7', text: 'Neutral' },
  };
  const lc = labelCfg[label] || labelCfg.NEUTRAL;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        data-testid="analysis-modal"
        className="relative bg-white rounded-2xl max-w-lg w-full max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-5">
          <div className="flex items-center gap-2">
            <Sparkles size={20} style={{ color: '#14b8a6' }} />
            <h3 className="text-base font-bold" style={{ color: cl.text }}>Sentiment Analysis</h3>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors">
            <X size={18} style={{ color: cl.muted }} />
          </button>
        </div>

        {/* Extraction preview */}
        {extraction && (
          <div className="mx-5 mt-4 p-3 rounded-xl" style={{ backgroundColor: '#f8fafc' }}>
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                <Globe size={16} style={{ color: cl.muted }} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs" style={{ color: cl.muted }}>
                  <span className="px-1.5 py-0.5 rounded bg-gray-200">{extraction.domain}</span>
                  <span>{extraction.textLen?.toLocaleString()} chars</span>
                </div>
                {extraction.title && (
                  <p className="text-sm font-medium mt-1 line-clamp-2" style={{ color: cl.text }}>{extraction.title}</p>
                )}
                {extraction.preview && (
                  <p className="text-xs mt-1 line-clamp-2" style={{ color: cl.muted }}>{extraction.preview}</p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Result */}
        <div className="p-5">
          {/* Label + Score */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm px-3 py-1 rounded-lg font-bold" style={{ backgroundColor: lc.bg, color: lc.color }}>
              {lc.text}
            </span>
            <span className="text-sm" style={{ color: cl.muted }}>Confidence: {confPct}%</span>
          </div>

          {/* Sentiment bar */}
          <div className="mb-4">
            <div className="w-full h-3 rounded-full overflow-hidden relative"
              style={{ background: 'linear-gradient(to right, #ef4444, #f59e0b, #22c55e)' }}>
              <div className="absolute top-0 h-full w-1.5 bg-white rounded"
                style={{ left: `calc(${pct}% - 3px)` }} />
            </div>
            <div className="flex justify-between text-[10px] mt-1" style={{ color: cl.muted }}>
              <span>Bearish</span>
              <span>Neutral</span>
              <span>Bullish</span>
            </div>
          </div>

          {/* Mock warning */}
          {meta?.mock && (
            <div className="mb-3 px-3 py-2 rounded-lg text-xs flex items-center gap-2"
              style={{ backgroundColor: '#fffbeb', color: '#d97706' }}>
              <AlertCircle size={14} /> Dev Mode (Mock) — sentiment runtime offline
            </div>
          )}

          {/* Signals */}
          {meta?.reasons?.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] uppercase tracking-wider mb-1.5 font-medium" style={{ color: cl.muted }}>Signals</p>
              <div className="space-y-1">
                {meta.reasons.slice(0, 4).map((r, i) => (
                  <div key={i} className="text-xs flex items-start gap-1.5" style={{ color: cl.text }}>
                    <span className="mt-0.5" style={{ color: cl.bullish }}>•</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rules applied */}
          {meta?.rulesApplied?.length > 0 && (
            <div className="mb-3">
              <p className="text-[10px] uppercase tracking-wider mb-1.5 font-medium" style={{ color: cl.muted }}>Rules Applied</p>
              <div className="flex flex-wrap gap-1">
                {meta.rulesApplied.map((r, i) => (
                  <span key={i} className="text-[10px] px-1.5 py-0.5 rounded" style={{ backgroundColor: '#f1f5f9', color: cl.muted }}>{r}</span>
                ))}
              </div>
            </div>
          )}

          {/* Meta */}
          <div className="pt-3 flex items-center justify-between text-[10px]" style={{ color: cl.muted }}>
            <span>Model: {meta?.modelVersion || 'unknown'} · {meta?.latencyMs || 0}ms</span>
            {meta?.rulesBoost !== undefined && meta.rulesBoost !== 0 && (
              <span style={{ color: meta.rulesBoost > 0 ? cl.bullish : cl.breaking }}>
                Adjusted {meta.rulesBoost > 0 ? '+' : ''}{Math.round(meta.rulesBoost * 100)}%
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

// ── URL Analyzer Bar ────────────────────────────────────────────
const UrlAnalyzer = memo(function UrlAnalyzer() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [result, setResult] = useState(null);

  const analyzeUrl = async () => {
    if (!url.trim()) return;
    try {
      const parsed = new URL(url);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        setError('Invalid URL');
        return;
      }
    } catch { setError('Invalid URL format'); return; }

    setLoading(true);
    setError(null);
    setExtraction(null);
    setResult(null);

    try {
      const res = await fetch(`${API_URL}/api/news/analyze-url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      const data = await res.json();
      if (!data.ok) { setError(data.message || 'Analysis failed'); return; }
      setExtraction(data.data.extracted);
      setResult(data.data.result);
    } catch (err) {
      setError(err.message || 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !loading) analyzeUrl(); };
  const closeModal = () => { setResult(null); setExtraction(null); };

  return (
    <>
      <div data-testid="url-analyzer" className="mb-5 p-4" style={{ backgroundColor: cl.surface }}>
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Link2 size={16} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: cl.textMuted }} />
            <input
              type="url"
              placeholder="Analyze any news URL..."
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={handleKeyDown}
              data-testid="url-input"
              className="w-full h-10 pl-9 pr-3 text-sm rounded-xl bg-white outline-none"
              style={{ color: cl.text }}
            />
          </div>
          <button
            onClick={analyzeUrl}
            disabled={loading || !url.trim()}
            data-testid="analyze-button"
            className="h-10 px-4 rounded-xl text-sm font-medium text-white flex items-center gap-1.5 transition-colors disabled:opacity-50"
            style={{ backgroundColor: '#14b8a6' }}
          >
            {loading ? <Loader2 size={16} className="animate-spin" /> : <><Sparkles size={14} /> Analyze</>}
          </button>
        </div>
        {error && (
          <div className="mt-2 text-xs flex items-center gap-1.5" style={{ color: cl.breaking }}>
            <AlertCircle size={12} /> {error}
            <button onClick={analyzeUrl} className="ml-1 underline">Retry</button>
          </div>
        )}
      </div>

      {/* Analysis Result Modal */}
      {result && <AnalysisModal data={result} extraction={extraction} onClose={closeModal} />}
    </>
  );
});

// ── Market Brief Widget (collapsible) ───────────────────────────
const VELOCITY_CFG = {
  CALM: { color: '#64748b', bg: '#f1f5f9', label: 'Quiet' },
  NORMAL: { color: '#16a34a', bg: '#f0fdf4', label: 'Normal' },
  ELEVATED: { color: '#d97706', bg: '#fffbeb', label: 'Elevated' },
  SPIKE: { color: '#dc2626', bg: '#fef2f2', label: 'Spike' },
};

const MarketBrief = memo(function MarketBrief() {
  const [open, setOpen] = useState(false);
  const [digest, setDigest] = useState(null);
  const [velocity, setVelocity] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fetched = useRef(false);

  const fetchBrief = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dRes, vRes] = await Promise.all([
        fetch(`${API_URL}/api/news/digest`),
        fetch(`${API_URL}/api/news/velocity`),
      ]);
      if (!dRes.ok) throw new Error(`Digest: HTTP ${dRes.status}`);
      if (!vRes.ok) throw new Error(`Velocity: HTTP ${vRes.status}`);
      const [dData, vData] = await Promise.all([dRes.json(), vRes.json()]);
      if (dData.ok) setDigest(dData.data);
      if (vData.ok) setVelocity(vData.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Lazy load on first open
  useEffect(() => {
    if (open && !fetched.current) {
      fetched.current = true;
      fetchBrief();
    }
  }, [open, fetchBrief]);

  const vc = velocity ? (VELOCITY_CFG[velocity.level] || VELOCITY_CFG.CALM) : null;

  return (
    <div data-testid="market-brief-widget" className="mb-5 rounded-2xl overflow-hidden" style={{ backgroundColor: '#0f172a' }}>
      {/* Toggle header */}
      <button
        data-testid="market-brief-toggle"
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-5 py-4 transition-colors hover:opacity-80"
      >
        <div className="flex items-center gap-3">
          <BarChart2 size={18} style={{ color: '#a78bfa' }} />
          <span className="text-sm font-bold" style={{ color: '#f1f5f9' }}>Market Brief</span>
          {digest && (
            <span className="text-xs font-medium" style={{ color: '#94a3b8' }}>
              {digest.totalEvents} events · {digest.breakingCount} breaking
            </span>
          )}
          {velocity && vc && !open && (
            <span className="text-xs font-bold ml-2" style={{ color: vc.color }}>
              {velocity.message}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {loading && <Loader2 size={14} className="animate-spin" style={{ color: '#94a3b8' }} />}
          {open ? <ChevronUp size={16} style={{ color: '#94a3b8' }} /> : <ChevronDown size={16} style={{ color: '#94a3b8' }} />}
        </div>
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="px-5 pb-5 pt-0 space-y-4">
          {error && (
            <div className="p-3 rounded-lg text-red-400 text-sm flex items-center gap-2" style={{ backgroundColor: '#1e1b2e' }}>
              <AlertTriangle size={14} /> {error}
              <button onClick={fetchBrief} className="ml-auto text-xs underline">Retry</button>
            </div>
          )}

          {loading && !digest && (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="animate-spin" style={{ color: '#a78bfa' }} />
            </div>
          )}

          {digest && (
            <>
              {/* Velocity */}
              {velocity && vc && (
                <div data-testid="brief-velocity" className="py-2">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <div className="flex items-center gap-2">
                      <Gauge size={16} style={{ color: vc.color }} />
                      <span className="text-sm font-bold" style={{ color: vc.color }}>{velocity.message}</span>
                    </div>
                    {velocity.trend24hPct !== undefined && velocity.trend24hPct !== 0 && (
                      <span className="text-xs font-medium" style={{ color: vc.color }}>
                        {velocity.trend24hPct > 0 ? 'Growing' : 'Declining'} {velocity.trend24hPct > 0 ? '+' : ''}{velocity.trend24hPct}% vs yesterday
                      </span>
                    )}
                  </div>
                </div>
              )}

              {/* Sentiment bar */}
              <div data-testid="brief-sentiment" className="py-2">
                <div className="flex items-center gap-2 mb-2">
                  <Activity size={14} style={{ color: '#60a5fa' }} />
                  <span className="text-xs font-bold" style={{ color: '#e2e8f0' }}>Sentiment</span>
                  {digest.sentimentShiftPct !== 0 && (
                    <span className="text-[10px] font-medium ml-auto"
                      style={{
                        color: digest.sentimentShiftPct > 0 ? '#4ade80' : '#f87171',
                      }}>
                      {digest.sentimentShiftPct > 0 ? '+' : ''}{digest.sentimentShiftPct}% vs yesterday
                    </span>
                  )}
                </div>
                <div className="flex h-2.5 rounded-full overflow-hidden mb-1.5" style={{ backgroundColor: '#1e293b' }}>
                  {parseInt(digest.sentiment?.bullish) > 0 && <div style={{ width: `${digest.sentiment.bullish}`, backgroundColor: '#4ade80' }} />}
                  {parseInt(digest.sentiment?.neutral) > 0 && <div style={{ width: `${digest.sentiment.neutral}`, backgroundColor: '#818cf8' }} />}
                  {parseInt(digest.sentiment?.bearish) > 0 && <div style={{ width: `${digest.sentiment.bearish}`, backgroundColor: '#f87171' }} />}
                </div>
                <div className="flex justify-between text-[10px]">
                  <span style={{ color: '#4ade80' }} className="font-semibold">Bullish {digest.sentiment?.bullish}</span>
                  <span style={{ color: '#818cf8' }} className="font-semibold">Neutral {digest.sentiment?.neutral}</span>
                  <span style={{ color: '#f87171' }} className="font-semibold">Bearish {digest.sentiment?.bearish}</span>
                </div>
              </div>

              {/* Top 5 Events */}
              {digest.top5?.length > 0 && (
                <div data-testid="brief-top-events">
                  <div className="flex items-center gap-2 mb-2">
                    <Flame size={14} style={{ color: '#f87171' }} />
                    <span className="text-xs font-bold" style={{ color: '#e2e8f0' }}>Top Events</span>
                  </div>
                  <div className="space-y-1.5">
                    {digest.top5.map((ev, i) => {
                      const ic = ev.importanceBand === 'high' ? '#f87171'
                        : ev.importanceBand === 'medium' ? '#fbbf24' : '#94a3b8';
                      return (
                        <div key={i} data-testid={`brief-event-${i + 1}`} className="flex items-start gap-2.5 py-2">
                          <span className="flex-shrink-0 text-[10px] font-bold" style={{ color: ic }}>{i + 1}.</span>
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold leading-snug line-clamp-2" style={{ color: '#e2e8f0' }}>{ev.title}</p>
                            <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                              {ev.eventType && (
                                <span className="text-[9px] font-medium uppercase" style={{ color: '#a78bfa' }}>{ev.eventType}</span>
                              )}
                              <span className="text-[9px] font-bold uppercase" style={{ color: ic }}>Score {ev.importance}</span>
                              {ev.isBreaking && (
                                <span className="text-[9px] font-bold" style={{ color: '#f87171' }}>BREAKING</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Why It Matters */}
              {digest.whyItMatters?.length > 0 && (
                <div data-testid="brief-why-it-matters" className="py-2">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap size={14} style={{ color: '#a78bfa' }} />
                    <span className="text-xs font-bold" style={{ color: '#a78bfa' }}>Why it matters</span>
                  </div>
                  <ul className="space-y-1">
                    {digest.whyItMatters.map((line, i) => (
                      <li key={i} className="text-xs flex items-start gap-1.5" style={{ color: '#cbd5e1' }}>
                        <span className="mt-1 w-1 h-1 rounded-full flex-shrink-0" style={{ backgroundColor: '#a78bfa' }} />
                        {line}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Refresh + timestamp */}
              <div className="flex items-center justify-between pt-2">
                <p className="text-[10px]" style={{ color: '#64748b' }}>
                  Generated {new Date(digest.generatedAt).toLocaleString()}
                </p>
                <button onClick={fetchBrief} data-testid="brief-refresh-btn" className="text-[10px] px-2 py-1 rounded-md transition-colors flex items-center gap-1" style={{ backgroundColor: '#1e293b', color: '#94a3b8' }}>
                  <RefreshCw size={10} /> Refresh
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
});


// ── Breaking Strip ──────────────────────────────────────────────
const BreakingStrip = memo(function BreakingStrip({ clusters, onSelect }) {
  // Breaking events first; fallback: top 3 by importanceScore
  const items = useMemo(() => {
    const breaking = clusters.filter(c => c.isBreaking);
    if (breaking.length > 0) return breaking.slice(0, 5);
    // Fallback v2: top 3 by importance score (any band)
    return [...clusters]
      .sort((a, b) => (b.importance || 0) - (a.importance || 0))
      .slice(0, 3);
  }, [clusters]);

  if (items.length === 0) return null;

  const hasBreaking = items.some(c => c.isBreaking);

  return (
    <div data-testid="breaking-strip" className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        {hasBreaking ? (
          <>
            <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: cl.breaking }} />
            <span className="text-sm font-bold uppercase tracking-wider" style={{ color: cl.breaking }}>
              Breaking
            </span>
          </>
        ) : (
          <>
            <Flame size={16} style={{ color: cl.high }} />
            <span className="text-sm font-bold uppercase tracking-wider" style={{ color: cl.high }}>
              Top Signal
            </span>
          </>
        )}
      </div>

      <div className="flex gap-3 overflow-x-auto pb-2">
        {items.map(c => {
          const si = sentimentIcon(c.sentimentHint);
          const tc = TYPE_CFG[c.eventType] || TYPE_CFG.market;
          return (
            <div
              key={c.clusterId}
              data-testid={`breaking-${c.clusterId}`}
              onClick={() => onSelect?.(c)}
              className="flex-shrink-0 w-80 p-4 transition-all cursor-pointer hover:opacity-80"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-[10px] font-bold uppercase" style={{ color: tc.color }}>{tc.label}</span>
                <span className="text-[10px] font-bold" style={{ color: '#64748b' }}>Score {c.importance}/100</span>
                <span className="ml-auto text-[10px] font-medium" style={{ color: cl.textMuted }}>
                  {c.sourcesCount} {c.sourcesCount === 1 ? 'source' : 'sources'}
                </span>
              </div>
              <p className="text-sm font-semibold line-clamp-2 mb-2" style={{ color: cl.text }}>
                {c.title}
              </p>
              <div className="flex items-center gap-2 text-xs" style={{ color: cl.textMuted }}>
                <si.Icon size={12} style={{ color: si.color }} />
                <span>{si.label}</span>
                <span>·</span>
                <Clock size={10} />
                <span>{timeAgo(c.firstSeenAt)}</span>
                {c.primaryAsset && (
                  <>
                    <span>·</span>
                    <span className="font-bold" style={{ color: cl.accent }}>{c.primaryAsset}</span>
                  </>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
});

// ── Market Pulse (instant overview) — ACCENTED ──────────────────
const MarketPulse = memo(function MarketPulse({ stats }) {
  if (!stats) return null;

  const barBullish = Math.max(5, stats.positivePct);
  const barBearish = Math.max(5, stats.negativePct);
  const barNeutral = Math.max(5, stats.neutralPct);

  return (
    <div data-testid="market-pulse" className="mb-6">
      {/* Main numbers row */}
      <div className="grid grid-cols-4 gap-4 mb-3">
        <div className="p-5" style={{ backgroundColor: '#f1f5f9' }}>
          <p className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: '#64748b' }}>Events</p>
          <p className="text-4xl font-bold tracking-tight" style={{ color: '#0f172a' }}>{stats.total}</p>
          <p className="text-xs mt-1" style={{ color: '#94a3b8' }}>last 48h</p>
        </div>
        <div className="p-5" style={{ backgroundColor: '#f0fdf4' }}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#16a34a' }}>Bullish</p>
            <p className="text-xs font-bold" style={{ color: '#22c55e' }}>{stats.positivePct.toFixed(0)}%</p>
          </div>
          <p className="text-4xl font-bold tracking-tight" style={{ color: '#16a34a' }}>{stats.bullish}</p>
          <div className="mt-2 h-1.5 overflow-hidden" style={{ backgroundColor: '#dcfce7' }}>
            <div className="h-full" style={{ width: `${barBullish}%`, backgroundColor: '#16a34a' }} />
          </div>
        </div>
        <div className="p-5" style={{ backgroundColor: '#fef2f2' }}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#dc2626' }}>Bearish</p>
            <p className="text-xs font-bold" style={{ color: '#ef4444' }}>{stats.negativePct.toFixed(0)}%</p>
          </div>
          <p className="text-4xl font-bold tracking-tight" style={{ color: '#dc2626' }}>{stats.bearish}</p>
          <div className="mt-2 h-1.5 overflow-hidden" style={{ backgroundColor: '#fecaca' }}>
            <div className="h-full" style={{ width: `${barBearish}%`, backgroundColor: '#dc2626' }} />
          </div>
        </div>
        <div className="p-5" style={{ backgroundColor: '#eef2ff' }}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#6366f1' }}>Neutral</p>
            <p className="text-xs font-bold" style={{ color: '#818cf8' }}>{stats.neutralPct.toFixed(0)}%</p>
          </div>
          <p className="text-4xl font-bold tracking-tight" style={{ color: '#4f46e5' }}>{stats.neutral}</p>
          <div className="mt-2 h-1.5 overflow-hidden" style={{ backgroundColor: '#c7d2fe' }}>
            <div className="h-full" style={{ width: `${barNeutral}%`, backgroundColor: '#6366f1' }} />
          </div>
        </div>
      </div>
    </div>
  );
});

// ── Compact News Card ───────────────────────────────────────────
const CompactCard = memo(function CompactCard({ cluster, onClick }) {
  const si = sentimentIcon(cluster.sentimentHint);
  const tc = TYPE_CFG[cluster.eventType] || TYPE_CFG.market;
  const bc = bandColor(cluster.importanceBand);

  return (
    <div
      data-testid={`cluster-${cluster.clusterId}`}
      onClick={() => onClick?.(cluster)}
      className="py-3 transition-all hover:opacity-70 cursor-pointer"
      style={{ borderBottom: '1px solid #f0f0f0' }}
    >
      {/* Row 1: meta */}
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <span className="text-[10px] font-bold" style={{ color: '#64748b' }}>Score {cluster.importance}/100</span>
        <span className="text-[10px] font-medium" style={{ color: tc.color }}>{tc.label}</span>
        {cluster.sourcesCount > 1 && (
          <span className="text-[10px] font-medium" style={{ color: cl.textMuted }}>
            {cluster.sourcesCount} {cluster.sourcesCount === 1 ? 'source' : 'sources'}
          </span>
        )}
        {cluster.primaryAsset && (
          <span className="text-[10px] font-bold" style={{ color: '#1d4ed8' }}>
            {cluster.primaryAsset}
          </span>
        )}
        <span className="ml-auto flex items-center gap-1.5">
          <si.Icon size={14} style={{ color: si.color }} />
          <span className="text-[10px] font-bold" style={{ color: si.color }}>{si.label}</span>
        </span>
      </div>

      {/* Row 2: title */}
      <p className="text-sm font-medium line-clamp-2 mb-1" style={{ color: cl.text }}>
        {cluster.title}
      </p>

      {/* Row 3: source + time */}
      <div className="flex items-center gap-2 text-xs" style={{ color: cl.textMuted }}>
        <span>{cluster.representativeSource || cluster.sources?.[0]}</span>
        <span>·</span>
        <Clock size={10} />
        <span>{timeAgo(cluster.firstSeenAt)}</span>
      </div>
    </div>
  );
});

// ── Cluster Detail Modal (sources only, no generation) ──────────
function ClusterModal({ cluster, onClose }) {
  if (!cluster) return null;
  const si = sentimentIcon(cluster.sentimentHint);
  const tc = TYPE_CFG[cluster.eventType] || TYPE_CFG.market;

  return (
    <div
      data-testid="cluster-modal"
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl max-w-3xl w-full max-h-[85vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-6">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-xs font-bold" style={{ color: '#64748b' }}>Importance {cluster.importance}/100</span>
            <span className="text-xs font-medium" style={{ color: tc.color }}>{tc.label}</span>
            <span className="flex items-center gap-1.5 text-xs font-bold" style={{ color: si.color }}>
              <si.Icon size={14} /> {si.label}
            </span>
            <button onClick={onClose} className="ml-auto p-1.5 hover:bg-gray-100 rounded-lg">
              <X size={18} style={{ color: cl.textMuted }} />
            </button>
          </div>
          <h2 className="text-xl font-bold mb-2" style={{ color: cl.text }}>{cluster.title}</h2>
          <div className="flex items-center gap-3 text-sm" style={{ color: cl.textMuted }}>
            <span>{cluster.sourcesCount} sources</span>
            <span>·</span>
            <span>{timeAgo(cluster.firstSeenAt)}</span>
            {cluster.primaryAsset && (
              <>
                <span>·</span>
                <span className="font-bold" style={{ color: cl.accent }}>{cluster.primaryAsset}</span>
              </>
            )}
          </div>
        </div>
        <div className="px-6 pb-6 space-y-0">
          {cluster.events?.map((ev, idx) => (
            <div key={idx} className="flex items-center gap-3 py-2.5">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: cl.text }}>{ev.publisher}</p>
                <p className="text-xs truncate" style={{ color: cl.textMuted }}>{ev.title}</p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="text-xs" style={{ color: cl.textMuted }}>{timeAgo(ev.publishedAt)}</span>
                {ev.url && (
                  <a href={ev.url} target="_blank" rel="noopener noreferrer"
                     className="text-gray-400 hover:text-blue-500" onClick={e => e.stopPropagation()}>
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Compute Stats ───────────────────────────────────────────────
function computeStats(clusters) {
  let bullish = 0, bearish = 0, neutral = 0;
  for (const c of clusters) {
    const s = mapSentiment(c.sentimentHint);
    if (s === 'positive') bullish++;
    else if (s === 'negative') bearish++;
    else neutral++;
  }
  const total = clusters.length || 1;
  return {
    bullish, bearish, neutral, total: clusters.length,
    positivePct: (bullish / total) * 100,
    neutralPct: (neutral / total) * 100,
    negativePct: (bearish / total) * 100,
  };
}

// ── Heatmap ─────────────────────────────────────────────────────
const Heatmap = memo(function Heatmap({ clusters }) {
  const buckets = useMemo(() => {
    const now = new Date();
    const result = [];
    const map = {};
    for (const c of clusters) {
      const h = new Date(c.firstSeenAt);
      const key = `${h.getFullYear()}-${h.getMonth()}-${h.getDate()}-${h.getHours()}`;
      if (!map[key]) map[key] = { p: 0, n: 0, ne: 0 };
      const s = mapSentiment(c.sentimentHint);
      if (s === 'positive') map[key].p++;
      else if (s === 'negative') map[key].n++;
      else map[key].ne++;
    }
    for (let i = 11; i >= 0; i--) {
      const h = new Date(now);
      h.setHours(now.getHours() - i, 0, 0, 0);
      const key = `${h.getFullYear()}-${h.getMonth()}-${h.getDate()}-${h.getHours()}`;
      const b = map[key] || { p: 0, n: 0, ne: 0 };
      result.push({ label: `${h.getHours()}:00`, ...b, total: b.p + b.n + b.ne });
    }
    return result;
  }, [clusters]);

  return (
    <div data-testid="heatmap" className="mb-6 rounded-2xl p-4" style={{ backgroundColor: '#0a0a0a' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={14} style={{ color: '#fb923c' }} />
          <span className="text-xs font-semibold text-white">Sentiment Heatmap</span>
        </div>
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-green-500" /><span className="text-slate-400">Bull</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-slate-500" /><span className="text-slate-400">Flat</span></span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-red-500" /><span className="text-slate-400">Bear</span></span>
        </div>
      </div>
      <div className="grid grid-cols-12 gap-1">
        {buckets.map((b, i) => {
          const t = b.total || 1;
          const pr = b.p / t;
          const nr = b.n / t;
          const dom = pr > nr ? 'p' : nr > pr ? 'n' : 'ne';
          const int = Math.max(pr, nr, 0.15);
          return (
            <div key={i} className="flex flex-col items-center">
              <div
                className="w-full h-10 rounded-lg hover:scale-105 transition-transform"
                style={{
                  backgroundColor: dom === 'p' ? `rgba(34,197,94,${0.3 + int * 0.7})` :
                    dom === 'n' ? `rgba(239,68,68,${0.3 + int * 0.7})` : 'rgba(100,116,139,0.4)'
                }}
                title={`${b.label}: ${b.p}↑ ${b.n}↓ ${b.ne}→`}
              />
              <span className="text-[8px] text-slate-500 mt-0.5">{b.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

// ── AI Digest Block ─────────────────────────────────────────────
const AIDigest = memo(function AIDigest() {
  const [article, setArticle] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [lang, setLang] = useState('ru');
  const [expanded, setExpanded] = useState(false);
  const [fullArticle, setFullArticle] = useState(null);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/ai-news/latest`);
      const data = await res.json();
      if (data.ok && data.article) setArticle(data.article);
    } catch (e) { /* silent */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchLatest(); }, [fetchLatest]);

  const generate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_URL}/api/ai-news/generate`, { method: 'POST' });
      const data = await res.json();
      if (data.ok && data.article) {
        setArticle(data.article);
        setFullArticle(null);
        toast.success('AI Digest generated');
      } else {
        toast.error(data.error || 'Generation failed');
      }
    } catch (e) {
      toast.error('Generation failed');
    }
    setGenerating(false);
  };

  const generateFull = () => {
    if (!article) return;
    const fullKey = lang === 'ru' ? 'fullRu' : 'fullEn';
    const fullContent = article[fullKey];
    if (fullContent) {
      setFullArticle(fullContent);
    } else {
      toast.error('Full version not available. Regenerate the digest.');
    }
  };

  const content = article?.[lang];
  const hasArticle = content?.title;

  return (
    <div data-testid="ai-digest" className="rounded-2xl p-5" style={{ backgroundColor: '#0a0a0a' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Sparkles size={14} style={{ color: '#ca8a04' }} />
          <span className="text-sm font-bold" style={{ color: '#f9fafb' }}>AI Digest</span>
          {article && (
            <span className="text-[10px]" style={{ color: '#6b7280' }}>
              {new Date(article.generatedAt).toLocaleDateString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Language toggle */}
          <div className="flex gap-0.5" style={{ backgroundColor: '#1f2937', borderRadius: 6, padding: 2 }}>
            {['ru', 'en'].map(l => (
              <button key={l} onClick={() => { setLang(l); setFullArticle(null); }}
                className="px-2 py-0.5 rounded text-[10px] font-bold uppercase transition-colors"
                style={{ backgroundColor: lang === l ? '#374151' : 'transparent', color: lang === l ? '#f9fafb' : '#6b7280' }}>
                {l}
              </button>
            ))}
          </div>
          {hasArticle && (
            <button onClick={generateFull}
              className="text-[10px] px-2.5 py-1 rounded font-bold transition-colors"
              style={{ backgroundColor: '#f9fafb', color: '#0a0a0a' }}
              data-testid="expand-article-btn">
              Full
            </button>
          )}
          <button onClick={generate} disabled={generating}
            className="text-[10px] px-2.5 py-1 rounded font-bold transition-colors disabled:opacity-50"
            style={{ backgroundColor: '#ca8a04', color: '#0a0a0a' }}
            data-testid="generate-digest-btn">
            {generating ? <Loader2 size={12} className="animate-spin" /> : 'Generate'}
          </button>
        </div>
      </div>

      {loading && !article && (
        <div className="flex items-center justify-center py-6">
          <Loader2 size={16} className="animate-spin" style={{ color: '#9ca3af' }} />
        </div>
      )}

      {!loading && !hasArticle && (
        <div className="text-center py-4">
          <p className="text-sm" style={{ color: '#6b7280' }}>No AI digest yet. Click "Generate" to create one.</p>
        </div>
      )}

      {hasArticle && !fullArticle && (
        <div>
          {/* Image + Title row */}
          <div className="flex gap-4 mb-3">
            {article.imageId && (
              <img src={`${API_URL}/api/ai-news/image/${article.imageId}`} alt="" className="w-32 h-32 rounded-lg object-cover flex-shrink-0" />
            )}
            <div className="flex-1">
              <h3 className="text-base font-semibold mb-1" style={{ color: '#f9fafb' }}>{content.title}</h3>
              {content.sentiment && (
                <span className="text-[10px] font-bold uppercase" style={{
                  color: content.sentiment === 'bullish' ? '#16a34a' : content.sentiment === 'bearish' ? '#dc2626' : '#6366f1',
                }}>
                  {content.sentiment}
                </span>
              )}
            </div>
          </div>

          {/* Body */}
          <p className="text-sm leading-relaxed mb-3" style={{
            color: '#d1d5db',
            display: expanded ? 'block' : '-webkit-box',
            WebkitLineClamp: expanded ? 'unset' : 4,
            WebkitBoxOrient: 'vertical',
            overflow: expanded ? 'visible' : 'hidden',
          }}>
            {content.body}
          </p>

          <button onClick={() => setExpanded(e => !e)} className="text-[10px] font-bold mb-3 transition-colors"
            style={{ color: '#ca8a04' }}>
            {expanded ? 'Collapse' : 'Read more'}
          </button>

          {/* Signals */}
          {content.signals?.length > 0 && (
            <div className="pt-2">
              <span className="text-[10px] uppercase tracking-wider font-bold block mb-1.5" style={{ color: '#9ca3af' }}>Key Signals</span>
              {content.signals.map((s, i) => (
                <div key={i} className="flex gap-2 mb-1">
                  <span className="text-[10px] mt-0.5" style={{ color: '#ca8a04' }}>-{'>'}</span>
                  <span className="text-xs" style={{ color: '#d1d5db' }}>{s}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Full article view */}
      {fullArticle && (
        <div>
          <button onClick={() => setFullArticle(null)} className="text-xs mb-3 flex items-center gap-1 transition-colors"
            style={{ color: '#ca8a04' }}>
            <ArrowLeft size={12} /> Back
          </button>
          {article?.imageId && (
            <img src={`${API_URL}/api/ai-news/image/${article.imageId}`} alt=""
              className="w-full h-80 rounded-lg object-cover mb-4" />
          )}
          <h3 className="text-lg font-bold mb-2" style={{ color: '#f9fafb' }}>{fullArticle.title}</h3>
          {fullArticle.sentiment && (
            <span className="text-[10px] font-bold uppercase mb-3 block" style={{
              color: fullArticle.sentiment === 'bullish' ? '#16a34a' : fullArticle.sentiment === 'bearish' ? '#dc2626' : '#6366f1',
            }}>{fullArticle.sentiment}</span>
          )}
          <div className="text-sm leading-relaxed space-y-3 mb-4" style={{ color: '#d1d5db' }}>
            {(fullArticle.body || '').split('\n\n').map((p, i) => (
              <p key={i}>{p.replace(/\n/g, ' ')}</p>
            ))}
          </div>
          {fullArticle.forecast && (
            <div className="mb-4">
              <span className="text-[10px] font-bold uppercase tracking-wider block mb-1" style={{ color: '#9ca3af' }}>Forecast</span>
              <p className="text-sm" style={{ color: '#d1d5db' }}>{fullArticle.forecast}</p>
            </div>
          )}
          {fullArticle.conclusions?.length > 0 && (
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider block mb-2" style={{ color: '#9ca3af' }}>Key Conclusions</span>
              {fullArticle.conclusions.map((c, i) => (
                <div key={i} className="flex gap-2 mb-1">
                  <span className="text-[10px] mt-0.5" style={{ color: '#ca8a04' }}>-{'>'}</span>
                  <span className="text-xs" style={{ color: '#d1d5db' }}>{c}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
});

// ═══════════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════════
export default function NewsTab() {
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [eventFilter, setEventFilter] = useState('all');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [showLow, setShowLow] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState(null);

  // Track already-alerted breaking cluster IDs
  const alertedRef = useRef(new Set());

  const fetchFeed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/news/feed?limit=50&hours=48`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || 'Failed');
      const newClusters = data.data?.clusters || [];
      setClusters(newClusters);

      // Breaking alerts: only on subsequent fetches (not initial load), max 3, short duration
      if (alertedRef.current.size > 0) {
        let shown = 0;
        for (const c of newClusters) {
          if (shown >= 3) break;
          if (c.isBreaking && (c.importance ?? 0) > 70 && !alertedRef.current.has(c.clusterId)) {
            alertedRef.current.add(c.clusterId);
            toast(c.title, {
              description: `Score ${c.importance}/100 · ${c.eventType || 'news'}`,
              duration: 3000,
            });
            shown++;
          }
        }
      }
      // Mark all current as seen (prevents flood on first load)
      for (const c of newClusters) {
        alertedRef.current.add(c.clusterId);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed();
    const feedIv = setInterval(fetchFeed, 90000);
    return () => { clearInterval(feedIv); };
  }, [fetchFeed]);

  // Filtered
  const filtered = useMemo(() => {
    return clusters.filter(c => {
      if (eventFilter !== 'all' && c.eventType !== eventFilter) return false;
      if (sentimentFilter !== 'all') {
        const m = mapSentiment(c.sentimentHint);
        if (m !== sentimentFilter) return false;
      }
      if (searchQuery.length >= 2) {
        const q = searchQuery.toLowerCase();
        if (!c.title?.toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [clusters, eventFilter, sentimentFilter, searchQuery]);

  // Split by band
  const highMed = filtered.filter(c => c.importanceBand !== 'low');
  const low = filtered.filter(c => c.importanceBand === 'low');

  const stats = useMemo(() => computeStats(clusters), [clusters]);

  return (
    <div data-testid="news-tab" className="space-y-4 p-6">
      {/* ── URL Analyzer ── */}
      <UrlAnalyzer />

      {/* ── Market Brief (collapsible) ── */}
      <MarketBrief />

      {/* ── Breaking Strip ── */}
      {clusters.length > 0 && <BreakingStrip clusters={clusters} onSelect={setSelectedCluster} />}

      {/* ── AI Digest ── */}
      <AIDigest />

      {/* ── Market Pulse ── */}
      <MarketPulse stats={stats} />

      {/* ── Filters Row ── */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <input
            data-testid="feed-search-input"
            type="text"
            placeholder="Search..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="w-full pl-3 pr-8 py-2 rounded-lg text-sm focus:outline-none"
            style={{ backgroundColor: cl.surface, color: cl.text }}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X size={14} style={{ color: cl.textMuted }} />
            </button>
          )}
        </div>

        {/* Event type pills */}
        <div className="flex gap-1 overflow-x-auto">
          {EVENT_FILTERS.map(f => (
            <button
              key={f}
              data-testid={`filter-${f}`}
              onClick={() => setEventFilter(f)}
              className="px-3 py-1.5 text-xs font-medium capitalize whitespace-nowrap transition-all"
              style={{
                color: eventFilter === f ? cl.accent : cl.textMuted,
                textDecoration: eventFilter === f ? 'underline' : 'none',
              }}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Sentiment pills */}
        <div className="flex gap-1">
          {SENTIMENT_FILTERS.map(f => {
            const active = sentimentFilter === f;
            const dotColor = f === 'positive' ? cl.bullish : f === 'negative' ? cl.bearish : f === 'neutral' ? '#6366f1' : '#6b7280';
            const activeColor = f === 'positive' ? cl.bullish : f === 'negative' ? cl.bearish : f === 'neutral' ? '#4f46e5' : '#f9fafb';
            return (
              <button
                key={f}
                data-testid={`sentiment-${f}`}
                onClick={() => setSentimentFilter(f)}
                className="px-3 py-1.5 text-xs font-bold capitalize transition-all flex items-center gap-1.5"
                style={{
                  color: active ? activeColor : cl.textMuted,
                  textDecoration: active ? 'underline' : 'none',
                }}
              >
                {f !== 'all' && <span className="w-2 h-2 rounded-full" style={{ backgroundColor: dotColor }} />}
                {f}
              </button>
            );
          })}
        </div>

        <button
          data-testid="news-refresh-btn"
          onClick={fetchFeed}
          disabled={loading}
          className="p-2 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} style={{ color: cl.textMuted }} />
        </button>
      </div>

      {/* ── Heatmap ── */}
      {clusters.length > 0 && <Heatmap clusters={clusters} />}

      {/* ── Error ── */}
      {error && (
        <div data-testid="news-error" className="p-3 rounded-lg bg-red-50 text-red-600 text-sm flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* ── Loading ── */}
      {loading && clusters.length === 0 && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-5 h-5 animate-spin" style={{ color: cl.accent }} />
        </div>
      )}

      {/* ── Empty ── */}
      {!loading && filtered.length === 0 && (
        <div className="p-12 text-center">
          <Newspaper size={36} className="mx-auto mb-3" style={{ color: cl.textMuted }} />
          <p className="text-sm" style={{ color: cl.textSec }}>No events match filters</p>
        </div>
      )}

      {/* ── HIGH + MEDIUM Clusters ── */}
      {highMed.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {highMed.map(c => (
            <CompactCard key={c.clusterId} cluster={c} onClick={setSelectedCluster} />
          ))}
        </div>
      )}

      {/* ── LOW Clusters (collapsed by default) ── */}
      {low.length > 0 && (
        <div>
          <button
            data-testid="toggle-low-events"
            onClick={() => setShowLow(!showLow)}
            className="flex items-center gap-2 text-sm font-medium w-full py-3 px-4 transition-colors"
            style={{ color: cl.textSec }}
          >
            <Eye size={14} />
            {showLow ? 'Hide' : 'Show'} {low.length} low-priority events
            <ChevronDown size={14} className={`ml-auto transition-transform ${showLow ? 'rotate-180' : ''}`} />
          </button>
          {showLow && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
              {low.map(c => (
                <CompactCard key={c.clusterId} cluster={c} onClick={setSelectedCluster} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Modal ── */}
      {selectedCluster && (
        <ClusterModal cluster={selectedCluster} onClose={() => setSelectedCluster(null)} />
      )}
    </div>
  );
}
