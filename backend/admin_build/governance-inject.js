/**
 * governance-inject.js — Governance Ledger with friction semantics.
 *
 * Adds a single sidebar nav «Управление» to the FOMO admin shell.
 * Activation mounts a 4-section governance surface into <main>.
 *
 * THIS IS NOT a control center / cockpit / live trading console.
 * It is a governance ledger — mutations are intentionally high-friction,
 * authority is server-validated, audit timeline is immutable-first.
 *
 * Architectural invariants (locked by contract — DO NOT VIOLATE):
 *
 *   1. SEMANTIC SEPARATION  commerce ≠ governance
 *      Tier defines the commercial product (free/pro/trader).
 *      liveAuthority is an admin operational decision that is NEVER
 *      auto-granted by buying a tier.  This is rendered verbatim in
 *      multiple visible locations.
 *
 *   2. FRICTION TIERS
 *        LOW    → tier change                       (single confirm)
 *        MEDIUM → override capability, console      (confirm + reason)
 *               mode change, grant base access
 *        HIGH   → grant live authority              (typed confirmation
 *               revoke live authority                + mandatory reason
 *                                                   + acknowledgement)
 *
 *   3. TYPED CONFIRMATION INVARIANT
 *      grant-live-authority requires the operator to literally type
 *      «GRANT LIVE TRADING» (exact match, case-sensitive).  Backend
 *      validates independently — frontend never trusts its own state.
 *
 *   4. NO COMMERCE VOCABULARY
 *      Never «enable live» / «activate trader» / «unlock trading» /
 *      «boost permissions».  Only «grant», «revoke», «authority»,
 *      «capability», «governance action».
 *
 *   5. AUDIT TIMELINE IS FIRST-CLASS
 *      Not «activity log» — it is the immutable governance timeline.
 *      Never collapsible by default.  Severity / actor / reason /
 *      before-after / timestamp.
 *
 *   6. MUTATION ROUTING — NO OPTIMISTIC UI
 *      Every mutation: POST → 200 → authoritative refetch → rerender.
 *      We NEVER mutate local state without re-reading the server.
 *      No local capability derivation — read structured[] verbatim.
 *
 *   7. AUTHORITY ACTIONS = SUBDUED
 *      Not hero, not sticky, not floating.  A normal panel section
 *      that demands attention through wording, not through visual
 *      promotion.
 *
 *   8. REUSE  window.__fomoAdminInject  primitives (no parallel
 *      framework, no separate overlay manager, no own state runtime).
 *
 * Endpoints consumed (admin-gated):
 *   GET  /api/admin/operator-access/list
 *   GET  /api/admin/operator-access/audit-timeline?userId={id}
 *   POST /api/admin/operator-access/set-tier
 *   POST /api/admin/operator-access/set-mode
 *   POST /api/admin/operator-access/set-console-access
 *   POST /api/admin/operator-access/grant
 *   POST /api/admin/operator-access/revoke
 *   POST /api/admin/operator-access/override-capability
 *   POST /api/admin/operator-access/grant-live-authority
 *   POST /api/admin/operator-access/revoke-live-authority
 */
(function () {
  'use strict';

  if (window.__fomoGovernanceInjectLoaded) return;
  window.__fomoGovernanceInjectLoaded = true;

  // ── Reuse canonical primitives (install fallbacks if loaded standalone)
  const FomoInject = (window.__fomoAdminInject = window.__fomoAdminInject || {});
  if (!FomoInject.getAdminToken) {
    FomoInject.getAdminToken = function () {
      try { const v = localStorage.getItem('admin_token'); if (v) return v.replace(/^"|"$/g, ''); } catch (_) {}
      return null;
    };
  }
  if (!FomoInject.fetchWithAdminJWT) {
    FomoInject.fetchWithAdminJWT = async function (path, opts) {
      opts = opts || {};
      const token = FomoInject.getAdminToken();
      const headers = Object.assign(
        { 'Content-Type': 'application/json' },
        token ? { Authorization: 'Bearer ' + token } : {},
        opts.headers || {}
      );
      const res = await fetch(path, Object.assign({}, opts, { headers, credentials: 'include' }));
      const txt = await res.text();
      let body = null;
      try { body = txt ? JSON.parse(txt) : null; } catch (_) { body = { raw: txt }; }
      if (!res.ok) { const err = new Error(res.status + ' ' + res.statusText); err.status = res.status; err.body = body; throw err; }
      return body;
    };
  }
  if (!FomoInject.destroyMountedPanel) {
    FomoInject.destroyMountedPanel = function (id) {
      const p = document.getElementById(id);
      if (p && p.parentElement) p.parentElement.removeChild(p);
    };
  }

  // ── Constants ──────────────────────────────────────────────────────
  const NAV_ID    = 'fomo-governance-nav';
  const PANEL_ID  = 'fomo-governance-panel';
  const CSS_ID    = 'fomo-governance-css';
  const MODAL_ID  = 'fomo-governance-modal';
  const HIDE_CLS  = 'fomo-governance-native-hidden';

  const ANCHOR_LABELS_AFTER  = ['Исполнение', 'Атрибуция', 'Billing'];
  const ANCHOR_LABELS_BEFORE = ['Referrals', 'Intel System'];

  const LIVE_AUTHORITY_PHRASE = 'GRANT LIVE TRADING';

  const TIER_VOCAB = ['free', 'pro', 'trader'];
  const MODE_VOCAB = ['paper', 'shadow', 'live', 'none'];
  const CAPABILITY_VOCAB = [
    'tradingOsVisible',
    'paperTrading',
    'shadowTrading',
    'executionConsole',
    'liveTrading',
  ];
  const SEVERITY_VOCAB = ['info', 'elevated', 'critical'];

  // Plain-language descriptors for each capability.  These are read-only
  // forensic labels — they DO NOT carry promotional or commerce wording.
  const CAPABILITY_LABELS = {
    tradingOsVisible: 'tradingOsVisible · surface visibility',
    paperTrading:     'paperTrading · simulated capital, no broker',
    shadowTrading:    'shadowTrading · live data, observational only',
    executionConsole: 'executionConsole · operator scheduler surface',
    liveTrading:      'liveTrading · live-capital deployment authority',
  };

  // ── CSS ────────────────────────────────────────────────────────────
  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = `
.${HIDE_CLS}{display:none !important}
#${PANEL_ID}{padding:24px 28px 96px;background:#f8fafc;min-height:calc(100vh - 3rem);color:#0f172a;font-size:13px;line-height:1.55}
#${PANEL_ID} *{box-sizing:border-box}
#${PANEL_ID} .fgi-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:6px;flex-wrap:wrap}
#${PANEL_ID} .fgi-title{font-size:22px;font-weight:700;letter-spacing:-0.01em;color:#0f172a;margin:0;display:flex;align-items:center;gap:10px}
#${PANEL_ID} .fgi-title::before{content:"";width:3px;height:18px;background:#475569;display:inline-block;border-radius:2px}
#${PANEL_ID} .fgi-subtitle{font-size:12px;color:#64748b;margin:4px 0 0;max-width:840px;line-height:1.55}
#${PANEL_ID} .fgi-assert{margin-top:14px;padding:12px 16px;background:#f1f5f9;border-left:3px solid #475569;border-radius:8px;color:#1e293b;font-size:12px;line-height:1.6}
#${PANEL_ID} .fgi-assert strong{color:#0f172a;font-weight:700}
#${PANEL_ID} .fgi-assert .fgi-assert-2{display:block;margin-top:6px;color:#475569;font-style:italic}
#${PANEL_ID} h3{font-size:10.5px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:0 0 12px;display:flex;align-items:center;gap:10px}
#${PANEL_ID} h3::before{content:"";width:14px;height:1px;background:#94a3b8;display:inline-block}
#${PANEL_ID} .fgi-section-spacer{height:28px}

/* Filters / toolbar */
#${PANEL_ID} .fgi-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px}
#${PANEL_ID} .fgi-toolbar-left{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
#${PANEL_ID} .fgi-toolbar label{font-size:10.5px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;font-weight:700}
#${PANEL_ID} .fgi-select,#${PANEL_ID} .fgi-input{padding:5px 9px;border:1px solid #e5e7eb;border-radius:7px;background:#ffffff;font-size:12px;color:#0f172a}
#${PANEL_ID} .fgi-btn{padding:5px 11px;border:1px solid #e5e7eb;border-radius:7px;background:#ffffff;font-size:12px;font-weight:600;color:#0f172a;cursor:pointer;transition:background .12s,border-color .12s}
#${PANEL_ID} .fgi-btn:hover{background:#f8fafc;border-color:#cbd5e1}
#${PANEL_ID} .fgi-btn[disabled]{opacity:.45;cursor:not-allowed;pointer-events:none}
#${PANEL_ID} .fgi-btn.fgi-btn-quiet{color:#475569;border-color:#e5e7eb}
#${PANEL_ID} .fgi-btn.fgi-btn-warn{color:#92400e;border-color:#fcd34d}
#${PANEL_ID} .fgi-btn.fgi-btn-warn:hover{background:#fffbeb}
#${PANEL_ID} .fgi-btn.fgi-btn-danger{color:#991b1b;border-color:#fecaca}
#${PANEL_ID} .fgi-btn.fgi-btn-danger:hover{background:#fef2f2}

/* Operators table */
#${PANEL_ID} table.fgi-table{width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;font-size:12px;margin-top:14px}
#${PANEL_ID} .fgi-table th{text-align:left;padding:10px 14px;font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:700;white-space:nowrap}
#${PANEL_ID} .fgi-table td{padding:11px 14px;border-bottom:1px solid #f1f5f9;color:#0f172a;font-variant-numeric:tabular-nums;vertical-align:top}
#${PANEL_ID} .fgi-table tr:last-child td{border-bottom:none}
#${PANEL_ID} .fgi-table tr.fgi-row{cursor:pointer;transition:background .1s}
#${PANEL_ID} .fgi-table tr.fgi-row:hover td{background:#f8fafc}
#${PANEL_ID} .fgi-table tr.fgi-row.selected td{background:#eef2ff}

#${PANEL_ID} .fgi-pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:9.5px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#e2e8f0;color:#334155;white-space:nowrap}
#${PANEL_ID} .fgi-pill.tier-free  {background:#f1f5f9;color:#64748b}
#${PANEL_ID} .fgi-pill.tier-pro   {background:#dbeafe;color:#1e40af}
#${PANEL_ID} .fgi-pill.tier-trader{background:#fef3c7;color:#854d0e}
#${PANEL_ID} .fgi-pill.mode-none  {background:#f1f5f9;color:#94a3b8}
#${PANEL_ID} .fgi-pill.mode-paper {background:#e2e8f0;color:#334155}
#${PANEL_ID} .fgi-pill.mode-shadow{background:#e0e7ff;color:#3730a3}
#${PANEL_ID} .fgi-pill.mode-live  {background:#fee2e2;color:#991b1b;border:1px solid #fecaca}
#${PANEL_ID} .fgi-pill.la-granted {background:#fee2e2;color:#991b1b;border:1px solid #fecaca}
#${PANEL_ID} .fgi-pill.la-none    {background:#f1f5f9;color:#64748b}
#${PANEL_ID} .fgi-pill.cap-on     {background:#dcfce7;color:#14532d}
#${PANEL_ID} .fgi-pill.cap-off    {background:#f1f5f9;color:#94a3b8}
#${PANEL_ID} .fgi-pill.cap-override{background:#fef3c7;color:#854d0e;border:1px solid #fde68a}
#${PANEL_ID} .fgi-pill.sev-info     {background:#e2e8f0;color:#475569}
#${PANEL_ID} .fgi-pill.sev-elevated {background:#fef3c7;color:#854d0e}
#${PANEL_ID} .fgi-pill.sev-critical {background:#fee2e2;color:#991b1b;border:1px solid #fecaca}

#${PANEL_ID} .fgi-meta{font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',ui-monospace,monospace}
#${PANEL_ID} .fgi-key{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:#334155}
#${PANEL_ID} .fgi-key-sub{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;color:#94a3b8}

#${PANEL_ID} .fgi-empty{padding:48px 16px;text-align:center;color:#64748b;font-size:13px;background:#ffffff;border:1px dashed #e5e7eb;border-radius:10px;margin-top:14px}
#${PANEL_ID} .fgi-loading{padding:24px;text-align:center;color:#94a3b8;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;font-weight:700}
#${PANEL_ID} .fgi-error{padding:14px 16px;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;color:#991b1b;font-size:13px;margin-bottom:14px}

/* Operator detail / Capability matrix */
#${PANEL_ID} .fgi-detail{margin-top:14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 20px}
#${PANEL_ID} .fgi-detail .fgi-detail-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap;margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid #f1f5f9}
#${PANEL_ID} .fgi-detail .fgi-detail-userid{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:14px;font-weight:700;color:#0f172a}
#${PANEL_ID} .fgi-detail .fgi-detail-meta{display:flex;gap:6px;flex-wrap:wrap;align-items:center}

#${PANEL_ID} .fgi-cap-table{width:100%;border-collapse:collapse;font-size:12px;margin-top:8px}
#${PANEL_ID} .fgi-cap-table th{text-align:left;padding:8px 12px;font-size:9.5px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:700}
#${PANEL_ID} .fgi-cap-table td{padding:9px 12px;border-bottom:1px solid #f1f5f9;color:#0f172a;vertical-align:middle}
#${PANEL_ID} .fgi-cap-table tr:last-child td{border-bottom:none}
#${PANEL_ID} .fgi-cap-table .fgi-cap-name{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11.5px;color:#0f172a;font-weight:600}
#${PANEL_ID} .fgi-cap-table .fgi-cap-desc{font-size:11px;color:#64748b;margin-top:2px;font-family:inherit}
#${PANEL_ID} .fgi-cap-table .fgi-cap-actions{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}

/* Timeline */
#${PANEL_ID} .fgi-timeline{margin-top:14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:6px 18px}
#${PANEL_ID} .fgi-tl-row{display:grid;grid-template-columns:160px 100px 1fr;gap:14px;padding:12px 0;border-bottom:1px solid #f1f5f9;align-items:start}
#${PANEL_ID} .fgi-tl-row:last-child{border-bottom:none}
#${PANEL_ID} .fgi-tl-ts{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:#64748b}
#${PANEL_ID} .fgi-tl-sev{display:flex;align-items:flex-start}
#${PANEL_ID} .fgi-tl-body{font-size:12.5px;color:#0f172a;line-height:1.55}
#${PANEL_ID} .fgi-tl-action{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:12px;font-weight:600;color:#0f172a}
#${PANEL_ID} .fgi-tl-actor{color:#64748b;margin-left:8px}
#${PANEL_ID} .fgi-tl-note{font-size:11px;color:#64748b;margin-top:3px;font-family:'JetBrains Mono',ui-monospace,monospace;word-break:break-all}
#${PANEL_ID} .fgi-tl-reason{font-size:11.5px;color:#475569;margin-top:3px;font-style:italic}
#${PANEL_ID} .fgi-tl-diff{font-size:11px;color:#94a3b8;margin-top:4px;font-family:'JetBrains Mono',ui-monospace,monospace;word-break:break-all}

/* Authority Actions block — intentionally subdued */
#${PANEL_ID} .fgi-authority{margin-top:14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 20px}
#${PANEL_ID} .fgi-authority .fgi-auth-status{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #f1f5f9}
#${PANEL_ID} .fgi-authority .fgi-auth-actions{display:flex;gap:8px;flex-wrap:wrap}
#${PANEL_ID} .fgi-authority .fgi-auth-note{font-size:11.5px;color:#475569;line-height:1.55;margin-top:10px;padding:10px 12px;background:#f8fafc;border-radius:8px;border-left:2px solid #cbd5e1}
#${PANEL_ID} .fgi-authority .fgi-auth-fact{font-size:11.5px;color:#0f172a;display:grid;grid-template-columns:160px 1fr;gap:8px;padding:5px 0}
#${PANEL_ID} .fgi-authority .fgi-auth-fact-k{color:#64748b}
#${PANEL_ID} .fgi-authority .fgi-auth-fact-v{font-family:'JetBrains Mono',ui-monospace,monospace;color:#0f172a;word-break:break-all}

/* Inline tier control row */
#${PANEL_ID} .fgi-tier-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:6px}

/* ── Modal ───────────────────────────────────────────────────────── */
.fgi-modal-backdrop{position:fixed;inset:0;background:rgba(15,23,42,0.32);z-index:9998;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .14s}
.fgi-modal-backdrop.open{opacity:1;pointer-events:auto}
#${MODAL_ID}{background:#ffffff;border-radius:14px;box-shadow:0 32px 60px rgba(15,23,42,0.32);width:560px;max-width:96vw;max-height:92vh;overflow:hidden;display:flex;flex-direction:column;transform:translateY(8px) scale(.97);transition:transform .18s ease;color:#0f172a;font-size:13px;line-height:1.55}
.fgi-modal-backdrop.open #${MODAL_ID}{transform:translateY(0) scale(1)}
#${MODAL_ID} .fgm-head{padding:18px 22px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
#${MODAL_ID} .fgm-title{font-size:14px;font-weight:700;color:#0f172a;letter-spacing:-0.005em;margin:0 0 4px}
#${MODAL_ID} .fgm-sub{font-size:11.5px;color:#64748b;line-height:1.55;font-family:inherit}
#${MODAL_ID} .fgm-close{background:transparent;border:none;font-size:18px;color:#94a3b8;cursor:pointer;padding:4px 8px;border-radius:6px;line-height:1}
#${MODAL_ID} .fgm-close:hover{background:#f8fafc;color:#0f172a}
#${MODAL_ID} .fgm-body{flex:1;overflow-y:auto;padding:18px 22px;font-size:12.5px;color:#0f172a;line-height:1.55}
#${MODAL_ID} .fgm-foot{padding:14px 22px;border-top:1px solid #e5e7eb;display:flex;justify-content:flex-end;align-items:center;gap:10px;background:#f8fafc}
#${MODAL_ID} .fgm-label{font-size:10.5px;color:#475569;text-transform:uppercase;letter-spacing:0.12em;font-weight:700;margin:14px 0 6px;display:block}
#${MODAL_ID} .fgm-label:first-child{margin-top:0}
#${MODAL_ID} .fgm-input,#${MODAL_ID} .fgm-select,#${MODAL_ID} .fgm-textarea{width:100%;padding:8px 11px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;font-size:13px;color:#0f172a;font-family:inherit}
#${MODAL_ID} .fgm-textarea{resize:vertical;min-height:80px;font-family:inherit;line-height:1.5}
#${MODAL_ID} .fgm-typed{font-family:'JetBrains Mono',ui-monospace,monospace;letter-spacing:0.04em;font-weight:600}
#${MODAL_ID} .fgm-typed.match{border-color:#86efac;background:#f0fdf4}
#${MODAL_ID} .fgm-typed.mismatch{border-color:#fecaca;background:#fef2f2}
#${MODAL_ID} .fgm-warn{padding:11px 14px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;color:#854d0e;font-size:12px;line-height:1.55;margin-bottom:12px}
#${MODAL_ID} .fgm-danger{padding:11px 14px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#991b1b;font-size:12px;line-height:1.55;margin-bottom:12px}
#${MODAL_ID} .fgm-danger strong{font-weight:700}
#${MODAL_ID} .fgm-fact{display:grid;grid-template-columns:140px 1fr;gap:8px;font-size:12px;padding:4px 0;color:#0f172a}
#${MODAL_ID} .fgm-fact-k{color:#64748b}
#${MODAL_ID} .fgm-fact-v{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11.5px;word-break:break-all}
#${MODAL_ID} .fgm-ack{display:flex;align-items:flex-start;gap:8px;padding:8px 0;font-size:12px;color:#0f172a;cursor:pointer}
#${MODAL_ID} .fgm-ack input{margin-top:3px}
#${MODAL_ID} .fgm-error{padding:9px 12px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;color:#991b1b;font-size:12px;margin-top:10px}
`;
    document.head.appendChild(s);
  }

  // ── Formatters ─────────────────────────────────────────────────────
  const fmt = {
    ts: (iso) => {
      if (!iso) return '—';
      try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toISOString().replace('T', ' ').slice(0, 19) + 'Z';
      } catch (_) { return iso; }
    },
    h: (s) => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    json: (o) => {
      try { return JSON.stringify(o, null, 2); } catch (_) { return String(o); }
    },
  };

  // ── Sidebar nav injection ─────────────────────────────────────────
  function findSidebar() {
    return document.querySelector('aside[data-testid="admin-sidebar"]')
      || document.querySelector('aside.admin-sidebar')
      || document.querySelector('aside');
  }
  function findMainArea() { return document.querySelector('main') || null; }
  function findSidebarItemByLabel(sidebar, label) {
    const candidates = sidebar.querySelectorAll('a, button');
    for (const el of candidates) {
      const t = (el.textContent || '').trim();
      if (t === label || t.startsWith(label + ' ') || t.endsWith(' ' + label) || t.indexOf(label) === 0) {
        if (el.children.length <= 4 && el.offsetHeight < 60) return el;
      }
    }
    return null;
  }
  function snapshotInactiveNavSample(sidebar) {
    const samples = ['Billing', 'Referrals', 'Intel System', 'News'];
    for (const label of samples) {
      const el = findSidebarItemByLabel(sidebar, label);
      if (el && el.tagName === 'A') return el;
    }
    return sidebar.querySelector('a[class*="flex"][class*="items-center"]') || null;
  }
  function applyNavActiveStyles(navEl, active) {
    if (active) {
      navEl.style.background = '#eef2ff';
      navEl.style.color = '#3730a3';
      navEl.style.borderLeft = '2px solid #6366f1';
      navEl.style.paddingLeft = '10px';
    } else {
      navEl.style.background = '';
      navEl.style.color = '';
      navEl.style.borderLeft = '';
      navEl.style.paddingLeft = '';
    }
  }
  function injectNav(sidebar) {
    if (document.getElementById(NAV_ID)) return document.getElementById(NAV_ID);
    const sample = snapshotInactiveNavSample(sidebar);
    if (!sample || !sample.parentElement) return null;
    const nav = document.createElement('button');
    nav.id = NAV_ID;
    nav.type = 'button';
    nav.setAttribute('data-testid', 'admin-nav-governance');
    if (sample.className) nav.className = sample.className;
    nav.className = (nav.className || '').replace(/bg-indigo-50|text-indigo-700|border-l-2|border-indigo-600/g, '').trim();
    // Icon: scales/governance glyph (key-like), neutral gray. No shields, no crowns.
    nav.innerHTML =
      '<svg class="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M12 3v18M5 7l7-4 7 4M5 7l-2 7a4 4 0 0 0 8 0l-2-7M19 7l-2 7a4 4 0 0 0 8 0l-2-7"/>' +
      '</svg>' +
      '<span class="flex-1 truncate">Управление</span>';

    let inserted = false;
    for (const label of ANCHOR_LABELS_AFTER) {
      const target = findSidebarItemByLabel(sidebar, label);
      if (target && target.parentElement) {
        target.parentElement.insertBefore(nav, target.nextElementSibling);
        inserted = true; break;
      }
    }
    if (!inserted) {
      for (const label of ANCHOR_LABELS_BEFORE) {
        const target = findSidebarItemByLabel(sidebar, label);
        if (target && target.parentElement) {
          target.parentElement.insertBefore(nav, target);
          inserted = true; break;
        }
      }
    }
    if (!inserted) sample.parentElement.appendChild(nav);

    nav.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      activate();
    });
    return nav;
  }

  // ── State ──────────────────────────────────────────────────────────
  let currentFilters = { tier: '', mode: '', status: '', hasOverrides: '', q: '', limit: 100 };
  let cachedOperators = [];
  let selectedUserId = null;
  let cachedSelectedOp = null;
  let cachedTimeline = [];
  let timelineSeverityFilter = '';

  function closeModal() {
    const bd = document.querySelector('.fgi-modal-backdrop');
    if (bd) {
      bd.classList.remove('open');
      setTimeout(() => { if (bd.parentElement) bd.parentElement.removeChild(bd); }, 220);
    }
  }
  function teardownPanel() {
    closeModal();
    FomoInject.destroyMountedPanel(PANEL_ID);
    document.querySelectorAll('.' + HIDE_CLS).forEach(n => n.classList.remove(HIDE_CLS));
    const nav = document.getElementById(NAV_ID);
    if (nav) applyNavActiveStyles(nav, false);
  }
  function wireSidebarTeardown(sidebar) {
    Array.from(sidebar.querySelectorAll('a, button')).forEach(item => {
      if (item.id === NAV_ID) return;
      if (item.__fomoGovernanceTeardownWired) return;
      item.__fomoGovernanceTeardownWired = true;
      item.addEventListener('click', () => { teardownPanel(); }, { capture: true });
    });
  }
  function mountPanel() {
    const main = findMainArea();
    if (!main) return null;
    Array.from(main.children).forEach(c => {
      if (c.id === PANEL_ID) return;
      c.classList.add(HIDE_CLS);
    });
    let panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement('div');
      panel.id = PANEL_ID;
      panel.setAttribute('data-testid', 'fomo-governance-panel');
      main.appendChild(panel);
    } else {
      panel.classList.remove(HIDE_CLS);
    }
    return panel;
  }

  async function activate() {
    injectCSS();
    const panel = mountPanel();
    if (!panel) return;
    const nav = document.getElementById(NAV_ID);
    if (nav) applyNavActiveStyles(nav, true);
    panel.innerHTML = '<div class="fgi-loading">Подгружаю governance…</div>';
    await renderShell(panel);
  }

  // ── Shell + operators table ───────────────────────────────────────
  async function renderShell(panel) {
    panel.innerHTML = `
      <div class="fgi-header">
        <div>
          <h1 class="fgi-title">Управление</h1>
          <p class="fgi-subtitle">Governance ledger с friction semantics. Не cockpit, не control center, не trading-консоль. Каждое изменение прав — append-only запись в audit timeline с reason и actor. Все mutations требуют admin JWT и независимо валидируются на сервере.</p>
        </div>
      </div>
      <div class="fgi-assert">
        <strong>Commerce ≠ governance.</strong>
        <span class="fgi-assert-2">Tier — это коммерческий продукт (free / pro / trader). Live authority — операционное governance-решение, которое <em>никогда</em> не выдаётся автоматически при покупке tier. Эти два слоя живут отдельно по дизайну.</span>
      </div>

      <div class="fgi-section-spacer"></div>

      <h3>Operators</h3>
      <div class="fgi-toolbar" id="fgi-toolbar">
        <div class="fgi-toolbar-left">
          <label>Tier</label>
          <select id="fgi-flt-tier" class="fgi-select">
            <option value="">все</option>
            ${TIER_VOCAB.map(t => `<option value="${t}">${t}</option>`).join('')}
          </select>
          <label>Mode</label>
          <select id="fgi-flt-mode" class="fgi-select">
            <option value="">все</option>
            ${MODE_VOCAB.map(m => `<option value="${m}">${m}</option>`).join('')}
          </select>
          <label>Status</label>
          <select id="fgi-flt-status" class="fgi-select">
            <option value="">все</option>
            <option value="none">none</option>
            <option value="applied">applied</option>
            <option value="approved">approved</option>
            <option value="revoked">revoked</option>
          </select>
          <label>Overrides</label>
          <select id="fgi-flt-overrides" class="fgi-select">
            <option value="">все</option>
            <option value="true">с overrides</option>
            <option value="false">без overrides</option>
          </select>
          <label>Поиск</label>
          <input id="fgi-flt-q" class="fgi-input" placeholder="userId substring" style="width:160px"/>
          <label>Limit</label>
          <select id="fgi-flt-limit" class="fgi-select">
            <option value="50">50</option>
            <option value="100" selected>100</option>
            <option value="250">250</option>
          </select>
        </div>
        <button class="fgi-btn" id="fgi-refresh">Обновить</button>
      </div>
      <div id="fgi-operators-body"><div class="fgi-loading">Загружаю operators…</div></div>

      <div class="fgi-section-spacer"></div>

      <h3>Capability matrix</h3>
      <div id="fgi-cap-body"><div class="fgi-empty">Выберите operator в таблице выше, чтобы увидеть его resolved capability matrix.</div></div>

      <div class="fgi-section-spacer"></div>

      <h3>Audit timeline</h3>
      <div id="fgi-timeline-body"><div class="fgi-empty">Выберите operator, чтобы увидеть его immutable governance timeline.</div></div>

      <div class="fgi-section-spacer"></div>

      <h3>Authority actions</h3>
      <div id="fgi-authority-body"><div class="fgi-empty">Выберите operator, чтобы увидеть actions. Authority is never purchased automatically.</div></div>
    `;

    const $ = (id) => panel.querySelector(id);
    const apply = () => {
      currentFilters.tier         = $('#fgi-flt-tier').value;
      currentFilters.mode         = $('#fgi-flt-mode').value;
      currentFilters.status       = $('#fgi-flt-status').value;
      currentFilters.hasOverrides = $('#fgi-flt-overrides').value;
      currentFilters.q            = $('#fgi-flt-q').value.trim();
      currentFilters.limit        = Number($('#fgi-flt-limit').value) || 100;
      renderOperators(panel);
    };
    ['#fgi-flt-tier','#fgi-flt-mode','#fgi-flt-status','#fgi-flt-overrides','#fgi-flt-limit'].forEach(sel => {
      $(sel).addEventListener('change', apply);
    });
    $('#fgi-flt-q').addEventListener('input', () => {
      clearTimeout(window.__fgi_q_timer);
      window.__fgi_q_timer = setTimeout(apply, 300);
    });
    $('#fgi-refresh').addEventListener('click', apply);

    await renderOperators(panel);
  }

  function buildQuery() {
    const p = new URLSearchParams();
    if (currentFilters.tier)         p.set('tier', currentFilters.tier);
    if (currentFilters.mode)         p.set('mode', currentFilters.mode);
    if (currentFilters.status)       p.set('status', currentFilters.status);
    if (currentFilters.hasOverrides) p.set('hasOverrides', currentFilters.hasOverrides);
    if (currentFilters.q)            p.set('q', currentFilters.q);
    p.set('limit',  String(currentFilters.limit || 100));
    return p.toString();
  }

  async function renderOperators(panel) {
    const body = panel.querySelector('#fgi-operators-body');
    body.innerHTML = '<div class="fgi-loading">Загружаю operators…</div>';
    let data;
    try {
      data = await FomoInject.fetchWithAdminJWT('/api/admin/operator-access/list?' + buildQuery());
    } catch (e) {
      body.innerHTML = '<div class="fgi-error">Operators недоступны: ' + fmt.h(e.message) + (e.status === 401 ? ' — переавторизуйтесь как админ.' : '') + '</div>';
      return;
    }
    cachedOperators = data.rows || [];
    if (!cachedOperators.length) {
      body.innerHTML = '<div class="fgi-empty">Operators не найдены под текущие фильтры.</div>';
      return;
    }
    body.innerHTML = `
      <table class="fgi-table">
        <thead><tr>
          <th>UserID</th>
          <th>Tier</th>
          <th>Mode</th>
          <th>Live authority</th>
          <th>Console</th>
          <th>Overrides</th>
          <th>Last capability change</th>
        </tr></thead>
        <tbody>
          ${cachedOperators.map(r => {
            const oa = r.operatorAccess || {};
            const la = oa.liveAuthority || {};
            const overrides = oa.capabilityOverrides || {};
            const overrideKeys = Object.keys(overrides);
            return `<tr class="fgi-row ${selectedUserId === r.userId ? 'selected' : ''}" data-user-id="${fmt.h(r.userId)}">
              <td><span class="fgi-key" style="font-weight:700;color:#0f172a">${fmt.h(r.userId)}</span></td>
              <td><span class="fgi-pill tier-${fmt.h(r.tier || 'free')}">${fmt.h(r.tier || 'free')}</span></td>
              <td><span class="fgi-pill mode-${fmt.h(oa.mode || 'none')}">${fmt.h(oa.mode || 'none')}</span></td>
              <td>${la.granted ? `<span class="fgi-pill la-granted">granted</span> <span class="fgi-key-sub">by ${fmt.h(la.grantedBy || '—')}</span>` : '<span class="fgi-pill la-none">none</span>'}</td>
              <td>${oa.consoleAccess ? '<span class="fgi-pill cap-on">on</span>' : '<span class="fgi-pill cap-off">off</span>'}</td>
              <td>${overrideKeys.length ? `<span class="fgi-pill cap-override">${overrideKeys.length} override${overrideKeys.length > 1 ? 's' : ''}</span>` : '<span class="fgi-key-sub">—</span>'}</td>
              <td class="fgi-meta">${fmt.ts(oa.lastCapabilityChangeAt)}${oa.lastCapabilityChangedBy ? ' · by ' + fmt.h(oa.lastCapabilityChangedBy) : ''}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      <div class="fgi-meta" style="margin-top:10px">${cachedOperators.length} of ${data.total} · sorted by updatedAt desc</div>
    `;

    body.querySelectorAll('.fgi-row').forEach(tr => {
      tr.addEventListener('click', async () => {
        const userId = tr.getAttribute('data-user-id');
        selectedUserId = userId;
        cachedSelectedOp = cachedOperators.find(o => o.userId === userId) || null;
        body.querySelectorAll('.fgi-row').forEach(r2 => r2.classList.toggle('selected', r2 === tr));
        await renderCapabilityMatrix(panel);
        await renderTimeline(panel);
        renderAuthorityActions(panel);
      });
    });
  }

  // ── Capability matrix ─────────────────────────────────────────────
  async function renderCapabilityMatrix(panel) {
    const body = panel.querySelector('#fgi-cap-body');
    if (!cachedSelectedOp) {
      body.innerHTML = '<div class="fgi-empty">Operator не выбран.</div>';
      return;
    }
    const op = cachedSelectedOp;
    const oa = op.operatorAccess || {};
    const caps = op.capabilities || {};
    const structured = caps.structured || {};
    const overrides = oa.capabilityOverrides || {};
    const summary = caps.effectiveSummary || { can: [], cannot: [] };

    body.innerHTML = `
      <div class="fgi-detail">
        <div class="fgi-detail-head">
          <div>
            <div class="fgi-detail-userid">${fmt.h(op.userId)}</div>
            <div class="fgi-meta">tier=${fmt.h(op.tier || 'free')} · status=${fmt.h(oa.status || 'none')} · mode=${fmt.h(oa.mode || 'none')}</div>
          </div>
          <div class="fgi-detail-meta">
            <span class="fgi-pill tier-${fmt.h(op.tier || 'free')}">${fmt.h(op.tier || 'free')}</span>
            ${oa.liveAuthority && oa.liveAuthority.granted ? '<span class="fgi-pill la-granted">live authority</span>' : '<span class="fgi-pill la-none">no live authority</span>'}
          </div>
        </div>

        <div class="fgi-tier-row">
          <span style="font-size:11px;color:#475569;font-weight:600">Tier change · LOW friction:</span>
          ${TIER_VOCAB.map(t => `<button class="fgi-btn ${op.tier === t ? '' : 'fgi-btn-quiet'}" data-fgi-tier="${t}" ${op.tier === t ? 'disabled' : ''}>${t === op.tier ? '· current · ' : ''}${t}</button>`).join('')}
        </div>

        <p style="margin:14px 0 6px;font-size:11.5px;color:#475569;line-height:1.55">
          Resolved capability matrix — backend renders precedence directly (override → revoke status → admin grant → tier default). Frontend reads <code>structured[name]</code> verbatim.
          <strong style="color:#1e293b">TRADER tier unlocks paper access only.</strong> Live authority is never purchased automatically.
        </p>

        <table class="fgi-cap-table">
          <thead><tr>
            <th>Capability</th>
            <th>Effective</th>
            <th>Source</th>
            <th>Override</th>
            <th style="text-align:right">Actions</th>
          </tr></thead>
          <tbody>
            ${CAPABILITY_VOCAB.map(cap => {
              const cell = structured[cap] || { effective: caps[cap] === true, source: 'not_granted', override: 'none' };
              const override = overrides[cap] || null;
              const overrideState = override ? override.value : 'none';
              return `<tr>
                <td>
                  <div class="fgi-cap-name">${fmt.h(cap)}</div>
                  <div class="fgi-cap-desc">${fmt.h(CAPABILITY_LABELS[cap] || '')}</div>
                </td>
                <td><span class="fgi-pill ${cell.effective ? 'cap-on' : 'cap-off'}">${cell.effective ? 'on' : 'off'}</span></td>
                <td><span class="fgi-key">${fmt.h(cell.source || '—')}</span></td>
                <td>${override ? `<span class="fgi-pill cap-override">${fmt.h(overrideState)}</span>${override.reason ? `<div class="fgi-key-sub" style="margin-top:3px">${fmt.h(override.reason)}</div>` : ''}` : '<span class="fgi-key-sub">none</span>'}</td>
                <td>
                  <div class="fgi-cap-actions">
                    <button class="fgi-btn fgi-btn-quiet" data-fgi-cap-action="grant" data-fgi-cap="${fmt.h(cap)}" ${cap === 'liveTrading' ? 'data-fgi-cap-warn="live"' : ''}>grant override</button>
                    <button class="fgi-btn fgi-btn-quiet" data-fgi-cap-action="revoke" data-fgi-cap="${fmt.h(cap)}">revoke override</button>
                    ${override ? `<button class="fgi-btn fgi-btn-quiet" data-fgi-cap-action="clear" data-fgi-cap="${fmt.h(cap)}">clear</button>` : ''}
                  </div>
                </td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>

        <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:18px">
          <div>
            <h3 style="margin-bottom:8px">Can</h3>
            ${summary.can.length ? summary.can.map(c => `<div style="font-size:12px;color:#0f172a;padding:3px 0">· ${fmt.h(c)}</div>`).join('') : '<div class="fgi-key-sub">—</div>'}
          </div>
          <div>
            <h3 style="margin-bottom:8px">Cannot</h3>
            ${summary.cannot.length ? summary.cannot.map(c => `<div style="font-size:12px;color:#475569;padding:3px 0">· ${fmt.h(c)}</div>`).join('') : '<div class="fgi-key-sub">—</div>'}
          </div>
        </div>
      </div>
    `;

    // Wire tier change buttons (LOW friction)
    body.querySelectorAll('[data-fgi-tier]').forEach(btn => {
      btn.addEventListener('click', () => {
        const tier = btn.getAttribute('data-fgi-tier');
        openTierChangeModal(op.userId, op.tier, tier);
      });
    });

    // Wire capability override buttons (MEDIUM + HIGH for liveTrading)
    body.querySelectorAll('[data-fgi-cap-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-fgi-cap-action'); // grant | revoke | clear
        const cap    = btn.getAttribute('data-fgi-cap');
        openCapabilityOverrideModal(op.userId, cap, action);
      });
    });
  }

  // ── Timeline (first-class, never collapsible) ─────────────────────
  async function renderTimeline(panel) {
    const body = panel.querySelector('#fgi-timeline-body');
    if (!selectedUserId) {
      body.innerHTML = '<div class="fgi-empty">Operator не выбран.</div>';
      return;
    }
    body.innerHTML = '<div class="fgi-loading">Загружаю timeline…</div>';
    let data;
    try {
      const q = new URLSearchParams({ userId: selectedUserId, limit: '200' });
      if (timelineSeverityFilter) q.set('severity', timelineSeverityFilter);
      data = await FomoInject.fetchWithAdminJWT('/api/admin/operator-access/audit-timeline?' + q.toString());
    } catch (e) {
      body.innerHTML = '<div class="fgi-error">Timeline недоступна: ' + fmt.h(e.message) + '</div>';
      return;
    }
    cachedTimeline = data.rows || [];

    const filterBar = `
      <div class="fgi-toolbar" style="margin-top:6px;border-radius:10px 10px 0 0;border-bottom:0">
        <div class="fgi-toolbar-left">
          <label>Severity</label>
          <select id="fgi-tl-sev" class="fgi-select">
            <option value="">все</option>
            ${SEVERITY_VOCAB.map(s => `<option value="${s}" ${timelineSeverityFilter === s ? 'selected' : ''}>${s}</option>`).join('')}
          </select>
          <span class="fgi-key-sub" style="margin-left:10px">immutable · append-only · ${cachedTimeline.length} entries</span>
        </div>
      </div>`;

    if (!cachedTimeline.length) {
      body.innerHTML = filterBar + '<div class="fgi-empty">Записей нет. Любое governance-действие появится здесь автоматически.</div>';
      wireTimelineFilter(panel);
      return;
    }

    const html = cachedTimeline.map(r => {
      const sev = (r.severity || 'info').toLowerCase();
      const beforeAfter = r.before || r.after ? `<div class="fgi-tl-diff">before: ${fmt.h(fmt.json(r.before || null))} → after: ${fmt.h(fmt.json(r.after || null))}</div>` : '';
      return `<div class="fgi-tl-row">
        <div class="fgi-tl-ts">${fmt.ts(r.ts)}</div>
        <div class="fgi-tl-sev"><span class="fgi-pill sev-${sev}">${fmt.h(sev)}</span></div>
        <div class="fgi-tl-body">
          <span class="fgi-tl-action">${fmt.h(r.action || '—')}</span>
          <span class="fgi-tl-actor">· actor=${fmt.h(r.actor || '—')}</span>
          ${r.note ? `<div class="fgi-tl-note">${fmt.h(r.note)}</div>` : ''}
          ${r.reason ? `<div class="fgi-tl-reason">reason: ${fmt.h(r.reason)}</div>` : ''}
          ${beforeAfter}
        </div>
      </div>`;
    }).join('');

    body.innerHTML = filterBar + `<div class="fgi-timeline">${html}</div>`;
    wireTimelineFilter(panel);
  }
  function wireTimelineFilter(panel) {
    const sel = panel.querySelector('#fgi-tl-sev');
    if (!sel) return;
    sel.addEventListener('change', () => {
      timelineSeverityFilter = sel.value;
      renderTimeline(panel);
    });
  }

  // ── Authority Actions (subdued — NOT hero) ────────────────────────
  function renderAuthorityActions(panel) {
    const body = panel.querySelector('#fgi-authority-body');
    if (!cachedSelectedOp) {
      body.innerHTML = '<div class="fgi-empty">Operator не выбран.</div>';
      return;
    }
    const op = cachedSelectedOp;
    const oa = op.operatorAccess || {};
    const la = oa.liveAuthority || {};
    const status = oa.status || 'none';

    const isNotApproved = status !== 'approved';
    const granted = !!la.granted;

    body.innerHTML = `
      <div class="fgi-authority">
        <div class="fgi-auth-status">
          <div>
            <div style="font-size:11.5px;color:#475569;font-weight:600;letter-spacing:0.08em;text-transform:uppercase">Current state</div>
            <div style="margin-top:6px;font-size:14px;font-weight:700;color:#0f172a">
              ${granted ? 'Live authority granted' : 'Live authority NOT granted'}
            </div>
          </div>
          <div class="fgi-auth-actions">
            ${isNotApproved
              ? `<button class="fgi-btn fgi-btn-quiet" data-fgi-auth="grant-access" title="Operator не в статусе approved — нужно сначала grant base access">grant base access · MEDIUM</button>`
              : ``}
            ${granted
              ? `<button class="fgi-btn fgi-btn-danger" data-fgi-auth="revoke-live">revoke live authority · HIGH</button>`
              : (isNotApproved
                  ? ''
                  : `<button class="fgi-btn fgi-btn-warn" data-fgi-auth="grant-live">grant live authority · HIGH</button>`)}
            ${!isNotApproved && !granted ? `<button class="fgi-btn fgi-btn-quiet" data-fgi-auth="set-console">set console access · MEDIUM</button>` : ''}
            ${!isNotApproved ? `<button class="fgi-btn fgi-btn-quiet" data-fgi-auth="set-mode">set mode · MEDIUM</button>` : ''}
            ${!isNotApproved ? `<button class="fgi-btn fgi-btn-danger" data-fgi-auth="revoke-base">revoke base access · MEDIUM</button>` : ''}
          </div>
        </div>

        ${granted ? `
          <div class="fgi-auth-fact"><span class="fgi-auth-fact-k">grantedAt</span><span class="fgi-auth-fact-v">${fmt.ts(la.grantedAt)}</span></div>
          <div class="fgi-auth-fact"><span class="fgi-auth-fact-k">grantedBy</span><span class="fgi-auth-fact-v">${fmt.h(la.grantedBy || '—')}</span></div>
          <div class="fgi-auth-fact"><span class="fgi-auth-fact-k">reason</span><span class="fgi-auth-fact-v">${fmt.h(la.reason || '—')}</span></div>
          <div class="fgi-auth-fact"><span class="fgi-auth-fact-k">expiresAt</span><span class="fgi-auth-fact-v">${fmt.ts(la.expiresAt)}</span></div>
        ` : ''}

        <div class="fgi-auth-note">
          <strong>Architectural separation.</strong> «mode = live» — это broker connection mode (broker может читать live market data). «liveAuthority.granted» — это операционная governance-decision, что operator имеет право deployить live капитал. Обе сущности валидируются независимо. Покупка trader-tier <em>не</em> выдаёт live authority. Backend server-validates typed confirmation phrase <code style="background:#f1f5f9;padding:1px 5px;border-radius:4px">${fmt.h(LIVE_AUTHORITY_PHRASE)}</code> и mandatory reason — frontend не trusts свой state.
        </div>
      </div>
    `;

    body.querySelectorAll('[data-fgi-auth]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-fgi-auth');
        if (action === 'grant-live')   openGrantLiveAuthorityModal(op.userId);
        if (action === 'revoke-live')  openRevokeLiveAuthorityModal(op.userId);
        if (action === 'grant-access') openGrantBaseAccessModal(op.userId);
        if (action === 'revoke-base')  openRevokeBaseAccessModal(op.userId);
        if (action === 'set-console')  openSetConsoleModal(op.userId, !!oa.consoleAccess);
        if (action === 'set-mode')     openSetModeModal(op.userId, oa.mode || 'none');
      });
    });
  }

  // ── Modal primitives (reusing CSS, NOT building parallel framework) ─
  function openModal({ title, sub, bodyHtml, footHtml, onMount }) {
    closeModal();
    const bd = document.createElement('div');
    bd.className = 'fgi-modal-backdrop';
    bd.innerHTML = `
      <div id="${MODAL_ID}" role="dialog" aria-modal="true" data-testid="fomo-governance-modal">
        <div class="fgm-head">
          <div>
            <div class="fgm-title">${title}</div>
            ${sub ? `<div class="fgm-sub">${sub}</div>` : ''}
          </div>
          <button class="fgm-close" aria-label="Close">×</button>
        </div>
        <div class="fgm-body">${bodyHtml}</div>
        <div class="fgm-foot">${footHtml || ''}</div>
      </div>
    `;
    document.body.appendChild(bd);
    bd.addEventListener('click', (e) => { if (e.target === bd) closeModal(); });
    bd.querySelector('.fgm-close').addEventListener('click', closeModal);
    requestAnimationFrame(() => bd.classList.add('open'));
    if (typeof onMount === 'function') onMount(bd);
    return bd;
  }
  function showModalError(bd, msg) {
    const body = bd.querySelector('.fgm-body');
    let host = body.querySelector('.fgm-error');
    if (!host) { host = document.createElement('div'); host.className = 'fgm-error'; body.appendChild(host); }
    host.textContent = msg;
  }

  // ── Mutation helper — POST + authoritative refetch ───────────────
  async function mutateAndRefetch(path, body) {
    const res = await FomoInject.fetchWithAdminJWT(path, { method: 'POST', body: JSON.stringify(body) });
    // Full refetch — NO optimistic UI.  Read structured[] from server.
    const panel = document.getElementById(PANEL_ID);
    if (!panel) return res;
    await renderOperators(panel);
    // Re-resolve selected op (it may have been deleted; degrade gracefully).
    cachedSelectedOp = cachedOperators.find(o => o.userId === selectedUserId) || null;
    if (cachedSelectedOp) {
      await renderCapabilityMatrix(panel);
      await renderTimeline(panel);
      renderAuthorityActions(panel);
    }
    return res;
  }

  // ── Modal: LOW — tier change ─────────────────────────────────────
  function openTierChangeModal(userId, currentTier, nextTier) {
    openModal({
      title: 'Tier change · LOW friction',
      sub: `Commercial tier позиционирование. Не выдаёт live authority и не меняет admin operational decisions.`,
      bodyHtml: `
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">tier</span><span class="fgm-fact-v">${fmt.h(currentTier)} → ${fmt.h(nextTier)}</span></div>
        <div style="margin-top:14px;font-size:12px;color:#475569;line-height:1.55">
          Tier=trader auto-derives paperTrading + tradingOsVisible как дефолты (если нет explicit revoke override). Live authority и executionConsole — это independent admin governance decisions.
        </div>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn" data-fgm-confirm>Подтвердить · set tier</button>
      `,
      onMount: (bd) => {
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        bd.querySelector('[data-fgm-confirm]').addEventListener('click', async () => {
          try {
            await mutateAndRefetch('/api/admin/operator-access/set-tier', { userId, tier: nextTier });
            closeModal();
          } catch (e) {
            showModalError(bd, 'Не удалось: ' + (e.body && e.body.detail ? JSON.stringify(e.body.detail) : e.message));
          }
        });
      },
    });
  }

  // ── Modal: MEDIUM — capability override ───────────────────────────
  function openCapabilityOverrideModal(userId, capability, action) {
    const isLive = capability === 'liveTrading';
    const isHigh = isLive && action === 'grant';
    if (isHigh) {
      // liveTrading override→granted goes through the same friction as
      // the dedicated grant-live-authority flow (per backend rule
      // "should normally go through grant-live-authority").
      openGrantLiveAuthorityModal(userId);
      return;
    }
    const valueMap = { grant: 'granted', revoke: 'revoked', clear: 'clear' };
    const value = valueMap[action];
    openModal({
      title: `Capability override · MEDIUM friction`,
      sub: `${capability} · ${value}`,
      bodyHtml: `
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">capability</span><span class="fgm-fact-v">${fmt.h(capability)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">value</span><span class="fgm-fact-v">${fmt.h(value)}</span></div>
        ${isLive ? `<div class="fgm-warn" style="margin-top:12px"><strong>Live trading capability.</strong> Революке override устанавливает <em>effective off</em> даже если live authority granted. Это hard-stop, не recovery prompt.</div>` : ''}
        <label class="fgm-label">Reason · audit-trail justification${action !== 'clear' ? ' (required)' : ' (optional)'}</label>
        <textarea class="fgm-textarea" id="fgm-reason" placeholder="например: prod incident — temporary block until upstream signal stabilizes"></textarea>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-${action === 'revoke' ? 'danger' : 'warn'}" data-fgm-confirm>Применить · ${value}</button>
      `,
      onMount: (bd) => {
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        bd.querySelector('[data-fgm-confirm]').addEventListener('click', async () => {
          const reason = bd.querySelector('#fgm-reason').value.trim();
          if (action !== 'clear' && !reason) {
            showModalError(bd, 'Reason обязателен для grant / revoke override.');
            return;
          }
          try {
            await mutateAndRefetch('/api/admin/operator-access/override-capability', {
              userId, capability, value, reason: reason || null,
            });
            closeModal();
          } catch (e) {
            showModalError(bd, 'Не удалось: ' + (e.body && e.body.detail ? JSON.stringify(e.body.detail) : e.message));
          }
        });
      },
    });
  }

  // ── Modal: HIGH — grant live authority (typed confirmation) ──────
  function openGrantLiveAuthorityModal(userId) {
    openModal({
      title: 'Grant live authority · HIGH friction',
      sub: `Operational governance action. Не commercial unlock. Authority is never purchased automatically.`,
      bodyHtml: `
        <div class="fgm-danger">
          <strong>Это самое опасное governance-действие в системе.</strong> После grant — operator имеет authority deployить live капитал (вместе с broker mode=live). Запись append-only в audit timeline с severity=critical. Никаких retry, ни автоматического expiry без явного <code>expiresAt</code>.
        </div>
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">action</span><span class="fgm-fact-v">grant-live-authority</span></div>

        <label class="fgm-label">Reason · mandatory governance justification</label>
        <textarea class="fgm-textarea" id="fgm-reason" placeholder="например: operator passed Q3 review · approved at governance board #2026-05"></textarea>

        <label class="fgm-label">Expires at (optional ISO timestamp, UTC)</label>
        <input class="fgm-input" id="fgm-expires" placeholder="2026-06-01T00:00:00Z (empty = no expiry)"/>

        <label class="fgm-label">Typed confirmation · type the exact phrase</label>
        <input class="fgm-input fgm-typed" id="fgm-typed" placeholder="${fmt.h(LIVE_AUTHORITY_PHRASE)}" autocomplete="off"/>

        <label class="fgm-ack" style="margin-top:12px">
          <input type="checkbox" id="fgm-ack"/>
          <span>Я подтверждаю, что прочитал commerce ≠ governance assertion, что live authority — это операционное решение, не commercial unlock, и что эта запись append-only в audit timeline.</span>
        </label>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-danger" data-fgm-confirm disabled>Grant live authority</button>
      `,
      onMount: (bd) => {
        const reason = bd.querySelector('#fgm-reason');
        const typed  = bd.querySelector('#fgm-typed');
        const ack    = bd.querySelector('#fgm-ack');
        const btn    = bd.querySelector('[data-fgm-confirm]');
        const expires = bd.querySelector('#fgm-expires');
        const recompute = () => {
          const reasonOk = reason.value.trim().length > 0;
          const typedOk  = typed.value === LIVE_AUTHORITY_PHRASE;
          typed.classList.toggle('match', typedOk && typed.value.length > 0);
          typed.classList.toggle('mismatch', !typedOk && typed.value.length > 0);
          btn.disabled = !(reasonOk && typedOk && ack.checked);
        };
        reason.addEventListener('input', recompute);
        typed.addEventListener('input', recompute);
        ack.addEventListener('change', recompute);
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        btn.addEventListener('click', async () => {
          if (btn.disabled) return;
          try {
            await mutateAndRefetch('/api/admin/operator-access/grant-live-authority', {
              userId,
              typedConfirmation: typed.value,
              reason: reason.value.trim(),
              expiresAt: expires.value.trim() || null,
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Backend отказал: ' + detail);
          }
        });
      },
    });
  }

  // ── Modal: HIGH — revoke live authority ──────────────────────────
  function openRevokeLiveAuthorityModal(userId) {
    openModal({
      title: 'Revoke live authority · HIGH friction',
      sub: `Immediate revocation — broker mode остаётся, но capital deployment authority снимается с этого момента.`,
      bodyHtml: `
        <div class="fgm-warn">
          После revoke — все будущие выпускающие операции (даже если mode=live) будут блокироваться preflight gate. Append-only запись в timeline.
        </div>
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <label class="fgm-label">Reason · mandatory</label>
        <textarea class="fgm-textarea" id="fgm-reason" placeholder="например: scheduled offboarding · governance review failed · operator request"></textarea>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-danger" data-fgm-confirm disabled>Revoke live authority</button>
      `,
      onMount: (bd) => {
        const reason = bd.querySelector('#fgm-reason');
        const btn = bd.querySelector('[data-fgm-confirm]');
        reason.addEventListener('input', () => { btn.disabled = !reason.value.trim(); });
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        btn.addEventListener('click', async () => {
          if (btn.disabled) return;
          try {
            await mutateAndRefetch('/api/admin/operator-access/revoke-live-authority', {
              userId, reason: reason.value.trim(),
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Не удалось: ' + detail);
          }
        });
      },
    });
  }

  // ── Modal: MEDIUM — grant base access ────────────────────────────
  function openGrantBaseAccessModal(userId) {
    openModal({
      title: 'Grant base operator access · MEDIUM friction',
      sub: `Базовая operator-аккредитация. Это НЕ live authority — только status=approved + начальный mode.`,
      bodyHtml: `
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <label class="fgm-label">Initial broker mode</label>
        <select class="fgm-select" id="fgm-mode">
          ${MODE_VOCAB.filter(m => m !== 'none').map(m => `<option value="${m}">${m}</option>`).join('')}
        </select>
        <label class="fgm-label">Console access</label>
        <select class="fgm-select" id="fgm-console">
          <option value="false">false</option>
          <option value="true">true</option>
        </select>
        <div style="margin-top:10px;font-size:11.5px;color:#475569;line-height:1.55">
          Customer tiers (free / pro / trader) <em>никогда</em> не auto-grant consoleAccess. Console access — это явная operator/admin boundary.
        </div>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn" data-fgm-confirm>Grant base access</button>
      `,
      onMount: (bd) => {
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        bd.querySelector('[data-fgm-confirm]').addEventListener('click', async () => {
          try {
            await mutateAndRefetch('/api/admin/operator-access/grant', {
              userId,
              mode: bd.querySelector('#fgm-mode').value,
              consoleAccess: bd.querySelector('#fgm-console').value === 'true',
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Не удалось: ' + detail);
          }
        });
      },
    });
  }

  // ── Modal: MEDIUM — revoke base access ───────────────────────────
  function openRevokeBaseAccessModal(userId) {
    openModal({
      title: 'Revoke base operator access · MEDIUM friction',
      sub: `Снимает status=approved → mode=none. Live authority должна быть revoked отдельно если ещё granted.`,
      bodyHtml: `
        <div class="fgm-warn">После revoke base access — все operator endpoints возвращают 403 capability_denied. Mutation append-only.</div>
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <label class="fgm-label">Reason · audit-trail justification</label>
        <textarea class="fgm-textarea" id="fgm-reason" placeholder="например: offboarding · 6-week dormant · governance review"></textarea>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-danger" data-fgm-confirm disabled>Revoke base access</button>
      `,
      onMount: (bd) => {
        const reason = bd.querySelector('#fgm-reason');
        const btn = bd.querySelector('[data-fgm-confirm]');
        reason.addEventListener('input', () => { btn.disabled = !reason.value.trim(); });
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        btn.addEventListener('click', async () => {
          if (btn.disabled) return;
          try {
            await mutateAndRefetch('/api/admin/operator-access/revoke', {
              userId, reason: reason.value.trim(),
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Не удалось: ' + detail);
          }
        });
      },
    });
  }

  // ── Modal: MEDIUM — set console access ───────────────────────────
  function openSetConsoleModal(userId, currentValue) {
    openModal({
      title: 'Set console access · MEDIUM friction',
      sub: `Operator/admin surface boundary toggle.`,
      bodyHtml: `
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">current</span><span class="fgm-fact-v">${currentValue ? 'true' : 'false'}</span></div>
        <label class="fgm-label">New value</label>
        <select class="fgm-select" id="fgm-console">
          <option value="false" ${!currentValue ? 'selected' : ''}>false</option>
          <option value="true" ${currentValue ? 'selected' : ''}>true</option>
        </select>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-warn" data-fgm-confirm>Apply</button>
      `,
      onMount: (bd) => {
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        bd.querySelector('[data-fgm-confirm]').addEventListener('click', async () => {
          try {
            await mutateAndRefetch('/api/admin/operator-access/set-console-access', {
              userId, consoleAccess: bd.querySelector('#fgm-console').value === 'true',
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Не удалось: ' + detail);
          }
        });
      },
    });
  }

  // ── Modal: MEDIUM — set broker mode ───────────────────────────────
  function openSetModeModal(userId, currentMode) {
    openModal({
      title: 'Set broker mode · MEDIUM friction',
      sub: `Broker connection mode — это НЕ live authority. mode=live без liveAuthority.granted означает только что broker может читать live data.`,
      bodyHtml: `
        <div class="fgm-fact"><span class="fgm-fact-k">userId</span><span class="fgm-fact-v">${fmt.h(userId)}</span></div>
        <div class="fgm-fact"><span class="fgm-fact-k">current</span><span class="fgm-fact-v">${fmt.h(currentMode)}</span></div>
        <label class="fgm-label">New mode</label>
        <select class="fgm-select" id="fgm-mode">
          ${MODE_VOCAB.map(m => `<option value="${m}" ${m === currentMode ? 'selected' : ''}>${m}</option>`).join('')}
        </select>
      `,
      footHtml: `
        <button class="fgi-btn fgi-btn-quiet" data-fgm-cancel>Отмена</button>
        <button class="fgi-btn fgi-btn-warn" data-fgm-confirm>Apply</button>
      `,
      onMount: (bd) => {
        bd.querySelector('[data-fgm-cancel]').addEventListener('click', closeModal);
        bd.querySelector('[data-fgm-confirm]').addEventListener('click', async () => {
          try {
            await mutateAndRefetch('/api/admin/operator-access/set-mode', {
              userId, mode: bd.querySelector('#fgm-mode').value,
            });
            closeModal();
          } catch (e) {
            const detail = e.body && e.body.detail ? (e.body.detail.error || JSON.stringify(e.body.detail)) : e.message;
            showModalError(bd, 'Не удалось: ' + detail);
          }
        });
      },
    });
  }

  // ── Lifecycle ──────────────────────────────────────────────────────
  function isAdminRoute() { return /\/admin(\/|$)/.test(window.location.pathname); }

  let attempts = 0;
  function tick() {
    if (!isAdminRoute()) { teardownPanel(); return; }
    const sidebar = findSidebar();
    if (!sidebar) {
      if (++attempts < 80) setTimeout(tick, 350);
      return;
    }
    const nav = injectNav(sidebar);
    if (nav) {
      wireSidebarTeardown(sidebar);
    } else if (++attempts < 80) setTimeout(tick, 350);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }

  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      attempts = 0;
      if (!isAdminRoute()) teardownPanel();
      else setTimeout(tick, 350);
    }
    if (!isAdminRoute()) return;
    const sidebar = findSidebar();
    if (!sidebar) return;
    if (!document.getElementById(NAV_ID)) {
      attempts = 0;
      injectNav(sidebar);
    }
    wireSidebarTeardown(sidebar);
  }, 800);
})();
