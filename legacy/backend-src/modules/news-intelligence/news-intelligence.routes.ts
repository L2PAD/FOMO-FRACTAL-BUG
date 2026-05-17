/**
 * News Intelligence Routes v2
 * ============================
 * User-facing API for the news intelligence layer.
 *
 * Endpoints:
 *   GET /feed              — Ranked, clustered news feed
 *   GET /breaking          — Breaking news only
 *   GET /asset/:symbol     — News for a specific asset
 *   GET /event/:id         — Single cluster detail
 *   GET /trends            — Event type and asset trends
 *   GET /stats             — Admin clustering stats
 */

import type { FastifyInstance } from 'fastify';
import { newsIntelligencePipeline } from './pipeline.service.js';

export async function registerNewsIntelligenceRoutes(app: FastifyInstance): Promise<void> {
  /**
   * GET /feed — Ranked, clustered news feed
   * Query: ?limit=20&hours=24&asset=BTC&eventType=hack&breakingOnly=false&importance=high&page=1
   */
  app.get('/feed', async (request) => {
    const q = request.query as Record<string, string>;

    const result = await newsIntelligencePipeline.buildFeed({
      limit: Math.min(parseInt(q.limit || '20', 10), 50),
      hoursBack: Math.min(parseInt(q.hours || '24', 10), 72),
      asset: q.asset || undefined,
      eventType: q.eventType || undefined,
      breakingOnly: q.breakingOnly === 'true',
      importanceBand: (['high', 'medium', 'low'].includes(q.importance) ? q.importance : undefined) as any,
      page: Math.max(1, parseInt(q.page || '1', 10)),
    });

    return { ok: true, data: result };
  });

  /**
   * GET /breaking — Breaking news only
   */
  app.get('/breaking', async () => {
    const result = await newsIntelligencePipeline.buildFeed({
      limit: 10,
      hoursBack: 6,
      breakingOnly: true,
    });
    return { ok: true, data: result };
  });

  /**
   * GET /asset/:symbol — News for a specific asset
   */
  app.get('/asset/:symbol', async (request) => {
    const params = request.params as { symbol: string };
    const q = request.query as Record<string, string>;

    const result = await newsIntelligencePipeline.buildFeed({
      limit: Math.min(parseInt(q.limit || '20', 10), 50),
      hoursBack: Math.min(parseInt(q.hours || '24', 10), 72),
      asset: params.symbol.toUpperCase(),
      page: Math.max(1, parseInt(q.page || '1', 10)),
    });

    return { ok: true, data: result };
  });

  /**
   * GET /event/:id — Single cluster detail
   */
  app.get('/event/:id', async (request, reply) => {
    const params = request.params as { id: string };

    const result = await newsIntelligencePipeline.buildFeed({
      limit: 100,
      hoursBack: 48,
    });

    const cluster = result.clusters.find(c => c.clusterId === params.id);
    if (!cluster) {
      return reply.code(404).send({ ok: false, error: 'Cluster not found' });
    }

    return { ok: true, data: cluster };
  });

  /**
   * GET /trends — Event type and asset trends
   */
  app.get('/trends', async () => {
    const stats = await newsIntelligencePipeline.getClusterStats();
    return {
      ok: true,
      data: {
        eventTypes: stats.eventTypeDistribution,
        importance: stats.importanceDistribution,
        clustering: {
          totalRaw: stats.totalRawNews,
          totalClusters: stats.totalClusters,
          avgClusterSize: stats.avgClusterSize,
          singleSource: stats.singleSourceClusters,
          multiSource: stats.multiSourceClusters,
          compressionRatio: stats.compressionRatio,
        },
        breaking: stats.breakingCount,
        topClusters: stats.topClusters,
      },
    };
  });

  /**
   * GET /stats — Admin clustering stats
   */
  app.get('/stats', async () => {
    const stats = await newsIntelligencePipeline.getClusterStats();
    return { ok: true, data: stats };
  });

  /**
   * GET /velocity — Narrative velocity v2
   * 
   * baseline = avg(clusters_per_hour за 24h)
   * current  = clusters_last_1h
   * ratio    = current / baseline
   * growth   = (current - baseline) / baseline
   * 
   * Levels:
   *   ratio < 0.8 → CALM
   *   ratio < 1.2 → NORMAL
   *   ratio < 1.8 → ELEVATED
   *   else        → SPIKE
   */
  app.get('/velocity', async () => {
    // Fetch clusters in parallel for different windows
    const [last1h, last3h, last6h, last24h, last48h] = await Promise.all([
      newsIntelligencePipeline.buildFeed({ limit: 100, hoursBack: 1 }),
      newsIntelligencePipeline.buildFeed({ limit: 100, hoursBack: 3 }),
      newsIntelligencePipeline.buildFeed({ limit: 100, hoursBack: 6 }),
      newsIntelligencePipeline.buildFeed({ limit: 100, hoursBack: 24 }),
      newsIntelligencePipeline.buildFeed({ limit: 100, hoursBack: 48 }),
    ]);

    const current = last1h.clusters.length;
    const clusters3h = last3h.clusters.length;
    const clusters6h = last6h.clusters.length;
    const clusters24h = last24h.clusters.length;
    const clusters48h = last48h.clusters.length;

    // ── Baseline: avg clusters per hour over 24h ──
    const baseline = clusters24h > 0 ? +(clusters24h / 24).toFixed(2) : 0;

    // ── Velocity ratio ──
    const velocityRatio = baseline > 0 ? +(current / baseline).toFixed(2) : (current > 0 ? 5 : 0);

    // ── Growth vs baseline ──
    const growthPct = baseline > 0
      ? +(((current - baseline) / baseline) * 100).toFixed(1)
      : (current > 0 ? 100 : 0);

    // ── Determine level by ratio ──
    let level: 'CALM' | 'NORMAL' | 'ELEVATED' | 'SPIKE' = 'CALM';
    if (velocityRatio >= 1.8) level = 'SPIKE';
    else if (velocityRatio >= 1.2) level = 'ELEVATED';
    else if (velocityRatio >= 0.8) level = 'NORMAL';

    // Override: breaking burst always = SPIKE
    const breakingLast1h = last1h.clusters.filter((c: any) => c.isBreaking).length;
    if (breakingLast1h >= 2) level = 'SPIKE';

    // ── High importance in last hour ──
    const highLast1h = last1h.clusters.filter((c: any) =>
      c.importanceBand === 'high' || (c.importance ?? c.importanceScore ?? 0) >= 65
    ).length;

    // ── 24h trend: compare today vs yesterday ──
    const yesterdayOnly = clusters48h - clusters24h;
    const trend24hPct = yesterdayOnly > 0
      ? +(((clusters24h - yesterdayOnly) / yesterdayOnly) * 100).toFixed(1)
      : (clusters24h > 0 ? 100 : 0);

    // ── CPH breakdown ──
    const cph3h = +(clusters3h / 3).toFixed(1);
    const cph6h = +(clusters6h / 6).toFixed(1);

    const messages: Record<string, string> = {
      CALM: 'Market is quiet',
      NORMAL: 'Normal news flow',
      ELEVATED: 'News velocity increasing',
      SPIKE: 'Market is heating up — spike detected',
    };

    return {
      ok: true,
      data: {
        // Core velocity metrics
        current,
        baseline,
        velocityRatio,
        growthPct,
        level,
        message: messages[level],

        // Detail
        clustersPerHour: { '1h': current, '3h': cph3h, '6h': cph6h },
        newClustersLast1h: current,
        breakingLast1h,
        highImportanceLast1h: highLast1h,

        // 24h trend
        trend24hPct,
        clusters24h,
        clustersYesterday: yesterdayOnly,

        ts: new Date().toISOString(),
      },
    };
  });

  /**
   * GET /digest — Daily market brief (top 5 + sentiment shift + velocity)
   */
  app.get('/digest', async () => {
    // Get 24h feed + 48h for comparison
    const [feed24, feed48] = await Promise.all([
      newsIntelligencePipeline.buildFeed({ limit: 50, hoursBack: 24 }),
      newsIntelligencePipeline.buildFeed({ limit: 50, hoursBack: 48 }),
    ]);

    const clusters24 = feed24.clusters;
    const clusters48 = feed48.clusters;

    // Top 5 events by importance
    const top5 = clusters24
      .sort((a: any, b: any) => (b.importance ?? b.importanceScore ?? 0) - (a.importance ?? a.importanceScore ?? 0))
      .slice(0, 5)
      .map((c: any) => ({
        title: c.title,
        eventType: c.eventType,
        importance: c.importance ?? c.importanceScore ?? 0,
        importanceBand: c.importanceBand,
        sentiment: c.sentimentHint || c.sentiment || 'neutral',
        assets: c.assets || [],
        sourcesCount: c.sourcesCount ?? c.sources?.length ?? 0,
        isBreaking: !!c.isBreaking,
      }));

    // Sentiment distribution (24h)
    const sentimentCount = { bullish: 0, bearish: 0, neutral: 0 };
    for (const c of clusters24) {
      const s = ((c as any).sentimentHint || (c as any).sentiment || 'neutral').toLowerCase();
      if (s === 'bullish' || s === 'positive') sentimentCount.bullish++;
      else if (s === 'bearish' || s === 'negative') sentimentCount.bearish++;
      else sentimentCount.neutral++;
    }
    const total24 = clusters24.length || 1;

    // Sentiment shift: compare today vs yesterday
    const yesterdayClusters = clusters48.filter((c: any) => {
      const age = Date.now() - new Date(c.publishedAt || c.createdAt || 0).getTime();
      return age > 24 * 3600000; // older than 24h
    });
    const yesterdaySent = { bullish: 0, bearish: 0 };
    for (const c of yesterdayClusters) {
      const s = ((c as any).sentimentHint || (c as any).sentiment || '').toLowerCase();
      if (s === 'bullish' || s === 'positive') yesterdaySent.bullish++;
      else if (s === 'bearish' || s === 'negative') yesterdaySent.bearish++;
    }
    const todayBullPct = (sentimentCount.bullish / total24) * 100;
    const yesterdayTotal = yesterdayClusters.length || 1;
    const yesterdayBullPct = (yesterdaySent.bullish / yesterdayTotal) * 100;
    const sentimentShift = +(todayBullPct - yesterdayBullPct).toFixed(1);

    // Velocity comparison
    const velocityChange = yesterdayClusters.length > 0
      ? +((clusters24.length - yesterdayClusters.length) / yesterdayClusters.length * 100).toFixed(1)
      : 0;

    // Breaking count
    const breakingCount = clusters24.filter((c: any) => c.isBreaking).length;

    // Why it matters — rule-based summary
    const whyItMatters: string[] = [];
    if (breakingCount > 0) whyItMatters.push(`${breakingCount} breaking event(s) detected`);
    if (sentimentShift > 10) whyItMatters.push('Sentiment shifting bullish');
    else if (sentimentShift < -10) whyItMatters.push('Sentiment shifting bearish');
    if (velocityChange > 30) whyItMatters.push(`News velocity up ${velocityChange}% vs yesterday`);
    const topTypes = [...new Set(top5.map(e => e.eventType))].filter(Boolean);
    if (topTypes.length) whyItMatters.push(`Key themes: ${topTypes.join(', ')}`);

    return {
      ok: true,
      data: {
        period: '24h',
        generatedAt: new Date().toISOString(),
        totalEvents: clusters24.length,
        breakingCount,
        top5,
        sentiment: {
          bullish: `${((sentimentCount.bullish / total24) * 100).toFixed(0)}%`,
          bearish: `${((sentimentCount.bearish / total24) * 100).toFixed(0)}%`,
          neutral: `${((sentimentCount.neutral / total24) * 100).toFixed(0)}%`,
        },
        sentimentShiftPct: sentimentShift,
        velocityChangePct: velocityChange,
        whyItMatters,
      },
    };
  });

  /**
   * POST /analyze-url — Sentiment analysis of a news article URL
   * 
   * Extracts text from URL, runs through keyword-based sentiment engine.
   * Returns sentiment label (POSITIVE/NEGATIVE/NEUTRAL), score, signals.
   */
  app.post('/analyze-url', async (req: any, reply: any) => {
    const { url } = req.body || {};

    if (!url || typeof url !== 'string') {
      return reply.status(400).send({ ok: false, error: 'INVALID_INPUT', message: 'URL is required' });
    }

    let parsed: URL;
    try {
      parsed = new URL(url);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') throw new Error('bad protocol');
    } catch {
      return reply.status(400).send({ ok: false, error: 'INVALID_URL', message: 'Invalid URL' });
    }

    const domain = parsed.hostname.replace(/^www\./, '');

    try {
      // Fetch the URL
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(url, {
        signal: controller.signal,
        headers: { 'User-Agent': 'Mozilla/5.0 IntelBot/1.0', 'Accept': 'text/html,application/xhtml+xml' },
      });
      clearTimeout(timeout);

      if (!response.ok) {
        return reply.send({
          ok: false,
          error: 'FETCH_FAILED',
          message: `HTTP ${response.status} from ${domain}`,
        });
      }

      const html = await response.text();

      // Extract text content from HTML
      const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
      const title = titleMatch ? titleMatch[1].trim().replace(/&amp;/g, '&').replace(/&#39;/g, "'") : `Article from ${domain}`;

      // Extract meta description
      const descMatch = html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']+)["']/i)
        || html.match(/<meta[^>]*content=["']([^"']+)["'][^>]*name=["']description["']/i);
      const description = descMatch ? descMatch[1].trim() : '';

      // Strip HTML tags, extract text
      const textContent = html
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/\s+/g, ' ')
        .trim()
        .substring(0, 5000);

      // Keyword-based sentiment analysis
      const BULLISH_KEYWORDS = [
        'surge', 'soar', 'rally', 'bullish', 'gain', 'rise', 'growth', 'moon', 'pump',
        'breakout', 'record high', 'all-time high', 'ath', 'buy', 'adoption', 'milestone',
        'approval', 'etf approved', 'partnership', 'upgrade', 'institutional', 'accumulate',
        'positive', 'optimistic', 'recovery', 'breakthrough', 'momentum', 'green',
      ];
      const BEARISH_KEYWORDS = [
        'crash', 'plunge', 'dump', 'bearish', 'decline', 'drop', 'fall', 'loss', 'sell',
        'correction', 'fear', 'panic', 'ban', 'hack', 'exploit', 'rug pull', 'scam',
        'regulation', 'crackdown', 'lawsuit', 'sec', 'fine', 'penalty', 'warning',
        'negative', 'pessimistic', 'recession', 'collapse', 'liquidation', 'red',
      ];

      const lower = (textContent + ' ' + title + ' ' + description).toLowerCase();
      const bullCount = BULLISH_KEYWORDS.filter(kw => lower.includes(kw)).length;
      const bearCount = BEARISH_KEYWORDS.filter(kw => lower.includes(kw)).length;
      const bullHits = BULLISH_KEYWORDS.filter(kw => lower.includes(kw));
      const bearHits = BEARISH_KEYWORDS.filter(kw => lower.includes(kw));

      const total = bullCount + bearCount || 1;
      const rawScore = (bullCount - bearCount) / total; // -1 to +1
      const score = (rawScore + 1) / 2; // 0 to 1 (0=very bearish, 1=very bullish)
      const confidence = Math.min(0.95, 0.4 + (total * 0.05));

      let label: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL' = 'NEUTRAL';
      if (rawScore > 0.15) label = 'POSITIVE';
      else if (rawScore < -0.15) label = 'NEGATIVE';

      const reasons: string[] = [];
      if (bullHits.length > 0) reasons.push(`Bullish signals: ${bullHits.slice(0, 4).join(', ')}`);
      if (bearHits.length > 0) reasons.push(`Bearish signals: ${bearHits.slice(0, 4).join(', ')}`);
      if (bullCount > bearCount) reasons.push(`${bullCount} positive vs ${bearCount} negative keywords`);
      else if (bearCount > bullCount) reasons.push(`${bearCount} negative vs ${bullCount} positive keywords`);
      else reasons.push('Balanced sentiment detected');

      return reply.send({
        ok: true,
        data: {
          url,
          extracted: {
            title,
            description: description || `Content from ${domain}`,
            textLen: textContent.length,
            preview: (description || textContent).substring(0, 280),
            domain,
            contentType: 'text/html',
          },
          result: {
            label,
            score,
            confidence,
            meta: {
              modelVersion: 'news-intel-v1',
              mode: 'URL',
              source: url,
              latencyMs: 0,
              rulesBoost: 0,
              confidenceScore: confidence,
              reasons,
              rulesApplied: bullHits.concat(bearHits).slice(0, 8),
            },
          },
        },
      });
    } catch (err: any) {
      if (err.name === 'AbortError') {
        return reply.send({ ok: false, error: 'TIMEOUT', message: 'Request timed out (10s)' });
      }
      return reply.send({ ok: false, error: 'FETCH_FAILED', message: err.message });
    }
  });

  console.log('[NewsIntelligence] Routes v2 registered');

  // ═══ Source Quality API ═══
  app.get('/source-quality', async () => {
    const { sourceQualityService } = await import('./source-quality.service.js');
    return {
      ok: true,
      data: {
        summary: sourceQualityService.getSummary(),
        sources: sourceQualityService.getAllScores(),
      },
    };
  });
}
