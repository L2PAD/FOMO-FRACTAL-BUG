import React, { useState, useEffect, useCallback } from 'react';
import {
  Flame, TrendingUp, TrendingDown, Minus, Gauge, AlertTriangle,
  Clock, ExternalLink, RefreshCw, Zap, BarChart2, Activity
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ── Color palette ──
const cl = {
  bg: '#ffffff',
  surface: '#f8fafc',
  text: '#0f172a',
  muted: '#64748b',
  border: '#e2e8f0',
  bullish: '#16a34a',
  bearish: '#dc2626',
  neutral: '#6366f1',
  accent: '#2563eb',
  breaking: '#dc2626',
};

const VELOCITY_CONFIG = {
  CALM: { color: '#64748b', bg: '#f1f5f9', label: 'Quiet' },
  NORMAL: { color: '#16a34a', bg: '#f0fdf4', label: 'Normal' },
  ELEVATED: { color: '#d97706', bg: '#fffbeb', label: 'Elevated' },
  SPIKE: { color: '#dc2626', bg: '#fef2f2', label: 'Spike' },
};

const IMPORTANCE_COLORS = {
  high: { bg: '#fef2f2', color: '#dc2626', border: '#fca5a5' },
  medium: { bg: '#fffbeb', color: '#d97706', border: '#fcd34d' },
  low: { bg: '#f1f5f9', color: '#64748b', border: '#cbd5e1' },
};

// ── Sentiment bar ──
function SentimentBar({ bullish, bearish, neutral }) {
  const b = parseInt(bullish) || 0;
  const be = parseInt(bearish) || 0;
  const n = parseInt(neutral) || 0;

  return (
    <div data-testid="digest-sentiment-bar">
      <div className="flex h-3 rounded-full overflow-hidden mb-2" style={{ backgroundColor: cl.border }}>
        {b > 0 && <div style={{ width: `${b}%`, backgroundColor: cl.bullish }} />}
        {n > 0 && <div style={{ width: `${n}%`, backgroundColor: cl.neutral }} />}
        {be > 0 && <div style={{ width: `${be}%`, backgroundColor: cl.bearish }} />}
      </div>
      <div className="flex justify-between text-xs">
        <span style={{ color: cl.bullish }} className="font-semibold">Bullish {bullish}</span>
        <span style={{ color: cl.neutral }} className="font-semibold">Neutral {neutral}</span>
        <span style={{ color: cl.bearish }} className="font-semibold">Bearish {bearish}</span>
      </div>
    </div>
  );
}

// ── Top Event Card ──
function TopEventCard({ event, rank }) {
  const ic = IMPORTANCE_COLORS[event.importanceBand] || IMPORTANCE_COLORS.low;
  const sentColor = event.sentiment === 'bullish' ? cl.bullish
    : event.sentiment === 'bearish' ? cl.bearish : cl.muted;

  return (
    <div
      data-testid={`digest-event-${rank}`}
      className="p-4 rounded-xl border transition-all hover:shadow-md"
      style={{ backgroundColor: cl.bg, borderColor: cl.border }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <span
            className="flex-shrink-0 w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ backgroundColor: ic.bg, color: ic.color, border: `1px solid ${ic.border}` }}
          >
            {rank}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold leading-snug" style={{ color: cl.text }}>
              {event.title}
            </p>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {event.eventType && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-md font-medium uppercase tracking-wide"
                  style={{ backgroundColor: '#ede9fe', color: '#7c3aed' }}>
                  {event.eventType}
                </span>
              )}
              <span className="text-[10px] px-1.5 py-0.5 rounded-md font-bold uppercase"
                style={{ backgroundColor: ic.bg, color: ic.color }}>
                IMP {event.importance}
              </span>
              <span className="text-[10px]" style={{ color: sentColor }}>
                {event.sentiment || 'neutral'}
              </span>
              {event.sourcesCount > 0 && (
                <span className="text-[10px]" style={{ color: cl.muted }}>
                  {event.sourcesCount} sources
                </span>
              )}
              {event.isBreaking && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-md font-bold"
                  style={{ backgroundColor: '#fef2f2', color: cl.breaking }}>
                  BREAKING
                </span>
              )}
            </div>
            {event.assets?.length > 0 && (
              <div className="flex gap-1 mt-1.5">
                {event.assets.slice(0, 5).map(a => (
                  <span key={a} className="text-[10px] px-1.5 py-0.5 rounded-md font-medium"
                    style={{ backgroundColor: '#f0f9ff', color: '#0369a1' }}>
                    {a}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Digest Page ──
export default function DigestPage() {
  const [digest, setDigest] = useState(null);
  const [velocity, setVelocity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAll = useCallback(async () => {
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

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 120000); // refresh every 2 min
    return () => clearInterval(iv);
  }, [fetchAll]);

  if (loading && !digest) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw size={24} className="animate-spin" style={{ color: cl.muted }} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20 gap-2">
        <AlertTriangle size={18} style={{ color: cl.bearish }} />
        <span className="text-sm" style={{ color: cl.bearish }}>{error}</span>
      </div>
    );
  }

  if (!digest) return null;

  const vc = velocity ? (VELOCITY_CONFIG[velocity.level] || VELOCITY_CONFIG.CALM) : null;

  return (
    <div data-testid="digest-page" className="max-w-3xl mx-auto py-2">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: '#ede9fe' }}>
            <BarChart2 size={20} style={{ color: '#7c3aed' }} />
          </div>
          <div>
            <h2 className="text-lg font-bold" style={{ color: cl.text }}>Market Brief</h2>
            <p className="text-xs" style={{ color: cl.muted }}>
              {digest.totalEvents} events · {digest.breakingCount} breaking · last 24h
            </p>
          </div>
        </div>
        <button
          data-testid="digest-refresh-btn"
          onClick={fetchAll}
          className="p-2 rounded-lg border hover:bg-slate-50 transition-colors"
          style={{ borderColor: cl.border }}
        >
          <RefreshCw size={16} style={{ color: cl.muted }} />
        </button>
      </div>

      {/* ── Velocity Block ── */}
      {velocity && vc && (
        <div
          data-testid="digest-velocity-block"
          className="p-4 rounded-xl border mb-5"
          style={{ backgroundColor: vc.bg, borderColor: `${vc.color}33` }}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Gauge size={18} style={{ color: vc.color }} />
              <span className="text-sm font-bold" style={{ color: vc.color }}>{velocity.message}</span>
            </div>
            <div className="flex gap-4 text-xs">
              <span style={{ color: vc.color }}>
                <span className="font-bold">{velocity.current ?? 0}</span> now · <span className="font-bold">{velocity.baseline ?? '—'}</span> avg/h
              </span>
              <span style={{ color: vc.color }}>
                Ratio <span className="font-bold">{velocity.velocityRatio ?? '—'}x</span>
              </span>
              {velocity.trend24hPct !== undefined && velocity.trend24hPct !== 0 && (
                <span style={{ color: vc.color }}>
                  24h <span className="font-bold">{velocity.trend24hPct > 0 ? '+' : ''}{velocity.trend24hPct}%</span>
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Sentiment Block ── */}
      <div className="p-4 rounded-xl border mb-5" style={{ borderColor: cl.border, backgroundColor: cl.surface }}>
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} style={{ color: cl.accent }} />
          <span className="text-sm font-bold" style={{ color: cl.text }}>Sentiment</span>
          {digest.sentimentShiftPct !== 0 && (
            <span className="text-xs px-2 py-0.5 rounded-md font-medium ml-auto"
              style={{
                backgroundColor: digest.sentimentShiftPct > 0 ? '#f0fdf4' : '#fef2f2',
                color: digest.sentimentShiftPct > 0 ? cl.bullish : cl.bearish,
              }}>
              {digest.sentimentShiftPct > 0 ? '+' : ''}{digest.sentimentShiftPct}% vs yesterday
            </span>
          )}
        </div>
        <SentimentBar
          bullish={digest.sentiment?.bullish}
          bearish={digest.sentiment?.bearish}
          neutral={digest.sentiment?.neutral}
        />
      </div>

      {/* ── Top 5 Events ── */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-3">
          <Flame size={16} style={{ color: cl.breaking }} />
          <span className="text-sm font-bold" style={{ color: cl.text }}>Top Events</span>
        </div>
        <div className="space-y-2">
          {digest.top5?.map((event, i) => (
            <TopEventCard key={i} event={event} rank={i + 1} />
          ))}
        </div>
      </div>

      {/* ── Why It Matters ── */}
      {digest.whyItMatters?.length > 0 && (
        <div
          data-testid="digest-why-it-matters"
          className="p-4 rounded-xl border"
          style={{ borderColor: '#c7d2fe', backgroundColor: '#eef2ff' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <Zap size={16} style={{ color: '#4f46e5' }} />
            <span className="text-sm font-bold" style={{ color: '#4f46e5' }}>Why it matters</span>
          </div>
          <ul className="space-y-1">
            {digest.whyItMatters.map((line, i) => (
              <li key={i} className="text-sm flex items-start gap-2" style={{ color: '#3730a3' }}>
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: '#818cf8' }} />
                {line}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Timestamp ── */}
      <p className="text-xs mt-4 text-center" style={{ color: cl.muted }}>
        Generated at {new Date(digest.generatedAt).toLocaleString()} · Auto-refresh every 2 min
      </p>
    </div>
  );
}
