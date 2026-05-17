/**
 * usePaywall — contextual paywall hook for the Signal Loop.
 *
 * Returns:
 *   - ctx: { state: 'cold'|'warm'|'hot', headline, subline, cta, is_subscribed }
 *   - startCheckout({ surface, signalId, signal_source }) — attribution-safe checkout
 *   - showIdentity — post-conversion identity loop message + hero_override
 *
 * Usage:
 *   const { ctx, startCheckout } = usePaywall({ surface: 'edge' });
 *   if (ctx.is_subscribed) return null;  // PRO users see nothing
 *   <Text>{ctx.headline}</Text>
 *   <Pressable onPress={() => startCheckout({ signalId: hero?.signalId })}>
 *     <Text>{ctx.cta}</Text>
 *   </Pressable>
 */
import { useCallback, useEffect, useState } from 'react';
import { Linking } from 'react-native';
import { apiClient } from '../services/api/api-client';
import { track } from '../services/analytics';

export type PaywallState = 'cold' | 'warm' | 'hot';
export type Surface = 'hero' | 'edge' | 'missed' | 'feed' | 'push' | 'unknown';

export interface PaywallContext {
  ok: boolean;
  state: PaywallState;
  surface: Surface;
  headline: string;
  subline: string;
  cta: string;
  reason: string;
  signals: {
    edge_open: number;
    hero_tap: number;
    missed_seen: number;
    hero_view: number;
  };
  is_subscribed: boolean;
}

export interface IdentityMessage {
  ok: boolean;
  percent_ahead: number;
  headline: string;
  subline: string;
  hero_override: {
    headline: string;
    subline: string;
    ttl_hours: number;
  } | null;
}

interface StartCheckoutArgs {
  surface?: Surface;
  signalId?: string;
  signal_source?: string;
  plan_id?: 'month' | 'year';
}

export function usePaywall({ surface = 'edge' }: { surface?: Surface } = {}) {
  const [ctx, setCtx] = useState<PaywallContext | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    try {
      const res = await apiClient.get(`/api/paywall/context?surface=${surface}`);
      setCtx(res.data as PaywallContext);
    } catch {
      setCtx(null);
    } finally {
      setLoading(false);
    }
  }, [surface]);

  useEffect(() => {
    reload();
  }, [reload]);

  const startCheckout = useCallback(
    async ({ surface: s, signalId, signal_source, plan_id = 'month' }: StartCheckoutArgs = {}) => {
      const state = ctx?.state ?? 'cold';
      // 1. Attribution analytics — BEFORE redirect
      await track('edge_paywall_click', { state, signalId, signal_source });

      // 2. Create checkout with attribution
      try {
        const res = await apiClient.post('/api/billing/v2/checkout', {
          plan_id,
          surface: s ?? surface,
          context: { state, signalId, signal_source: signal_source ?? surface },
        });
        const { ok, url, error } = res.data || {};
        if (!ok || !url) {
          console.warn('[paywall] checkout failed:', error);
          return { ok: false, error };
        }
        // 3. Open provider checkout (Stripe Checkout / NOWPayments invoice)
        await Linking.openURL(url);
        return { ok: true, url };
      } catch (e: unknown) {
        console.warn('[paywall] checkout exception', e);
        return { ok: false, error: 'network' };
      }
    },
    [ctx, surface],
  );

  const showView = useCallback(async () => {
    if (!ctx || ctx.is_subscribed) return;
    await track('edge_paywall_view', { state: ctx.state });
  }, [ctx]);

  return { ctx, loading, reload, startCheckout, showView };
}

/**
 * useIdentity — post-conversion identity loop.
 * Call on app boot after login. If `hero_override` is present,
 * swap the next Hero screen headline with it for 24h.
 */
export function useIdentity() {
  const [data, setData] = useState<IdentityMessage | null>(null);
  useEffect(() => {
    (async () => {
      try {
        const res = await apiClient.get('/api/paywall/identity');
        setData(res.data as IdentityMessage);
      } catch {
        setData(null);
      }
    })();
  }, []);
  return data;
}
