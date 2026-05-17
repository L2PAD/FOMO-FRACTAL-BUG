/**
 * execution-inject.js — T10.2D Execution Ledger (Forensic Surface)
 *
 * Adds a single sidebar nav «Исполнение» to the FOMO admin shell.
 * Activation mounts a read-only immutable ledger into <main>.
 *
 * THIS IS NOT a trade console. NOT a trading terminal. NOT an
 * execution cockpit. NOT a deploy center. NOT an order manager.
 * It is a forensic receipt ledger — every row is an immutable
 * transport observation, never a live actionable record.
 *
 * Architectural invariants (locked by user — DO NOT VIOLATE):
 *   1. ZERO submit-side semantics. UI never calls POST /submit.
 *   2. NO retry / resubmit / replay / resend / recover affordances.
 *      Not as buttons, not as disabled buttons, not as wording.
 *   3. NO PnL, slippage quality, latency leaderboard, broker score,
 *      execution edge, fill optimization, success-rate hero cards.
 *   4. Failures are observational records, not recovery prompts.
 *      That sentence is rendered verbatim in the header.
 *   5. Mode is shown plainly (MOCK / TESTNET) — no celebration.
 *   6. Drilldown is inline expand or right drawer ONLY — no SPA route.
 *   7. Reuses canonical primitives from window.__fomoAdminInject.
 *
 * Endpoints consumed (read-only, all GET):
 *   GET /api/admin/execution/testnet/config
 *   GET /api/admin/execution/testnet/receipts
 *   GET /api/admin/execution/testnet/receipts/{receiptId}
 *   GET /api/admin/execution/testnet/receipts/by-lineage/{lineageId}
 *
 * (The POST /submit endpoint is intentionally never referenced here.)
 */
(function () {
  'use strict';

  if (window.__fomoExecutionInjectLoaded) return;
  window.__fomoExecutionInjectLoaded = true;

  // Reuse canonical primitives created by billing-inject; install thin
  // fallbacks so this inject still works in isolation.
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
  const NAV_ID   = 'fomo-execution-nav';
  const PANEL_ID = 'fomo-execution-panel';
  const CSS_ID   = 'fomo-execution-css';
  const DRAWER_ID = 'fomo-execution-drawer';
  const HIDE_CLS = 'fomo-execution-native-hidden';

  // Anchor sequence for sidebar insertion.
  const ANCHOR_LABELS_AFTER  = ['Атрибуция', 'Billing'];
  const ANCHOR_LABELS_BEFORE = ['Referrals', 'Intel System'];

  // Canonical terminal status set (FORBIDDEN wording elsewhere).
  const STATUS_DEFS = {
    submitted:       { ru: 'submitted',       hint: 'broker принял заявку' },
    broker_reject:   { ru: 'broker_reject',   hint: 'broker отклонил заявку' },
    transport_error: { ru: 'transport_error', hint: 'network/SDK сбой до broker' },
    preflight_fail:  { ru: 'preflight_fail',  hint: 'наша gate-сторона отказала' },
  };
  const STATUS_ORDER = ['submitted', 'broker_reject', 'transport_error', 'preflight_fail'];

  // ── CSS ────────────────────────────────────────────────────────────
  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = `
.${HIDE_CLS}{display:none !important}
#${PANEL_ID}{padding:24px 28px 56px;background:#f8fafc;min-height:calc(100vh - 3rem);color:#0f172a;font-size:13px;line-height:1.55}
#${PANEL_ID} *{box-sizing:border-box}
#${PANEL_ID} .fei-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:6px;flex-wrap:wrap}
#${PANEL_ID} .fei-title{font-size:22px;font-weight:700;letter-spacing:-0.01em;color:#0f172a;margin:0;display:flex;align-items:center;gap:10px}
#${PANEL_ID} .fei-title::before{content:"";width:3px;height:18px;background:#475569;display:inline-block;border-radius:2px}
#${PANEL_ID} .fei-subtitle{font-size:12px;color:#64748b;margin:4px 0 0;max-width:820px;line-height:1.55}
#${PANEL_ID} .fei-invariants{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}
#${PANEL_ID} .fei-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,monospace;font-size:11px;color:#334155}
#${PANEL_ID} .fei-chip.mode-mock{border-color:#cbd5e1;color:#475569}
#${PANEL_ID} .fei-chip.mode-testnet{border-color:#fcd34d;color:#92400e;background:#fffbeb}
#${PANEL_ID} .fei-assert{margin-top:14px;padding:12px 16px;background:#f1f5f9;border-left:3px solid #475569;border-radius:8px;color:#1e293b;font-size:12px;line-height:1.6}
#${PANEL_ID} .fei-assert strong{color:#0f172a;font-weight:700}
#${PANEL_ID} .fei-assert .fei-assert-2{display:block;margin-top:6px;color:#475569;font-style:italic}
#${PANEL_ID} h3{font-size:10.5px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:0 0 12px;display:flex;align-items:center;gap:10px}
#${PANEL_ID} h3::before{content:"";width:14px;height:1px;background:#94a3b8;display:inline-block}
#${PANEL_ID} .fei-kpis{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-top:16px}
#${PANEL_ID} .fei-kpi{padding:12px 14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px}
#${PANEL_ID} .fei-kpi .fei-kpi-label{font-size:9.5px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px}
#${PANEL_ID} .fei-kpi .fei-kpi-value{font-size:18px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums}
#${PANEL_ID} .fei-kpi .fei-kpi-sub{font-size:10.5px;color:#94a3b8;margin-top:3px;font-family:'JetBrains Mono',ui-monospace,monospace}
#${PANEL_ID} .fei-toolbar{margin-top:18px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 14px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px}
#${PANEL_ID} .fei-toolbar-left{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
#${PANEL_ID} .fei-toolbar label{font-size:10.5px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.1em;font-weight:700}
#${PANEL_ID} .fei-select{padding:5px 9px;border:1px solid #e5e7eb;border-radius:7px;background:#ffffff;font-size:12px;color:#0f172a}
#${PANEL_ID} .fei-btn{padding:5px 11px;border:1px solid #e5e7eb;border-radius:7px;background:#ffffff;font-size:12px;font-weight:600;color:#0f172a;cursor:pointer;transition:background .12s,border-color .12s}
#${PANEL_ID} .fei-btn:hover{background:#f8fafc;border-color:#cbd5e1}
#${PANEL_ID} table.fei-table{width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;font-size:12px;margin-top:14px}
#${PANEL_ID} .fei-table th{text-align:left;padding:10px 14px;font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:700;white-space:nowrap}
#${PANEL_ID} .fei-table td{padding:11px 14px;border-bottom:1px solid #f1f5f9;color:#0f172a;font-variant-numeric:tabular-nums;vertical-align:top}
#${PANEL_ID} .fei-table tr:last-child td{border-bottom:none}
#${PANEL_ID} .fei-table tr.fei-row{cursor:pointer;transition:background .1s}
#${PANEL_ID} .fei-table tr.fei-row:hover td{background:#f8fafc}
#${PANEL_ID} .fei-meta{font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',ui-monospace,monospace}
#${PANEL_ID} .fei-key{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:#334155}
#${PANEL_ID} .fei-key-sub{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;color:#94a3b8}
#${PANEL_ID} .fei-pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:9.5px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;background:#e2e8f0;color:#334155;white-space:nowrap}
#${PANEL_ID} .fei-pill.s-submitted     {background:#e0e7ff;color:#3730a3}
#${PANEL_ID} .fei-pill.s-broker_reject {background:#fef3c7;color:#854d0e}
#${PANEL_ID} .fei-pill.s-transport_error{background:#fee2e2;color:#991b1b}
#${PANEL_ID} .fei-pill.s-preflight_fail{background:#f1f5f9;color:#475569}
#${PANEL_ID} .fei-pill.side-buy {background:#e2e8f0;color:#334155}
#${PANEL_ID} .fei-pill.side-sell{background:#e2e8f0;color:#334155}
#${PANEL_ID} .fei-pill.mode-mock {background:#f1f5f9;color:#64748b}
#${PANEL_ID} .fei-pill.mode-testnet{background:#fffbeb;color:#92400e;border:1px solid #fde68a}
#${PANEL_ID} .fei-pill.pf-ok    {background:#e2e8f0;color:#475569}
#${PANEL_ID} .fei-pill.pf-fail  {background:#fee2e2;color:#991b1b}
#${PANEL_ID} .fei-empty{padding:48px 16px;text-align:center;color:#64748b;font-size:13px;background:#ffffff;border:1px dashed #e5e7eb;border-radius:10px;margin-top:14px}
#${PANEL_ID} .fei-loading{padding:24px;text-align:center;color:#94a3b8;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;font-weight:700}
#${PANEL_ID} .fei-error{padding:14px 16px;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;color:#991b1b;font-size:13px;margin-bottom:14px}
#${PANEL_ID} .fei-section-spacer{height:24px}

/* Right drawer */
#${DRAWER_ID}{position:fixed;top:0;right:0;width:520px;max-width:96vw;height:100vh;background:#ffffff;box-shadow:-12px 0 40px rgba(15,23,42,0.18);border-left:1px solid #e5e7eb;z-index:9999;display:flex;flex-direction:column;transform:translateX(100%);transition:transform .22s ease}
#${DRAWER_ID}.open{transform:translateX(0)}
#${DRAWER_ID} .fed-head{padding:18px 22px;border-bottom:1px solid #e5e7eb;display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
#${DRAWER_ID} .fed-title{font-size:14px;font-weight:700;color:#0f172a;letter-spacing:-0.005em;margin:0 0 4px;display:flex;align-items:center;gap:8px}
#${DRAWER_ID} .fed-sub{font-size:11px;color:#64748b;font-family:'JetBrains Mono',ui-monospace,monospace}
#${DRAWER_ID} .fed-close{background:transparent;border:none;font-size:18px;color:#94a3b8;cursor:pointer;padding:4px 8px;border-radius:6px;line-height:1}
#${DRAWER_ID} .fed-close:hover{background:#f8fafc;color:#0f172a}
#${DRAWER_ID} .fed-body{flex:1;overflow-y:auto;padding:18px 22px 80px;font-size:12.5px;color:#0f172a;line-height:1.55}
#${DRAWER_ID} .fed-section{margin-bottom:18px}
#${DRAWER_ID} .fed-section:last-child{margin-bottom:0}
#${DRAWER_ID} .fed-section-h{font-size:10px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:#475569;margin:0 0 8px;display:flex;align-items:center;gap:8px}
#${DRAWER_ID} .fed-section-h::before{content:"";width:10px;height:1px;background:#94a3b8;display:inline-block}
#${DRAWER_ID} .fed-row{display:flex;justify-content:space-between;padding:6px 0;font-size:12px;border-bottom:1px solid #f1f5f9}
#${DRAWER_ID} .fed-row:last-child{border-bottom:none}
#${DRAWER_ID} .fed-row .fed-k{color:#64748b;font-size:11px}
#${DRAWER_ID} .fed-row .fed-v{font-variant-numeric:tabular-nums;color:#0f172a;font-weight:600;text-align:right;max-width:60%;word-break:break-all;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px}
#${DRAWER_ID} pre.fed-json{background:#0f172a;color:#e2e8f0;padding:12px 14px;border-radius:8px;font-family:'JetBrains Mono',ui-monospace,monospace;font-size:10.5px;line-height:1.5;overflow:auto;max-height:280px;margin:0;white-space:pre-wrap;word-break:break-word}
#${DRAWER_ID} .fed-preflight-row{display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9}
#${DRAWER_ID} .fed-preflight-row:last-child{border-bottom:none}
#${DRAWER_ID} .fed-collapse{border:1px solid #e5e7eb;border-radius:8px;overflow:hidden}
#${DRAWER_ID} .fed-collapse-head{padding:9px 12px;background:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;font-size:11px;font-weight:600;color:#0f172a;user-select:none}
#${DRAWER_ID} .fed-collapse-head:hover{background:#f1f5f9}
#${DRAWER_ID} .fed-collapse-arrow{font-size:9px;color:#94a3b8;transition:transform .15s;display:inline-block;margin-left:8px}
#${DRAWER_ID} .fed-collapse.open .fed-collapse-arrow{transform:rotate(90deg)}
#${DRAWER_ID} .fed-collapse-body{display:none;padding:12px}
#${DRAWER_ID} .fed-collapse.open .fed-collapse-body{display:block}
#${DRAWER_ID} .fed-note{font-size:11px;color:#64748b;font-style:italic;line-height:1.55;padding:10px 12px;background:#f8fafc;border-radius:8px;margin-top:10px}
.fei-drawer-backdrop{position:fixed;inset:0;background:rgba(15,23,42,0.18);z-index:9998;opacity:0;pointer-events:none;transition:opacity .15s}
.fei-drawer-backdrop.open{opacity:1;pointer-events:auto}
`;
    document.head.appendChild(s);
  }

  // ── Formatters ─────────────────────────────────────────────────────
  const fmt = {
    int: (n) => (n == null || isNaN(n) ? '—' : Number(n).toLocaleString('en-US')),
    usd: (n) => (n == null || isNaN(n) ? '—' : '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })),
    num: (n) => (n == null || isNaN(n) ? '—' : String(n)),
    ts: (iso) => {
      if (!iso) return '—';
      try {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return iso;
        return d.toISOString().replace('T', ' ').slice(0, 19) + 'Z';
      } catch (_) { return iso; }
    },
    short: (s, n) => {
      n = n || 12;
      if (!s) return '—';
      const str = String(s);
      if (str.length <= n + 2) return str;
      return str.slice(0, n) + '…';
    },
    h: (s) => String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    json: (o) => {
      try { return JSON.stringify(o, null, 2); } catch (_) { return String(o); }
    },
  };

  // ── Sidebar nav injection (reuses pattern from attribution-inject) ─
  function findSidebar() {
    return document.querySelector('aside[data-testid="admin-sidebar"]')
      || document.querySelector('aside.admin-sidebar')
      || document.querySelector('aside');
  }
  function findMainArea() {
    return document.querySelector('main') || null;
  }
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
    const samples = ['Billing', 'Referrals', 'Intel System', 'News', 'Signals'];
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
    nav.setAttribute('data-testid', 'admin-nav-execution');
    if (sample.className) nav.className = sample.className;
    nav.className = (nav.className || '').replace(/bg-indigo-50|text-indigo-700|border-l-2|border-indigo-600/g, '').trim();
    // Icon: ledger / receipt glyph, neutral gray. No play arrows, no flame.
    nav.innerHTML =
      '<svg class="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M6 3h10a2 2 0 0 1 2 2v15l-3-1.5L12 20l-3-1.5L6 20V3Z"/>' +
      '<path d="M9 8h6M9 12h6M9 16h4"/>' +
      '</svg>' +
      '<span class="flex-1 truncate">Исполнение</span>';

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

  // ── Panel mount / teardown ─────────────────────────────────────────
  let currentFilters = { status: '', mode: '', symbol: '', limit: 100 };
  let cachedConfig = null;
  let cachedReceipts = [];

  function closeDrawer() {
    const d = document.getElementById(DRAWER_ID);
    const bd = document.querySelector('.fei-drawer-backdrop');
    if (d)  d.classList.remove('open');
    if (bd) bd.classList.remove('open');
    setTimeout(() => {
      if (d && d.parentElement)  d.parentElement.removeChild(d);
      if (bd && bd.parentElement) bd.parentElement.removeChild(bd);
    }, 240);
  }

  function teardownPanel() {
    closeDrawer();
    FomoInject.destroyMountedPanel(PANEL_ID);
    document.querySelectorAll('.' + HIDE_CLS).forEach(n => n.classList.remove(HIDE_CLS));
    const nav = document.getElementById(NAV_ID);
    if (nav) applyNavActiveStyles(nav, false);
  }

  function wireSidebarTeardown(sidebar) {
    Array.from(sidebar.querySelectorAll('a, button')).forEach(item => {
      if (item.id === NAV_ID) return;
      if (item.__fomoExecTeardownWired) return;
      item.__fomoExecTeardownWired = true;
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
      panel.setAttribute('data-testid', 'fomo-execution-panel');
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
    panel.innerHTML = '<div class="fei-loading">Подгружаю ledger…</div>';
    await renderPanel(panel);
  }

  // ── Renderers ──────────────────────────────────────────────────────
  async function renderPanel(panel) {
    let config = null;
    try {
      config = await FomoInject.fetchWithAdminJWT('/api/admin/execution/testnet/config');
      cachedConfig = config;
    } catch (e) {
      panel.innerHTML = '<div class="fei-error">Ledger недоступен: ' + fmt.h(e.message) + (e.status === 401 ? ' — переавторизуйтесь как админ.' : '') + '</div>';
      return;
    }

    const inv = config.invariants || {};
    panel.innerHTML = `
      <div class="fei-header">
        <div>
          <h1 class="fei-title">Исполнение</h1>
          <p class="fei-subtitle">Immutable execution receipt ledger. T10.2C/D — testnet-only forensic surface. Не trading-консоль, не cockpit, не deploy-center. Каждая строка — апостериорная фотография одной transport-попытки.</p>
        </div>
        <div class="fei-invariants">
          <span class="fei-chip">pipeline · ${fmt.h(config.pipelineVersion || '—')}</span>
          <span class="fei-chip ${config.mode === 'testnet' ? 'mode-testnet' : 'mode-mock'}">mode · ${fmt.h((config.mode || '?').toUpperCase())}</span>
          <span class="fei-chip">TESTNET_ONLY · ${inv.TESTNET_ONLY ? 'true' : 'false'}</span>
          <span class="fei-chip">MAX_NOTIONAL · ${fmt.usd(inv.MAX_NOTIONAL_USD)}</span>
          <span class="fei-chip">symbols · ${(inv.SYMBOL_ALLOWLIST || []).join(', ')}</span>
          <span class="fei-chip">retry · forbidden</span>
        </div>
      </div>
      <div class="fei-assert">
        <strong>Execution receipts are immutable transport observations.</strong>
        <span class="fei-assert-2">Failures are observational records, not recovery prompts.</span>
      </div>

      <div class="fei-section-spacer"></div>

      <h3>Transport observation</h3>
      <div class="fei-kpis" id="fei-kpis"><div class="fei-loading">Считаю…</div></div>

      <div class="fei-section-spacer"></div>

      <h3>Receipts</h3>
      <div class="fei-toolbar" id="fei-toolbar">
        <div class="fei-toolbar-left">
          <label>Status</label>
          <select id="fei-flt-status" class="fei-select">
            <option value="">все</option>
            ${STATUS_ORDER.map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
          <label>Mode</label>
          <select id="fei-flt-mode" class="fei-select">
            <option value="">все</option>
            <option value="mock">mock</option>
            <option value="testnet">testnet</option>
          </select>
          <label>Symbol</label>
          <select id="fei-flt-symbol" class="fei-select">
            <option value="">все</option>
            ${(inv.SYMBOL_ALLOWLIST || []).map(s => `<option value="${fmt.h(s)}">${fmt.h(s)}</option>`).join('')}
          </select>
          <label>Окно</label>
          <select id="fei-flt-window" class="fei-select">
            <option value="">всё время</option>
            <option value="24h">24h</option>
            <option value="7d">7d</option>
            <option value="30d">30d</option>
          </select>
          <label>Limit</label>
          <select id="fei-flt-limit" class="fei-select">
            <option value="50">50</option>
            <option value="100" selected>100</option>
            <option value="250">250</option>
            <option value="500">500</option>
          </select>
        </div>
        <button class="fei-btn" id="fei-refresh">Обновить</button>
      </div>
      <div id="fei-receipts-body"><div class="fei-loading">Загружаю receipts…</div></div>
    `;

    // Wire filters
    const $ = (id) => panel.querySelector(id);
    const apply = () => {
      currentFilters.status = $('#fei-flt-status').value;
      currentFilters.mode = $('#fei-flt-mode').value;
      currentFilters.symbol = $('#fei-flt-symbol').value;
      currentFilters.window = $('#fei-flt-window').value;
      currentFilters.limit = Number($('#fei-flt-limit').value) || 100;
      renderReceipts(panel);
    };
    ['#fei-flt-status', '#fei-flt-mode', '#fei-flt-symbol', '#fei-flt-window', '#fei-flt-limit'].forEach(sel => {
      $(sel).addEventListener('change', apply);
    });
    $('#fei-refresh').addEventListener('click', apply);

    await renderReceipts(panel);
  }

  function applyFilters(rows) {
    return rows.filter(r => {
      if (currentFilters.status && r.status !== currentFilters.status) return false;
      if (currentFilters.mode && ((r.transport || {}).mode !== currentFilters.mode)) return false;
      if (currentFilters.symbol) {
        const sym = (r.symbol || '').toUpperCase();
        const want = currentFilters.symbol.toUpperCase();
        if (sym !== want && sym.replace('/', '') !== want.replace('/', '')) return false;
      }
      if (currentFilters.window) {
        const ms = { '24h': 86400e3, '7d': 7 * 86400e3, '30d': 30 * 86400e3 }[currentFilters.window];
        if (ms) {
          const ts = new Date(r.createdAt || r.submittedAt || 0).getTime();
          if (!ts || (Date.now() - ts) > ms) return false;
        }
      }
      return true;
    });
  }

  async function renderReceipts(panel) {
    const body = panel.querySelector('#fei-receipts-body');
    const kpis = panel.querySelector('#fei-kpis');
    body.innerHTML = '<div class="fei-loading">Загружаю receipts…</div>';
    kpis.innerHTML = '<div class="fei-loading">Считаю…</div>';
    let data;
    try {
      data = await FomoInject.fetchWithAdminJWT('/api/admin/execution/testnet/receipts?limit=' + encodeURIComponent(currentFilters.limit || 100));
    } catch (e) {
      body.innerHTML = '<div class="fei-error">Receipts недоступны: ' + fmt.h(e.message) + '</div>';
      kpis.innerHTML = '';
      return;
    }
    cachedReceipts = data.rows || [];
    const filtered = applyFilters(cachedReceipts);

    // KPIs computed on ENTIRE fetched window (not the filter view) so the
    // operator can see baseline counts even while drilling down.
    const counts = { total: cachedReceipts.length };
    STATUS_ORDER.forEach(s => { counts[s] = 0; });
    cachedReceipts.forEach(r => {
      if (counts.hasOwnProperty(r.status)) counts[r.status]++;
    });
    kpis.innerHTML = `
      <div class="fei-kpi">
        <div class="fei-kpi-label">Total receipts</div>
        <div class="fei-kpi-value">${fmt.int(counts.total)}</div>
        <div class="fei-kpi-sub">в выбранном лимите</div>
      </div>
      ${STATUS_ORDER.map(s => `
        <div class="fei-kpi">
          <div class="fei-kpi-label">${STATUS_DEFS[s].ru}</div>
          <div class="fei-kpi-value">${fmt.int(counts[s])}</div>
          <div class="fei-kpi-sub">${fmt.h(STATUS_DEFS[s].hint)}</div>
        </div>
      `).join('')}
    `;

    if (!filtered.length) {
      body.innerHTML = '<div class="fei-empty">Receipts с такими фильтрами не найдено. Ledger append-only — данные появятся, как только пройдут execution-попытки.</div>';
      return;
    }

    body.innerHTML = `
      <table class="fei-table">
        <thead><tr>
          <th>Created</th>
          <th>Symbol</th>
          <th>Side</th>
          <th style="text-align:right">Notional</th>
          <th>Lineage ID</th>
          <th>Preflight</th>
          <th>Transport</th>
          <th>Terminal</th>
          <th>Mode</th>
          <th>Receipt</th>
        </tr></thead>
        <tbody>
          ${filtered.map(r => {
            const pf = r.preflight || {};
            const pfFail = r.failedCheck || (Object.values(pf).some(v => v === false) ? 'fail' : null);
            const t = r.transport || {};
            return `<tr class="fei-row" data-receipt-id="${fmt.h(r.receiptId)}">
              <td class="fei-meta">${fmt.ts(r.createdAt)}</td>
              <td><strong>${fmt.h(r.symbol || '—')}</strong></td>
              <td><span class="fei-pill side-${(r.side || '').toLowerCase()}">${fmt.h(r.side || '—')}</span></td>
              <td style="text-align:right">${fmt.usd(r.sizeUsd)}</td>
              <td class="fei-key" title="${fmt.h(r.lineageId || '')}">${fmt.h(fmt.short(r.lineageId, 14))}</td>
              <td><span class="fei-pill ${pfFail ? 'pf-fail' : 'pf-ok'}">${pfFail ? ('fail: ' + fmt.h(r.failedCheck || '?')) : 'ok'}</span></td>
              <td><span class="fei-pill">${fmt.h((t.status || '—').toLowerCase())}</span>${t.latencyMs != null ? ' <span class="fei-key-sub">' + fmt.int(t.latencyMs) + 'ms</span>' : ''}</td>
              <td><span class="fei-pill s-${fmt.h(r.status)}">${fmt.h(r.status)}</span></td>
              <td><span class="fei-pill mode-${fmt.h((t.mode || '').toLowerCase())}">${fmt.h((t.mode || '—').toUpperCase())}</span></td>
              <td class="fei-key-sub" title="${fmt.h(r.receiptId || '')}">${fmt.h(fmt.short(r.receiptId, 10))}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      <div class="fei-meta" style="margin-top:10px">${filtered.length} of ${cachedReceipts.length} · sorted by createdAt desc · append-only, без перезаписи</div>
    `;

    // Wire row click → drawer
    body.querySelectorAll('.fei-row').forEach(tr => {
      tr.addEventListener('click', async () => {
        const rid = tr.getAttribute('data-receipt-id');
        await openDrawer(rid);
      });
    });
  }

  // ── Drawer (Receipt Detail) ────────────────────────────────────────
  async function openDrawer(receiptId) {
    // Find cached row first for instant render, then fetch canonical detail.
    const cached = cachedReceipts.find(r => r.receiptId === receiptId);
    let backdrop = document.querySelector('.fei-drawer-backdrop');
    if (!backdrop) {
      backdrop = document.createElement('div');
      backdrop.className = 'fei-drawer-backdrop';
      document.body.appendChild(backdrop);
      backdrop.addEventListener('click', closeDrawer);
    }
    let drawer = document.getElementById(DRAWER_ID);
    if (!drawer) {
      drawer = document.createElement('div');
      drawer.id = DRAWER_ID;
      drawer.setAttribute('data-testid', 'fomo-execution-drawer');
      document.body.appendChild(drawer);
    }
    drawer.innerHTML = `
      <div class="fed-head">
        <div>
          <h2 class="fed-title"><span style="display:inline-block;width:8px;height:8px;border-radius:2px;background:#475569"></span>Receipt detail</h2>
          <div class="fed-sub">${fmt.h(receiptId)}</div>
        </div>
        <button class="fed-close" aria-label="Close">×</button>
      </div>
      <div class="fed-body"><div class="fei-loading">Подгружаю детали…</div></div>
    `;
    drawer.querySelector('.fed-close').addEventListener('click', closeDrawer);
    requestAnimationFrame(() => {
      drawer.classList.add('open');
      backdrop.classList.add('open');
    });

    let r = cached;
    try {
      const data = await FomoInject.fetchWithAdminJWT('/api/admin/execution/testnet/receipts/' + encodeURIComponent(receiptId));
      r = data.receipt || r;
    } catch (e) {
      drawer.querySelector('.fed-body').innerHTML = '<div class="fei-error">Не удалось получить receipt: ' + fmt.h(e.message) + '</div>';
      return;
    }
    if (!r) {
      drawer.querySelector('.fed-body').innerHTML = '<div class="fei-empty">Receipt не найден.</div>';
      return;
    }
    renderDrawerBody(drawer.querySelector('.fed-body'), r);
  }

  function renderDrawerBody(host, r) {
    const pf = r.preflight || {};
    const t  = r.transport || {};
    const pfKeys = ['symbolAllowed', 'notionalOk', 'lineageOk', 'authorityOk', 'testnetOnly'];
    const brokerAckIsNull = (r.brokerAck == null);
    host.innerHTML = `
      <div class="fed-section">
        <div class="fed-section-h">Receipt</div>
        <div class="fed-row"><span class="fed-k">receiptId</span><span class="fed-v">${fmt.h(r.receiptId || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">lineageId</span><span class="fed-v">${fmt.h(r.lineageId || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">pipelineVersion</span><span class="fed-v">${fmt.h(r.pipelineVersion || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">submittedBy</span><span class="fed-v">${fmt.h(r.submittedBy || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">operatorUserId</span><span class="fed-v">${fmt.h(r.operatorUserId || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">symbol · side · notional</span><span class="fed-v">${fmt.h(r.symbol || '—')} · ${fmt.h(r.side || '—')} · ${fmt.usd(r.sizeUsd)}</span></div>
        <div class="fed-row"><span class="fed-k">submittedAt</span><span class="fed-v">${fmt.ts(r.submittedAt)}</span></div>
        <div class="fed-row"><span class="fed-k">completedAt</span><span class="fed-v">${fmt.ts(r.completedAt)}</span></div>
        <div class="fed-row"><span class="fed-k">createdAt</span><span class="fed-v">${fmt.ts(r.createdAt)}</span></div>
        <div class="fed-row"><span class="fed-k">status</span><span class="fed-v"><span class="fei-pill s-${fmt.h(r.status)}">${fmt.h(r.status)}</span></span></div>
      </div>

      <div class="fed-section">
        <div class="fed-section-h">Preflight snapshot</div>
        ${pfKeys.map(k => {
          if (!(k in pf)) return '';
          const v = pf[k];
          return `<div class="fed-preflight-row">
            <span class="fed-k">${fmt.h(k)}</span>
            <span class="fed-v"><span class="fei-pill ${v ? 'pf-ok' : 'pf-fail'}">${v ? 'ok' : 'fail'}</span></span>
          </div>`;
        }).join('')}
        ${r.failedCheck ? `<div class="fed-note">failedCheck = <strong>${fmt.h(r.failedCheck)}</strong>. Это observational outcome — receipt вписан, transport не вызывался.</div>` : ''}
      </div>

      <div class="fed-section">
        <div class="fed-section-h">Broker acknowledgement</div>
        ${brokerAckIsNull
          ? '<div class="fed-note">broker не вызывался — preflight отказал ранее.</div>'
          : `<div class="fed-collapse" data-collapse="brokerAck">
              <div class="fed-collapse-head">
                <span>brokerAck (raw snapshot)</span>
                <span class="fed-collapse-arrow">▶</span>
              </div>
              <div class="fed-collapse-body"><pre class="fed-json">${fmt.h(fmt.json(r.brokerAck))}</pre></div>
             </div>`
        }
      </div>

      <div class="fed-section">
        <div class="fed-section-h">Transport</div>
        <div class="fed-row"><span class="fed-k">mode</span><span class="fed-v"><span class="fei-pill mode-${fmt.h((t.mode || '').toLowerCase())}">${fmt.h((t.mode || '—').toUpperCase())}</span></span></div>
        <div class="fed-row"><span class="fed-k">status</span><span class="fed-v">${fmt.h(t.status || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">latencyMs</span><span class="fed-v">${fmt.int(t.latencyMs)}</span></div>
        <div class="fed-row"><span class="fed-k">errorCode</span><span class="fed-v">${fmt.h(t.errorCode || '—')}</span></div>
        <div class="fed-row"><span class="fed-k">errorMessage</span><span class="fed-v" style="text-align:left">${fmt.h(t.errorMessage || '—')}</span></div>
      </div>

      <div class="fed-note">Этот receipt immutable. Здесь нет действий — нет retry, нет resubmit, нет recover. Если нужна новая попытка по бизнес-смыслу, она требует нового lineageId, прошедшего gate заново.</div>
    `;
    // Wire collapse(s)
    host.querySelectorAll('.fed-collapse').forEach(box => {
      const head = box.querySelector('.fed-collapse-head');
      head.addEventListener('click', () => box.classList.toggle('open'));
    });
  }

  // ── Lifecycle ───────────────────────────────────────────────────────
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
    } else {
      if (++attempts < 80) setTimeout(tick, 350);
    }
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
