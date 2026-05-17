import { motion } from 'framer-motion';

export function MiniAppEdge({ data }) {
  const { polymarket, asset } = data;
  const hasEdge = polymarket.market_prob > 0 && polymarket.action !== 'SKIP';
  const edgePct = (polymarket.edge * 100).toFixed(1);
  const isPositiveEdge = polymarket.edge > 0;

  const actionColor =
    polymarket.action === 'BUY_YES' ? '#00FF66' :
    polymarket.action === 'BUY_NO' ? '#FF3333' : '#888';

  return (
    <div data-testid="miniapp-edge-screen" style={{ paddingTop: '4px' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h2
          style={{
            fontSize: '13px',
            letterSpacing: '0.2em',
            color: '#555',
            fontWeight: 600,
            textTransform: 'uppercase',
            marginBottom: '4px',
            fontFamily: "'Manrope', sans-serif",
          }}
        >
          Polymarket Edge
        </h2>
      </div>

      {hasEdge ? (
        <>
          {/* Market name */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            data-testid="edge-market-name"
            style={{
              fontSize: '16px',
              color: '#ccc',
              fontFamily: "'Manrope', sans-serif",
              fontWeight: 600,
              marginBottom: '32px',
              lineHeight: 1.4,
            }}
          >
            {polymarket.market}
          </motion.div>

          {/* Probability comparison */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '32px' }}>
            <ProbCard
              label="Market"
              value={polymarket.market_prob}
              testId="edge-market-prob"
              delay={0.1}
            />
            <ProbCard
              label="Model"
              value={polymarket.model_prob}
              testId="edge-model-prob"
              delay={0.2}
            />
          </div>

          {/* Edge display */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            style={{
              textAlign: 'center',
              marginBottom: '32px',
            }}
          >
            <div style={{ fontSize: '11px', letterSpacing: '0.2em', color: '#555', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
              Edge
            </div>
            <div
              data-testid="edge-value"
              style={{
                fontSize: '48px',
                fontFamily: "'Oswald', sans-serif",
                fontWeight: 700,
                color: isPositiveEdge ? '#00FF66' : '#FF3333',
                lineHeight: 1,
              }}
            >
              {isPositiveEdge ? '+' : ''}{edgePct}%
            </div>
          </motion.div>

          {/* Action */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            data-testid="edge-action"
            style={{
              padding: '20px',
              borderRadius: '12px',
              background: `${actionColor}0F`,
              border: `1px solid ${actionColor}22`,
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '11px', letterSpacing: '0.15em', color: '#888', fontWeight: 500, textTransform: 'uppercase', marginBottom: '6px' }}>
              Recommended
            </div>
            <div
              style={{
                fontSize: '24px',
                fontFamily: "'Oswald', sans-serif",
                fontWeight: 700,
                color: actionColor,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
              }}
            >
              {polymarket.action.replace('_', ' ')}
            </div>
          </motion.div>
        </>
      ) : (
        <NoEdgeState asset={asset} />
      )}
    </div>
  );
}


function ProbCard({ label, value, testId, delay }) {
  const pct = (value * 100).toFixed(0);
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      data-testid={testId}
      style={{
        padding: '20px 16px',
        borderRadius: '12px',
        background: 'rgba(255,255,255,0.04)',
        border: '1px solid rgba(255,255,255,0.06)',
        textAlign: 'center',
      }}
    >
      <div style={{ fontSize: '11px', letterSpacing: '0.15em', color: '#555', fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
        {label}
      </div>
      <div style={{ fontSize: '36px', fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: '#fff', lineHeight: 1 }}>
        {pct}%
      </div>
    </motion.div>
  );
}


function NoEdgeState({ asset }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      data-testid="edge-no-data"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '48px 24px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: 'rgba(255,255,255,0.04)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '20px',
          color: '#444',
          marginBottom: '16px',
        }}
      >
        —
      </div>
      <div style={{ fontSize: '14px', color: '#888', fontFamily: "'Manrope', sans-serif", marginBottom: '8px' }}>
        No active prediction markets
      </div>
      <div style={{ fontSize: '12px', color: '#555', fontFamily: "'Manrope', sans-serif" }}>
        Polymarket edge data for {asset} is not available right now.
      </div>
    </motion.div>
  );
}
