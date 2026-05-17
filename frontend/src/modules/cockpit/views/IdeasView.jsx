/**
 * IdeasView.jsx — Ideas Evolution Tracker (REDESIGNED v2)
 * ========================================================
 *
 * Layout:
 *   ┌──────────────────────────────────────────────────────┐
 *   │  Header (title · stats · filters · refresh)          │
 *   ├──────────────────────────────────────────────────────┤
 *   │  IdeaCard                                            │
 *   │    ▸ Asset row (symbol + tf + age + status)          │
 *   │    ▸ Featured "Current Snapshot" (pattern, levels,   │
 *   │      bias, probability, interpretation)              │
 *   │    ▸ Evolution strip (horizontal scroll, compact     │
 *   │      version chips with active state, hover detail)  │
 *   │    ▸ Stats grid (4 KPI tiles)                        │
 *   │    ▸ Actions (chart / delete)                        │
 *   └──────────────────────────────────────────────────────┘
 *
 * No layout overflow regardless of versions count.
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import styled, { css, keyframes } from 'styled-components';
import {
  Bookmark,
  RefreshCw,
  CheckCircle2,
  XCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronLeft,
  ChevronRight,
  Zap,
  Trash2,
  ExternalLink,
  AlertCircle,
  Loader2,
  Activity,
  Target,
  Sparkles,
} from 'lucide-react';
import { useMarket } from '../../../store/marketStore';

/* ════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ════════════════════════════════════════════════════════════ */
const T = {
  bg:        '#f6f7fb',
  surface:   '#ffffff',
  surface2:  '#f9fafc',
  border:    '#e6eaf2',
  borderHi:  '#d2d9e7',
  text:      '#0f172a',
  text2:     '#475569',
  text3:     '#94a3b8',
  primary:   '#3b82f6',
  primaryBg: 'rgba(59,130,246,0.08)',
  green:     '#16a34a',
  greenBg:   'rgba(34,197,94,0.10)',
  red:       '#dc2626',
  redBg:     'rgba(239,68,68,0.10)',
  amber:     '#d97706',
  amberBg:   'rgba(217,119,6,0.10)',
};

const spin = keyframes`from { transform: rotate(0); } to { transform: rotate(360deg); }`;

/* ════════════════════════════════════════════════════════════
   LAYOUT
   ════════════════════════════════════════════════════════════ */
const Container = styled.div`
  padding: 22px 26px 60px;
  min-height: calc(100vh - 140px);
  background: ${T.bg};
  box-sizing: border-box;
  /* Hard contain inner cards no matter how big inner content is */
  max-width: 100%;
  overflow-x: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 22px;
`;

const Title = styled.h2`
  font-size: 19px;
  font-weight: 700;
  color: ${T.text};
  margin: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  letter-spacing: -0.01em;

  svg { color: ${T.primary}; }
`;

const TitleSubtle = styled.span`
  font-size: 12px;
  font-weight: 500;
  color: ${T.text3};
  margin-left: 4px;
`;

const Controls = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
`;

const FilterBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: 8px;
  border: 1px solid ${({ $active }) => ($active ? T.primary : T.border)};
  background: ${({ $active }) => ($active ? T.primaryBg : T.surface)};
  color: ${({ $active }) => ($active ? T.primary : T.text2)};
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s ease;
  white-space: nowrap;
  font-family: inherit;

  svg { width: 12px; height: 12px; }
  .count { font-weight: 700; opacity: ${({ $active }) => ($active ? 1 : 0.7)}; }

  &:hover {
    border-color: ${T.primary};
    color: ${T.primary};
  }
`;

const IconBtn = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid ${T.border};
  background: ${T.surface};
  color: ${T.text2};
  cursor: pointer;
  transition: all 0.12s ease;

  svg { width: 15px; height: 15px; }

  &:hover { border-color: ${T.primary}; color: ${T.primary}; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
  &.spinning svg { animation: ${spin} 1s linear infinite; }
`;

/* ════════════════════════════════════════════════════════════
   IDEA CARD
   ════════════════════════════════════════════════════════════ */
const IdeasList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

const IdeaCard = styled.article`
  background: ${T.surface};
  border-radius: 14px;
  border: 1px solid ${T.border};
  padding: 0;
  overflow: hidden;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:hover {
    border-color: ${T.borderHi};
    box-shadow: 0 4px 18px rgba(15, 23, 42, 0.04);
  }
`;

const TopBar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid ${T.border};
  gap: 12px;
  flex-wrap: wrap;
`;

const AssetGroup = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
`;

const Symbol = styled.div`
  font-size: 17px;
  font-weight: 700;
  color: ${T.text};
  letter-spacing: -0.01em;
`;

const TFChip = styled.span`
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  background: ${T.surface2};
  border-radius: 6px;
  color: ${T.text2};
  border: 1px solid ${T.border};
`;

const Age = styled.span`
  font-size: 12px;
  color: ${T.text3};
  &::before { content: '·'; margin: 0 8px; color: ${T.text3}; }
`;

const StatusPill = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;

  svg { width: 13px; height: 13px; }

  ${({ $status }) => {
    if ($status === 'completed') return css`background: ${T.greenBg}; color: ${T.green};`;
    if ($status === 'invalidated') return css`background: ${T.redBg}; color: ${T.red};`;
    return css`background: ${T.primaryBg}; color: ${T.primary};`;
  }}
`;

/* ════════════════════════════════════════════════════════════
   FEATURED CURRENT SNAPSHOT
   ════════════════════════════════════════════════════════════ */
const Featured = styled.div`
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 18px;
  padding: 20px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const FeaturedLeft = styled.div`
  min-width: 0;
`;

const FeaturedKicker = styled.div`
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: ${T.text3};
  text-transform: uppercase;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 6px;

  svg { width: 12px; height: 12px; color: ${T.primary}; }
`;

const PatternHeading = styled.div`
  font-size: 22px;
  font-weight: 700;
  color: ${T.text};
  text-transform: capitalize;
  margin: 0 0 10px 0;
  letter-spacing: -0.015em;
  line-height: 1.2;
  word-wrap: break-word;
`;

const BiasRow = styled.div`
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
`;

const BiasChip = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  text-transform: capitalize;

  svg { width: 12px; height: 12px; }

  ${({ $bias }) => {
    if ($bias === 'bullish') return css`background: ${T.greenBg}; color: ${T.green};`;
    if ($bias === 'bearish') return css`background: ${T.redBg}; color: ${T.red};`;
    return css`background: ${T.surface2}; color: ${T.text2}; border: 1px solid ${T.border};`;
  }}
`;

const ConfidenceTrack = styled.div`
  position: relative;
  height: 6px;
  background: ${T.surface2};
  border-radius: 999px;
  overflow: hidden;
  margin-top: 4px;
`;

const ConfidenceFill = styled.div`
  position: absolute;
  inset: 0 auto 0 0;
  width: ${({ $pct }) => Math.max(0, Math.min(100, $pct))}%;
  background: ${({ $pct }) =>
    $pct >= 70 ? T.green :
    $pct >= 50 ? T.amber :
    T.red};
  border-radius: 999px;
  transition: width 0.4s ease;
`;

const ConfidenceLabel = styled.div`
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: ${T.text3};
  font-weight: 500;
  margin-bottom: 6px;

  .pct {
    font-weight: 700;
    color: ${({ $pct }) =>
      $pct >= 70 ? T.green :
      $pct >= 50 ? T.amber :
      T.text2};
  }
`;

const Interpretation = styled.p`
  font-size: 13px;
  color: ${T.text2};
  line-height: 1.55;
  margin: 14px 0 0 0;
  padding: 12px 14px;
  background: ${T.surface2};
  border-radius: 10px;
  border-left: 3px solid ${T.primary};
  word-wrap: break-word;
`;

/* Right side stats */
const FeaturedRight = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 10px;
  align-content: start;
`;

const StatTile = styled.div`
  background: ${T.surface2};
  border: 1px solid ${T.border};
  border-radius: 10px;
  padding: 12px 14px;
  min-width: 0;

  ${({ $span }) => $span && css`grid-column: span ${$span};`}

  .label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: ${T.text3};
    text-transform: uppercase;
    margin-bottom: 6px;
  }

  .value {
    font-size: 16px;
    font-weight: 700;
    color: ${T.text};
    line-height: 1.2;
    word-wrap: break-word;
  }

  .sub {
    font-size: 11px;
    color: ${T.text3};
    margin-top: 3px;
  }

  &.positive .value { color: ${T.green}; }
  &.negative .value { color: ${T.red}; }
`;

const ProbBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;

  .seg {
    height: 5px;
    border-radius: 999px;
    flex: 1;
    background: ${T.surface};
    border: 1px solid ${T.border};
    overflow: hidden;
    position: relative;
  }
  .seg-fill {
    position: absolute;
    inset: 0 auto 0 0;
    width: ${({ $pct }) => Math.max(0, Math.min(100, $pct))}%;
    background: ${({ $color }) => $color || T.primary};
    transition: width 0.3s ease;
  }
  .seg-pct {
    font-size: 11px;
    font-weight: 700;
    color: ${T.text2};
    min-width: 32px;
    text-align: right;
  }
`;

/* ════════════════════════════════════════════════════════════
   EVOLUTION STRIP
   ════════════════════════════════════════════════════════════ */
const EvolutionWrap = styled.div`
  border-top: 1px solid ${T.border};
  padding: 16px 20px;
  background: ${T.surface2};
`;

const EvolutionHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;

  .left {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: ${T.text3};
    text-transform: uppercase;

    .count {
      background: ${T.surface};
      color: ${T.text2};
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid ${T.border};
      letter-spacing: 0;
      text-transform: none;
    }
  }

  .nav {
    display: flex;
    gap: 4px;
  }

  .nav button {
    width: 26px;
    height: 26px;
    border-radius: 6px;
    border: 1px solid ${T.border};
    background: ${T.surface};
    color: ${T.text2};
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    transition: all 0.12s;
    font-family: inherit;
  }
  .nav button:hover:not(:disabled) {
    border-color: ${T.primary};
    color: ${T.primary};
  }
  .nav button:disabled { opacity: 0.4; cursor: default; }
  .nav svg { width: 14px; height: 14px; }
`;

const StripScroll = styled.div`
  display: flex;
  gap: 10px;
  overflow-x: auto;
  overflow-y: hidden;
  scroll-behavior: smooth;
  padding: 4px 2px 8px;

  /* Scrollbar */
  &::-webkit-scrollbar { height: 6px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: ${T.border};
    border-radius: 999px;
  }
  &::-webkit-scrollbar-thumb:hover { background: ${T.borderHi}; }
`;

const VChip = styled.button`
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 10px 12px;
  min-width: 130px;
  max-width: 180px;
  border-radius: 10px;
  border: 1px solid ${({ $active }) => ($active ? T.primary : T.border)};
  background: ${({ $active }) => ($active ? T.primaryBg : T.surface)};
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
  font-family: inherit;
  position: relative;

  &:hover {
    border-color: ${T.primary};
    transform: translateY(-1px);
  }

  ${({ $active }) =>
    $active &&
    css`
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.18);
    `}

  .v-tag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: ${({ $active }) => ($active ? T.primary : T.text3)};
    text-transform: uppercase;
  }

  .v-tag .dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: ${({ $active, $bias }) =>
      $active
        ? T.primary
        : $bias === 'bullish'
        ? T.green
        : $bias === 'bearish'
        ? T.red
        : T.text3};
  }

  .v-pattern {
    font-size: 12px;
    font-weight: 600;
    color: ${T.text};
    text-transform: capitalize;
    line-height: 1.25;
    overflow: hidden;
    text-overflow: ellipsis;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    word-break: break-word;
    width: 100%;
  }

  .v-meta {
    font-size: 10px;
    color: ${T.text3};
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .v-conf { font-weight: 700; color: ${T.text2}; }
`;

/* ════════════════════════════════════════════════════════════
   VALIDATION ROW
   ════════════════════════════════════════════════════════════ */
const ValidationRow = styled.div`
  margin: 0 20px 16px;
  padding: 11px 14px;
  background: ${({ $result }) =>
    $result === 'correct' ? T.greenBg :
    $result === 'invalidated' ? T.redBg :
    T.surface2};
  border-radius: 10px;
  border-left: 3px solid ${({ $result }) =>
    $result === 'correct' ? T.green :
    $result === 'invalidated' ? T.red :
    T.text3};
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: ${T.text2};
  flex-wrap: wrap;

  .v-label {
    font-weight: 700;
    color: ${({ $result }) =>
      $result === 'correct' ? T.green :
      $result === 'invalidated' ? T.red :
      T.text2};
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .v-price { font-weight: 600; color: ${T.text}; }
  .v-pnl {
    font-weight: 700;
    color: ${({ $pnl }) => ($pnl > 0 ? T.green : $pnl < 0 ? T.red : T.text2)};
  }
  .v-notes { color: ${T.text3}; font-size: 11px; }
`;

/* ════════════════════════════════════════════════════════════
   ACTIONS
   ════════════════════════════════════════════════════════════ */
const Actions = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px 18px;
  border-top: 1px solid ${T.border};
`;

const ActionBtn = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px;
  border-radius: 8px;
  border: 1px solid ${T.border};
  background: ${T.surface};
  color: ${T.text2};
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.12s;
  font-family: inherit;

  svg { width: 13px; height: 13px; }

  &:hover { border-color: ${T.primary}; color: ${T.primary}; }
  &.danger:hover { border-color: ${T.red}; color: ${T.red}; }
  &:disabled { opacity: 0.5; cursor: not-allowed; }

  &.spinning svg { animation: ${spin} 1s linear infinite; }
`;

/* ════════════════════════════════════════════════════════════
   STATES
   ════════════════════════════════════════════════════════════ */
const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;
  background: ${T.surface};
  border-radius: 14px;
  border: 1px dashed ${T.border};

  svg.icn { width: 44px; height: 44px; color: ${T.borderHi}; margin-bottom: 14px; }
  h4 { font-size: 16px; font-weight: 700; color: ${T.text}; margin: 0 0 8px 0; }
  p { font-size: 13px; color: ${T.text2}; margin: 0; max-width: 360px; line-height: 1.5; }
`;

const LoadingState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  text-align: center;

  svg { width: 30px; height: 30px; color: ${T.primary}; animation: ${spin} 1s linear infinite; }
  p { font-size: 14px; color: ${T.text2}; margin-top: 12px; }
`;

const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: ${T.redBg};
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  margin-bottom: 16px;
  font-size: 13px;
  color: ${T.red};

  svg { width: 16px; height: 16px; flex-shrink: 0; }
`;

/* ════════════════════════════════════════════════════════════
   API
   ════════════════════════════════════════════════════════════ */
const API_URL = process.env.REACT_APP_BACKEND_URL || '';

async function fetchIdeasAPI() {
  const res = await fetch(`${API_URL}/api/ta/ideas?full=true`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  const data = await res.json();
  return data.ideas || [];
}
async function deleteIdeaAPI(ideaId) {
  const res = await fetch(`${API_URL}/api/ta/ideas/${ideaId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
  return await res.json();
}
async function seedIdeasAPI() {
  const res = await fetch(`${API_URL}/api/ta/ideas/seed`, { method: 'POST' });
  if (!res.ok) throw new Error(`Seed failed: ${res.status}`);
  return await res.json();
}

/* ════════════════════════════════════════════════════════════
   HELPERS
   ════════════════════════════════════════════════════════════ */
const formatDate = (isoString) => {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return '—';
  }
};

const ageString = (isoString) => {
  if (!isoString) return '';
  try {
    const created = new Date(isoString).getTime();
    const now = Date.now();
    const diff = Math.max(0, now - created);
    const days = Math.floor(diff / 86_400_000);
    const hours = Math.floor((diff % 86_400_000) / 3_600_000);
    if (days > 0) return `${days}d ${hours}h ago`;
    if (hours > 0) return `${hours}h ago`;
    const mins = Math.floor(diff / 60_000);
    if (mins > 0) return `${mins}m ago`;
    return 'just now';
  } catch {
    return '';
  }
};

const getStatusLabel = (status) => {
  if (status === 'completed') return 'Completed';
  if (status === 'invalidated') return 'Invalidated';
  return 'Active';
};

const getStatusIcon = (status) => {
  if (status === 'completed') return <CheckCircle2 />;
  if (status === 'invalidated') return <XCircle />;
  return <Zap />;
};

const formatPattern = (pattern) =>
  !pattern ? 'Unknown pattern' : String(pattern).replace(/_/g, ' ');

const getBias = (snap, version) =>
  (snap?.technical_bias || version?.technical_bias || snap?.direction || 'neutral').toLowerCase();

const BiasIcon = ({ bias }) => {
  if (bias === 'bullish') return <TrendingUp />;
  if (bias === 'bearish') return <TrendingDown />;
  return <Minus />;
};

const fmtPrice = (n) => {
  if (n == null || isNaN(n)) return '—';
  if (n >= 1000) return n.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (n >= 1) return n.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return Number(n).toPrecision(4);
};

/* ════════════════════════════════════════════════════════════
   IDEA CARD COMPONENT
   ════════════════════════════════════════════════════════════ */
const IdeaCardItem = ({ idea, onView, onDelete, deleting }) => {
  const stripRef = useRef(null);
  const versions = idea.versions || [];
  const [activeIdx, setActiveIdx] = useState(Math.max(0, versions.length - 1));
  // Keep activeIdx in sync if versions length changes
  useEffect(() => {
    setActiveIdx(Math.max(0, versions.length - 1));
  }, [versions.length]);

  const activeVersion = versions[activeIdx] || versions[versions.length - 1] || {};
  const snap = activeVersion.setup_snapshot || {};
  const conf = Math.round(((snap.confidence ?? activeVersion.confidence) || 0) * 100);
  const bias = getBias(snap, activeVersion);
  const prob = snap.probability || {};
  const probUp = Math.round((prob.up || 0) * 100);
  const probDown = Math.round((prob.down || 0) * 100);
  const levels = snap.levels || {};
  const validations = idea.validations || [];
  const lastValidation = validations[validations.length - 1];

  // Auto-scroll latest version into view on first render
  useEffect(() => {
    if (!stripRef.current) return;
    const el = stripRef.current;
    el.scrollLeft = el.scrollWidth;
  }, [versions.length]);

  const scrollBy = (delta) => {
    if (!stripRef.current) return;
    stripRef.current.scrollBy({ left: delta, behavior: 'smooth' });
  };

  return (
    <IdeaCard data-testid={`idea-card-${idea.idea_id}`}>
      <TopBar>
        <AssetGroup>
          <Symbol>{(idea.asset || '').replace('USDT', '')}</Symbol>
          <TFChip>{idea.timeframe}</TFChip>
          <Age>{ageString(idea.created_at)}</Age>
          <Age>v{versions.length} version{versions.length === 1 ? '' : 's'}</Age>
        </AssetGroup>

        <StatusPill $status={idea.status} data-testid={`status-${idea.idea_id}`}>
          {getStatusIcon(idea.status)}
          {getStatusLabel(idea.status)}
        </StatusPill>
      </TopBar>

      {/* FEATURED CURRENT/SELECTED VERSION */}
      <Featured>
        <FeaturedLeft>
          <FeaturedKicker>
            <Sparkles />
            {activeIdx === versions.length - 1 ? 'Current snapshot' : `Snapshot · V${activeVersion.version || activeIdx + 1}`}
          </FeaturedKicker>

          <PatternHeading>{formatPattern(snap.pattern)}</PatternHeading>

          <BiasRow>
            <BiasChip $bias={bias}>
              <BiasIcon bias={bias} />
              {bias}
            </BiasChip>
            <span style={{ fontSize: 12, color: T.text3 }}>
              {fmtPrice(activeVersion.price_at_creation || snap.price)} · {formatDate(activeVersion.timestamp)}
            </span>
          </BiasRow>

          <ConfidenceLabel $pct={conf}>
            <span>Confidence</span>
            <span className="pct">{conf}%</span>
          </ConfidenceLabel>
          <ConfidenceTrack>
            <ConfidenceFill $pct={conf} />
          </ConfidenceTrack>

          {snap.interpretation && (
            <Interpretation>{snap.interpretation}</Interpretation>
          )}
        </FeaturedLeft>

        <FeaturedRight>
          <StatTile>
            <div className="label">Breakout ↑</div>
            <div className="value">{probUp}%</div>
            <ProbBar $pct={probUp} $color={T.green}>
              <div className="seg"><div className="seg-fill" /></div>
            </ProbBar>
          </StatTile>

          <StatTile>
            <div className="label">Breakdown ↓</div>
            <div className="value">{probDown}%</div>
            <ProbBar $pct={probDown} $color={T.red}>
              <div className="seg"><div className="seg-fill" /></div>
            </ProbBar>
          </StatTile>

          <StatTile $span={2}>
            <div className="label">Key Levels</div>
            <div className="value" style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
              <span style={{ color: T.green }}>↑ {fmtPrice(levels.top)}</span>
              <span style={{ color: T.text3, fontSize: 13 }}>/</span>
              <span style={{ color: T.red }}>↓ {fmtPrice(levels.bottom)}</span>
            </div>
            <div className="sub">
              Accuracy:{' '}
              <strong style={{
                color: idea.accuracy_score > 0.5 ? T.green :
                       idea.accuracy_score === 0 ? T.red : T.text2,
              }}>
                {idea.accuracy_score != null ? `${Math.round(idea.accuracy_score * 100)}%` : 'N/A'}
              </strong>
            </div>
          </StatTile>
        </FeaturedRight>
      </Featured>

      {/* VALIDATION (if any) */}
      {lastValidation && (
        <ValidationRow $result={lastValidation.result} $pnl={lastValidation.price_change_pct}>
          <span className="v-label">
            {lastValidation.result === 'correct' ? '✓ Correct' :
             lastValidation.result === 'invalidated' ? '✗ Invalidated' :
             lastValidation.result}
          </span>
          {lastValidation.price_at_validation != null && (
            <span className="v-price">@ ${fmtPrice(lastValidation.price_at_validation)}</span>
          )}
          {lastValidation.price_change_pct != null && (
            <span className="v-pnl">
              {lastValidation.price_change_pct > 0 ? '+' : ''}{lastValidation.price_change_pct?.toFixed(2)}%
            </span>
          )}
          {lastValidation.notes && <span className="v-notes">— {lastValidation.notes}</span>}
        </ValidationRow>
      )}

      {/* EVOLUTION STRIP */}
      {versions.length > 0 && (
        <EvolutionWrap>
          <EvolutionHeader>
            <div className="left">
              <Activity size={12} /> Evolution
              <span className="count">{versions.length} version{versions.length === 1 ? '' : 's'}</span>
            </div>
            {versions.length > 4 && (
              <div className="nav">
                <button onClick={() => scrollBy(-260)} aria-label="Scroll left">
                  <ChevronLeft />
                </button>
                <button onClick={() => scrollBy(260)} aria-label="Scroll right">
                  <ChevronRight />
                </button>
              </div>
            )}
          </EvolutionHeader>

          <StripScroll ref={stripRef} data-testid={`timeline-${idea.idea_id}`}>
            {versions.map((v, idx) => {
              const sn = v.setup_snapshot || {};
              const c = Math.round(((sn.confidence ?? v.confidence) || 0) * 100);
              const b = getBias(sn, v);
              const isActive = idx === activeIdx;
              return (
                <VChip
                  key={v.version ?? idx}
                  $active={isActive}
                  $bias={b}
                  onClick={() => setActiveIdx(idx)}
                  data-testid={`version-chip-${idea.idea_id}-${idx}`}
                  title={`V${v.version ?? idx + 1} · ${formatPattern(sn.pattern)} · ${c}% · ${b}`}
                >
                  <span className="v-tag">
                    <span className="dot" />
                    {idx === versions.length - 1 ? 'Current' : `V${v.version ?? idx + 1}`}
                  </span>
                  <span className="v-pattern">{formatPattern(sn.pattern)}</span>
                  <span className="v-meta">
                    <span className="v-conf">{c}%</span>
                    <span>·</span>
                    <span style={{ textTransform: 'capitalize' }}>{b}</span>
                  </span>
                </VChip>
              );
            })}
          </StripScroll>
        </EvolutionWrap>
      )}

      <Actions>
        <ActionBtn
          onClick={() => onView(idea.asset, idea.timeframe)}
          data-testid={`view-chart-${idea.idea_id}`}
        >
          <ExternalLink /> View in Chart
        </ActionBtn>
        <ActionBtn
          className={`danger${deleting ? ' spinning' : ''}`}
          onClick={() => onDelete(idea.idea_id)}
          disabled={deleting}
          data-testid={`delete-${idea.idea_id}`}
        >
          {deleting ? <Loader2 /> : <Trash2 />}
          {deleting ? 'Removing…' : 'Remove'}
        </ActionBtn>
      </Actions>
    </IdeaCard>
  );
};

/* ════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ════════════════════════════════════════════════════════════ */
const IdeasView = ({ onNavigateToChart }) => {
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [deletingId, setDeletingId] = useState(null);
  const { setSymbol, setTimeframe } = useMarket();

  const loadIdeas = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let items = await fetchIdeasAPI();
      if (items.length === 0) {
        try {
          await seedIdeasAPI();
          items = await fetchIdeasAPI();
        } catch (e) {
          /* swallow seed failure — empty state will guide user */
        }
      }
      setIdeas(items);
    } catch (err) {
      console.error('Failed to fetch ideas:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadIdeas(); }, [loadIdeas]);

  const handleDelete = useCallback(async (ideaId) => {
    if (deletingId) return;
    setDeletingId(ideaId);
    try {
      await deleteIdeaAPI(ideaId);
      setIdeas(prev => prev.filter(i => i.idea_id !== ideaId));
    } catch (err) {
      console.error('Failed to delete idea:', err);
      setError(`Failed to delete: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  }, [deletingId]);

  const handleViewInChart = useCallback((asset, timeframe) => {
    if (asset) setSymbol(asset);
    if (timeframe) setTimeframe(String(timeframe).toLowerCase());
    if (onNavigateToChart) onNavigateToChart(asset, timeframe);
  }, [setSymbol, setTimeframe, onNavigateToChart]);

  const filteredIdeas = useMemo(() => {
    if (filter === 'all') return ideas;
    return ideas.filter(i => i.status === filter);
  }, [ideas, filter]);

  const stats = useMemo(() => {
    const completed = ideas.filter(i => i.status === 'completed').length;
    const invalidated = ideas.filter(i => i.status === 'invalidated').length;
    const active = ideas.filter(i => i.status === 'active').length;
    return { completed, invalidated, active };
  }, [ideas]);

  if (loading) {
    return (
      <Container data-testid="ideas-view">
        <LoadingState>
          <Loader2 />
          <p>Loading ideas…</p>
        </LoadingState>
      </Container>
    );
  }

  return (
    <Container data-testid="ideas-view">
      <Header>
        <Title>
          <Bookmark size={20} />
          Saved Ideas
          <TitleSubtle>· Track patterns & their evolution</TitleSubtle>
        </Title>

        <Controls>
          <FilterBtn
            $active={filter === 'all'}
            onClick={() => setFilter('all')}
            data-testid="filter-all"
          >
            All <span className="count">{ideas.length}</span>
          </FilterBtn>
          <FilterBtn
            $active={filter === 'active'}
            onClick={() => setFilter('active')}
            data-testid="filter-active"
          >
            <Zap /> Active <span className="count">{stats.active}</span>
          </FilterBtn>
          <FilterBtn
            $active={filter === 'completed'}
            onClick={() => setFilter('completed')}
            data-testid="filter-completed"
          >
            <CheckCircle2 /> Completed <span className="count">{stats.completed}</span>
          </FilterBtn>
          <FilterBtn
            $active={filter === 'invalidated'}
            onClick={() => setFilter('invalidated')}
            data-testid="filter-invalidated"
          >
            <XCircle /> Invalidated <span className="count">{stats.invalidated}</span>
          </FilterBtn>
          <IconBtn
            onClick={loadIdeas}
            disabled={loading}
            className={loading ? 'spinning' : ''}
            data-testid="refresh-btn"
            aria-label="Refresh"
          >
            <RefreshCw />
          </IconBtn>
        </Controls>
      </Header>

      {error && (
        <ErrorBanner data-testid="error-banner">
          <AlertCircle />
          {error}
        </ErrorBanner>
      )}

      {filteredIdeas.length === 0 ? (
        <EmptyState data-testid="empty-state">
          <Bookmark className="icn" />
          <h4>No saved ideas{filter !== 'all' ? ` in "${filter}"` : ''}</h4>
          <p>
            {filter !== 'all'
              ? 'Try switching to "All" filter to see all your saved ideas.'
              : 'Save patterns from the Research tab to track their evolution and accuracy over time.'}
          </p>
        </EmptyState>
      ) : (
        <IdeasList data-testid="ideas-list">
          {filteredIdeas.map(idea => (
            <IdeaCardItem
              key={idea.idea_id}
              idea={idea}
              onView={handleViewInChart}
              onDelete={handleDelete}
              deleting={deletingId === idea.idea_id}
            />
          ))}
        </IdeasList>
      )}
    </Container>
  );
};

export default IdeasView;
