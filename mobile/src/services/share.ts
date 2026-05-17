/**
 * Share Service (Growth Layer G1)
 * ================================
 * Telegram WebApp share → fallback to native React Native Share.
 * Always ensures a refCode is attached before sharing.
 *
 * Link format:
 *   https://t.me/FOMO_mini_bot?startapp=news_<ASSET>&ref=<REF>
 * For non-asset signals (metabrain/market-wide):
 *   https://t.me/FOMO_mini_bot?startapp=home&ref=<REF>
 */
import { Platform, Share } from 'react-native';
import { ensureOwnRefCode } from './referral.service';

const BOT = 'FOMO_mini_bot';

export interface ShareInput {
  asset?: string | null;
  source?: string | null;
  priority?: string | null;
  title?: string | null;
}

export interface ShareResult {
  ok: boolean;
  via: 'telegram' | 'native' | 'clipboard' | 'none';
  url: string;
  refCode: string | null;
}

function isTelegramWebApp(): boolean {
  try {
    if (Platform.OS !== 'web') return false;
    const tg: any = (globalThis as any).window?.Telegram?.WebApp;
    return !!(tg && tg.initData && tg.initDataUnsafe);
  } catch {
    return false;
  }
}

export function buildShareLink(asset: string | null | undefined, refCode: string | null | undefined): string {
  const cleanAsset = (asset || '').trim().toUpperCase();
  const startapp = cleanAsset ? `news_${cleanAsset}` : 'home';
  const base = `https://t.me/${BOT}?startapp=${encodeURIComponent(startapp)}`;
  if (refCode) return `${base}&ref=${encodeURIComponent(refCode)}`;
  return base;
}

export function buildShareText(input: ShareInput, url: string): string {
  const asset = (input.asset || '').trim().toUpperCase();
  const head = asset
    ? `\uD83D\uDE80 ${asset} setup forming on FOMO`
    : `\uD83D\uDE80 Market setup forming on FOMO`;
  const subtitle = 'system signals + narrative alignment';
  const cta = "\u2192 See what's forming";
  return `${head}\n${subtitle}\n${cta}\n${url}`;
}

/**
 * Open share UI. Returns ok:true if the flow completed (user dismissed or sent).
 * On web+Telegram: uses openTelegramLink which DOES NOT resolve completion,
 *   so we optimistically mark ok:true after calling it.
 */
export async function shareSignal(input: ShareInput): Promise<ShareResult> {
  // Always ensure a ref is present — no share without ref (per product rule).
  let refCode: string | null = null;
  try {
    refCode = await ensureOwnRefCode();
  } catch {
    refCode = null;
  }

  const url = buildShareLink(input.asset, refCode);
  const text = buildShareText(input, url);

  // 1) Telegram WebApp path
  if (isTelegramWebApp()) {
    try {
      const tg: any = (globalThis as any).window?.Telegram?.WebApp;
      const tgShare = `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(text.replace(url, '').trim())}`;
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(tgShare);
      } else if (tg?.openLink) {
        tg.openLink(tgShare);
      } else if ((globalThis as any).window?.open) {
        (globalThis as any).window.open(tgShare, '_blank');
      }
      return { ok: true, via: 'telegram', url, refCode };
    } catch {
      // fall through to native / clipboard
    }
  }

  // 2) Native React Native Share (iOS/Android)
  if (Platform.OS !== 'web') {
    try {
      const res = await Share.share({ message: text, url });
      // res.action === 'sharedAction' → completed
      const completed = (res as any)?.action && (res as any).action !== 'dismissedAction';
      return { ok: !!completed, via: 'native', url, refCode };
    } catch {
      return { ok: false, via: 'none', url, refCode };
    }
  }

  // 3) Web fallback — navigator.share or clipboard
  try {
    const nav: any = (globalThis as any).navigator;
    if (nav?.share) {
      await nav.share({ text, url });
      return { ok: true, via: 'native', url, refCode };
    }
    if (nav?.clipboard?.writeText) {
      await nav.clipboard.writeText(text);
      return { ok: true, via: 'clipboard', url, refCode };
    }
  } catch {}
  return { ok: false, via: 'none', url, refCode };
}

/**
 * UI rule: when to show Share button.
 * Strict: CRITICAL, or source in {metabrain, listing, polymarket},
 *         or (HIGH and watchersCount > 80).
 */
export function canShareSignal(signal: {
  priority?: string | null;
  source?: string | null;
  watchersCount?: number | null;
}): boolean {
  const p = (signal.priority || '').toUpperCase();
  const src = (signal.source || '').toLowerCase();
  const watchers = Number(signal.watchersCount || 0);
  if (p === 'CRITICAL') return true;
  if (['metabrain', 'listing', 'polymarket'].includes(src)) return true;
  if (p === 'HIGH' && watchers > 80) return true;
  return false;
}
