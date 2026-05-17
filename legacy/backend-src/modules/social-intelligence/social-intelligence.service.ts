/**
 * Social Intelligence Service — Main Orchestrator
 *
 * Pipeline: raw events → cluster → echo filter → origin detect →
 * propagation → influence → saturation → narrative lifecycle →
 * aggregation → market social impact
 */
import { getDb } from '../../db/mongodb.js';
import type { SocialEvent } from './types/social.types.js';
import type { AccountProfile } from './types/account.types.js';
import type { SocialIntel } from './types/narrative.types.js';
import { buildClusters } from './services/cluster-builder.service.js';
import { aggregateCluster } from './services/social-signal-aggregator.service.js';
import { computeMarketSocialImpact } from './services/market-social-impact.service.js';

async function loadSocialEvents(asset: string, hoursBack: number = 48): Promise<SocialEvent[]> {
  try {
    const db = getDb();
    const since = new Date(Date.now() - hoursBack * 3600 * 1000);

    const docs = await db.collection('notification_events')
      .find({
        $or: [
          { assets: asset },
          { entities: { $in: [asset] } },
          { text: { $regex: asset, $options: 'i' } },
        ],
        created_at: { $gte: since.toISOString() },
      })
      .sort({ created_at: -1 })
      .limit(100)
      .project({ _id: 0 })
      .toArray();

    return docs.map((d: any) => ({
      id: d.id || d.event_id || `ne_${Math.random().toString(36).slice(2, 8)}`,
      platform: (d.source || '').toLowerCase().includes('twitter') ? 'twitter' as const : 'news' as const,
      authorId: d.source || d.author_id || 'unknown',
      authorName: d.source || d.author_name || 'unknown',
      text: d.text || d.title || d.content || '',
      timestamp: d.created_at ? new Date(d.created_at).getTime() : Date.now(),
      entities: d.entities || d.assets || [],
      tags: d.tags || [],
      repostOfId: d.repost_of || null,
      quotedEventId: d.quoted_event || null,
      replyToId: d.reply_to || null,
      metrics: d.metrics || {},
    }));
  } catch {
    return [];
  }
}

async function loadAccountProfiles(): Promise<Map<string, AccountProfile>> {
  const profiles = new Map<string, AccountProfile>();
  try {
    const db = getDb();
    const docs = await db.collection('social_account_profiles')
      .find({}).project({ _id: 0 }).limit(500).toArray();
    for (const d of docs) {
      profiles.set(d.accountId, d as AccountProfile);
    }
  } catch {
    // No profiles yet — engine will use heuristics
  }
  return profiles;
}

export async function analyzeSocial(asset: string): Promise<SocialIntel> {
  const events = await loadSocialEvents(asset);
  if (!events.length) {
    return computeMarketSocialImpact([]);
  }

  const profiles = await loadAccountProfiles();
  const clusters = buildClusters(events, asset);

  const assessments = clusters.map(cl => aggregateCluster(cl, profiles));

  return computeMarketSocialImpact(assessments);
}

export async function analyzeSocialBatch(assets: string[]): Promise<Record<string, SocialIntel>> {
  const results: Record<string, SocialIntel> = {};
  const uniqueAssets = [...new Set(assets)];

  for (const asset of uniqueAssets) {
    results[asset] = await analyzeSocial(asset);
  }

  return results;
}

// Exposed for detailed debugging
export async function analyzeSocialDetailed(asset: string) {
  const events = await loadSocialEvents(asset);
  const profiles = await loadAccountProfiles();
  const clusters = buildClusters(events, asset);
  const assessments = clusters.map(cl => aggregateCluster(cl, profiles));
  const impact = computeMarketSocialImpact(assessments);

  return {
    eventsCount: events.length,
    clustersCount: clusters.length,
    clusters: clusters.map(cl => ({
      clusterId: cl.clusterId,
      eventCount: cl.events.length,
      canonicalText: cl.canonicalText.slice(0, 100),
    })),
    assessments,
    impact,
  };
}
