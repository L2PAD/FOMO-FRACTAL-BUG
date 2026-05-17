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
interface SentimentData {
  asset: string;
  state: string;
  confidence: number;
  score: { value: number; trend: string; interpretation: string };
  social: { mentionsPct: number; trend: string; interpretation: string };
  twitter: { velocityPct: number; activeInfluencers: number; interpretation: string };
  narrative: { title: string; sentiment: string; interpretation: string };
  positioning: { longPct: number; shortPct: number; interpretation: string };
  fearGreed: { value: number; state: string; interpretation: string };
  interpretation: string[];
  signal: { strength: string; direction: string };
}

export function SentimentIntelScreen() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [data, setData] = useState<SentimentData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const currentAsset = useAssetStore((s) => s.currentAsset);

  const fetchData = async () => {
    try {
      const res = await api.get(`/api/mobile/intel/sentiment?asset=${currentAsset}`);
      setData(res.data);
    } catch (err) {
      console.error('Sentiment intel error:', err);
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
        <ActivityIndicator size="large" color={colors.neutral} />
      </View>
    );
  }

  const stateColor = data.state === 'EUPHORIA' ? colors.neutral : data.state === 'FEAR' ? colors.sell : colors.textSecondary;
  const fearGreedColor = data.fearGreed.value > 70 ? colors.sell : data.fearGreed.value > 50 ? colors.neutral : colors.buy;

  return (
    <FeatureGate feature="deep_intel" onUnlock={openPaywall}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.neutral} />}
    >
      {/* Verdict */}
      <View style={styles.verdictCard}>
        <View style={styles.verdictRow}>
          <View>
            <Text style={styles.verdictAsset}>{data.asset}</Text>
            <Text style={[styles.verdictState, { color: stateColor }]}>{data.state}</Text>
          </View>
          <View style={styles.verdictConfidence}>
            <Text style={styles.confidenceValue}>{Math.round(data.confidence * 100)}%</Text>
            <Text style={styles.confidenceLabel}>confidence</Text>
          </View>
        </View>
      </View>

      {/* Sentiment Score */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: stateColor + '20' }]}>
            <Ionicons name="speedometer" size={16} color={stateColor} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.sentimentScore')}</Text>
          <View style={[styles.trendBadge, { backgroundColor: stateColor + '20' }]}>
            <Text style={[styles.trendText, { color: stateColor }]}>{data.score.trend.toUpperCase()}</Text>
          </View>
        </View>
        {/* Circular gauge visual */}
        <View style={styles.scoreRow}>
          <Text style={[styles.scoreValue, { color: stateColor }]}>{data.score.value}</Text>
          <Text style={styles.scoreMax}>/ 100</Text>
        </View>
        <View style={styles.scoreBar}>
          <View style={[styles.scoreBarFill, { width: `${data.score.value}%`, backgroundColor: stateColor }]} />
        </View>
        <Text style={styles.interpret}>{data.score.interpretation}</Text>
      </View>

      {/* Social Volume */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name="megaphone" size={16} color={colors.accent} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.socialVolume')}</Text>
        </View>
        <Text style={styles.cardValue}>+{data.social.mentionsPct}%</Text>
        <Text style={styles.interpret}>{data.social.interpretation}</Text>
      </View>

      {/* Twitter Velocity */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: '#1DA1F2' + '20' }]}>
            <Ionicons name="logo-twitter" size={16} color="#1DA1F2" />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.twitterVelocity')}</Text>
        </View>
        <Text style={styles.cardValue}>+{data.twitter.velocityPct}% / 1h</Text>
        <Text style={styles.cardSubValue}>{data.twitter.activeInfluencers} top accounts active</Text>
        <Text style={styles.interpret}>{data.twitter.interpretation}</Text>
      </View>

      {/* Narrative */}
      <View style={[styles.card, { borderLeftWidth: 3, borderLeftColor: colors.accent }]}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.accent + '20' }]}>
            <Ionicons name="newspaper" size={16} color={colors.accent} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.dominantNarrative')}</Text>
        </View>
        <Text style={styles.narrativeTitle}>{data.narrative.title}</Text>
        <View style={[styles.trendBadge, { backgroundColor: (data.narrative.sentiment === 'positive' ? colors.buy : colors.sell) + '20', alignSelf: 'flex-start', marginTop: 6 }]}>
          <Text style={[styles.trendText, { color: data.narrative.sentiment === 'positive' ? colors.buy : colors.sell }]}>
            {data.narrative.sentiment.toUpperCase()}
          </Text>
        </View>
        <Text style={styles.interpret}>{data.narrative.interpretation}</Text>
      </View>

      {/* Crowd Positioning */}
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={[styles.iconContainer, { backgroundColor: colors.neutral + '20' }]}>
            <Ionicons name="people" size={16} color={colors.neutral} />
          </View>
          <Text style={styles.cardTitle}>{t('intelDeep.crowdPositioning')}</Text>
        </View>
        <View style={styles.posRow}>
          <Text style={[styles.posValue, { color: colors.buy }]}>Long {data.positioning.longPct}%</Text>
          <Text style={[styles.posValue, { color: colors.sell }]}>Short {data.positioning.shortPct}%</Text>
        </View>
        <View style={styles.posBar}>
          <View style={[styles.posBarLong, { flex: data.positioning.longPct }]} />
          <View style={[styles.posBarShort, { flex: data.positioning.shortPct }]} />
        </View>
        <Text style={styles.interpret}>{data.positioning.interpretation}</Text>
      </View>

      {/* Fear & Greed */}
      {data.fearGreed && (
        <View style={styles.card}>
          <View style={styles.cardHeader}>
            <View style={[styles.iconContainer, { backgroundColor: fearGreedColor + '20' }]}>
              <Ionicons name="thermometer" size={16} color={fearGreedColor} />
            </View>
            <Text style={styles.cardTitle}>{t('intelDeep.fearGreedIndex')}</Text>
          </View>
          <View style={styles.fgRow}>
            <Text style={[styles.fgValue, { color: fearGreedColor }]}>{data.fearGreed.value}</Text>
            <View style={[styles.trendBadge, { backgroundColor: fearGreedColor + '20' }]}>
              <Text style={[styles.trendText, { color: fearGreedColor }]}>{data.fearGreed.state}</Text>
            </View>
          </View>
          <View style={styles.fgBar}>
            <View style={[styles.fgBarFill, { width: `${data.fearGreed.value}%`, backgroundColor: fearGreedColor }]} />
          </View>
          <View style={styles.fgLabels}>
            <Text style={[styles.fgLabel, { color: colors.buy }]}>Fear</Text>
            <Text style={[styles.fgLabel, { color: colors.neutral }]}>Neutral</Text>
            <Text style={[styles.fgLabel, { color: colors.sell }]}>Greed</Text>
          </View>
          <Text style={styles.interpret}>{data.fearGreed.interpretation}</Text>
        </View>
      )}

      {/* Signal Summary */}
      <View style={[styles.summaryCard, { borderColor: stateColor + '40' }]}>
        <View style={styles.summaryHeader}>
          <Ionicons name="chatbubble-ellipses" size={18} color={stateColor} />
          <Text style={[styles.summaryTitle, { color: stateColor }]}>
            {data.signal.strength} {data.signal.direction}
          </Text>
        </View>
        {data.interpretation.map((item, i) => (
          <View key={i} style={styles.summaryItem}>
            <Text style={[styles.summaryBullet, { color: item.startsWith('Risk') ? colors.sell : stateColor }]}>
              {item.startsWith('Risk') ? '-' : '+'}
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
  verdictRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  verdictAsset: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary },
  verdictState: { fontSize: theme.fontSize['2xl'], fontWeight: '800', marginTop: 2 },
  verdictConfidence: { alignItems: 'flex-end' },
  confidenceValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800', color: colors.textPrimary },
  confidenceLabel: { fontSize: 10, color: colors.textMuted },
  card: { backgroundColor: colors.surface, borderRadius: theme.radius.md, padding: theme.spacing.md, marginBottom: theme.spacing.sm },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.sm },
  iconContainer: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  cardTitle: { fontSize: theme.fontSize.sm, fontWeight: '600', color: colors.textSecondary, flex: 1 },
  trendBadge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: theme.radius.full },
  trendText: { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },
  cardValue: { fontSize: theme.fontSize.xl, fontWeight: '700', color: colors.textPrimary, marginBottom: 2 },
  cardSubValue: { fontSize: theme.fontSize.sm, color: colors.textMuted, marginBottom: theme.spacing.xs },
  scoreRow: { flexDirection: 'row', alignItems: 'baseline', gap: 4, marginBottom: theme.spacing.xs },
  scoreValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800' },
  scoreMax: { fontSize: theme.fontSize.base, color: colors.textMuted },
  scoreBar: { height: 6, borderRadius: 3, backgroundColor: colors.surfaceHover, overflow: 'hidden', marginBottom: theme.spacing.sm },
  scoreBarFill: { height: '100%', borderRadius: 3 },
  narrativeTitle: { fontSize: theme.fontSize.lg, fontWeight: '700', color: colors.textPrimary, lineHeight: 22 },
  posRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.xs },
  posValue: { fontSize: theme.fontSize.base, fontWeight: '700' },
  posBar: { flexDirection: 'row', height: 8, borderRadius: 4, overflow: 'hidden', marginBottom: theme.spacing.sm },
  posBarLong: { backgroundColor: colors.buy },
  posBarShort: { backgroundColor: colors.sell },
  fgRow: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.md, marginBottom: theme.spacing.sm },
  fgValue: { fontSize: theme.fontSize['3xl'], fontWeight: '800' },
  fgBar: { height: 8, borderRadius: 4, backgroundColor: colors.surfaceHover, overflow: 'hidden', marginBottom: 4 },
  fgBarFill: { height: '100%', borderRadius: 4 },
  fgLabels: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: theme.spacing.sm },
  fgLabel: { fontSize: 9 },
  interpret: { fontSize: theme.fontSize.sm, color: colors.textMuted, lineHeight: 18, marginTop: theme.spacing.xs },
  summaryCard: { backgroundColor: colors.surface, borderRadius: theme.radius.lg, padding: theme.spacing.lg, marginTop: theme.spacing.sm, borderWidth: 1 },
  summaryHeader: { flexDirection: 'row', alignItems: 'center', gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  summaryTitle: { fontSize: theme.fontSize.lg, fontWeight: '800' },
  summaryItem: { flexDirection: 'row', gap: theme.spacing.sm, marginBottom: 4 },
  summaryBullet: { fontSize: theme.fontSize.base, fontWeight: '700', width: 14 },
  summaryText: { fontSize: theme.fontSize.sm, color: colors.textSecondary, flex: 1, lineHeight: 18 },
});
