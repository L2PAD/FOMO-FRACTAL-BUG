import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useMiniApp } from '../../../context/MiniAppContext';

const DIR_COLORS = { BUY: '#10b981', SELL: '#ef4444', WAIT: '#eab308' };

export function EdgeScreen() {
  const { edgeData, fetchEdge, setActiveTab, setSelectedAsset, trackEvent } = useMiniApp();
  const [tracked, setTracked] = useState(false);

  useEffect(() => {
    if (!edgeData) fetchEdge();
    if (!tracked) { trackEvent('edge_viewed', { source: 'edge_tab' }); setTracked(true); }
  }, [edgeData, fetchEdge, trackEvent, tracked]);

  if (!edgeData) return <EdgeLoading />;

  const isActive = edgeData.status === 'ACTIVE';
  const best = edgeData.best;
  const markets = edgeData.markets || [];

  return (
    <div data-testid="edge-screen" style={{ flex: 1, overflowY: 'auto', paddingBottom: '80px' }}>
      {/* Header */}
      <div style={{ padding: '16px 16px 8px' }}>
        <h2 style={{
          fontSize: '18px', fontWeight: 700, color: 'var(--ma-text)',
          fontFamily: "'Manrope', sans-serif", letterSpacing: '-0.02em',
        }}>
          Edge Engine
        </h2>
        <p style={{ fontSize: '12px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", marginTop: '2px' }}>
          Where model sees money
        </p>
      </div>

      {isActive && best ? (
        <>
          <BestEdgeCard edge={best} onOpenAsset={(a) => { setSelectedAsset(a); setActiveTab('home'); }} />

          {/* Priority-based edge sections */}
          {(() => {
            const rest = markets.filter(m => m !== best);
            const strong = rest.filter(m => (m.priorityScore || 0) >= 0.55 && m.status !== 'watching');
            const other = rest.filter(m => (m.priorityScore || 0) < 0.55 && m.status !== 'watching');
            const watching = rest.filter(m => m.status === 'watching');
            return (
              <div style={{ padding: '16px' }}>
                {strong.length > 0 && (
                  <>
                    <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '10px' }}>
                      Strong Edges
                    </div>
                    {strong.map((m, i) => (
                      <MarketRow key={`s-${m.asset}-${i}`} market={m} index={i} onOpenAsset={(a) => { setSelectedAsset(a); setActiveTab('home'); }} />
                    ))}
                  </>
                )}
                {other.length > 0 && (
                  <CollapsibleSection label="Other Edges" count={other.length}>
                    {other.map((m, i) => (
                      <MarketRow key={`o-${m.asset}-${i}`} market={m} index={i} onOpenAsset={(a) => { setSelectedAsset(a); setActiveTab('home'); }} />
                    ))}
                  </CollapsibleSection>
                )}
                {watching.length > 0 && (
                  <CollapsibleSection label="Watching" count={watching.length}>
                    {watching.map((m, i) => (
                      <MarketRow key={`w-${m.asset}-${i}`} market={m} index={i} onOpenAsset={(a) => { setSelectedAsset(a); setActiveTab('home'); }} />
                    ))}
                  </CollapsibleSection>
                )}
              </div>
            );
          })()}
        </>
      ) : (
        <NoEdgeState reason={edgeData.reason} explanation={edgeData.explanation} markets={markets} />
      )}
    </div>
  );
}


function BestEdgeCard({ edge, onOpenAsset }) {
  const [showWhy, setShowWhy] = useState(false);
  const edgePct = (edge.edge * 100).toFixed(1);
  const color = DIR_COLORS[edge.direction] || '#a1a1aa';
  const isNeg = edge.edge < 0;
  const tier = edge.confidenceTier || 'STANDARD';
  const ttl = edge.ttlHours;

  const tierConfig = {
    EXTREME: { label: 'EXTREME EDGE', color: '#ef4444', bg: 'rgba(239,68,68,0.12)' },
    HIGH_CONVICTION: { label: 'HIGH CONVICTION', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' },
    STANDARD: { label: edge.priorityLabel || 'LIVE EDGE', color: 'var(--ma-muted)', bg: 'var(--ma-stat-bg)' },
  };
  const tc = tierConfig[tier] || tierConfig.STANDARD;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="best-edge-card"
      style={{
        margin: '0 16px',
        padding: '20px',
        background: `radial-gradient(ellipse at top left, ${color}10, #18181b 70%)`,
        borderRadius: '20px',
        border: `1px solid ${color}30`,
      }}
    >
      {/* Tier badge + TTL */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
        <span data-testid="edge-tier-badge" style={{
          fontSize: '9px', fontWeight: 800, letterSpacing: '0.15em',
          color: tc.color, background: tc.bg, padding: '3px 10px',
          borderRadius: '20px', fontFamily: "'Oswald', sans-serif",
          textTransform: 'uppercase',
        }}>
          {tc.label}
        </span>
        {ttl && (
          <span data-testid="edge-ttl" style={{
            fontSize: '9px', fontWeight: 600, color: 'var(--ma-muted)',
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            Valid ~{ttl}h
          </span>
        )}
      </div>

      {/* Asset */}
      <div style={{
        fontSize: '12px', fontWeight: 700, color: 'var(--ma-secondary)',
        fontFamily: "'JetBrains Mono', monospace", marginBottom: '6px',
      }}>
        {edge.asset}
      </div>

      {/* Question */}
      <div style={{
        fontSize: '15px', color: 'var(--ma-text)',
        fontFamily: "'Manrope', sans-serif", fontWeight: 600,
        marginBottom: '12px', lineHeight: 1.4,
      }}>
        {edge.question}
      </div>

      {/* Loss framing line */}
      <div data-testid="edge-loss-framing" style={{
        fontSize: '11px', fontWeight: 600, color: color,
        fontFamily: "'Manrope', sans-serif", marginBottom: '14px',
        opacity: 0.9,
      }}>
        Market mispriced by {Math.abs(parseFloat(edgePct))}%
      </div>

      {/* Probabilities */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <DataCol label="Market" value={`${Math.round(edge.marketProbability * 100)}%`} />
        <DataCol label="Model" value={`${Math.round(edge.modelProbability * 100)}%`} />
        <DataCol label="Edge" value={`${isNeg ? '' : '+'}${edgePct}%`} color={color} />
      </div>

      {/* Action */}
      <div data-testid="edge-direction" style={{
        padding: '12px',
        borderRadius: '12px',
        background: `${color}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <span style={{
          fontSize: '14px', fontWeight: 700, color,
          fontFamily: "'Oswald', sans-serif", letterSpacing: '0.1em', textTransform: 'uppercase',
        }}>
          {edge.direction}
        </span>
        <span style={{
          fontSize: '11px', fontWeight: 600, color: 'var(--ma-muted)',
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          Confidence: {Math.round(edge.confidence * 100)}%
        </span>
      </div>

      {/* Why */}
      {edge.reason && edge.reason.length > 0 && (
        <div style={{ marginTop: '12px' }}>
          <button
            onClick={() => setShowWhy(!showWhy)}
            data-testid="edge-why-toggle"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              width: '100%', padding: '0', background: 'transparent', border: 'none', cursor: 'pointer',
            }}
          >
            <span style={{
              fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
              color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif",
            }}>
              Why This Edge
            </span>
            {showWhy ? <ChevronUp size={14} color="var(--ma-muted)" /> : <ChevronDown size={14} color="var(--ma-muted)" />}
          </button>

          <AnimatePresence>
            {showWhy && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                style={{ overflow: 'hidden' }}
              >
                <div style={{ paddingTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {edge.reason.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
                      <div style={{ width: '4px', height: '4px', borderRadius: '50%', background: '#52525b', marginTop: '7px', flexShrink: 0 }} />
                      <span style={{ fontSize: '12px', color: '#a1a1aa', fontFamily: "'Manrope', sans-serif", lineHeight: 1.4 }}>
                        {r}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* CTA */}
      <button
        data-testid="edge-open-asset"
        onClick={() => onOpenAsset(edge.asset)}
        style={{
          marginTop: '14px', width: '100%', padding: '10px',
          borderRadius: '12px', background: `${color}18`, border: `1px solid ${color}30`,
          color, fontSize: '12px', fontWeight: 700, fontFamily: "'Manrope', sans-serif",
          cursor: 'pointer', textTransform: 'uppercase', letterSpacing: '0.08em',
        }}
      >
        Open {edge.asset} Analysis
      </button>
    </motion.div>
  );
}


function MarketRow({ market, index, onOpenAsset }) {
  const edgePct = (market.edge * 100).toFixed(1);
  const isWatching = market.status === 'watching';
  const color = isWatching ? 'var(--ma-muted)' : (DIR_COLORS[market.direction] || 'var(--ma-secondary)');
  const tier = market.confidenceTier || 'STANDARD';
  const ttl = market.ttlHours;

  return (
    <motion.button
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: index * 0.04 }}
      data-testid={`edge-market-${market.asset}`}
      onClick={() => onOpenAsset(market.asset)}
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 0', borderBottom: '1px solid rgba(39,39,42,0.4)',
        width: '100%', background: 'transparent', border: 'none',
        borderBottomWidth: '1px', borderBottomStyle: 'solid', borderBottomColor: 'var(--ma-divider, var(--ma-border))',
        cursor: 'pointer', textAlign: 'left',
      }}
    >
      <div style={{ flex: 1, minWidth: 0, marginRight: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ma-text)', fontFamily: "'JetBrains Mono', monospace" }}>
            {market.asset}
          </span>
          {isWatching && (
            <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace", background: 'var(--ma-stat-bg)', padding: '1px 6px', borderRadius: '20px' }}>
              WATCHING
            </span>
          )}
          {!isWatching && tier !== 'STANDARD' && (
            <span style={{
              fontSize: '8px', fontWeight: 700,
              color: tier === 'EXTREME' ? '#ef4444' : '#f59e0b',
              background: tier === 'EXTREME' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
              padding: '1px 6px', borderRadius: '20px',
              fontFamily: "'Oswald', sans-serif", letterSpacing: '0.1em',
            }}>
              {tier === 'EXTREME' ? 'EXTREME' : 'HIGH'}
            </span>
          )}
        </div>
        <div style={{ fontSize: '12px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {market.question}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        {!isWatching && (
          <>
            <div style={{ fontSize: '13px', fontWeight: 700, color, fontFamily: "'JetBrains Mono', monospace" }}>
              {market.edge > 0 ? '+' : ''}{edgePct}%
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '6px' }}>
              <span style={{ fontSize: '10px', fontWeight: 600, color, fontFamily: "'Manrope', sans-serif", textTransform: 'uppercase' }}>
                {market.direction}
              </span>
              {ttl && (
                <span style={{ fontSize: '8px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                  ~{ttl}h
                </span>
              )}
            </div>
          </>
        )}
        {isWatching && (
          <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
            0%
          </div>
        )}
      </div>
    </motion.button>
  );
}


function NoEdgeState({ reason, explanation, markets }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      data-testid="no-edge-state"
      style={{ margin: '0 16px' }}
    >
      <div style={{
        padding: '28px 20px',
        background: 'var(--ma-surface)',
        borderRadius: '20px',
        border: '1px solid var(--ma-border)',
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: '14px', fontWeight: 600, color: 'var(--ma-secondary)',
          fontFamily: "'Manrope', sans-serif", marginBottom: '8px',
        }}>
          No strong edges right now
        </div>
        <div style={{
          fontSize: '12px', color: 'var(--ma-muted)',
          fontFamily: "'Manrope', sans-serif", lineHeight: 1.5,
        }}>
          {explanation || reason || 'Edge appears when model and market diverge significantly'}
        </div>
      </div>

      {/* Watching list */}
      {markets && markets.length > 0 && (
        <div style={{ marginTop: '16px' }}>
          <div style={{
            fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em',
            color: 'var(--ma-muted)', textTransform: 'uppercase',
            fontFamily: "'Manrope', sans-serif", marginBottom: '10px',
          }}>
            Watching
          </div>
          {markets.map((m, i) => (
            <div key={i} style={{
              padding: '10px 0', borderBottom: '1px solid var(--ma-divider, var(--ma-border))',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
              <div>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace" }}>
                  {m.asset}
                </span>
                <span style={{ fontSize: '11px', color: 'var(--ma-muted)', fontFamily: "'Manrope', sans-serif", marginLeft: '8px' }}>
                  {m.question}
                </span>
              </div>
              <span style={{ fontSize: '9px', fontWeight: 600, color: 'var(--ma-muted)', fontFamily: "'JetBrains Mono', monospace", background: 'var(--ma-stat-bg)', padding: '2px 6px', borderRadius: '20px' }}>
                WAIT
              </span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}


function DataCol({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: '10px', color: 'var(--ma-muted)', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif", marginBottom: '2px' }}>
        {label}
      </div>
      <div style={{ fontSize: '20px', fontWeight: 700, color: color || 'var(--ma-text)', fontFamily: "'JetBrains Mono', monospace" }}>
        {value}
      </div>
    </div>
  );
}


function CollapsibleSection({ label, count, children }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: '16px' }}>
      <button
        onClick={() => setOpen(!open)}
        data-testid={`collapse-${label.toLowerCase().replace(/\s/g, '-')}`}
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          width: '100%', padding: '0', background: 'transparent', border: 'none', cursor: 'pointer',
          marginBottom: '8px',
        }}
      >
        <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.15em', color: 'var(--ma-muted)', textTransform: 'uppercase', fontFamily: "'Manrope', sans-serif" }}>
          {label} ({count})
        </span>
        {open ? <ChevronUp size={14} color="var(--ma-muted)" /> : <ChevronDown size={14} color="var(--ma-muted)" />}
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: 'hidden' }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


function EdgeLoading() {
  return (
    <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ height: '30px', background: 'var(--ma-surface)', borderRadius: '8px', animation: 'pulse 1.5s ease infinite' }} />
      <div style={{ height: '220px', background: 'var(--ma-surface)', borderRadius: '16px', animation: 'pulse 1.5s ease infinite' }} />
      <div style={{ height: '80px', background: 'var(--ma-surface)', borderRadius: '16px', animation: 'pulse 1.5s ease infinite' }} />
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}

