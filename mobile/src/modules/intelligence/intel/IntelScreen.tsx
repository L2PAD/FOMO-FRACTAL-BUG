import React, { useEffect, useState, useCallback } from 'react';
import { 
  View, 
  Text, 
  StyleSheet, 
  ScrollView, 
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { mobileApi, IntelOverview, IntelModule } from '../../../services/api/mobile-api';
import { useAssetStore } from '../../../stores/asset.store';
import { theme } from '../../../core/theme';
import { useColors } from '../../../core/useColors';

import { t } from '../../../core/i18n';
export function IntelScreen() {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);

  const [data, setData] = useState<IntelOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const currentAsset = useAssetStore((s) => s.currentAsset);

  const fetchData = async () => {
    try {
      const result = await mobileApi.getIntelOverview(currentAsset);
      setData(result);
    } catch (error) {
      console.error('Error fetching intel:', error);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchData();
    setRefreshing(false);
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchData();
  }, [currentAsset]);

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.accent} />
        <Text style={styles.loadingText}>{t('intelIntel.loadingIntelligence')}</Text>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>{t('intelIntel.failedToLoadData')}</Text>
      </View>
    );
  }

  const { verdict, modules } = data;
  const verdictColor = getDirectionColor(verdict.direction, colors);

  return (
    <ScrollView 
      style={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          tintColor={colors.accent}
          colors={[colors.accent]}
        />
      }
    >
      {/* Overall Verdict */}
      <View style={styles.verdictCard}>
        <Text style={styles.verdictLabel}>{t('intelIntel.overallVerdict')}</Text>
        <View style={styles.verdictRow}>
          <Text style={[styles.verdictDirection, { color: verdictColor }]}>
            {verdict.direction}
          </Text>
          <Text style={styles.verdictConfidence}>
            {Math.round(verdict.confidence * 100)}% confidence
          </Text>
        </View>
        <View style={styles.alignmentRow}>
          <View style={styles.alignmentIndicator}>
            {[...Array(verdict.totalModules)].map((_, i) => (
              <View 
                key={i} 
                style={[
                  styles.alignmentDot,
                  i < verdict.alignedModules && { backgroundColor: verdictColor }
                ]} 
              />
            ))}
          </View>
          <Text style={styles.verdictAligned}>
            {verdict.alignedModules} of {verdict.totalModules} modules aligned{
              verdict.alignedModules === 0 ? ' — watching for first trigger'
              : verdict.alignedModules >= verdict.totalModules - 1 ? ' — almost ready'
              : verdict.alignedModules >= Math.ceil(verdict.totalModules / 2) ? ' — building momentum'
              : ''
            }
          </Text>
        </View>
      </View>

      {/* Modules */}
      <Text style={styles.sectionTitle}>{t('intelIntel.intelligenceModules')}</Text>
      
      {modules.map((module) => (
        <ModuleCard key={module.id} module={module} />
      ))}

      <View style={{ height: 20 }} />
    </ScrollView>
  );
}

function ModuleCard({ module }: { module: IntelModule }) {
  const colors = useColors();
  const styles = React.useMemo(() => makeStyles(colors), [colors]);
  const isSun = module.status === 'SUN';
  const color = isSun ? colors.textMuted : getDirectionColor(module.direction || 'NEUTRAL', colors);
  const icon = getModuleIcon(module.id);

  return (
    <TouchableOpacity style={styles.moduleCard} disabled={isSun}>
      <View style={styles.moduleHeader}>
        <View style={styles.moduleLeft}>
          <View style={[
            styles.moduleIcon,
            { backgroundColor: isSun ? colors.surface : color + '20' }
          ]}>
            <Ionicons 
              name={isSun ? 'construct' : icon}
              size={22}
              color={isSun ? colors.textMuted : color}
            />
          </View>
          <Text style={styles.moduleName}>{module.name}</Text>
        </View>
        <Ionicons name="chevron-forward" size={20} color={colors.textMuted} />
      </View>
      
      {isSun ? (
        <View style={styles.sunContainer}>
          <View style={styles.sunBadge}>
            <Text style={styles.sunText}>{t('intelIntel.comingSoon')}</Text>
          </View>
          <Text style={styles.sunMessage}>{module.message || 'Module under development'}</Text>
        </View>
      ) : (
        <>
          <View style={styles.moduleStats}>
            <Text style={[styles.moduleDirection, { color }]}>
              {module.direction}
            </Text>
            <View style={styles.confidenceBar}>
              <View 
                style={[
                  styles.confidenceFill, 
                  { 
                    width: `${(module.confidence || 0) * 100}%`,
                    backgroundColor: color
                  }
                ]} 
              />
            </View>
            <Text style={styles.confidenceText}>
              {Math.round((module.confidence || 0) * 100)}%
            </Text>
          </View>
          <Text style={styles.moduleSummary}>{module.summary}</Text>
        </>
      )}
    </TouchableOpacity>
  );
}

function getDirectionColor(direction: string, colors: any): string {
  switch (direction) {
    case 'BULLISH': return colors.bullish;
    case 'BEARISH': return colors.bearish;
    default: return colors.neutral;
  }
}

function getModuleIcon(id: string): keyof typeof Ionicons.glyphMap {
  switch (id) {
    case 'exchange': return 'bar-chart';
    case 'fractal': return 'git-network';
    case 'sentiment': return 'chatbubbles';
    case 'onchain': return 'link';
    case 'ta': return 'trending-up';
    default: return 'analytics';
  }
}

const makeStyles = (colors: any) => StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: theme.spacing.md,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: colors.textSecondary,
    marginTop: theme.spacing.md,
  },
  errorText: {
    color: colors.sell,
  },

  // Verdict
  verdictCard: {
    backgroundColor: colors.surface,
    borderRadius: theme.radius.lg,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
  },
  verdictLabel: {
    fontSize: theme.fontSize.xs,
    color: colors.textMuted,
    letterSpacing: 1,
    marginBottom: theme.spacing.sm,
  },
  verdictRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: theme.spacing.md,
  },
  verdictDirection: {
    fontSize: theme.fontSize['3xl'],
    fontWeight: '700',
  },
  verdictConfidence: {
    fontSize: theme.fontSize.base,
    color: colors.textSecondary,
  },
  alignmentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing.md,
    gap: theme.spacing.md,
  },
  alignmentIndicator: {
    flexDirection: 'row',
    gap: 4,
  },
  alignmentDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.surfaceHover,
  },
  verdictAligned: {
    fontSize: theme.fontSize.sm,
    color: colors.textMuted,
  },

  // Section
  sectionTitle: {
    fontSize: theme.fontSize.xs,
    fontWeight: '700',
    color: colors.textMuted,
    letterSpacing: 1,
    marginBottom: theme.spacing.md,
  },

  // Module Card
  moduleCard: {
    backgroundColor: colors.surface,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
  },
  moduleHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  moduleLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: theme.spacing.sm,
  },
  moduleIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moduleName: {
    fontSize: theme.fontSize.base,
    fontWeight: '600',
    color: colors.textPrimary,
  },
  moduleStats: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  moduleDirection: {
    fontSize: theme.fontSize.sm,
    fontWeight: '600',
    width: 70,
  },
  confidenceBar: {
    flex: 1,
    height: 4,
    backgroundColor: colors.surfaceHover,
    borderRadius: 2,
    overflow: 'hidden',
  },
  confidenceFill: {
    height: '100%',
    borderRadius: 2,
  },
  confidenceText: {
    fontSize: theme.fontSize.sm,
    color: colors.textSecondary,
    width: 35,
    textAlign: 'right',
  },
  moduleSummary: {
    fontSize: theme.fontSize.sm,
    color: colors.textSecondary,
    marginTop: theme.spacing.sm,
  },

  // SUN State
  sunContainer: {
    marginTop: theme.spacing.md,
  },
  sunBadge: {
    backgroundColor: colors.surfaceHover,
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.radius.sm,
    alignSelf: 'flex-start',
  },
  sunText: {
    fontSize: theme.fontSize.xs,
    color: colors.textMuted,
    fontWeight: '600',
  },
  sunMessage: {
    fontSize: theme.fontSize.sm,
    color: colors.textMuted,
    marginTop: theme.spacing.sm,
  },
});
