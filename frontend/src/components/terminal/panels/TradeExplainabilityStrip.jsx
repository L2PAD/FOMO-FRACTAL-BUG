/**
 * TradeExplainabilityStrip — top "System Bar".
 *
 * 5 human-readable status pills, semantic color only:
 *   System  · Market · Signal · Decision · Risk
 *
 * Source: GET /api/trading/system/explainability  (untouched).
 * No new fields, no API change. Pure label/visual mapping.
 */
import { useEffect, useState } from "react";
import { Eye, Compass, Target, GitBranch, ShieldCheck } from "lucide-react";

const ICON = { width: 16, height: 16, strokeWidth: 1.75 };

// ── tone palette ────────────────────────────────────────────────
// active   = system is actively doing something (trading / setup ready / risk normal)
// waiting  = neutral / observing / no setup
// blocked  = risk blocks trading
// unknown  = data not classified yet
const TONE = {
  active:  'bg-emerald-50 text-emerald-700',
  waiting: 'bg-amber-50 text-amber-700',
  blocked: 'bg-red-50 text-red-700',
  unknown: 'bg-gray-100 text-gray-600',
};

function Pill({ icon: Icon, label, value, tone = 'unknown' }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12px] ${TONE[tone]}`}
    >
      <Icon {...ICON} className="opacity-80" />
      <span className="text-gray-500">{label}</span>
      <span className="font-semibold">{value}</span>
    </span>
  );
}

function toTitle(s) {
  if (!s) return '';
  return String(s)
    .toLowerCase()
    .replace(/_/g, ' ')
    .replace(/^./, (c) => c.toUpperCase());
}

export default function TradeExplainabilityStrip() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    async function load() {
      try {
        const API_URL = process.env.REACT_APP_BACKEND_URL || '';
        const res = await fetch(`${API_URL}/api/trading/system/explainability`);
        const json = await res.json();
        if (alive) setData(json.data || null);
      } catch (_e) {
        if (alive) setData(null);
      }
    }
    load();
    const i = setInterval(load, 5000);
    return () => { alive = false; clearInterval(i); };
  }, []);

  // Map raw payload → human strings + tones.
  const view = (() => {
    if (!data) return null;

    // System: observing in bootstrap, trading in production.
    const isProd = data.mode === 'production';
    const system = {
      label: 'System',
      value: isProd ? 'Trading' : 'Observing',
      tone:  isProd ? 'active' : 'waiting',
    };

    // Market: regime as-is (humanised).
    const regimeRaw = String(data.regime || '').toLowerCase();
    const market = {
      label: 'Market',
      value: regimeRaw && regimeRaw !== 'unknown' ? toTitle(regimeRaw) : 'Unknown',
      tone:  regimeRaw && regimeRaw !== 'unknown' ? 'active' : 'unknown',
    };

    // Signal: any setup generated this cycle?
    const signalsN = Number(data.signals?.generated ?? 0);
    const signal = {
      label: 'Signal',
      value: signalsN > 0 ? `${signalsN} active` : 'No active setup',
      tone:  signalsN > 0 ? 'active' : 'waiting',
    };

    // Decision: ready / filtered / waiting.
    const dOut = Number(data.allocator?.decisions_out ?? 0);
    const dIn  = Number(data.allocator?.signals_in ?? 0);
    const decision = dOut > 0
      ? { value: `${dOut} ready`,  tone: 'active'  }
      : dIn > 0
        ? { value: 'Filtered out', tone: 'waiting' }
        : { value: 'Waiting',      tone: 'waiting' };
    decision.label = 'Decision';

    // Risk: blocked vs normal — always last so the eye lands on it.
    const canTrade = data.risk?.can_trade !== false;
    const risk = {
      label: 'Risk',
      value: canTrade ? toTitle(data.risk?.reason || 'Normal') : 'Blocked',
      tone:  canTrade ? 'active' : 'blocked',
    };

    return { system, market, signal, decision, risk };
  })();

  if (!view) {
    return (
      <div
        className="flex items-center gap-2 px-1 py-1"
        data-testid="trade-explainability-strip"
      >
        <Pill icon={Eye}         label="System"   value="—" tone="unknown" />
        <Pill icon={Compass}     label="Market"   value="—" tone="unknown" />
        <Pill icon={Target}      label="Signal"   value="—" tone="unknown" />
        <Pill icon={GitBranch}   label="Decision" value="—" tone="unknown" />
        <Pill icon={ShieldCheck} label="Risk"     value="—" tone="unknown" />
      </div>
    );
  }

  return (
    <div
      className="flex flex-wrap items-center gap-2 px-1 py-1"
      data-testid="trade-explainability-strip"
      style={{ fontVariantNumeric: 'tabular-nums' }}
    >
      <Pill icon={Eye}         {...view.system}   />
      <Pill icon={Compass}     {...view.market}   />
      <Pill icon={Target}      {...view.signal}   />
      <Pill icon={GitBranch}   {...view.decision} />
      <Pill icon={ShieldCheck} {...view.risk}     />
    </div>
  );
}
