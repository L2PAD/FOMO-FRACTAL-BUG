import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Share, Platform, ActivityIndicator, TextInput, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useColors } from '../../../core/useColors';
import { mobileApi, GrowthProfile, LeaderboardEntry } from '../../../services/api/mobile-api';
import { useSessionStore } from '../../../stores/session.store';

import { t } from '../../../core/i18n';
type GrowthView = 'profile' | 'leaderboard';

export function GrowthScreen({ onClose }: { onClose?: () => void }) {
  const colors = useColors();
  const user = useSessionStore(s => s.user);
  const [view, setView] = useState<GrowthView>('profile');
  const [profile, setProfile] = useState<GrowthProfile | null>(null);
  const [board, setBoard] = useState<LeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [promoCode, setPromoCode] = useState('');
  const [promoMsg, setPromoMsg] = useState('');
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const [p, b] = await Promise.all([mobileApi.getGrowthProfile(), mobileApi.getLeaderboard()]);
    if (p) setProfile(p);
    setBoard(b);
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const copyCode = async () => {
    if (!profile?.code) return;
    try {
      if (Platform.OS === 'web') await (navigator as any).clipboard.writeText(profile.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const shareCode = async () => {
    if (!profile) return;
    try {
      await Share.share({ message: `Join FOMO — crypto intelligence.\n\nUse my code: ${profile.code}\n\n${profile.shareUrl}` });
    } catch {}
  };

  const applyCode = async () => {
    if (!promoCode.trim()) return;
    const res = await mobileApi.applyGrowthCode(promoCode.trim());
    setPromoMsg(res.ok ? (res.message || 'Applied!') : (res.error || 'Invalid code'));
    if (res.ok) { setPromoCode(''); load(); }
  };

  if (loading) return (
    <View style={[s.center, { backgroundColor: colors.background }]}>
      <ActivityIndicator size="large" color={colors.accent} />
    </View>
  );

  if (!profile) return (
    <View style={[s.center, { backgroundColor: colors.background }]}>
      <Text style={{ color: colors.textMuted }}>{t('growth.failedToLoadGrowthData')}</Text>
    </View>
  );

  // Progress calc
  const milestones = profile.milestones || [];
  const paidCount = profile.stats.paidConfirmed;
  const currentMilestoneIdx = milestones.findIndex(m => paidCount < m.paid);
  const progressTarget = currentMilestoneIdx >= 0 ? milestones[currentMilestoneIdx].paid : (milestones[milestones.length - 1]?.paid || 10);
  const progressPct = Math.min(100, Math.round((paidCount / progressTarget) * 100));

  const rankColor = profile.rank <= 3 ? '#f59e0b' : profile.rank <= 10 ? '#4DA3FF' : colors.textPrimary;
  const deltaIcon = profile.rankDelta > 0 ? 'arrow-up' : profile.rankDelta < 0 ? 'arrow-down' : 'remove';
  const deltaColor = profile.rankDelta > 0 ? '#2FE6A6' : profile.rankDelta < 0 ? '#FF6B6B' : colors.textMuted;

  return (
    <View style={[s.container, { backgroundColor: colors.background }]}>
      {/* Header */}
      <View style={[s.header, { borderBottomColor: colors.border }]}>
        <View style={s.tabs}>
          <TouchableOpacity testID="growth-tab-profile" style={[s.tab, view === 'profile' && { borderBottomColor: colors.accent, borderBottomWidth: 2 }]} onPress={() => setView('profile')}>
            <Text style={[s.tabText, { color: view === 'profile' ? colors.accent : colors.textMuted }]}>Profile</Text>
          </TouchableOpacity>
          <TouchableOpacity testID="growth-tab-leaderboard" style={[s.tab, view === 'leaderboard' && { borderBottomColor: colors.accent, borderBottomWidth: 2 }]} onPress={() => { setView('leaderboard'); }}>
            <Text style={[s.tabText, { color: view === 'leaderboard' ? colors.accent : colors.textMuted }]}>Leaderboard</Text>
          </TouchableOpacity>
        </View>
        {onClose && <TouchableOpacity testID="growth-close" onPress={onClose} style={s.closeBtn}><Ionicons name="close" size={22} color={colors.textMuted} /></TouchableOpacity>}
      </View>

      <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent} showsVerticalScrollIndicator={false}>
        {view === 'profile' ? (
          <>
            {/* Identity + Rank */}
            <View testID="growth-identity" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={s.identityRow}>
                <View style={[s.avatar, { backgroundColor: colors.accent + '20' }]}>
                  <Text style={[s.avatarText, { color: colors.accent }]}>{(user?.name || 'U')[0].toUpperCase()}</Text>
                </View>
                <View style={s.identityInfo}>
                  <Text style={[s.userName, { color: colors.textPrimary }]}>{user?.name || 'User'}</Text>
                  <View style={s.rankRow}>
                    <Text style={[s.rankLabel, { color: colors.textMuted }]}>Rank</Text>
                    <Text style={[s.rankValue, { color: rankColor }]}>#{profile.rank || '—'}</Text>
                    {profile.rankDelta !== 0 && (
                      <View style={s.deltaChip}>
                        <Ionicons name={deltaIcon as any} size={12} color={deltaColor} />
                        <Text style={[s.deltaText, { color: deltaColor }]}>{Math.abs(profile.rankDelta)}</Text>
                      </View>
                    )}
                  </View>
                </View>
                <View style={s.scoreBlock}>
                  <Text style={[s.scoreValue, { color: colors.textPrimary }]}>{profile.seasonScore}</Text>
                  <Text style={[s.scoreLabel, { color: colors.textMuted }]}>Score</Text>
                </View>
              </View>
              <View style={[s.seasonBadge, { backgroundColor: colors.accent + '15' }]}>
                <Ionicons name="trophy" size={14} color={colors.accent} />
                <Text style={[s.seasonText, { color: colors.accent }]}>{profile.season.name}</Text>
              </View>
            </View>

            {/* Progress */}
            <View testID="growth-progress" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.nextReward')}</Text>
              {profile.nextMilestone ? (
                <>
                  <Text style={[s.progressLabel, { color: colors.textPrimary }]}>
                    {profile.nextMilestone.need} more paid referral{profile.nextMilestone.need > 1 ? 's' : ''}
                  </Text>
                  <Text style={[s.progressReward, { color: colors.accent }]}>→ {profile.nextMilestone.label}</Text>
                  <View style={[s.progressBar, { backgroundColor: colors.border }]}>
                    <View style={[s.progressFill, { width: `${progressPct}%`, backgroundColor: colors.accent }]} />
                  </View>
                  <Text style={[s.progressPct, { color: colors.textMuted }]}>{progressPct}%</Text>
                </>
              ) : (
                <Text style={[s.progressLabel, { color: '#2FE6A6' }]}>{t('growth.allMilestonesReached')}</Text>
              )}
            </View>

            {/* Referral Code */}
            <View testID="growth-code" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.yourReferralCode')}</Text>
              <View style={s.codeRow}>
                <Text style={[s.codeValue, { color: colors.textPrimary }]}>{profile.code}</Text>
                <TouchableOpacity testID="growth-copy-code" style={[s.codeBtn, { backgroundColor: colors.accent + '15' }]} onPress={copyCode}>
                  <Text style={[s.codeBtnText, { color: colors.accent }]}>{copied ? 'Copied!' : 'Copy'}</Text>
                </TouchableOpacity>
              </View>
              <TouchableOpacity testID="growth-share-btn" style={[s.shareBtn, { backgroundColor: colors.accent }]} onPress={shareCode}>
                <Ionicons name="share-outline" size={18} color="#fff" />
                <Text style={s.shareBtnText}>{t('growth.shareInviteLink')}</Text>
              </TouchableOpacity>
            </View>

            {/* Leaderboard Preview */}
            <View testID="growth-leaderboard-preview" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={s.cardTitleRow}>
                <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.topThisSeason')}</Text>
                <TouchableOpacity onPress={() => setView('leaderboard')}>
                  <Text style={[s.viewAll, { color: colors.accent }]}>View all →</Text>
                </TouchableOpacity>
              </View>
              {board.slice(0, 5).map((e, i) => (
                <View key={i} style={[s.boardRow, { borderBottomColor: colors.border }]}>
                  <Text style={[s.boardRank, { color: i < 3 ? '#f59e0b' : colors.textMuted }]}>#{e.rank}</Text>
                  <Text style={[s.boardName, { color: colors.textPrimary }]} numberOfLines={1}>{e.name}</Text>
                  <Text style={[s.boardScore, { color: colors.textPrimary }]}>{e.score}</Text>
                </View>
              ))}
              {board.length === 0 && <Text style={[s.emptyText, { color: colors.textMuted }]}>{t('growth.noEntriesYetBeThe')}</Text>}
            </View>

            {/* Reward Ladder */}
            <View testID="growth-rewards" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.rewardLadder')}</Text>
              {milestones.map((m, i) => {
                const done = paidCount >= m.paid;
                return (
                  <View key={i} style={s.milestoneRow}>
                    <Ionicons name={done ? 'checkmark-circle' : 'ellipse-outline'} size={20} color={done ? '#2FE6A6' : colors.textMuted} />
                    <Text style={[s.milestoneText, { color: done ? '#2FE6A6' : colors.textPrimary }]}>{m.paid} referral{m.paid > 1 ? 's' : ''}</Text>
                    <Text style={[s.milestoneReward, { color: done ? '#2FE6A6' : colors.accent }]}>{m.label}</Text>
                  </View>
                );
              })}
            </View>

            {/* Stats */}
            <View testID="growth-stats" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.yourStats')}</Text>
              <View style={s.statsGrid}>
                <StatBox label="Clicks" value={profile.stats.clicks} color={colors} />
                <StatBox label="Signups" value={profile.stats.signups} color={colors} />
                <StatBox label="Paid" value={profile.stats.paidConfirmed} color={colors} />
                <StatBox label="Pending" value={profile.stats.paidPending} color={colors} />
              </View>
            </View>

            {/* Apply Code */}
            <View testID="growth-apply" style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.applyReferralPromoCode')}</Text>
              <View style={s.applyRow}>
                <TextInput testID="growth-code-input" style={[s.applyInput, { color: colors.textPrimary, borderColor: colors.border, backgroundColor: colors.background }]} placeholder={t('growth.enterCode')} placeholderTextColor={colors.textMuted} value={promoCode} onChangeText={setPromoCode} autoCapitalize="characters" />
                <TouchableOpacity testID="growth-apply-btn" style={[s.applyBtn, { backgroundColor: colors.accent }]} onPress={applyCode}>
                  <Text style={s.applyBtnText}>Apply</Text>
                </TouchableOpacity>
              </View>
              {promoMsg ? <Text style={[s.promoMsg, { color: promoMsg.includes('!') ? '#2FE6A6' : '#FF6B6B' }]}>{promoMsg}</Text> : null}
            </View>
          </>
        ) : (
          /* LEADERBOARD VIEW */
          <>
            <View style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <View style={s.seasonHeader}>
                <Ionicons name="trophy" size={24} color="#f59e0b" />
                <Text style={[s.seasonTitle, { color: colors.textPrimary }]}>{profile.season.name}</Text>
              </View>
              <Text style={[s.seasonSub, { color: colors.textMuted }]}>Season leaderboard — top performers win PRO access</Text>
            </View>

            {/* Your position (sticky feel) */}
            <View testID="growth-your-rank" style={[s.card, { backgroundColor: colors.accent + '10', borderColor: colors.accent + '30' }]}>
              <View style={s.yourRankRow}>
                <View>
                  <Text style={[s.yourRankLabel, { color: colors.textMuted }]}>{t('growth.yourRank')}</Text>
                  <View style={s.rankRow}>
                    <Text style={[s.yourRankValue, { color: colors.accent }]}>#{profile.rank || '—'}</Text>
                    {profile.rankDelta !== 0 && (
                      <View style={s.deltaChip}>
                        <Ionicons name={deltaIcon as any} size={14} color={deltaColor} />
                        <Text style={[s.deltaText, { color: deltaColor }]}>{Math.abs(profile.rankDelta)}</Text>
                      </View>
                    )}
                  </View>
                </View>
                <View style={{ alignItems: 'flex-end' }}>
                  <Text style={[s.yourRankLabel, { color: colors.textMuted }]}>Score</Text>
                  <Text style={[s.yourRankValue, { color: colors.textPrimary }]}>{profile.seasonScore}</Text>
                </View>
              </View>
              {profile.nextMilestone && (
                <Text style={[s.yourNextText, { color: colors.accent }]}>+{profile.nextMilestone.need} paid → {profile.nextMilestone.label}</Text>
              )}
            </View>

            {/* Full leaderboard */}
            <View style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              {board.map((e, i) => {
                const isYou = e.user_id === user?.userId;
                const medalColor = i === 0 ? '#f59e0b' : i === 1 ? '#94a3b8' : i === 2 ? '#cd7f32' : undefined;
                return (
                  <View key={i} style={[s.lbRow, isYou && { backgroundColor: colors.accent + '08' }, { borderBottomColor: colors.border }]}>
                    <View style={[s.lbRankCircle, medalColor ? { backgroundColor: medalColor + '20' } : { backgroundColor: colors.background }]}>
                      <Text style={[s.lbRankNum, { color: medalColor || colors.textMuted }]}>{e.rank}</Text>
                    </View>
                    <View style={s.lbInfo}>
                      <Text style={[s.lbName, { color: colors.textPrimary }]} numberOfLines={1}>{e.name}{isYou ? ' (You)' : ''}</Text>
                      {e.delta !== 0 && (
                        <View style={s.lbDelta}>
                          <Ionicons name={e.delta > 0 ? 'arrow-up' : 'arrow-down'} size={10} color={e.delta > 0 ? '#2FE6A6' : '#FF6B6B'} />
                          <Text style={{ fontSize: 10, color: e.delta > 0 ? '#2FE6A6' : '#FF6B6B' }}>{Math.abs(e.delta)}</Text>
                        </View>
                      )}
                    </View>
                    <Text style={[s.lbScore, { color: colors.textPrimary }]}>{e.score}</Text>
                  </View>
                );
              })}
              {board.length === 0 && (
                <View style={s.emptyBoard}>
                  <Ionicons name="podium-outline" size={48} color={colors.textMuted} />
                  <Text style={[s.emptyText, { color: colors.textMuted, marginTop: 12 }]}>{t('growth.noEntriesYet')}</Text>
                  <Text style={[s.emptyText, { color: colors.textMuted }]}>{t('growth.inviteUsersToClimbThe')}</Text>
                </View>
              )}
            </View>

            {/* Season rewards */}
            <View style={[s.card, { backgroundColor: colors.surface, borderColor: colors.border }]}>
              <Text style={[s.cardTitle, { color: colors.textMuted }]}>{t('growth.seasonRewards')}</Text>
              <SeasonReward icon="medal" rank="Top 1" reward="1 year PRO" color="#f59e0b" colors={colors} />
              <SeasonReward icon="ribbon" rank="Top 3" reward="90 days PRO" color="#94a3b8" colors={colors} />
              <SeasonReward icon="star" rank="Top 10" reward="30 days PRO" color="#cd7f32" colors={colors} />
            </View>

            {/* CTA */}
            <TouchableOpacity testID="growth-invite-cta" style={[s.ctaBtn, { backgroundColor: colors.accent }]} onPress={shareCode}>
              <Ionicons name="rocket-outline" size={20} color="#fff" />
              <Text style={s.ctaBtnText}>Invite more → climb leaderboard</Text>
            </TouchableOpacity>
          </>
        )}
      </ScrollView>
    </View>
  );
}

function StatBox({ label, value, color }: { label: string; value: number; color: any }) {
  return (
    <View style={s.statBox}>
      <Text style={[s.statValue, { color: color.textPrimary }]}>{value}</Text>
      <Text style={[s.statLabel, { color: color.textMuted }]}>{label}</Text>
    </View>
  );
}

function SeasonReward({ icon, rank, reward, color, colors }: any) {
  return (
    <View style={[s.seasonRewardRow, { borderBottomColor: colors.border }]}>
      <Ionicons name={icon} size={20} color={color} />
      <View style={s.seasonRewardInfo}>
        <Text style={[s.seasonRewardRank, { color: colors.textPrimary }]}>{rank}</Text>
        <Text style={[s.seasonRewardText, { color: colors.textMuted }]}>{reward}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  header: { flexDirection: 'row', alignItems: 'center', borderBottomWidth: 1, paddingHorizontal: 16 },
  tabs: { flex: 1, flexDirection: 'row', gap: 16 },
  tab: { paddingVertical: 14, paddingHorizontal: 4 },
  tabText: { fontSize: 15, fontWeight: '600' },
  closeBtn: { padding: 8 },
  scroll: { flex: 1 },
  scrollContent: { padding: 16, paddingBottom: 40 },
  card: { borderWidth: 1, borderRadius: 14, padding: 16, marginBottom: 12 },
  cardTitle: { fontSize: 11, fontWeight: '700', letterSpacing: 0.8, marginBottom: 10, textTransform: 'uppercase' as any },
  cardTitleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 },
  viewAll: { fontSize: 12, fontWeight: '600' },
  // Identity
  identityRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  avatar: { width: 48, height: 48, borderRadius: 24, justifyContent: 'center', alignItems: 'center' },
  avatarText: { fontSize: 20, fontWeight: '800' },
  identityInfo: { flex: 1 },
  userName: { fontSize: 17, fontWeight: '700' },
  rankRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 2 },
  rankLabel: { fontSize: 12 },
  rankValue: { fontSize: 16, fontWeight: '800' },
  deltaChip: { flexDirection: 'row', alignItems: 'center', gap: 1 },
  deltaText: { fontSize: 11, fontWeight: '700' },
  scoreBlock: { alignItems: 'center' },
  scoreValue: { fontSize: 24, fontWeight: '800' },
  scoreLabel: { fontSize: 10, textTransform: 'uppercase' as any, letterSpacing: 0.5 },
  seasonBadge: { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 12, paddingVertical: 6, paddingHorizontal: 10, borderRadius: 8, alignSelf: 'flex-start' },
  seasonText: { fontSize: 12, fontWeight: '600' },
  // Progress
  progressLabel: { fontSize: 15, fontWeight: '600', marginBottom: 4 },
  progressReward: { fontSize: 14, fontWeight: '700', marginBottom: 10 },
  progressBar: { height: 6, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: 6, borderRadius: 3 },
  progressPct: { fontSize: 11, marginTop: 4, textAlign: 'right' },
  // Code
  codeRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  codeValue: { fontSize: 22, fontWeight: '800', letterSpacing: 1, flex: 1 },
  codeBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  codeBtnText: { fontSize: 13, fontWeight: '600' },
  shareBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, borderRadius: 12 },
  shareBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  // Board preview
  boardRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, gap: 10 },
  boardRank: { fontSize: 13, fontWeight: '700', width: 28 },
  boardName: { flex: 1, fontSize: 14, fontWeight: '500' },
  boardScore: { fontSize: 14, fontWeight: '700' },
  emptyText: { fontSize: 13, textAlign: 'center', paddingVertical: 16 },
  // Milestones
  milestoneRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 8 },
  milestoneText: { fontSize: 13, fontWeight: '500', flex: 1 },
  milestoneReward: { fontSize: 12, fontWeight: '600' },
  // Stats
  statsGrid: { flexDirection: 'row', gap: 8 },
  statBox: { flex: 1, alignItems: 'center', paddingVertical: 8 },
  statValue: { fontSize: 18, fontWeight: '800' },
  statLabel: { fontSize: 10, textTransform: 'uppercase' as any, marginTop: 2, letterSpacing: 0.5 },
  // Apply
  applyRow: { flexDirection: 'row', gap: 8 },
  applyInput: { flex: 1, borderWidth: 1, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontSize: 14 },
  applyBtn: { paddingHorizontal: 18, borderRadius: 10, justifyContent: 'center' },
  applyBtnText: { color: '#fff', fontSize: 14, fontWeight: '700' },
  promoMsg: { fontSize: 12, marginTop: 6 },
  // Leaderboard full
  seasonHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 4 },
  seasonTitle: { fontSize: 20, fontWeight: '800' },
  seasonSub: { fontSize: 13 },
  yourRankRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  yourRankLabel: { fontSize: 11, textTransform: 'uppercase' as any, letterSpacing: 0.5 },
  yourRankValue: { fontSize: 28, fontWeight: '800' },
  yourNextText: { fontSize: 12, fontWeight: '600', marginTop: 8 },
  lbRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 12, borderBottomWidth: 1 },
  lbRankCircle: { width: 32, height: 32, borderRadius: 16, justifyContent: 'center', alignItems: 'center' },
  lbRankNum: { fontSize: 13, fontWeight: '800' },
  lbInfo: { flex: 1 },
  lbName: { fontSize: 14, fontWeight: '600' },
  lbDelta: { flexDirection: 'row', alignItems: 'center', gap: 2, marginTop: 1 },
  lbScore: { fontSize: 16, fontWeight: '800' },
  emptyBoard: { alignItems: 'center', paddingVertical: 32 },
  seasonRewardRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1 },
  seasonRewardInfo: { flex: 1 },
  seasonRewardRank: { fontSize: 14, fontWeight: '700' },
  seasonRewardText: { fontSize: 12 },
  ctaBtn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 16, borderRadius: 14, marginTop: 4 },
  ctaBtnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
});
