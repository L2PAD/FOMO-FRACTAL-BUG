/**
 * CurrentDeploymentConditions — Stage A-8 atmospheric reading layer.
 *
 * NOT a per-symbol signal grid.  NOT BTC→bullish / ETH→bullish.
 *
 * This is the cognition climate layer: each row reads the system's
 * current deployment posture for a symbol in observational, posture-
 * oriented language:
 *
 *     BTC · restraint held
 *     ETH · directional pressure unresolved
 *     SOL · conditions remain compressed
 *
 * Symbols are HARDCODED to BTC / ETH / SOL (canonical runtime universe).
 * Dynamic listing would create visual jitter and break rhythmic memory.
 *
 * Rules:
 *   • If shadow runtime returns nothing for a symbol → omit silently.
 *   • If all 3 are empty → render entire block as nothing (absence).
 *   • Never use direction/CTA wording.
 *   • Color is energy-token only — no agency-color (green/red).
 */
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { mbrainApi } from '../../services/api/mbrain-api';
import { tokenFor, SemanticEnergy } from './cognitiveTokens';

type Props = {
  colors: any;
  marginTop?: number;
  marginBottom?: number;
};

type SymbolVerdict = {
  symbol: string;
  status: 'blocked' | 'wait' | 'considered' | 'unresolved';
  rawAction: string;
  finalAction: string | null;
  reason: string[];
  deploymentBlockedBy: string[];
};

const SYMBOLS = ['BTC', 'ETH', 'SOL'] as const;

function energyForStatus(status: string): SemanticEnergy {
  if (status === 'blocked') return 'suppression';
  if (status === 'considered') return 'compression';
  if (status === 'unresolved') return 'flux';
  return 'dormant';
}

// ─── Atmospheric phrase derivation ─────────────────────────────────────
function postureLine(v: SymbolVerdict): string {
  const status = v.status;
  const blocked = v.deploymentBlockedBy || [];
  if (status === 'blocked') {
    if (blocked.includes('fractal')) return 'restraint held · structure compressed';
    if (blocked.includes('technical_alignment')) return 'restraint held · alignment thin';
    if (blocked.includes('sentiment_confidence')) return 'restraint held · sentiment unconfirmed';
    return 'restraint held';
  }
  if (status === 'considered') return 'structural consideration forming';
  if (status === 'unresolved') return 'directional pressure unresolved';
  return 'conditions remain neutral';
}

export const CurrentDeploymentConditions: React.FC<Props> = ({
  colors, marginTop = 8, marginBottom = 8,
}) => {
  const [rows, setRows] = useState<(SymbolVerdict | null)[]>([null, null, null]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const summary = await mbrainApi.shadowSummary(SYMBOLS.join(','));
        if (!alive) return;
        if (!summary?.ok || !summary.perSymbol) {
          setRows([null, null, null]);
        } else {
          const out: (SymbolVerdict | null)[] = SYMBOLS.map((s) => {
            const r = summary.perSymbol![s];
            if (!r) return null;
            return {
              symbol: s,
              status: r.status,
              rawAction: r.rawAction,
              finalAction: r.finalAction,
              reason: r.reason || [],
              deploymentBlockedBy: r.deploymentBlockedBy || [],
            };
          });
          setRows(out);
        }
      } catch {
        if (alive) setRows([null, null, null]);
      } finally {
        if (alive) setLoaded(true);
      }
    })();
    return () => { alive = false; };
  }, []);

  if (!loaded) return null;
  const visible = rows.filter(Boolean) as SymbolVerdict[];
  if (visible.length === 0) return null; // truthful absence

  return (
    <View style={[styles.wrap, { marginTop, marginBottom }]}>
      <View style={styles.headRow}>
        <Text style={[styles.headTitle, { color: colors.text }]}>
          DEPLOYMENT CONDITIONS
        </Text>
        <Text style={[styles.headSub, { color: colors.textMuted }]}>
          posture · per asset
        </Text>
      </View>

      <View style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
        {visible.map((v, i) => {
          const token = tokenFor(energyForStatus(v.status));
          const accent = colors[token.colorKey] ?? colors.textMuted;
          return (
            <View
              key={v.symbol}
              style={[
                styles.row,
                i < visible.length - 1 && { borderBottomWidth: 0.5, borderBottomColor: colors.border },
              ]}
            >
              <View style={styles.rowLeft}>
                <View style={[styles.dot, { backgroundColor: accent, opacity: 0.6 }]} />
                <Text style={[styles.sym, { color: colors.text }]}>{v.symbol}</Text>
              </View>
              <View style={styles.rowMid}>
                <Text style={[styles.line, { color: colors.textMuted, opacity: token.opacity }]}>
                  {postureLine(v)}
                </Text>
              </View>
              <Text style={[styles.statusWord, { color: accent }]}>
                {v.status}
              </Text>
            </View>
          );
        })}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  wrap: {},
  headRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline',
    marginBottom: 8, paddingHorizontal: 2,
  },
  headTitle: {
    fontSize: 11, fontWeight: '800', letterSpacing: 1.6,
  },
  headSub: {
    fontSize: 10, fontStyle: 'italic',
  },
  card: {
    borderRadius: 12, borderWidth: 1, paddingHorizontal: 4,
  },
  row: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 11, paddingHorizontal: 10,
  },
  rowLeft: {
    flexDirection: 'row', alignItems: 'center',
    minWidth: 52,
  },
  rowMid: {
    flex: 1, paddingHorizontal: 4,
  },
  rowRight: {},
  dot: {
    width: 6, height: 6, borderRadius: 3, marginRight: 7,
  },
  sym: {
    fontSize: 13, fontWeight: '800', letterSpacing: 0.6,
  },
  line: {
    fontSize: 12, fontStyle: 'italic',
  },
  statusWord: {
    fontSize: 10, fontWeight: '700', letterSpacing: 1, textTransform: 'lowercase',
    marginLeft: 6,
  },
});
