/**
 * Signal Terminal — Decision Intelligence Interface
 * 
 * Layout: MarketPulse → Hero → LiveFlow + Sidebar(MarketMap + Engine + Influencers)
 * Signal Fusion: 1 Asset = 1 Card (merged across all data sources)
 * Color System: Gold=Confluence, Red=Listing, Purple=Early, Emerald=Signal
 */
import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent } from '../components/ui/dialog';
import { ScrollArea } from '../components/ui/scroll-area';
import { Skeleton } from '../components/ui/skeleton';
import {
  TrendingUp, TrendingDown, BarChart3, Activity, Target, RefreshCw,
  Clock, MessageCircle, Heart, Repeat2, Eye, ChevronRight, ExternalLink,
  Zap, Shield, ArrowRight, AlertTriangle, ArrowUpRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const ACCENT = {
  CONFLUENCE: { border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', badge: 'text-amber-600', dot: 'bg-amber-400', leftBorder: 'border-l-amber-400' },
  LISTING: { border: 'border-red-200', bg: 'bg-red-50', text: 'text-red-600', badge: 'text-red-600', dot: 'bg-red-400', leftBorder: 'border-l-red-400' },
  LIVE_LISTING: { border: 'border-red-200', bg: 'bg-red-50', text: 'text-red-600', badge: 'text-red-600', dot: 'bg-red-500', leftBorder: 'border-l-red-500' },
  EARLY: { border: 'border-purple-200', bg: 'bg-purple-50', text: 'text-purple-600', badge: 'text-purple-600', dot: 'bg-purple-400', leftBorder: 'border-l-purple-400' },
  SIGNAL: { border: 'border-emerald-200', bg: 'bg-emerald-50', text: 'text-emerald-600', badge: 'text-emerald-600', dot: 'bg-emerald-400', leftBorder: 'border-l-emerald-400' },
};

// Crypto logo URL with fallback
const getTokenLogo = (symbol) => `https://raw.githubusercontent.com/spothq/cryptocurrency-icons/master/128/color/${(symbol || '').toLowerCase()}.png`;
const formatEventType = (t) => (t || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
const formatTime = (minutes) => {
  if (!minutes && minutes !== 0) return '';
  const m = Number(minutes);
  if (m < 60) return `${m}m`;
  if (m < 1440) return `${Math.floor(m / 60)}h ${m % 60 > 0 ? (m % 60) + 'm' : ''}`.trim();
  return `${Math.floor(m / 1440)}d ${Math.floor((m % 1440) / 60)}h`.trim();
};

// ═══════════════════════════════════════════
// SIGNAL FUSION ENGINE
// ═══════════════════════════════════════════
const buildFusedSignals = (correlations, listings, earlyData) => {
  const map = new Map();

  (correlations || []).forEach(c => {
    if (!c.symbol) return;
    map.set(c.symbol, {
      id: c.id, entityId: c.id, symbol: c.symbol, name: c.name,
      priceChange24h: c.priceChange24h || 0,
      sentiment: c.sentiment, signal: c.signal || {},
      tweets24h: c.tweets24h || 0, influencerMentions: c.influencerMentions || 0,
      layers: [], listingData: null, earlyData: null, confluenceData: null, isLive: false,
    });
  });

  const liveIds = new Set((listings?.live || []).map(l => l.id));
  [...(listings?.live || []), ...(listings?.confirmed || []), ...(listings?.potential || []), ...(listings?.mentions || [])].forEach(l => {
    const isLive = liveIds.has(l.id);
    const existing = map.get(l.token);
    if (existing) {
      if (!existing.listingData || l.listingScore > existing.listingData.listingScore) existing.listingData = l;
      if (isLive) existing.isLive = true;
      if (!existing.layers.includes('LISTING')) existing.layers.push('LISTING');
    } else {
      map.set(l.token, {
        id: l.id, entityId: l.id, symbol: l.token, name: l.tokenName || l.token,
        priceChange24h: 0, sentiment: null, signal: {}, tweets24h: 0, influencerMentions: 0,
        layers: ['LISTING'], listingData: l, earlyData: null, confluenceData: null, isLive,
      });
    }
  });

  (earlyData?.earlySignals || []).forEach(e => {
    const existing = map.get(e.symbol);
    if (existing) {
      existing.earlyData = e;
      if (!existing.layers.includes('EARLY')) existing.layers.push('EARLY');
    } else {
      map.set(e.symbol, {
        id: e.id, entityId: e.entityId, symbol: e.symbol, name: e.name || e.symbol,
        priceChange24h: 0, sentiment: e.sentiment != null ? { score: e.sentiment } : null,
        signal: {}, tweets24h: 0, influencerMentions: 0,
        layers: ['EARLY'], listingData: null, earlyData: e, confluenceData: null, isLive: false,
      });
    }
  });

  (earlyData?.confluences || []).forEach(c => {
    const existing = map.get(c.token);
    if (existing) {
      existing.confluenceData = c;
      if (!existing.layers.includes('CONFLUENCE')) existing.layers.push('CONFLUENCE');
    } else {
      map.set(c.token, {
        id: c.id, entityId: c.id, symbol: c.token, name: c.name || c.token,
        priceChange24h: 0, sentiment: c.sentiment ? { score: c.sentiment.value } : null,
        signal: {}, tweets24h: 0, influencerMentions: 0,
        layers: ['CONFLUENCE'], listingData: null, earlyData: null, confluenceData: c, isLive: false,
      });
    }
  });

  map.forEach(v => {
    if (v.signal?.type && v.signal.type !== 'NEUTRAL' && !v.layers.includes('SIGNAL')) {
      v.layers.push('SIGNAL');
    }
  });

  return Array.from(map.values()).map(s => {
    let p = 0;
    if (s.confluenceData) p += 1000;
    if (s.isLive) p += 500;
    const isExchangeMention = s.listingData?.eventType === 'EXCHANGE_MENTION';
    if (s.listingData && !isExchangeMention && !s.listingData.isPotential) p += 300;
    if (s.listingData && !isExchangeMention) p += 200;
    if (s.listingData && isExchangeMention) p += 50;
    if (s.earlyData?.anomalyLevel === 'HIGH') p += 150;
    if (s.earlyData) p += 100;
    if (s.signal?.decayedScore) p += s.signal.decayedScore;
    if (s.signal?.rank === 1) p += 50;
    s.fusedPriority = p;
    s.primaryType = s.confluenceData ? 'CONFLUENCE'
      : s.isLive ? 'LIVE_LISTING'
      : (s.listingData && !isExchangeMention) ? 'LISTING'
      : s.earlyData ? 'EARLY' : 'SIGNAL';
    return s;
  }).filter(s => s.layers.length > 0 || (s.signal?.type && s.signal.type !== 'NEUTRAL'))
    .sort((a, b) => b.fusedPriority - a.fusedPriority);
};

// ═══════════════════════════════════════════
// SIGNAL TIMELINE — dot-line-dot, single color, no text
// ═══════════════════════════════════════════
const SignalTimeline = ({ fused }) => {
  const sig = fused.signal || {};
  const hasEarly = !!fused.earlyData;
  const hasListing = !!fused.listingData;
  const isBreakout = sig.setupType === 'BREAKOUT' || !!fused.confluenceData;

  let progress;
  if (hasEarly && isBreakout) progress = 85;
  else if (hasEarly && hasListing) progress = 70;
  else if (hasEarly) progress = sig.signalMaturity === 'LATE' ? 70 : sig.signalMaturity === 'MID' ? 45 : 25;
  else if (hasListing) progress = fused.listingData.status === 'CONFIRMED' ? 90 : 40;
  else if (sig.setupType) progress = sig.signalMaturity === 'LATE' ? 75 : sig.signalMaturity === 'MID' ? 50 : 30;
  else return null;

  return (
    <div className="mt-3 mb-1 flex items-center gap-1.5" data-testid="signal-timeline">
      <div className="w-2 h-2 rounded-full bg-emerald-400 flex-shrink-0" />
      <div className="relative flex-1 h-0.5 bg-emerald-200 rounded-full">
        <div className="absolute left-0 top-0 h-0.5 rounded-full bg-emerald-400 transition-all" style={{ width: `${progress}%` }} />
        <div className="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white shadow-sm transition-all" style={{ left: `${progress}%`, marginLeft: '-5px' }} />
      </div>
      <div className="w-2 h-2 rounded-full bg-emerald-200 flex-shrink-0" />
    </div>
  );
};

// ═══════════════════════════════════════════
// HERO CARD — Two variants: Listing-focused (priority alpha) vs Early Signal
// ═══════════════════════════════════════════
const HeroCard = ({ fused, onClick }) => {
  const sig = fused.signal || {};
  const sentPct = fused.sentiment?.score != null ? Math.round(fused.sentiment.score * 100) : fused.confluenceData?.sentiment?.value != null ? Math.round(fused.confluenceData.sentiment.value * 100) : null;
  const vel = sig.velocityDisplay || fused.earlyData?.velocityDisplay || fused.confluenceData?.anomaly?.velocityDisplay;
  const hasListingData = fused.listingData && fused.listingData.eventType !== 'EXCHANGE_MENTION';

  // ═══ VARIANT 2: LISTING HERO — priority alpha when listing data exists ═══
  if (hasListingData) {
    const ld = fused.listingData;
    const eventLabel = ld.eventType === 'NEW_SPOT_LISTING' ? 'NEW SPOT LISTING'
      : ld.eventType === 'FUTURES_LISTING' ? 'FUTURES LISTING'
      : ld.eventType === 'NEW_PAIR' ? 'NEW TRADING PAIR'
      : ld.eventType === 'POTENTIAL_LISTING' ? 'POTENTIAL LISTING'
      : formatEventType(ld.eventType);
    const confColor = ld.confidence === 'HIGH' ? 'text-emerald-600 bg-emerald-50' : ld.confidence === 'MED' ? 'text-amber-600 bg-amber-50' : 'text-gray-500 bg-gray-100';
    const statusColor = ld.status === 'CONFIRMED' ? 'text-emerald-700 bg-emerald-50 border-emerald-200' : 'text-amber-700 bg-amber-50 border-amber-200';

    return (
      <div className="rounded-lg border-2 border-red-200 bg-gradient-to-br from-red-50/60 to-white p-4 cursor-pointer hover:shadow-md transition-shadow"
        onClick={() => onClick?.(fused)} data-testid="hero-zone-listing">

        {/* Header: Event badge + Freshness + Time */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold uppercase text-red-600 tracking-wide">{eventLabel}</span>
            {ld.freshness && <span className="text-[9px] font-bold uppercase px-2 py-0.5 rounded-full bg-red-100 text-red-600">{ld.freshness}</span>}
            <span className={`text-[9px] font-semibold uppercase px-2 py-0.5 rounded-full border ${statusColor}`}>{ld.status}</span>
          </div>
          <div className="flex items-center gap-1 text-gray-400 text-sm">
            <Clock className="w-3.5 h-3.5" />
            <span>{ld.minutesAgo != null ? formatTime(ld.minutesAgo) + ' ago' : ''}</span>
          </div>
        </div>

        {/* Main: Logo + Token + Exchange prominent */}
        <div className="flex items-start gap-3">
          <img src={getTokenLogo(fused.symbol)} alt={fused.symbol} className="w-12 h-12 rounded-full bg-gray-100 object-contain" onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${fused.symbol}`; }} />
          <div className="flex-1">
            {/* Token name + price + exchange */}
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className="text-lg font-semibold text-gray-900">{fused.symbol}</span>
              <span className="text-sm text-gray-500">{fused.name}</span>
              <ArrowRight className="w-3.5 h-3.5 text-red-400" />
              <span className="text-lg font-bold text-red-600">{ld.exchange}</span>
              {fused.priceChange24h !== 0 && (
                <span className={`flex items-center gap-0.5 text-sm font-medium ${fused.priceChange24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                  {fused.priceChange24h >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                  {fused.priceChange24h >= 0 ? '+' : ''}{fused.priceChange24h.toFixed(2)}%
                </span>
              )}
            </div>

            {/* Listing metrics row */}
            <div className="flex items-start gap-5 mb-2 flex-wrap">
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Listing Score</div>
                <div className="text-sm text-red-600 font-bold">{ld.listingScore}</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Confidence</div>
                <div className={`text-sm font-semibold px-1.5 rounded ${confColor}`}>{ld.confidence}</div>
              </div>
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Event</div>
                <div className="text-sm text-gray-700 font-medium">{formatEventType(ld.eventType)}</div>
              </div>
              {vel && (
                <div>
                  <div className="text-[10px] text-gray-400 uppercase tracking-wider">Velocity</div>
                  <div className="text-sm text-blue-600 font-medium">{vel}</div>
                </div>
              )}
              {sentPct != null && (
                <div>
                  <div className="text-[10px] text-gray-400 uppercase tracking-wider">Sentiment</div>
                  <div className="text-sm text-gray-700 font-medium">{sentPct}%</div>
                </div>
              )}
              {fused.earlyData?.anomalyLevel && (
                <div>
                  <div className="text-[10px] text-gray-400 uppercase tracking-wider">Anomaly</div>
                  <div className="text-sm text-purple-600 font-medium">{fused.earlyData.anomalyLevel}</div>
                </div>
              )}
            </div>

            {/* Market Reaction */}
            {ld.marketReaction && (
              <div className="flex items-center gap-2 mb-2 bg-red-50/60 rounded-lg px-3 py-2">
                <ArrowUpRight className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
                <span className="text-xs text-gray-400 uppercase">Market Reaction</span>
                <span className="text-xs text-gray-500 flex-1">{ld.marketReaction.timeframe}</span>
                <span className="font-semibold text-sm text-red-700">{ld.marketReaction.typicalMove}</span>
                {ld.marketReaction.historicalAccuracy && <span className="text-xs text-emerald-600 font-medium">({ld.marketReaction.historicalAccuracy})</span>}
              </div>
            )}

            {/* Sources preview */}
            {ld.sources?.length > 0 && (
              <div className="mb-2">
                <div className="flex items-center gap-1.5 mb-1.5">
                  <MessageCircle className="w-3 h-3 text-gray-400" />
                  <span className="text-[10px] text-gray-400 uppercase tracking-wider font-medium">{ld.sourceCount || ld.sources.length} Sources</span>
                  {ld.sourceIsExchange && <span className="text-[9px] font-bold text-red-500 bg-red-50 border border-red-200 px-1.5 py-0.5 rounded">OFFICIAL EXCHANGE</span>}
                </div>
                {ld.sources.slice(0, 2).map((src, i) => (
                  <div key={i} className="text-xs text-gray-500 leading-relaxed pl-4 border-l-2 border-red-200 mb-1.5">
                    <span className={`font-medium ${src.type === 'twitter' ? 'text-blue-600' : 'text-gray-600'}`}>@{src.author}</span>
                    <span className="text-gray-300 mx-1">·</span>
                    <span>{src.text?.slice(0, 120)}{src.text?.length > 120 ? '...' : ''}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Expected Move (if signal data exists too) */}
            {sig.expectedMove && (
              <div className="flex items-center gap-2 mb-2 bg-white/80 rounded-lg px-3 py-2">
                <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                <span className="text-xs text-gray-400 uppercase">Expected Move</span>
                <span className="text-xs text-gray-500 flex-1">{sig.expectedMove.risk}</span>
                <span className="font-semibold text-sm text-amber-700">{sig.expectedMove.text}</span>
              </div>
            )}

            {/* Timeline */}
            <SignalTimeline fused={fused} />

            {/* Layer badges + rank */}
            <div className="flex items-center gap-2 mt-1.5">
              {fused.layers.map(layer => {
                const la = ACCENT[layer] || ACCENT.SIGNAL;
                return <span key={layer} className={`text-[10px] font-medium uppercase ${la.badge}`}>{layer === 'CONFLUENCE' ? 'TRIPLE' : layer}</span>;
              })}
              {sig.rank && <span className="text-[10px] text-amber-600 font-medium ml-auto">Top {sig.rank}</span>}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ═══ VARIANT 1: EARLY SIGNAL / DEFAULT — current amber style ═══
  const accent = ACCENT[fused.primaryType] || ACCENT.SIGNAL;
  const hasRichData = sig.setupType || vel || sentPct != null || fused.confluenceData;

  // No rich data → compact inline alert
  if (!hasRichData) {
    const typeLabel = fused.primaryType === 'LISTING' ? 'NEW LISTING' : fused.primaryType === 'LIVE_LISTING' ? 'LIVE ALERT' : fused.primaryType === 'EARLY' ? 'EARLY SIGNAL' : 'SIGNAL';
    return (
      <div className="flex items-center gap-3 rounded-lg bg-white border border-gray-200 border-l-4 border-l-red-400 px-4 py-2.5 cursor-pointer hover:bg-gray-50 transition-colors h-full flex-wrap"
        onClick={() => onClick?.(fused)} data-testid="hero-zone">
        <img src={getTokenLogo(fused.symbol)} alt={fused.symbol} className="w-6 h-6 rounded-full" onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${fused.symbol}`; }} />
        <span className={`text-xs font-medium uppercase ${accent.badge}`}>{typeLabel}</span>
        <span className="font-semibold text-gray-900">{fused.symbol}</span>
        <span className="text-sm text-gray-500">{fused.name}</span>
        {fused.listingData?.minutesAgo != null && <span className="text-sm text-gray-400 ml-auto">{formatTime(fused.listingData.minutesAgo)} ago</span>}
        <ChevronRight className="w-4 h-4 text-gray-300" />
      </div>
    );
  }

  // Rich data (Early Signal) → full hero card
  const typeLabel = fused.primaryType === 'CONFLUENCE' ? 'TRIPLE CONFLUENCE' : fused.primaryType === 'EARLY' ? 'EARLY SIGNAL' : sig.setupType || 'ACTIVE SIGNAL';

  return (
    <div className="rounded-lg border border-amber-200 bg-gradient-to-br from-amber-50/60 to-white p-4 cursor-pointer hover:shadow-md transition-shadow h-full"
      onClick={() => onClick?.(fused)} data-testid="hero-zone">

      {/* Header row: Badge + rarity + time */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-medium uppercase ${accent.badge}`}>{typeLabel}</span>
          {fused.confluenceData && <span className="text-xs text-amber-600">{fused.confluenceData.rarity}</span>}
        </div>
        <div className="flex items-center gap-1 text-gray-400 text-sm">
          <Clock className="w-3.5 h-3.5" />
          <span>{sig.age || (fused.earlyData?.minutesAgo != null ? formatTime(fused.earlyData.minutesAgo) : '')}</span>
        </div>
      </div>

      {/* Main: Logo + Content */}
      <div className="flex items-start gap-3">
        <img src={getTokenLogo(fused.symbol)} alt={fused.symbol} className="w-12 h-12 rounded-full bg-gray-100 object-contain" onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${fused.symbol}`; }} />
        <div className="flex-1">
          {/* Name + Price */}
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg font-semibold text-gray-900">{fused.symbol}</span>
            <span className="text-sm text-gray-500">{fused.name}</span>
            {fused.priceChange24h !== 0 && (
              <span className={`flex items-center gap-0.5 text-sm font-medium ${fused.priceChange24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {fused.priceChange24h >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                {fused.priceChange24h >= 0 ? '+' : ''}{fused.priceChange24h.toFixed(2)}%
              </span>
            )}
          </div>

          {/* Setup info */}
          {sig.setupType && (
            <div className="text-sm text-gray-600 mb-2">
              {sig.setupType} · {sig.signalMaturity} · <span className={sig.signalQuality === 'HIGH' ? 'text-emerald-600' : sig.signalQuality === 'MED' ? 'text-amber-600' : 'text-gray-400'}>{sig.signalQuality} Quality</span>
              {sig.alignment && <> · <span className={sig.alignment === 'STRONG' ? 'text-emerald-600' : sig.alignment === 'MIXED' ? 'text-amber-600' : 'text-red-600'}>{sig.alignment}</span></>}
            </div>
          )}

          {/* Data columns */}
          <div className="flex items-start gap-5 mb-2 flex-wrap">
            {vel && (
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Velocity</div>
                <div className="text-sm text-blue-600 font-medium">{vel}</div>
              </div>
            )}
            {sentPct != null && (
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Sentiment</div>
                <div className="text-sm text-gray-700 font-medium">{sentPct}%</div>
              </div>
            )}
            {fused.earlyData?.anomalyLevel && (
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Anomaly</div>
                <div className="text-sm text-purple-600 font-medium">{fused.earlyData.anomalyLevel}</div>
              </div>
            )}
            {fused.earlyData?.signalType && (
              <div>
                <div className="text-[10px] text-gray-400 uppercase tracking-wider">Signal Type</div>
                <div className="text-sm text-purple-600 font-medium">{formatEventType(fused.earlyData.signalType)}</div>
              </div>
            )}
          </div>

          {/* Expected Move */}
          {sig.expectedMove && (
            <div className="flex items-center gap-2 mb-2 bg-white/80 rounded-lg px-3 py-2">
              <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
              <span className="text-xs text-gray-400 uppercase">Expected Move</span>
              <span className="text-xs text-gray-500 flex-1">{sig.expectedMove.risk}</span>
              <span className="font-semibold text-sm text-amber-700">{sig.expectedMove.text}</span>
            </div>
          )}

          {/* Confluence details */}
          {fused.confluenceData && (
            <div className="text-xs text-gray-500 mb-2 leading-relaxed">
              Listing: {fused.confluenceData.listing.exchange} ({fused.confluenceData.listing.status}) · Anomaly: {fused.confluenceData.anomaly.level} ({fused.confluenceData.anomaly.velocityDisplay}) · Sent: {Math.round(fused.confluenceData.sentiment.value * 100)}%{fused.confluenceData.sentiment.shift != null ? ` (shift ${fused.confluenceData.sentiment.shift > 0 ? '+' : ''}${fused.confluenceData.sentiment.shift.toFixed(2)})` : ''}
            </div>
          )}

          {/* Timeline */}
          <SignalTimeline fused={fused} />

          {/* Layer badges (colored text) + rank */}
          <div className="flex items-center gap-2 mt-1.5">
            {fused.layers.map(layer => {
              const la = ACCENT[layer] || ACCENT.SIGNAL;
              return <span key={layer} className={`text-[10px] font-medium uppercase ${la.badge}`}>{layer === 'CONFLUENCE' ? 'TRIPLE' : layer}</span>;
            })}
            {sig.rank && <span className="text-[10px] text-amber-600 font-medium ml-auto">Top {sig.rank}</span>}
          </div>

          {/* Drivers */}
          {sig.drivers && sig.drivers.length > 0 && (
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <ArrowRight className="w-3 h-3 text-gray-400 flex-shrink-0" />
              <span className="text-xs text-gray-500">{sig.action || 'High probability continuation'}</span>
              {sig.drivers.slice(0, 3).map((d, i) => <span key={i} className="text-[10px] bg-gray-100 px-1.5 py-0.5 rounded text-gray-500">{d}</span>)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════
// FUSED SIGNAL CARD (LIVE FLOW) — airy, Twitter Sentiment style
// ═══════════════════════════════════════════
const FusedSignalCard = ({ fused, onClick }) => {
  const accent = ACCENT[fused.primaryType] || ACCENT.SIGNAL;
  const sig = fused.signal || {};
  const sentPct = fused.sentiment?.score != null ? Math.round(fused.sentiment.score * 100) : fused.confluenceData?.sentiment?.value != null ? Math.round(fused.confluenceData.sentiment.value * 100) : null;
  const vel = sig.velocityDisplay || fused.earlyData?.velocityDisplay || fused.confluenceData?.anomaly?.velocityDisplay;
  const typeLabel = fused.primaryType === 'CONFLUENCE' ? 'TRIPLE' : fused.primaryType === 'LIVE_LISTING' ? 'LIVE' : fused.primaryType === 'LISTING' ? 'LISTING' : fused.primaryType === 'EARLY' ? 'EARLY' : sig.setupType || 'SIGNAL';

  return (
    <div className={`rounded-lg bg-white border border-gray-200 border-l-4 ${accent.leftBorder} p-4 cursor-pointer hover:bg-gray-50 transition-colors`}
      onClick={() => onClick?.(fused)} data-testid={`signal-card-${fused.symbol}`}>
      <div className="flex items-start gap-3">
        {/* Logo */}
        <img src={getTokenLogo(fused.symbol)} alt={fused.symbol}
          className="w-10 h-10 rounded-full bg-gray-100 object-contain"
          onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${fused.symbol}`; }} />

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Row 1: Name + Ticker + Price */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-gray-900">{fused.symbol}</span>
            <span className="text-gray-500 text-sm">{fused.name}</span>
            {fused.priceChange24h !== 0 && (
              <span className={`text-sm font-medium ${fused.priceChange24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {fused.priceChange24h >= 0 ? '+' : ''}{fused.priceChange24h.toFixed(2)}%
              </span>
            )}
          </div>

          {/* Row 2: Setup + Maturity + Quality */}
          {sig.setupType && (
            <div className="text-sm text-gray-600 mt-1">
              {sig.setupType} · {sig.signalMaturity || 'EARLY'} · <span className={sig.signalQuality === 'HIGH' ? 'text-emerald-600' : sig.signalQuality === 'MED' ? 'text-amber-600' : 'text-gray-400'}>{sig.signalQuality} Quality</span>
              {sig.alignment && <> · <span className={sig.alignment === 'STRONG' ? 'text-emerald-600' : sig.alignment === 'MIXED' ? 'text-amber-600' : 'text-red-600'}>{sig.alignment}</span></>}
            </div>
          )}

          {/* Row 3: Data row — Vel + Sent + Exchange + Expected */}
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500 flex-wrap">
            {vel && <span>Vel: <span className="text-blue-600 font-medium">{vel}</span></span>}
            {sentPct != null && <span>Sent: <span className="text-gray-700 font-medium">{sentPct}%</span></span>}
            {fused.listingData && <span className="text-red-600">{fused.listingData.exchange} ({fused.listingData.status})</span>}
            {sig.expectedMove && (
              <span><ArrowUpRight className="w-3 h-3 inline text-emerald-600" /> <span className="text-emerald-600 font-medium">{sig.expectedMove.text}</span></span>
            )}
          </div>

          {/* Row 4: Risk warning */}
          {sig.riskContext && sig.riskContext.length > 0 && sig.riskContext[0] !== 'Normal conditions' && (
            <div className="flex items-center gap-1 text-xs text-amber-600 mt-1.5">
              <AlertTriangle className="w-3 h-3" />{sig.riskContext.join(' · ')}
            </div>
          )}

          {/* Timeline */}
          <SignalTimeline fused={fused} />
        </div>

        {/* Right: Layers + Rank + Chevron */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <div className="flex items-center gap-2">
            {fused.layers.length > 0 && (
              <span className="text-[10px] text-gray-400 font-medium uppercase">{fused.layers.map(l => l === 'CONFLUENCE' ? 'TRIPLE' : l).join(' · ')}</span>
            )}
            {sig.rank != null && sig.rank > 0 && sig.rank <= 5 && <span className="text-[10px] text-amber-600 font-medium">Top {sig.rank}</span>}
          </div>
          <ChevronRight className="w-4 h-4 text-gray-300" />
        </div>
      </div>
    </div>
  );
};

// ═══════════════════════════════════════════
// TWEET CARD
// ═══════════════════════════════════════════
const TweetCard = ({ tweet }) => (
  <div className="p-4 rounded-lg bg-white border border-gray-100">
    <div className="flex items-start gap-3">
      {tweet.type === 'news' ? (
        <div className="w-9 h-9 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
          <ExternalLink className="w-4 h-4 text-blue-500" />
        </div>
      ) : (
        <img src={tweet.avatar} alt={tweet.username} className="w-9 h-9 rounded-full bg-gray-100 object-cover flex-shrink-0"
          onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${tweet.username}`; }} />
      )}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900 text-sm">{tweet.username}</span>
          {tweet.type !== 'news' && <span className="text-gray-400 text-xs">{tweet.handle}</span>}
          <span className="text-gray-300 text-xs">· {tweet.timestamp}</span>
          {tweet.type === 'news' && <span className="text-[9px] text-blue-500 uppercase font-medium">News</span>}
        </div>
        <p className="text-gray-700 mt-1 leading-relaxed text-sm">{tweet.content}</p>
        <div className="flex items-center gap-4 mt-2 text-gray-400 text-xs">
          {tweet.type !== 'news' && (<>
            <span className="flex items-center gap-1"><Heart className="w-3 h-3" />{typeof tweet.metrics?.likes === 'number' ? tweet.metrics.likes.toLocaleString() : tweet.metrics?.likes}</span>
            <span className="flex items-center gap-1"><Repeat2 className="w-3 h-3" />{typeof tweet.metrics?.retweets === 'number' ? tweet.metrics.retweets.toLocaleString() : tweet.metrics?.retweets}</span>
            <span className="flex items-center gap-1"><Eye className="w-3 h-3" />{tweet.metrics?.views}</span>
          </>)}
          {tweet.url && (
            <a href={tweet.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-blue-500 hover:text-blue-600 ml-auto"
              onClick={(e) => e.stopPropagation()}>
              <ExternalLink className="w-3 h-3" />Source
            </a>
          )}
        </div>
      </div>
    </div>
  </div>
);

// ═══════════════════════════════════════════
// ASSET DETAIL MODAL — data-dense, all info
// ═══════════════════════════════════════════
const AssetDetailModal = ({ fused, open, onClose, tweets }) => {
  if (!fused) return null;
  const sig = fused.signal || {};
  const accent = ACCENT[fused.primaryType] || ACCENT.SIGNAL;
  const vel = sig.velocityDisplay || fused.earlyData?.velocityDisplay || fused.confluenceData?.anomaly?.velocityDisplay;
  const sentPct = fused.sentiment?.score != null ? Math.round(fused.sentiment.score * 100) : fused.confluenceData?.sentiment?.value != null ? Math.round(fused.confluenceData.sentiment.value * 100) : null;
  const typeLabel = fused.primaryType === 'CONFLUENCE' ? 'TRIPLE CONFLUENCE' : fused.primaryType === 'LIVE_LISTING' ? 'LIVE ALERT' : fused.primaryType === 'LISTING' ? 'NEW LISTING' : fused.primaryType === 'EARLY' ? 'EARLY SIGNAL' : sig.setupType || 'ACTIVE SIGNAL';

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl bg-white border-slate-200 p-0 max-h-[90vh] overflow-hidden" style={{ borderRadius: 12 }}>
        {/* Header: Logo + Ticker + Price + Type badge (single, no duplicates) */}
        <div className="sticky top-0 bg-white border-b border-slate-100 px-4 py-3 z-10">
          <div className="flex items-center gap-3">
            <img src={getTokenLogo(fused.symbol)} alt={fused.symbol} className="w-10 h-10 rounded-full bg-slate-100" onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${fused.symbol}`; }} />
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-slate-900">{fused.symbol}</h2>
                <span className="text-sm text-slate-400">{fused.name}</span>
                {fused.priceChange24h !== 0 && (
                  <span className={`flex items-center gap-0.5 font-bold text-sm ${fused.priceChange24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {fused.priceChange24h >= 0 ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                    {fused.priceChange24h >= 0 ? '+' : ''}{fused.priceChange24h.toFixed(2)}%
                  </span>
                )}
              </div>
              <span className={`text-xs font-medium uppercase ${accent.badge}`}>{typeLabel}</span>
            </div>
          </div>
        </div>

        {/* Data Grid: All available signal data */}
        <div className="px-4 py-3 border-b border-slate-100">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
            {sig.setupType && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Setup</div>
                <div className="text-xs font-medium text-gray-800">{sig.setupType}</div>
              </div>
            )}
            {sig.signalMaturity && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Maturity</div>
                <div className="text-xs font-medium text-gray-800">{sig.signalMaturity}</div>
              </div>
            )}
            {sig.signalQuality && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Quality</div>
                <div className={`text-xs font-medium ${sig.signalQuality === 'HIGH' ? 'text-emerald-600' : sig.signalQuality === 'MED' ? 'text-amber-600' : 'text-gray-500'}`}>{sig.signalQuality}</div>
              </div>
            )}
            {sig.alignment && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Alignment</div>
                <div className={`text-xs font-medium ${sig.alignment === 'STRONG' ? 'text-emerald-600' : sig.alignment === 'MIXED' ? 'text-amber-600' : 'text-red-600'}`}>{sig.alignment}</div>
              </div>
            )}
            {vel && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Velocity</div>
                <div className="text-xs font-medium text-blue-600">{vel}</div>
              </div>
            )}
            {sentPct != null && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Sentiment</div>
                <div className="text-xs font-medium text-gray-800">{sentPct}%</div>
              </div>
            )}
            {fused.listingData && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Exchange</div>
                <div className="text-xs font-medium text-red-600">{fused.listingData.exchange} ({fused.listingData.status})</div>
              </div>
            )}
            {fused.listingData?.listingScore != null && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Listing Score</div>
                <div className="text-xs font-medium text-gray-800">{fused.listingData.listingScore}</div>
              </div>
            )}
            {fused.listingData?.eventType && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Event Type</div>
                <div className="text-xs font-medium text-gray-600">{formatEventType(fused.listingData.eventType)}</div>
              </div>
            )}
            {fused.earlyData?.signalType && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Signal Type</div>
                <div className="text-xs font-medium text-purple-600">{formatEventType(fused.earlyData.signalType)}</div>
              </div>
            )}
            {fused.earlyData?.anomalyLevel && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Anomaly</div>
                <div className="text-xs font-medium text-purple-600">{fused.earlyData.anomalyLevel}</div>
              </div>
            )}
            {sig.rank && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Rank</div>
                <div className="text-xs font-medium text-amber-600">Top {sig.rank}</div>
              </div>
            )}
            {(sig.age || fused.listingData?.minutesAgo != null || fused.earlyData?.minutesAgo != null) && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Age</div>
                <div className="text-xs font-medium text-gray-600">{sig.age || (fused.listingData?.minutesAgo != null ? formatTime(fused.listingData.minutesAgo) : '') || (fused.earlyData?.minutesAgo != null ? formatTime(fused.earlyData.minutesAgo) : '')}</div>
              </div>
            )}
            {fused.tweets24h > 0 && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Tweets 24h</div>
                <div className="text-xs font-medium text-gray-600">{fused.tweets24h}</div>
              </div>
            )}
            {fused.influencerMentions > 0 && (
              <div>
                <div className="text-[9px] text-gray-400 uppercase tracking-wider font-medium">Influencer Mentions</div>
                <div className="text-xs font-medium text-gray-600">{fused.influencerMentions}</div>
              </div>
            )}
          </div>
        </div>

        {/* Expected Move */}
        {sig.expectedMove && (
          <div className="px-4 py-2.5 border-b border-slate-100">
            <div className="rounded-md bg-slate-50 border border-slate-200 p-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Expected Move</span>
                </div>
                <span className="text-sm font-semibold text-amber-700">{sig.expectedMove.text}</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-1 flex items-center gap-1"><Shield className="w-3 h-3" />{sig.expectedMove.risk}</div>
            </div>
          </div>
        )}

        {/* Risk Context */}
        {sig.riskContext && sig.riskContext.length > 0 && sig.riskContext[0] !== 'Normal conditions' && (
          <div className="px-4 py-2 border-b border-slate-100">
            <div className="flex items-center gap-1.5 text-xs text-amber-600"><AlertTriangle className="w-3 h-3" />{sig.riskContext.join(' · ')}</div>
          </div>
        )}

        {/* Confluence Details */}
        {fused.confluenceData && (
          <div className="px-4 py-2.5 border-b border-slate-100 bg-amber-50/30">
            <div className="text-[10px] font-semibold text-amber-800 mb-1">{fused.confluenceData.description}</div>
            <div className="text-[11px] text-amber-700 space-y-0.5">
              <div>Listing: {fused.confluenceData.listing.exchange} ({fused.confluenceData.listing.status})</div>
              <div>Anomaly: {fused.confluenceData.anomaly.level} ({fused.confluenceData.anomaly.velocityDisplay})</div>
              <div>Sentiment: {Math.round(fused.confluenceData.sentiment.value * 100)}%</div>
            </div>
          </div>
        )}

        {/* Timeline */}
        {(fused.earlyData || fused.listingData) && (
          <div className="px-4 py-2 border-b border-slate-100">
            <SignalTimeline fused={fused} />
          </div>
        )}

        {/* Drivers */}
        {sig.drivers && sig.drivers.length > 0 && (
          <div className="px-4 py-2.5 border-b border-slate-100">
            <div className="flex items-center gap-1.5 mb-1.5"><ArrowRight className="w-3 h-3 text-blue-500" /><span className="text-xs font-medium text-slate-700">{sig.action || 'Signal Drivers'}</span></div>
            <div className="flex flex-wrap gap-1.5">
              {sig.drivers.map((d, i) => <span key={i} className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-500">{d}</span>)}
            </div>
          </div>
        )}

        {/* Listing Sources — from listing detection engine */}
        {fused.listingData?.sources?.length > 0 && (
          <div className="px-4 py-2.5 border-b border-slate-100" data-testid="listing-sources">
            <h3 className="text-[10px] font-medium text-red-500 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Target className="w-3 h-3" />Listing Sources ({fused.listingData.sources.length})
            </h3>
            <div className="space-y-2">
              {fused.listingData.sources.map((src, i) => (
                <div key={i} className="rounded-md bg-red-50/50 border border-red-100 p-2.5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded ${src.type === 'twitter' ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'}`}>{src.type}</span>
                    <span className="text-xs font-medium text-slate-700">{src.author}</span>
                    {src.time && <span className="text-[10px] text-slate-400 ml-auto">{new Date(src.time).toLocaleString()}</span>}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">{src.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Market Reaction — for listings */}
        {fused.listingData?.marketReaction && (
          <div className="px-4 py-2.5 border-b border-slate-100">
            <div className="rounded-md bg-slate-50 border border-slate-200 p-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <ArrowUpRight className="w-3.5 h-3.5 text-red-500" />
                  <span className="text-[10px] text-slate-400 uppercase font-semibold">Market Reaction Pattern</span>
                </div>
                <span className="text-sm font-semibold text-red-600">{fused.listingData.marketReaction.typicalMove}</span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-slate-500 mt-1">
                <span>Timeframe: {fused.listingData.marketReaction.timeframe}</span>
                {fused.listingData.marketReaction.historicalAccuracy && <span>Accuracy: <span className="text-emerald-600 font-medium">{fused.listingData.marketReaction.historicalAccuracy}</span></span>}
              </div>
            </div>
          </div>
        )}

        {/* Tweets + News */}
        <ScrollArea className="max-h-[calc(90vh-350px)]">
          <div className="p-4 space-y-2">
            {tweets.length > 0 && (
              <>
                <h3 className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-2">Sources ({tweets.length})</h3>
                {tweets.map(tweet => <TweetCard key={tweet.id} tweet={tweet} />)}
              </>
            )}
            {tweets.length === 0 && !(fused.listingData?.sources?.length > 0) && (
              <div className="py-6 text-center text-slate-400"><MessageCircle className="w-5 h-5 mx-auto mb-1 opacity-50" /><p className="text-xs">No sources found</p></div>
            )}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
};

// ═══════════════════════════════════════════
// ALERT SOUND ENGINE
// ═══════════════════════════════════════════
const playAlertSound = (level = 'HIGH') => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain); gain.connect(ctx.destination);
    osc.type = level === 'HIGH' ? 'square' : 'sine';
    osc.frequency.value = level === 'HIGH' ? 880 : 660;
    gain.gain.value = 0.08;
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.3);
  } catch (e) { /* silent */ }
};

// ═══════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════
export default function TwitterAIPage() {
  const [loading, setLoading] = useState(true);
  const [correlations, setCorrelations] = useState([]);
  const [selectedFused, setSelectedFused] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [assetTweets, setAssetTweets] = useState([]);
  const [modelStats, setModelStats] = useState(null);
  const [listings, setListings] = useState(null);
  const [earlyData, setEarlyData] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [heroSlide, setHeroSlide] = useState(0);
  const alertedIdsRef = useRef(new Set());
  const lastAlertTimeRef = useRef(0);
  const SIGNALS_PER_PAGE = 10;

  useEffect(() => { fetchAll(); }, []);

  useEffect(() => {
    let li, si;
    const update = () => {
      const active = document.visibilityState === 'visible';
      clearInterval(li); clearInterval(si);
      li = setInterval(fetchListings, active ? 15000 : 60000);
      si = setInterval(() => { fetchCorrelations(); fetchEarlySignals(); }, active ? 30000 : 90000);
    };
    update();
    document.addEventListener('visibilitychange', update);
    return () => { clearInterval(li); clearInterval(si); document.removeEventListener('visibilitychange', update); };
  }, []);

  const fetchAll = () => { fetchCorrelations(); fetchModelStats(); fetchListings(); fetchEarlySignals(); };

  const fetchCorrelations = async () => {
    setLoading(true);
    try { const r = await fetch(`${API_URL}/api/v4/sentiment/correlations`); const d = await r.json(); if (d.ok) setCorrelations(d.data); }
    catch (e) { console.error(e); } finally { setLoading(false); }
  };
  const fetchModelStats = async () => {
    try { const r = await fetch(`${API_URL}/api/v4/sentiment/model-stats`); const d = await r.json(); if (d.ok) setModelStats(d.data); } catch (e) { console.error(e); }
  };
  const fetchListings = async () => {
    try {
      const r = await fetch(`${API_URL}/api/v4/sentiment/listings`); const d = await r.json(); if (!d.ok) return;
      setListings(d.data);
      const live = d.data.live || [];
      const newAlerts = live.filter(l => !alertedIdsRef.current.has(l.id));
      if (newAlerts.length > 0 && Date.now() - lastAlertTimeRef.current > 10000) {
        lastAlertTimeRef.current = Date.now();
        newAlerts.forEach(l => alertedIdsRef.current.add(l.id));
        playAlertSound(newAlerts.some(l => l.confidence === 'HIGH') ? 'HIGH' : 'MED');
        showAlertToast(newAlerts);
      }
    } catch (e) { console.error(e); }
  };
  const fetchEarlySignals = async () => {
    try { const r = await fetch(`${API_URL}/api/v4/sentiment/early-signals`); const d = await r.json(); if (d.ok) setEarlyData(d.data); } catch (e) { console.error(e); }
  };

  const showAlertToast = (alerts) => {
    const container = document.getElementById('alert-toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'fixed top-4 right-4 z-50 bg-red-600 text-white rounded-xl px-5 py-4 shadow-2xl max-w-sm';
    toast.setAttribute('data-testid', 'alert-toast');
    const title = alerts.length > 1 ? `${alerts.length} NEW LISTINGS DETECTED` : 'NEW LISTING DETECTED';
    const lines = alerts.map(a => `${a.token} -> ${a.exchange} | Score: ${a.listingScore}`).join('\n');
    toast.innerHTML = `<div class="font-bold text-sm mb-1">${title}</div><div class="text-xs opacity-90 whitespace-pre-line">${lines}</div>`;
    container.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.5s'; setTimeout(() => toast.remove(), 500); }, 6000);
  };

  const handleFusedClick = async (fused) => {
    setSelectedFused(fused);
    setModalOpen(true);
    setAssetTweets([]);
    const searchId = fused.symbol?.toLowerCase() || fused.entityId || fused.id;
    try { const r = await fetch(`${API_URL}/api/v4/sentiment/asset-tweets/${searchId}?limit=20`); const d = await r.json(); if (d.ok) setAssetTweets(d.data); } catch (e) { console.error(e); }
  };

  const fusedSignals = useMemo(() => buildFusedSignals(correlations, listings, earlyData), [correlations, listings, earlyData]);

  // Hero selection: Listing always takes priority as #1 hero, Early Signal as #2
  const bestListingSignal = useMemo(() => fusedSignals.find(f => f.listingData && f.listingData.eventType !== 'EXCHANGE_MENTION'), [fusedSignals]);
  const bestEarlySignal = useMemo(() => fusedSignals.find(f => {
    const sig = f.signal || {};
    return !f.listingData && (sig.setupType || f.earlyData || f.confluenceData);
  }), [fusedSignals]);

  // Primary hero: listing if exists, otherwise best overall
  const heroSignal = bestListingSignal || (fusedSignals.length > 0 ? fusedSignals[0] : null);
  // Secondary hero: early signal if listing took primary slot
  const secondaryHero = bestListingSignal && bestEarlySignal && bestListingSignal.symbol !== bestEarlySignal.symbol ? bestEarlySignal : null;

  // Hero slides array for slider
  const heroSlides = useMemo(() => {
    const slides = [];
    if (heroSignal) slides.push(heroSignal);
    if (secondaryHero) slides.push(secondaryHero);
    return slides;
  }, [heroSignal, secondaryHero]);

  // Auto-rotate hero slider
  useEffect(() => {
    if (heroSlides.length <= 1) return;
    const timer = setInterval(() => {
      setHeroSlide(prev => (prev + 1) % heroSlides.length);
    }, 7000);
    return () => clearInterval(timer);
  }, [heroSlides.length]);

  // Reset slide index when slides change
  useEffect(() => {
    if (heroSlide >= heroSlides.length) setHeroSlide(0);
  }, [heroSlides.length, heroSlide]);

  // Exclude hero signals from flow
  const heroSymbols = new Set([heroSignal?.symbol, secondaryHero?.symbol].filter(Boolean));

  // Only show signals with real data in the flow; move empty/mention-only to monitoring
  const hasRealData = (f) => {
    const sig = f.signal || {};
    return sig.setupType || sig.velocityDisplay || f.earlyData?.velocityDisplay || f.confluenceData ||
      (f.sentiment?.score != null && f.sentiment.score > 0) || f.tweets24h > 5;
  };
  const flowSignals = fusedSignals.filter(f => !heroSymbols.has(f.symbol)).filter(hasRealData);

  // Reset page when data changes
  useEffect(() => { setCurrentPage(1); }, [flowSignals.length]);

  const totalPages = Math.max(1, Math.ceil(flowSignals.length / SIGNALS_PER_PAGE));
  const paginatedSignals = flowSignals.slice((currentPage - 1) * SIGNALS_PER_PAGE, currentPage * SIGNALS_PER_PAGE);

  // Compute market pulse stats for Signal Engine card
  const activeSignalCount = fusedSignals.filter(s => s.signal?.type && s.signal.type !== 'NEUTRAL').length;
  const listingCount = (listings?.confirmed?.length || 0) + (listings?.live?.length || 0);
  const earlyCount = earlyData?.earlySignals?.length || 0;
  const confluenceCount = earlyData?.confluences?.length || 0;
  const momentumLevel = confluenceCount > 0 ? 'EXTREME' : activeSignalCount >= 5 ? 'HIGH' : activeSignalCount >= 2 ? 'MED' : 'LOW';

  const SIGNAL_DOT = { MOMENTUM: 'bg-emerald-500', ATTENTION: 'bg-amber-500', NEUTRAL: 'bg-gray-400' };

  return (
    <div className="min-h-screen bg-gray-50" style={{ fontFamily: "'Gilroy', sans-serif" }} data-testid="twitter-ai-page">
      <div id="alert-toast-container" />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-blue-500" />Signal Terminal
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">Real-time decision intelligence</p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchAll} disabled={loading} data-testid="refresh-correlations-btn">
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />Refresh
          </Button>
        </div>

        {/* Hero Slider — horizontal carousel with auto-rotation */}
        {heroSlides.length > 0 && (
          <div className="mb-4 relative" data-testid="hero-slider">
            {/* Slider viewport */}
            <div className="overflow-hidden rounded-lg">
              <div
                className="flex transition-transform duration-500 ease-in-out"
                style={{ transform: `translateX(-${heroSlide * 100}%)` }}
              >
                {heroSlides.map((slide, i) => (
                  <div key={slide.symbol} className="w-full flex-shrink-0" style={{ minWidth: '100%' }}>
                    <HeroCard fused={slide} onClick={handleFusedClick} />
                  </div>
                ))}
              </div>
            </div>

            {/* Navigation arrows */}
            {heroSlides.length > 1 && (
              <>
                <button
                  onClick={(e) => { e.stopPropagation(); setHeroSlide(prev => (prev - 1 + heroSlides.length) % heroSlides.length); }}
                  className="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/80 backdrop-blur-sm border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-white hover:text-gray-900 transition-all shadow-sm z-10"
                  data-testid="hero-slider-prev"
                >
                  <ChevronRight className="w-4 h-4 rotate-180" />
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); setHeroSlide(prev => (prev + 1) % heroSlides.length); }}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/80 backdrop-blur-sm border border-gray-200 flex items-center justify-center text-gray-500 hover:bg-white hover:text-gray-900 transition-all shadow-sm z-10"
                  data-testid="hero-slider-next"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </>
            )}

            {/* Dot indicators */}
            {heroSlides.length > 1 && (
              <div className="flex items-center justify-center gap-2 mt-2">
                {heroSlides.map((slide, i) => (
                  <button
                    key={slide.symbol}
                    onClick={() => setHeroSlide(i)}
                    className={`transition-all duration-300 rounded-full ${
                      i === heroSlide
                        ? 'w-6 h-2 bg-gray-800'
                        : 'w-2 h-2 bg-gray-300 hover:bg-gray-400'
                    }`}
                    data-testid={`hero-dot-${i}`}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Main Grid: Flow + Sidebar */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Live Signal Flow */}
          <div className="lg:col-span-2 space-y-2" data-testid="live-signal-flow">
            <div className="flex items-center gap-2 mb-1">
              <Activity className="w-4 h-4 text-blue-500" />
              <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider">Live Signal Flow</h2>
              <span className="text-[9px] font-medium px-2 py-0.5 rounded-full bg-blue-50 text-blue-600">{flowSignals.length}</span>
            </div>

            {loading && fusedSignals.length === 0 ? (
              <div className="space-y-3">{[1, 2, 3].map(i => <div key={i} className="rounded-xl bg-white border border-gray-200 p-4"><Skeleton className="h-24 w-full" /></div>)}</div>
            ) : (
              <>
                {paginatedSignals.map(f => <FusedSignalCard key={f.symbol} fused={f} onClick={handleFusedClick} />)}

                {/* Pagination Controls */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-1 pt-3 pb-1" data-testid="pagination-controls">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="px-2 py-1 text-xs text-gray-500 hover:text-gray-900 disabled:text-gray-300 disabled:cursor-not-allowed"
                      data-testid="pagination-prev"
                    >&lt;</button>
                    {Array.from({ length: totalPages }, (_, i) => i + 1).map(page => {
                      // Show: first, last, current, and neighbors; ellipsis for gaps
                      const show = page === 1 || page === totalPages || Math.abs(page - currentPage) <= 1;
                      const prevShow = page === 1 || page === totalPages || Math.abs((page - 1) - currentPage) <= 1 || (page - 1) === 1;
                      if (!show) {
                        if (prevShow) return <span key={page} className="px-1 text-xs text-gray-300">...</span>;
                        return null;
                      }
                      return (
                        <button
                          key={page}
                          onClick={() => setCurrentPage(page)}
                          className={`w-7 h-7 rounded text-xs font-medium transition-colors ${
                            page === currentPage
                              ? 'bg-gray-900 text-white'
                              : 'text-gray-500 hover:bg-gray-100'
                          }`}
                          data-testid={`pagination-page-${page}`}
                        >{page}</button>
                      );
                    })}
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="px-2 py-1 text-xs text-gray-500 hover:text-gray-900 disabled:text-gray-300 disabled:cursor-not-allowed"
                      data-testid="pagination-next"
                    >&gt;</button>
                  </div>
                )}

                {fusedSignals.length === 0 && !loading && (
                  <div className="rounded-xl bg-white border border-gray-200 py-16 text-center">
                    <BarChart3 className="w-8 h-8 mx-auto mb-3 text-gray-300" />
                    <p className="text-gray-400 text-sm">No active signals</p>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Signal Engine Stats — first */}
            <Card className="bg-gradient-to-br from-gray-800 to-gray-900 text-white border-0">
              <CardContent className="p-4">
                <h3 className="font-semibold mb-3 flex items-center gap-2 text-sm"><Target className="w-4 h-4" />Signal Engine</h3>
                {/* Market Pulse Stats — compact row */}
                <div className="flex items-center gap-2 flex-wrap mb-3 pb-3 border-b border-gray-700">
                  <div className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${momentumLevel === 'LOW' ? 'bg-gray-500' : 'bg-emerald-400 animate-pulse'}`} />
                    <span className="text-[10px] text-emerald-400 uppercase font-semibold tracking-wider">LIVE</span>
                  </div>
                  <span className="text-gray-600">|</span>
                  <span className="text-[10px] text-gray-400">Momentum <span className={`font-semibold ${momentumLevel === 'EXTREME' ? 'text-amber-400' : momentumLevel === 'HIGH' ? 'text-emerald-400' : momentumLevel === 'MED' ? 'text-yellow-400' : 'text-gray-500'}`}>{momentumLevel}</span></span>
                  <span className="text-[10px] text-gray-400">Listings <span className="font-semibold text-red-400">{listingCount}</span></span>
                  <span className="text-[10px] text-gray-400">Early <span className="font-semibold text-purple-400">{earlyCount}</span></span>
                  {confluenceCount > 0 && <span className="text-[10px] text-gray-400">Triple <span className="font-semibold text-amber-400">{confluenceCount}</span></span>}
                </div>
                {modelStats ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div><div className="text-gray-400 text-xs">Active</div><div className="text-xl font-semibold">{modelStats.activeAlerts || 0}</div></div>
                      <div><div className="text-gray-400 text-xs">Total</div><div className="text-xl font-semibold">{modelStats.totalAlerts}</div></div>
                    </div>
                    {modelStats.typeBreakdown && (
                      <div className="space-y-1.5 pt-2 border-t border-gray-700">
                        <div className="text-[10px] text-gray-400 uppercase tracking-wider">By Type</div>
                        {Object.entries(modelStats.typeBreakdown).filter(([k]) => k !== 'NEUTRAL').map(([type, data]) => (
                          <div key={type} className="flex items-center justify-between text-sm">
                            <div className="flex items-center gap-1.5"><span className={`w-1.5 h-1.5 rounded-full ${SIGNAL_DOT[type] || 'bg-gray-400'}`} /><span className="text-gray-300">{type}</span></div>
                            <span className="text-white font-medium">{data.count} ({data.avgScore})</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : <Skeleton className="h-16 w-full bg-gray-700" />}
              </CardContent>
            </Card>

            {/* Alpha Map — unique edge per asset, not signal duplication */}
            <div data-testid="market-map">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-amber-500" />
                <h2 className="text-xs font-medium text-gray-400 uppercase tracking-wider">Alpha Map</h2>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {fusedSignals.slice(0, 8).map(f => {
                  const accent = ACCENT[f.primaryType] || ACCENT.SIGNAL;
                  const vel = f.signal?.velocityDisplay || f.earlyData?.velocityDisplay;
                  const sentPct = f.sentiment?.score != null ? Math.round(f.sentiment.score * 100) : null;
                  // Determine the unique alpha edge for this asset
                  let alphaEdge = null;
                  if (f.confluenceData) alphaEdge = { label: 'Triple Confluence', color: 'text-amber-600' };
                  else if (f.isLive) alphaEdge = { label: `LIVE ${f.listingData?.exchange || ''}`, color: 'text-red-600' };
                  else if (f.listingData && f.listingData.eventType !== 'EXCHANGE_MENTION') alphaEdge = { label: `${f.listingData.exchange} listing`, color: 'text-red-600' };
                  else if (f.earlyData?.anomalyLevel === 'HIGH') alphaEdge = { label: 'High Anomaly', color: 'text-purple-600' };
                  else if (vel) alphaEdge = { label: vel, color: 'text-blue-600' };

                  return (
                    <div key={f.symbol} className={`rounded-lg border ${accent.border} bg-white p-3 cursor-pointer hover:shadow-sm transition-all`}
                      onClick={() => handleFusedClick(f)} data-testid={`market-map-${f.symbol}`}>
                      <div className="flex items-center gap-2 mb-1.5">
                        <img src={getTokenLogo(f.symbol)} alt="" className="w-5 h-5 rounded-full" onError={(e) => { e.target.src = `https://api.dicebear.com/7.x/initials/svg?seed=${f.symbol}`; }} />
                        <span className="text-sm font-semibold text-gray-900">{f.symbol}</span>
                      </div>
                      {alphaEdge && <div className={`text-[10px] font-medium ${alphaEdge.color} mb-1`}>{alphaEdge.label}</div>}
                      <div className="flex items-center justify-between text-[10px]">
                        {sentPct != null && <span className="text-gray-400">Sent <span className="text-gray-600 font-medium">{sentPct}%</span></span>}
                        {f.priceChange24h !== 0 && (
                          <span className={`font-medium ${f.priceChange24h >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                            {f.priceChange24h >= 0 ? '+' : ''}{f.priceChange24h.toFixed(1)}%
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Link to Twitter Feed */}
            <Card className="bg-white border-dashed border-2 border-gray-200">
              <CardContent className="p-4 text-center">
                <MessageCircle className="w-6 h-6 text-gray-400 mx-auto mb-2" />
                <p className="text-xs text-gray-500 mb-2">Individual post signals</p>
                <Link to="/sentiment/twitter"><Button variant="outline" size="sm">Twitter Feed</Button></Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      <AssetDetailModal fused={selectedFused} open={modalOpen} onClose={() => setModalOpen(false)} tweets={assetTweets} />
    </div>
  );
}
