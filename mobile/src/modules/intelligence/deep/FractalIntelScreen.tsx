import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { theme } from '../../../core/theme';
import { useColors } from '../../../core/useColors';
import { api } from '../../../services/api/api-client';
import { useAssetStore } from '../../../stores/asset.store';
import { FeatureGate } from '../../../components/FeatureGate';
import { openPaywall } from '../../../utils/paywall-controller';

import { t } from '../../../core/i18n';
interface FractalData {
  asset: string;
  state: string;
  confidence: number;
  regime: { current: string; bias: string; interpretation: string };
  alignment: { tf5m: string; tf1h: string; tf4h: string; tf1d: string; score: number; interpretation: string };
  levels: { support: number; resistance: number; breakoutLow: number; breakoutHigh: number; invalidation: number; interpretation: string };
  scenarios: { base: string; alternative: string; interpretation: string };
  volatility: { compression: string; expansionRisk: string; interpretation: string };
  interpretation: string[];
  signal: { strength: string; direction: string };
}

export function FractalIntelScreen() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [data, setData] = useState<FractalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const currentAsset = useAssetStore((s) => s.currentAsset);

  const fetchData = async () => {
    try {
      const res = await api.get(`/api/mobile/intel/fractal?asset=${currentAsset}`);
      setData(res.data);
    } catch (err) {
      console.error('Fractal intel error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { setLoading(true); fetchData(); }, [currentAsset]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  };

  if (loading || !data) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  const biasColor = data.regime.bias === 'BULLISH' ? colors.buy : data.regime.bias === 'BEARISH' ? colors.sell : colors.neutral;

  const tfIcon = (dir: string) => {
    if (dir === 'UP') return { name: 'arrow-up' as const, color: colors.buy };
    if (dir === 'DOWN') return { name: 'arrow-down' as const, color: colors.sell };
    return { name: 'remove' as const, color: colors.neutral };
  };

  return (
    <FeatureGate feature="deep_intel" onUnlock={openPaywall}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />}
    >
      {/* Verdict */}
      <View style={styles.verdictCard}>
        <View style={styles.verdictRow}>
          <View>
            <Text style={styles.verdictAsset}>{data.asset}</Text>
            <Text style={[styles.verdictState, { color: biasColor }]}>
              {data.state.replace(/_/g, ' ')}
            </Text>
          </View>
          <View style={styles.verdictConfidence}>
            <Text style={styles.confidenceValue}>{Math.round(data.confidence * 100)}%</Text>
            <Text style={styles.confidenceLabel}>confidence</Text>
          </View>
        </View>
        <View style={[styles.verdictBar, { backgroundColor: biasColor + '20' }]}>
          <View style={[styles.verdictBarFill, { width: `${data.confidence * 100}%`, backgroundColor: biasColor }]} />
        </View>
      </View>

      {/* Market Regime */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: biasColor + '20' }]}>
            <Ionicons name="analytics" size={16} color={biasColor} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.marketRegime')}</Text>
          <View style={[styles.trendBadge, { backgroundColor: biasColor + '20' }]}>
            <Text style={[styles.trendText, { color: biasColor }]}>{data.regime.current}</Text>
          </View>
        </View>
        <Text style={[styles.regimeValue, { color: biasColor }]}>{data.regime.bias}</Text>
        <Text style={styles.interpret}>{data.regime.interpretation}</Text>
      </View>

      {/* Structure Alignment */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name="layers" size={16} color={colors.accent} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.structureAlignment')}</Text>
          <Text style={styles.alignScore}>{data.alignment.score}/4</Text>
        </View>
        <View style={styles.tfGrid}>
          {[
            { label: '5m', dir: data.alignment.tf5m },
            { label: '1h', dir: data.alignment.tf1h },
            { label: '4h', dir: data.alignment.tf4h },
            { label: '1D', dir: data.alignment.tf1d },
          ].map(tf => {
            const ic = tfIcon(tf.dir);
            return (
              <View key={tf.label} style={styles.tfItem}>
                <View style={[styles.tfDot, { backgroundColor: ic.color + '20' }]}>
                  <Ionicons name={ic.name} size={16} color={ic.color} />
                </View>
                <Text style={styles.tfLabel}>{tf.label}</Text>
                <Text style={[styles.tfDir, { color: ic.color }]}>{tf.dir}</Text>
              </View>
            );
          })}
        </View>
        {/* Alignment dots */}
        <View style={styles.alignDots}>
          {[...Array(4)].map((_, i) => (
            <View
              key={i}
              style={[
                styles.alignDot,
                i < data.alignment.score && { backgroundColor: biasColor },
              ]}
            />
          ))}
        </View>
        <Text style={styles.interpret}>{data.alignment.interpretation}</Text>
      </View>

      {/* Key Levels */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.neutral + '20' }]}>
            <Ionicons name="resize" size={16} color={colors.neutral} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.keyLevels')}</Text>
        </View>
        <View style={styles.levelsGrid}>
          <View style={styles.levelItem}>
            <Text style={styles.levelLabel}>Support</Text>
            <Text style={[styles.levelValue, { color: colors.buy }]}>${data.levels.support.toLocaleString()}</Text>
          </View>
          <View style={styles.levelDivider} />
          <View style={styles.levelItem}>
            <Text style={styles.levelLabel}>Resistance</Text>
            <Text style={[styles.levelValue, { color: colors.sell }]}>${data.levels.resistance.toLocaleString()}</Text>
          </View>
        </View>
        <Text style={styles.interpret}>{data.levels.interpretation}</Text>
      </View>

      {/* Breakout Zone */}
      <View style={[styles.card, { borderLeftWidth: 3, borderLeftColor: colors.accent }]}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name="exit" size={16} color={colors.accent} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.breakoutZone')}</Text>
          <View style={[styles.trendBadge, { backgroundColor: colors.accent + '20' }]}>
            <Text style={[styles.trendText, { color: colors.accent }]}>ACTIVE</Text>
          </View>
        </View>
        <Text style={styles.breakoutValue}>
          ${data.levels.breakoutLow.toLocaleString()} {'\u2014'} ${data.levels.breakoutHigh.toLocaleString()}
        </Text>
        <Text style={styles.interpret}>{t('intelDeep.breakAboveThisZoneOpens')}</Text>
      </View>

      {/* Invalidation */}
      <View style={[styles.card, { borderLeftWidth: 3, borderLeftColor: colors.sell }]}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.sell + '20' }]}>
            <Ionicons name="alert-circle" size={16} color={colors.sell} />
          </View>
          <Text style={styles.cardTitle}>Invalidation</Text>
        </View>
        <Text style={[styles.breakoutValue, { color: colors.sell }]}>
          Below ${data.levels.invalidation.toLocaleString()}
        </Text>
        <Text style={styles.interpret}>{t('intelDeep.lossOfStructuralSupportWeakens')}</Text>
      </View>

      {/* Scenarios */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.textSecondary + '20' }]}>
            <Ionicons name="git-branch" size={16} color={colors.textSecondary} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.pathScenarios')}</Text>
        </View>
        <View style={styles.scenarioItem}>
          <View style={[styles.scenarioDot, { backgroundColor: colors.buy }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.scenarioLabel}>BASE</Text>
            <Text style={styles.scenarioText}>{data.scenarios.base}</Text>
          </View>
        </View>
        <View style={styles.scenarioItem}>
          <View style={[styles.scenarioDot, { backgroundColor: colors.sell }]} />
          <View style={{ flex: 1 }}>
            <Text style={styles.scenarioLabel}>ALTERNATIVE</Text>
            <Text style={styles.scenarioText}>{data.scenarios.alternative}</Text>
          </View>
        </View>
        <Text style={styles.interpret}>{data.scenarios.interpretation}</Text>
      </View>

      {/* Volatility */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.neutral + '20' }]}>
            <Ionicons name="pulse" size={16} color={colors.neutral} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.volatilityCompression')}</Text>
        </View>
        <View style={styles.volRow}>
          <View style={styles.volItem}>
            <Text style={styles.volLabel}>Compression</Text>
            <Text style={styles.volValue}>{data.volatility.compression}</Text>
          </View>
          <View style={styles.volDivider} />
          <View style={styles.volItem}>
            <Text style={styles.volLabel}>{t('intelDeep.expansionRisk')}</Text>
            <Text style={[styles.volValue, { color: data.volatility.expansionRisk === 'HIGH' ? colors.sell : colors.neutral }]}>
              {data.volatility.expansionRisk}
            </Text>
          </View>
        </View>
        <Text style={styles.interpret}>{data.volatility.interpretation}</Text>
      </View>

      {/* Signal Summary */}
      <View style={[styles.summaryCard, { borderColor: biasColor + '40' }]}>
        <View style={styles.summaryHeader}>
          <Ionicons name="git-network" size={18} color={biasColor} />
          <Text style={[styles.summaryTitle, { color: biasColor }]}>
            {data.signal.strength} {data.signal.direction}
          </Text>
        </View>
        {data.interpretation.map((item, i) => (
          <View key={i} style={styles.summaryItem}>
            <Text style={[styles.summaryBullet, { color: item.includes('needs') || item.includes('Invalidation') ? colors.sell : biasColor }]}>
              {item.includes('needs') || item.includes('Invalidation') ? '-' : '+'}
            </Text>
            <Text style={styles.summaryText}>{item}</Text>
          </View>
        ))}
      </View>

      <View style={{ height: 24 }} />
    </ScrollView>
    </FeatureGate>
  );
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: theme.spacing.md },
  loadingContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.background },
  verdictCard: { backgroundColor: colors.surface, borderRadius: theme.radius.lg, padding: theme.spacing.lg, marginBottom: theme.spacing.md },
  verdictRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: theme.spacing.md },
  verdictAsset: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary },
  verdictState: { fontSize: theme.fontSize.xl, fontWeight: '800', marginTop: 2 },
  verdictConfidence: { alignItems: 'flex-end' },
  confidenceValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800', color: colors.textPrimary },
  confidenceLabel: { fontSize: 10, color: colors.textMuted },
  verdictBar: { height: 4, borderRadius: 2, overflow: 'hidden' },
  verdictBarFill: { height: '100%', borderRadius: 2 },
  card: { backgroundColor: colors.surface, borderRadius: theme.radius.md, padding: theme.spacing.md, marginBottom: theme.spacing.sm },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.sm },
  iconContainer: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: theme.fontSize.sm, fontWeight: '600', color: colors.textSecondary, flex: 1 },
  trendBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: theme.radius.full },
  trendText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  regimeValue: { fontSize: theme.fontSize.xl, fontWeight: '800', marginBottom: theme.spacing.xs },
  interpret: { fontSize: theme.fontSize.sm, color: colors.textMuted, lineHeight: 18, marginTop: theme.spacing.xs },
  alignScore: { fontSize: theme.fontSize.base, fontWeight: '700', color: colors.accent },
  tfGrid: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: theme.spacing.md },
  tfItem: { alignItems: 'center', gap: 4 },
  tfDot: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  tfLabel: { fontSize: 10, fontWeight: '600', color: colors.textSecondary },
  tfDir: { fontSize: 10, fontWeight: '700' },
  alignDots: { flexDirection: 'row', gap: 6, marginBottom: theme.spacing.sm },
  alignDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: colors.surfaceHover },
  levelsGrid: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.spacing.sm },
  levelItem: { flex: 1, alignItems: 'center' },
  levelLabel: { fontSize: 10, color: colors.textMuted, marginBottom: 2 },
  levelValue: { fontSize: theme.fontSize.lg, fontWeight: '700' },
  levelDivider: { width: 1, height: 30, backgroundColor: colors.border },
  breakoutValue: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.accent, marginBottom: theme.spacing.xs },
  scenarioItem: { flexDirection: 'row', gap: theme.spacing.sm, alignItems: 'flex-start', marginBottom: theme.spacing.sm },
  scenarioDot: { width: 8, height: 8, borderRadius: 4, marginTop: 4 },
  scenarioLabel: { fontSize: 9, fontWeight: '700', color: colors.textMuted, letterSpacing: 1 },
  scenarioText: { fontSize: theme.fontSize.sm, color: colors.textSecondary, lineHeight: 18 },
  volRow: { flexDirection: 'row', alignItems: 'center', marginBottom: theme.spacing.sm },
  volItem: { flex: 1, alignItems: 'center' },
  volLabel: { fontSize: 10, color: colors.textMuted, marginBottom: 2 },
  volValue: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary },
  volDivider: { width: 1, height: 30, backgroundColor: colors.border },
  summaryCard: { backgroundColor: colors.surface, borderRadius: theme.radius.lg, padding: theme.spacing.lg, marginTop: theme.spacing.sm, borderWidth: 1 },
  summaryHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  summaryTitle: { fontSize: theme.fontSize.lg, fontWeight: '800' },
  summaryItem: { flexDirection: 'row', gap: theme.spacing.sm, marginBottom: 4 },
  summaryBullet: { fontSize: theme.fontSize.base, fontWeight: '700', width: 14 },
  summaryText: { fontSize: theme.fontSize.sm, color: colors.textSecondary, flex: 1, lineHeight: 18 },
});
