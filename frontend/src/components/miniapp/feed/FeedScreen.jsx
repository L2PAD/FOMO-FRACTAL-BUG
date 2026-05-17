import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useMiniApp } from '../../../context/MiniAppContext';

const FILTERS = ['All', 'High', 'Favorites', 'Alerts'];
const DIR_COLORS = { BULLISH: '#4ade80', BEARISH: '#f87171', NEUTRAL: '#a1a1aa' };
const IMPACT_COLORS = { HIGH: '#f87171', MED: '#facc15', LOW: '#71717a' };
const TYPE_ICONS = { whale: 'W', sentiment: 'S', exchange: 'E', risk: 'R', system: 'A' };

export function FeedScreen() {
  const { feedData, fetchFeed } = useMiniApp();
  const [filter, setFilter] = useState('All');

  useEffect(() => { if (!feedData) fetchFeed(); }, [feedData, fetchFeed]);

  // feedData is now { sections: [...], counts: {...} }
  const sections = feedData?.sections || [];
  const counts = feedData?.counts || {};

  const filterItems = (items) => {
    if (filter === 'All') return items;
    if (filter === 'High') return items.filter(i => i.impact === 'HIGH');
    return items;
  };

  return (
    <div data-testid="feed-screen" style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 8px' }}>
        <h2 style={{
          fontSize: '18px', fontWeight: 700, color: 'var(--ma-text)',
          fontFamily: "'Manrope', sans-serif", letterSpacing: '-0.02em',
        }}>
          Signal Feed
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", marginTop: '2px' }}>
          What matters right now
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: '6px', padding: '0 16px 12px', overflowX: 'auto' }}>
        {FILTERS.map(f => (
          <button
            key={f}
            data-testid={`feed-filter-${f.toLowerCase()}`}
            onClick={() => setFilter(f)}
            style={{
              padding: '6px 14px', borderRadius: '20px',
              border: filter === f ? 'none' : '1px solid var(--ma-border)',
              background: filter === f ? 'var(--ma-text)' : 'transparent',
              color: filter === f ? 'var(--ma-bg)' : 'var(--ma-secondary)',
              fontSize: '12px', fontWeight: 600, fontFamily: "'Manrope', sans-serif",
              cursor: 'pointer', whiteSpace: 'nowrap',
              display: 'flex', alignItems: 'center', gap: '4px',
            }}
          >
            {f}
            {f === 'High' && counts.high > 0 && (
              <span style={{
                fontSize: '10px', fontWeight: 700,
                color: filter === f ? '#ef4444' : '#f87171',
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {counts.high}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Sections */}
      <div style={{ padding: '0 16px' }}>
        {sections.map((section) => {
          const items = filterItems(section.items);
          if (items.length === 0) return null;
          return (
            <div key={section.label} style={{ marginBottom: '16px' }}>
              <div style={{
                fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
                color: 'var(--ma-muted)', textTransform: 'uppercase',
                fontFamily: "'Manrope', sans-serif",
                padding: '4px 0 8px',
              }}>
                {section.label}
              </div>
              {items.map((item, i) => (
                <FeedItem key={i} item={item} index={i} />
              ))}
            </div>
          );
        })}

        {sections.every(s => filterItems(s.items).length === 0) && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--ma-muted)', fontSize: '13px', fontFamily: "'Manrope', sans-serif" }}>
            No signals match this filter
          </div>
        )}
      </div>
    </div>
  );
}


function FeedItem({ item, index }) {
  const impactColor = IMPACT_COLORS[item.impact] || '#71717a';
  const dirColor = DIR_COLORS[item.direction] || '#a1a1aa';
  const icon = TYPE_ICONS[item.source] || '?';

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03 }}
      style={{
        padding: '12px',
        background: item.impact === 'HIGH' ? 'rgba(239,68,68,0.04)' : 'transparent',
        borderRadius: '12px',
        marginBottom: '4px',
        border: item.impact === 'HIGH' ? '1px solid rgba(239,68,68,0.1)' : '1px solid transparent',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
        {/* Icon */}
        <div style={{
          width: '32px', height: '32px', borderRadius: '8px',
          background: `${dirColor}12`, border: `1px solid ${dirColor}20`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '13px', fontFamily: "'JetBrains Mono', monospace",
          fontWeight: 700, color: dirColor, flexShrink: 0,
        }}>
          {icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Header: asset + direction + impact */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px', flexWrap: 'wrap' }}>
            {item.asset && (
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--ma-text)', fontFamily: "'JetBrains Mono', monospace" }}>
                {item.asset}
              </span>
            )}
            <span style={{
              fontSize: '10px', fontWeight: 700, color: dirColor,
              fontFamily: "'JetBrains Mono', monospace", textTransform: 'uppercase',
            }}>
              {item.direction}
            </span>
            <span style={{
              fontSize: '9px', fontWeight: 700, color: impactColor,
              fontFamily: "'JetBrains Mono', monospace",
              background: `${impactColor}18`, padding: '1px 6px', borderRadius: '20px',
            }}>
              {item.impact}
            </span>
          </div>

          {/* Title */}
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--ma-text)', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>
            {item.title}
          </div>

          {/* Summary */}
          <div style={{
            fontSize: '12px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif",
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {item.summary}
          </div>

          {/* Interpretation */}
          {item.interpretation && (
            <div style={{
              fontSize: '11px', color: '#52525b', fontFamily: "'Manrope', sans-serif",
              fontStyle: 'italic', marginTop: '4px',
            }}>
              &rarr; {item.interpretation}
            </div>
          )}

          {/* Timestamp */}
          <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace", marginTop: '4px' }}>
            {formatTime(item.timestamp)}
          </div>
        </div>
      </div>
    </motion.div>
  );
}


function formatTime(ts) {
  if (!ts) return '';
  try {
    const d = new Date(ts);
    const now = new Date();
    const min = Math.floor((now - d) / 60000);
    if (min < 1) return 'now';
    if (min < 60) return `${min}m ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  } catch { return ''; }
}

