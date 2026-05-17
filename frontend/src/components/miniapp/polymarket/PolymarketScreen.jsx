import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useMiniApp } from '../../../context/MiniAppContext';

const CATEGORIES = ['Crypto', 'Macro', 'Politics', 'Trending'];

export function PolymarketScreen() {
  const { polyData, fetchPoly } = useMiniApp();
  const [category, setCategory] = useState('Crypto');

  useEffect(() => { if (!polyData) fetchPoly(); }, [polyData, fetchPoly]);

  const spotlight = polyData?.spotlight;
  const markets = polyData?.markets || [];

  return (
    <div data-testid="polymarket-screen" style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 8px' }}>
        <h2 style={{
          fontSize: '18px',
          fontWeight: 700,
          color: '#fafafa',
          fontFamily: "'Manrope', sans-serif",
          letterSpacing: '-0.02em',
        }}>
          Polymarket Edge
        </h2>
        <p style={{ fontSize: '12px', color: '#52525b', fontFamily: "'Manrope', sans-serif", marginTop: '2px' }}>
          Where model sees money
        </p>
      </div>

      {/* Category filters */}
      <div style={{ display: 'flex', gap: '6px', padding: '0 16px 12px', overflowX: 'auto' }}>
        {CATEGORIES.map(c => (
          <button
            key={c}
            data-testid={`poly-cat-${c.toLowerCase()}`}
            onClick={() => setCategory(c)}
            style={{
              padding: '6px 14px',
              borderRadius: '20px',
              border: category === c ? 'none' : '1px solid #27272a',
              background: category === c ? '#fafafa' : 'transparent',
              color: category === c ? '#09090b' : '#a1a1aa',
              fontSize: '12px',
              fontWeight: 600,
              fontFamily: "'Manrope', sans-serif",
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {c}
          </button>
        ))}
      </div>

      {/* Spotlight */}
      {spotlight ? (
        <SpotlightCard market={spotlight} />
      ) : (
        <div style={{
          margin: '0 16px',
          padding: '32px 16px',
          background: '#18181b',
          borderRadius: '16px',
          border: '1px solid #27272a',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '14px', color: '#52525b', fontFamily: "'Manrope', sans-serif" }}>
            No active markets with edge
          </div>
          <div style={{ fontSize: '12px', color: '#3f3f46', fontFamily: "'Manrope', sans-serif", marginTop: '4px' }}>
            Edge data will appear when prediction markets are active
          </div>
        </div>
      )}

      {/* Market list */}
      {markets.length > 0 && (
        <div style={{ padding: '16px' }}>
          <div style={{
            fontSize: '10px',
            fontWeight: 700,
            letterSpacing: '0.15em',
            color: '#52525b',
            textTransform: 'uppercase',
            fontFamily: "'Manrope', sans-serif",
            marginBottom: '12px',
          }}>
            All Markets
          </div>
          {markets.map((m, i) => (
            <MarketRow key={i} market={m} index={i} />
          ))}
        </div>
      )}
    </div>
  );
}


function SpotlightCard({ market }) {
  const edgePct = (market.edge * 100).toFixed(1);
  const isPositive = market.edge > 0;
  const actionColor = market.action === 'BUY_YES' ? '#10b981' : market.action === 'BUY_NO' ? '#ef4444' : '#a1a1aa';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="poly-spotlight"
      style={{
        margin: '0 16px',
        padding: '20px',
        background: `radial-gradient(ellipse at top left, ${actionColor}10, #18181b 70%)`,
        borderRadius: '20px',
        border: `1px solid ${actionColor}30`,
      }}
    >
      <div style={{
        fontSize: '10px',
        fontWeight: 700,
        letterSpacing: '0.15em',
        color: '#52525b',
        textTransform: 'uppercase',
        fontFamily: "'Manrope', sans-serif",
        marginBottom: '8px',
      }}>
        Best Edge Now
      </div>
      <div style={{ fontSize: '14px', color: '#fafafa', fontFamily: "'Manrope', sans-serif", fontWeight: 600, marginBottom: '16px', lineHeight: 1.4 }}>
        {market.market}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div>
          <div style={{ fontSize: '10px', color: '#52525b', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>Market</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#fafafa', fontFamily: "'JetBrains Mono', monospace" }}>{Math.round(market.market_prob * 100)}%</div>
        </div>
        <div>
          <div style={{ fontSize: '10px', color: '#52525b', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>Model</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: '#fafafa', fontFamily: "'JetBrains Mono', monospace" }}>{Math.round(market.model_prob * 100)}%</div>
        </div>
        <div>
          <div style={{ fontSize: '10px', color: '#52525b', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>Edge</div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: isPositive ? '#4ade80' : '#f87171', fontFamily: "'JetBrains Mono', monospace" }}>
            {isPositive ? '+' : ''}{edgePct}%
          </div>
        </div>
      </div>

      <div style={{
        padding: '12px',
        borderRadius: '12px',
        background: `${actionColor}15`,
        textAlign: 'center',
      }}>
        <span style={{ fontSize: '14px', fontWeight: 700, color: actionColor, fontFamily: "'Oswald', sans-serif", letterSpacing: '0.1em', textTransform: 'uppercase' }}>
          {market.action.replace('_', ' ')}
        </span>
      </div>
    </motion.div>
  );
}


function MarketRow({ market, index }) {
  const edgePct = (market.edge * 100).toFixed(1);
  const isPositive = market.edge > 0;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.03 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 0',
        borderBottom: '1px solid rgba(39,39,42,0.4)',
      }}
    >
      <div style={{ flex: 1, minWidth: 0, marginRight: '12px' }}>
        <div style={{ fontSize: '13px', color: '#a1a1aa', fontFamily: "'Manrope', sans-serif", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {market.market}
        </div>
      </div>
      <div style={{
        fontSize: '13px',
        fontWeight: 700,
        color: isPositive ? '#4ade80' : '#f87171',
        fontFamily: "'JetBrains Mono', monospace",
        flexShrink: 0,
      }}>
        {isPositive ? '+' : ''}{edgePct}%
      </div>
    </motion.div>
  );
}
