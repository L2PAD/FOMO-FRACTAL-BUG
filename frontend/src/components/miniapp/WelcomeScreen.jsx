import { motion } from 'framer-motion';

export function WelcomeScreen({ onComplete }) {
  return (
    <div data-testid="welcome-screen" style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      background: 'var(--ma-bg)', color: 'var(--ma-text)',
      display: 'flex', flexDirection: 'column',
      fontFamily: "'Manrope', sans-serif",
    }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '0 24px', justifyContent: 'center' }}>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div style={{
            fontSize: 9, textTransform: 'uppercase', letterSpacing: 2.5,
            color: '#D4AF37', marginBottom: 12, fontWeight: 600,
          }}>PREDICTION INTELLIGENCE</div>

          <h1 style={{ fontSize: 28, fontWeight: 700, lineHeight: 1.15, marginBottom: 14, letterSpacing: -0.5 }}>
            Your Edge in<br/>Crypto Markets
          </h1>

          <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--ma-secondary)', marginBottom: 28, maxWidth: 320 }}>
            10 AI layers analyze 2,400+ markets 24/7 — fractal patterns, on-chain flows, sentiment, prediction markets — and deliver high-conviction alerts straight to you.
          </p>
        </motion.div>

        {/* Terminal visual */}
        <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.4 }}>
          <div style={{
            background: '#0d0d0d', borderRadius: 12, border: '1px solid rgba(255,255,255,0.08)',
            padding: '12px 14px', fontFamily: 'monospace', fontSize: 11, lineHeight: 1.8,
            maxWidth: 300,
          }}>
            <div style={{ display: 'flex', gap: 5, marginBottom: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#22c55e' }} />
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#eab308' }} />
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#3f3f46' }} />
            </div>
            {[
              { c: '#D4AF37', t: '[FRACTAL] BTC wave 3 → $102K' },
              { c: '#60a5fa', t: '[EXCHANGE] OI +$840M | 38/40' },
              { c: '#34d399', t: '[ONCHAIN] Whale acc. 12,400 BTC' },
              { c: '#fbbf24', t: '[SENTIMENT] Bullish 78%' },
              { c: '#f87171', t: '[PREDICTION] >$100K → 0.78' },
              { c: '#D4AF37', t: '[META] Confidence: 0.87 HIGH' },
            ].map((l, i) => (
              <motion.div key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.4 + i * 0.12 }}
                style={{ color: l.c, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
              >{l.t}</motion.div>
            ))}
          </div>
        </motion.div>

        {/* Features */}
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
          style={{ display: 'flex', gap: 8, marginTop: 24, flexWrap: 'wrap' }}
        >
          {['Smart Alerts', 'Edge Markets', 'PRO Signals', 'Zero Noise'].map((f) => (
            <span key={f} style={{
              fontSize: 11, padding: '5px 10px', borderRadius: 20,
              background: 'var(--ma-surface)', border: '1px solid var(--ma-border)',
              color: 'var(--ma-secondary)', fontWeight: 500,
            }}>{f}</span>
          ))}
        </motion.div>
      </div>

      {/* Single CTA */}
      <div style={{ padding: '16px 24px 48px' }}>
        <button
          data-testid="welcome-start-btn"
          onClick={onComplete}
          style={{
            width: '100%', padding: '16px 20px', borderRadius: 14, fontSize: 15, fontWeight: 700,
            background: '#D4AF37', color: '#0A0A0A',
            border: 'none', cursor: 'pointer',
            letterSpacing: -0.3,
          }}
        >Open Intelligence Dashboard</button>
      </div>
    </div>
  );
}
