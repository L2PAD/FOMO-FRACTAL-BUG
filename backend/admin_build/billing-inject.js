/**
 * billing-inject.js — Canonical Billing Domains (Pilot Injector)
 *
 * Adds three canonical billing tabs to the existing Billing Console
 * inside the FOMO Intelligence Terminal:
 *
 *   • Инвойсы        — /api/billing/invoices (immutable invoice ledger)
 *   • Reconciliation — /api/admin/billing/reconciliation/* (findings stream)
 *   • Analytics      — /api/admin/billing/analytics/summary (derived KPIs)
 *
 * This is a READ-ONLY ledger surface — no checkout, no cart, no SaaS
 * subscription affordances. Tone is forensic, governance-adjacent.
 *
 * Architectural invariants (locked by user):
 *   1. NO router hijack — we never push routes. We mount a panel under
 *      the existing tab bar and tear it down when any native tab is clicked.
 *   2. NO mini-UI duplication — we surface canonical APIs only; we never
 *      reimplement subscription / customer flows that already exist.
 *   3. Reusable injection primitives live on window.__fomoAdminInject so
 *      governance-inject.js / attribution-inject.js / execution-inject.js
 *      can use the same grammar.
 *   4. Tabs are self-healing — if the React layer re-renders the tab bar,
 *      we re-inject our tabs.
 *   5. Visually matches the existing pill-tab grammar (same classes cloned
 *      from a native inactive tab; active class cloned from the live
 *      active tab at first paint).
 */
(function () {
  'use strict';

  if (window.__fomoBillingInjectLoaded) return;
  window.__fomoBillingInjectLoaded = true;

  // ── Reusable injection primitives (shared with future injectors) ────
  const FomoInject = (window.__fomoAdminInject = window.__fomoAdminInject || {});

  // Locate JWT in localStorage (FOMO admin uses `admin_token`).
  FomoInject.getAdminToken = function () {
    try {
      const v = localStorage.getItem('admin_token');
      if (v) return v.replace(/^"|"$/g, '');
    } catch (_) {}
    // Fallback: any localStorage value that looks like a JWT.
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        const val = localStorage.getItem(k) || '';
        if (/^eyJ[\w-]+\.[\w-]+\.[\w-]+$/.test(val)) return val;
      }
    } catch (_) {}
    return null;
  };

  // Fetch with admin Bearer JWT. Returns parsed JSON or throws.
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
    if (!res.ok) {
      const err = new Error(res.status + ' ' + res.statusText);
      err.status = res.status;
      err.body = body;
      throw err;
    }
    return body;
  };

  // Append a sibling tab into an existing tab bar, cloning style from a sample.
  // opts: { tabBar, sampleTab, id, label, icon, onActivate, onDeactivate }
  FomoInject.createSidebarTab = function (opts) {
    const existing = document.getElementById(opts.id);
    if (existing) return existing;
    const btn = document.createElement('button');
    btn.id = opts.id;
    btn.type = 'button';
    btn.setAttribute('data-fomo-inject-tab', opts.id);
    // Clone the sample tab's classes & inline style so we look native.
    if (opts.sampleTab) {
      if (opts.sampleTab.className) btn.className = opts.sampleTab.className;
      const inline = opts.sampleTab.getAttribute('style') || '';
      if (inline) btn.setAttribute('style', inline);
    }
    btn.innerHTML = (opts.icon || '') + '<span>' + (opts.label || '') + '</span>';
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (typeof opts.onActivate === 'function') opts.onActivate(btn);
    });
    opts.tabBar.appendChild(btn);
    return btn;
  };

  // Mount a panel as the next sibling of the tab bar's content area.
  // opts: { anchorAfter, id, build }
  FomoInject.createPanelShell = function (opts) {
    let panel = document.getElementById(opts.id);
    if (panel) {
      panel.classList.remove('fomo-inject-hidden');
      return panel;
    }
    panel = document.createElement('div');
    panel.id = opts.id;
    panel.setAttribute('data-fomo-inject-panel', opts.id);
    panel.style.cssText = 'margin-top:18px;padding:24px;border-radius:14px;background:#ffffff;border:1px solid #e5e7eb;box-shadow:0 1px 2px rgba(0,0,0,0.04);color:#111827;font-size:13px;line-height:1.5;';
    if (typeof opts.build === 'function') opts.build(panel);
    const after = opts.anchorAfter;
    if (after && after.parentElement) {
      after.parentElement.insertBefore(panel, after.nextElementSibling);
    } else {
      document.body.appendChild(panel);
    }
    return panel;
  };

  FomoInject.destroyMountedPanel = function (panelId) {
    const p = document.getElementById(panelId);
    if (p && p.parentElement) p.parentElement.removeChild(p);
  };

  // ── Billing inject implementation ──────────────────────────────────

  const ROOT_ID = 'fomo-billing-inject';
  const CSS_ID  = ROOT_ID + '-css';
  const PANEL_ID = ROOT_ID + '-panel';
  const TABS = [
    {
      key: 'invoices',
      id:  'fomo-billing-tab-invoices',
      label: 'Инвойсы',
      icon: svgIcon('M9 2h6a2 2 0 0 1 2 2v17l-3-2-2 2-2-2-2 2-3-2V4a2 2 0 0 1 2-2z M9 7h6 M9 11h6 M9 15h4'),
    },
    {
      key: 'reconciliation',
      id:  'fomo-billing-tab-reconciliation',
      label: 'Reconciliation',
      icon: svgIcon('M3 12a9 9 0 0 1 15-6.7L21 8 M21 3v5h-5 M21 12a9 9 0 0 1-15 6.7L3 16 M3 21v-5h5'),
    },
    {
      key: 'analytics',
      id:  'fomo-billing-tab-analytics',
      label: 'Analytics',
      icon: svgIcon('M3 3v18h18 M7 14l4-4 4 4 5-7'),
    },
  ];

  function svgIcon(d) {
    return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;margin-right:6px;flex-shrink:0">' +
      d.split(' M').map((part, i) => '<path d="' + (i === 0 ? part : 'M' + part) + '"/>').join('') +
      '</svg>';
  }

  function isBillingRoute() {
    return /\/admin\/billing(\/|$|\?)/.test(window.location.pathname + window.location.search);
  }

  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = `
.fomo-inject-hidden{display:none !important}
#${PANEL_ID} h3{font-size:13px;font-weight:700;letter-spacing:0.12em;color:#475569;text-transform:uppercase;margin:0 0 12px;display:flex;align-items:center;gap:8px}
#${PANEL_ID} h3::before{content:"";width:14px;height:1px;background:#94a3b8;display:inline-block}
#${PANEL_ID} .fbi-card{padding:18px;border:1px solid #e5e7eb;border-radius:12px;background:#fafafa;margin-bottom:14px}
#${PANEL_ID} .fbi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
#${PANEL_ID} .fbi-stat{padding:14px 16px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px}
#${PANEL_ID} .fbi-stat-label{font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px}
#${PANEL_ID} .fbi-stat-value{font-size:20px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums}
#${PANEL_ID} .fbi-stat-sub{font-size:11px;color:#64748b;margin-top:4px}
#${PANEL_ID} table.fbi-table{width:100%;border-collapse:collapse;font-size:12px;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}
#${PANEL_ID} .fbi-table th{text-align:left;padding:10px 12px;font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:700}
#${PANEL_ID} .fbi-table td{padding:10px 12px;border-bottom:1px solid #f1f5f9;color:#0f172a;font-variant-numeric:tabular-nums;vertical-align:top}
#${PANEL_ID} .fbi-table tr:last-child td{border-bottom:none}
#${PANEL_ID} .fbi-table tr:hover td{background:#f8fafc}
#${PANEL_ID} .fbi-pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase}
#${PANEL_ID} .fbi-pill.paid{background:#dcfce7;color:#166534}
#${PANEL_ID} .fbi-pill.pending{background:#fef3c7;color:#854d0e}
#${PANEL_ID} .fbi-pill.refunded{background:#fee2e2;color:#991b1b}
#${PANEL_ID} .fbi-pill.failed{background:#e0e7ff;color:#3730a3}
#${PANEL_ID} .fbi-pill.open{background:#dbeafe;color:#1e40af}
#${PANEL_ID} .fbi-pill.acknowledged{background:#e0e7ff;color:#3730a3}
#${PANEL_ID} .fbi-pill.resolved_later{background:#dcfce7;color:#166534}
#${PANEL_ID} .fbi-pill.info{background:#e2e8f0;color:#334155}
#${PANEL_ID} .fbi-pill.elevated{background:#fef3c7;color:#854d0e}
#${PANEL_ID} .fbi-pill.critical{background:#fee2e2;color:#991b1b}
#${PANEL_ID} .fbi-empty{padding:32px;text-align:center;color:#64748b;font-size:13px}
#${PANEL_ID} .fbi-loading{padding:24px;text-align:center;color:#94a3b8;font-size:12px;letter-spacing:0.1em;text-transform:uppercase;font-weight:700}
#${PANEL_ID} .fbi-error{padding:14px 16px;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;color:#991b1b;font-size:13px;margin-bottom:14px}
#${PANEL_ID} .fbi-title{font-size:20px;font-weight:700;color:#0f172a;margin:0 0 4px}
#${PANEL_ID} .fbi-subtitle{font-size:12px;color:#64748b;margin:0 0 20px;line-height:1.5}
#${PANEL_ID} .fbi-section{margin-bottom:22px}
#${PANEL_ID} .fbi-section:last-child{margin-bottom:0}
#${PANEL_ID} .fbi-meta{font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',ui-monospace,monospace}
#${PANEL_ID} .fbi-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap}
#${PANEL_ID} .fbi-toolbar-left{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
#${PANEL_ID} .fbi-select{padding:6px 10px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;font-size:12px;color:#0f172a}
#${PANEL_ID} .fbi-btn{padding:6px 12px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;font-size:12px;font-weight:600;color:#0f172a;cursor:pointer;transition:background .12s,border-color .12s}
#${PANEL_ID} .fbi-btn:hover{background:#f8fafc;border-color:#cbd5e1}
#${PANEL_ID} .fbi-btn.primary{background:#0f172a;color:#fafafa;border-color:#0f172a}
#${PANEL_ID} .fbi-btn.primary:hover{background:#1e293b}
#${PANEL_ID} .fbi-key{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:#334155}
`;
    document.head.appendChild(s);
  }

  // ── Tab strip discovery ────────────────────────────────────────────
  // Find the Billing Console's inner tab strip. It contains buttons
  // whose text matches the known Billing tabs (Обзор, Crypto Payments, etc).
  const NATIVE_TAB_LABELS = [
    'Обзор', 'Crypto Payments', 'Тарифы', 'Промокоды',
    'Подписчики', 'Платежи', 'Подписки', 'События', 'Доступ',
  ];

  function findNativeTabBar() {
    // Find a parent element that contains buttons matching most native labels.
    const candidates = new Map();
    document.querySelectorAll('button').forEach(b => {
      const t = (b.textContent || '').trim();
      if (NATIVE_TAB_LABELS.indexOf(t) === -1) return;
      const parent = b.parentElement;
      if (!parent) return;
      candidates.set(parent, (candidates.get(parent) || 0) + 1);
    });
    let best = null, bestCount = 0;
    candidates.forEach((count, parent) => {
      if (count > bestCount) { best = parent; bestCount = count; }
    });
    if (!best || bestCount < 3) return null;
    return best;
  }

  function findActiveSampleTab(tabBar) {
    // The active tab usually has a distinct class or background. We pick the
    // one whose computed background color has the highest saturation or whose
    // class string differs most from the others.
    const btns = Array.from(tabBar.querySelectorAll('button'));
    let activeBtn = null, inactiveBtn = null;
    // Heuristic 1: classnames containing "selected" / "active" / "data-state=active".
    for (const b of btns) {
      const cls = (b.className || '').toString();
      const ds = b.getAttribute('data-state') || '';
      const ariaSel = b.getAttribute('aria-selected') || '';
      if (!activeBtn && (
        /selected|active/i.test(cls) ||
        ds === 'active' || ariaSel === 'true'
      )) { activeBtn = b; }
    }
    // Heuristic 2: if not found, pick the one with the strongest computed bg.
    if (!activeBtn) {
      let bestScore = 0;
      for (const b of btns) {
        const cs = window.getComputedStyle(b);
        const m = (cs.backgroundColor || '').match(/\d+/g);
        if (!m || m.length < 3) continue;
        const r = +m[0], g = +m[1], bl = +m[2];
        const a = m.length >= 4 ? +m[3] : 1;
        const mx = Math.max(r, g, bl), mn = Math.min(r, g, bl);
        const sat = mx === 0 ? 0 : (mx - mn) / mx;
        const score = sat + (a === 1 ? 0 : 0) + (mx > 200 ? 0.2 : 0);
        if (score > bestScore) { bestScore = score; activeBtn = b; }
      }
    }
    inactiveBtn = btns.find(b => b !== activeBtn) || null;
    return { activeBtn, inactiveBtn };
  }

  function snapshotTabClasses(tabBar) {
    const { activeBtn, inactiveBtn } = findActiveSampleTab(tabBar);
    return {
      activeClass:   activeBtn   ? (activeBtn.className   || '') : '',
      inactiveClass: inactiveBtn ? (inactiveBtn.className || '') : '',
      activeStyle:   activeBtn   ? (activeBtn.getAttribute('style')   || '') : '',
      inactiveStyle: inactiveBtn ? (inactiveBtn.getAttribute('style') || '') : '',
      sampleTab: inactiveBtn || activeBtn,
    };
  }

  // ── Panel renderers ────────────────────────────────────────────────
  let currentMountedKey = null;

  function fmtUsd(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function fmtPct(n) {
    if (n === null || n === undefined || isNaN(n)) return '—';
    return Number(n).toFixed(2) + '%';
  }
  function fmtTs(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toISOString().replace('T', ' ').slice(0, 19) + 'Z';
    } catch (_) { return iso; }
  }
  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function pill(value, knownClasses) {
    const v = String(value || '').toLowerCase();
    const cls = (knownClasses && knownClasses.indexOf(v) !== -1) ? v : '';
    return '<span class="fbi-pill ' + cls + '">' + escapeHtml(value || '—') + '</span>';
  }

  // Invoices
  async function renderInvoices(panel) {
    panel.innerHTML = `
      <h2 class="fbi-title">Инвойсы — Immutable Ledger</h2>
      <p class="fbi-subtitle">Read-only выписка из <span class="fbi-key">billing_invoices</span>. Источник истины для всех плат — мутации запрещены, только append через FSM.</p>
      <div class="fbi-toolbar">
        <div class="fbi-toolbar-left">
          <label class="fbi-meta">Статус:</label>
          <select id="fbi-inv-status" class="fbi-select">
            <option value="">все</option>
            <option value="paid">paid</option>
            <option value="pending">pending</option>
            <option value="refunded">refunded</option>
            <option value="failed">failed</option>
          </select>
          <label class="fbi-meta">Лимит:</label>
          <select id="fbi-inv-limit" class="fbi-select">
            <option value="25">25</option>
            <option value="50" selected>50</option>
            <option value="100">100</option>
            <option value="200">200</option>
          </select>
        </div>
        <button class="fbi-btn" id="fbi-inv-refresh">Обновить</button>
      </div>
      <div id="fbi-inv-body" class="fbi-loading">Загружаю инвойсы…</div>
    `;
    const body = panel.querySelector('#fbi-inv-body');
    const statusSel = panel.querySelector('#fbi-inv-status');
    const limitSel = panel.querySelector('#fbi-inv-limit');
    const refreshBtn = panel.querySelector('#fbi-inv-refresh');

    async function load() {
      body.className = 'fbi-loading';
      body.textContent = 'Загружаю инвойсы…';
      try {
        const params = new URLSearchParams();
        params.set('limit', limitSel.value || '50');
        if (statusSel.value) params.set('status', statusSel.value);
        const data = await FomoInject.fetchWithAdminJWT('/api/billing/invoices?' + params.toString());
        const rows = data.rows || [];
        if (!rows.length) {
          body.className = 'fbi-empty';
          body.textContent = 'Инвойсов с такими фильтрами не найдено.';
          return;
        }
        body.className = '';
        body.innerHTML = `
          <table class="fbi-table">
            <thead><tr>
              <th>Invoice ID</th>
              <th>Product</th>
              <th>User</th>
              <th>Status</th>
              <th style="text-align:right">Amount</th>
              <th>Created</th>
            </tr></thead>
            <tbody>
              ${rows.map(r => `
                <tr>
                  <td class="fbi-key">${escapeHtml(r.invoiceId || '')}</td>
                  <td>${escapeHtml(r.productCode || '—')}</td>
                  <td class="fbi-key">${escapeHtml(r.userId || '—')}</td>
                  <td>${pill(r.status, ['paid','pending','refunded','failed'])}</td>
                  <td style="text-align:right">${fmtUsd(r.priceUsd != null ? r.priceUsd : r.amountUsd)}</td>
                  <td class="fbi-meta">${fmtTs(r.createdAt)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div class="fbi-meta" style="margin-top:10px">${rows.length} строк · читаем напрямую из billing_invoices</div>
        `;
      } catch (e) {
        body.className = '';
        body.innerHTML = '<div class="fbi-error">Не удалось загрузить инвойсы: ' + escapeHtml(e.message) + (e.status === 401 ? ' — войдите как админ повторно.' : '') + '</div>';
      }
    }
    statusSel.addEventListener('change', load);
    limitSel.addEventListener('change', load);
    refreshBtn.addEventListener('click', load);
    load();
  }

  // Reconciliation
  async function renderReconciliation(panel) {
    panel.innerHTML = `
      <h2 class="fbi-title">Reconciliation — Findings Stream</h2>
      <p class="fbi-subtitle">Append-only журнал расхождений: stuck pending, entitlement mismatch, orphan audit rows. Атестации не мутируют finding — это отдельный append-event.</p>
      <div class="fbi-toolbar">
        <div class="fbi-toolbar-left">
          <button class="fbi-btn primary" id="fbi-rec-scan">Запустить scan</button>
          <span id="fbi-rec-scan-result" class="fbi-meta"></span>
        </div>
        <button class="fbi-btn" id="fbi-rec-refresh">Обновить</button>
      </div>
      <div class="fbi-section">
        <h3>Сводка</h3>
        <div id="fbi-rec-summary" class="fbi-loading">Загружаю сводку…</div>
      </div>
      <div class="fbi-section">
        <h3>Findings — последние 100</h3>
        <div id="fbi-rec-findings" class="fbi-loading">Загружаю findings…</div>
      </div>
    `;
    const sumEl = panel.querySelector('#fbi-rec-summary');
    const findEl = panel.querySelector('#fbi-rec-findings');
    const scanBtn = panel.querySelector('#fbi-rec-scan');
    const scanResult = panel.querySelector('#fbi-rec-scan-result');
    const refreshBtn = panel.querySelector('#fbi-rec-refresh');

    async function loadSummary() {
      sumEl.className = 'fbi-loading';
      sumEl.textContent = 'Загружаю сводку…';
      try {
        const data = await FomoInject.fetchWithAdminJWT('/api/admin/billing/reconciliation/summary');
        const sev = data.bySeverity || {};
        const st = data.byStatus || {};
        const cat = data.byCategory || {};
        sumEl.className = '';
        sumEl.innerHTML = `
          <div class="fbi-grid">
            <div class="fbi-stat">
              <div class="fbi-stat-label">Total findings</div>
              <div class="fbi-stat-value">${data.totalFindings || 0}</div>
              <div class="fbi-stat-sub">все детекторы</div>
            </div>
            <div class="fbi-stat">
              <div class="fbi-stat-label">Critical / Elevated / Info</div>
              <div class="fbi-stat-value">${sev.critical || 0} · ${sev.elevated || 0} · ${sev.info || 0}</div>
              <div class="fbi-stat-sub">severity raw counts</div>
            </div>
            <div class="fbi-stat">
              <div class="fbi-stat-label">Open / Ack / Resolved-Later</div>
              <div class="fbi-stat-value">${st.open || 0} · ${st.acknowledged || 0} · ${st.resolved_later || 0}</div>
              <div class="fbi-stat-sub">effective status overlay</div>
            </div>
            <div class="fbi-stat">
              <div class="fbi-stat-label">Last Scan</div>
              <div class="fbi-stat-value" style="font-size:13px">${data.lastScan ? fmtTs(data.lastScan.finishedAt) : '—'}</div>
              <div class="fbi-stat-sub">${data.lastScan ? (data.lastScan.scanId || '') : 'ни одного скана'}</div>
            </div>
          </div>
          <div class="fbi-meta" style="margin-top:10px">categories: ${Object.keys(cat).length ? Object.entries(cat).map(([k,v]) => k+'='+v).join(' · ') : '—'}</div>
        `;
      } catch (e) {
        sumEl.className = '';
        sumEl.innerHTML = '<div class="fbi-error">Сводка недоступна: ' + escapeHtml(e.message) + '</div>';
      }
    }

    async function loadFindings() {
      findEl.className = 'fbi-loading';
      findEl.textContent = 'Загружаю findings…';
      try {
        const data = await FomoInject.fetchWithAdminJWT('/api/admin/billing/reconciliation/findings?limit=100');
        const rows = data.rows || [];
        if (!rows.length) {
          findEl.className = 'fbi-empty';
          findEl.textContent = 'Активных findings нет.';
          return;
        }
        findEl.className = '';
        findEl.innerHTML = `
          <table class="fbi-table">
            <thead><tr>
              <th>Finding ID</th>
              <th>Type</th>
              <th>Severity</th>
              <th>Status</th>
              <th>User</th>
              <th>Invoice</th>
              <th>Detected</th>
            </tr></thead>
            <tbody>
              ${rows.map(r => `
                <tr>
                  <td class="fbi-key">${escapeHtml(r.findingId || '')}</td>
                  <td>${escapeHtml(r.findingType || '—')}</td>
                  <td>${pill(r.severity, ['info','elevated','critical'])}</td>
                  <td>${pill(r.status, ['open','acknowledged','resolved_later'])}</td>
                  <td class="fbi-key">${escapeHtml(r.userId || '—')}</td>
                  <td class="fbi-key">${escapeHtml(r.invoiceId || '—')}</td>
                  <td class="fbi-meta">${fmtTs(r.detectedAt)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div class="fbi-meta" style="margin-top:10px">${rows.length} строк · forensic журнал, перезаписи нет</div>
        `;
      } catch (e) {
        findEl.className = '';
        findEl.innerHTML = '<div class="fbi-error">Findings недоступны: ' + escapeHtml(e.message) + '</div>';
      }
    }

    scanBtn.addEventListener('click', async () => {
      scanBtn.disabled = true;
      const orig = scanBtn.textContent;
      scanBtn.textContent = 'Сканирую…';
      scanResult.textContent = '';
      try {
        const data = await FomoInject.fetchWithAdminJWT('/api/admin/billing/reconciliation/scan', { method: 'POST' });
        const scan = data.scan || {};
        scanResult.innerHTML = '<span style="color:#166534">✓ ' + escapeHtml(scan.scanId || '') + ' · ' + (scan.newFindingsCount || 0) + ' new · ' + (scan.durationMs || 0) + 'ms</span>';
        await Promise.all([loadSummary(), loadFindings()]);
      } catch (e) {
        scanResult.innerHTML = '<span style="color:#991b1b">✗ ' + escapeHtml(e.message) + '</span>';
      } finally {
        scanBtn.disabled = false;
        scanBtn.textContent = orig;
      }
    });
    refreshBtn.addEventListener('click', () => { loadSummary(); loadFindings(); });
    loadSummary();
    loadFindings();
  }

  // Analytics
  async function renderAnalytics(panel) {
    panel.innerHTML = `
      <h2 class="fbi-title">Analytics — Derived Read Model</h2>
      <p class="fbi-subtitle">Производное окно из <span class="fbi-key">billing_invoices</span> и <span class="fbi-key">billing_audit</span>. Refunds показываются параллельно gross — никакого тихого неттинга.</p>
      <div class="fbi-toolbar">
        <div class="fbi-toolbar-left">
          <label class="fbi-meta">Окно:</label>
          <select id="fbi-an-window" class="fbi-select">
            <option value="7d">7d</option>
            <option value="30d" selected>30d</option>
            <option value="90d">90d</option>
          </select>
        </div>
        <button class="fbi-btn" id="fbi-an-refresh">Обновить</button>
      </div>
      <div id="fbi-an-body" class="fbi-loading">Считаю окно…</div>
    `;
    const body = panel.querySelector('#fbi-an-body');
    const winSel = panel.querySelector('#fbi-an-window');
    const refresh = panel.querySelector('#fbi-an-refresh');

    async function load() {
      body.className = 'fbi-loading';
      body.textContent = 'Считаю окно…';
      try {
        const data = await FomoInject.fetchWithAdminJWT('/api/admin/billing/analytics/summary?window=' + encodeURIComponent(winSel.value || '30d'));
        const rev = data.revenue || {};
        const mrr = data.mrr || {};
        const conv = data.conversion || {};
        const mix = data.productMix || {};
        const refundRate = data.refundRate || {};
        const churn = data.churn || {};
        // productMix is { <productCode>: { count, grossRevenue, countShare, revShare }, ... }
        // — flatten into table rows, skipping aggregate scalars.
        const mixRows = Object.keys(mix)
          .filter(k => mix[k] && typeof mix[k] === 'object' && 'grossRevenue' in mix[k])
          .map(code => Object.assign({ productCode: code }, mix[code]));
        // refundRate has per-product objects; sum refundedCount + paidCount.
        let rrPaid = 0, rrRefunded = 0;
        Object.keys(refundRate).forEach(k => {
          const v = refundRate[k];
          if (v && typeof v === 'object' && 'paidCount' in v) {
            rrPaid += (v.paidCount || 0);
            rrRefunded += (v.refundedCount || 0);
          }
        });
        body.className = '';
        body.innerHTML = `
          <div class="fbi-section">
            <h3>Revenue · окно ${escapeHtml(data.window || '')} (${data.windowDays || ''}d)</h3>
            <div class="fbi-grid">
              <div class="fbi-stat">
                <div class="fbi-stat-label">Gross</div>
                <div class="fbi-stat-value">${fmtUsd(rev.grossRevenue)}</div>
                <div class="fbi-stat-sub">${rev.grossPaidCount || 0} paid invoices</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Refunded</div>
                <div class="fbi-stat-value">${fmtUsd(rev.refundedRevenue)}</div>
                <div class="fbi-stat-sub">${rev.refundedCount || 0} refund events</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Net</div>
                <div class="fbi-stat-value">${fmtUsd(rev.netRevenue)}</div>
                <div class="fbi-stat-sub">gross − refunded (dual-tracked)</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Refund Rate (overall)</div>
                <div class="fbi-stat-value">${fmtPct(refundRate.overallRefundRatePct)}</div>
                <div class="fbi-stat-sub">${rrRefunded} / ${rrPaid} invoices</div>
              </div>
            </div>
          </div>

          <div class="fbi-section">
            <h3>MRR · Conversion · Churn</h3>
            <div class="fbi-grid">
              <div class="fbi-stat">
                <div class="fbi-stat-label">MRR (approx)</div>
                <div class="fbi-stat-value">${fmtUsd(mrr.mrrApproxUsd)}</div>
                <div class="fbi-stat-sub">trailing ${mrr.trailingWindowDays || 0}d</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Conversion Rate</div>
                <div class="fbi-stat-value">${fmtPct(conv.conversionRatePct)}</div>
                <div class="fbi-stat-sub">${conv.paidCount || 0} paid / ${conv.createdCount || 0} created</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Refund-driven Churn</div>
                <div class="fbi-stat-value">${(churn.refundDriven && churn.refundDriven.total) || 0}</div>
                <div class="fbi-stat-sub">PRO→FREE ${(churn.refundDriven && churn.refundDriven.proToFree) || 0} · TRADER→FREE ${(churn.refundDriven && churn.refundDriven.traderToFree) || 0}</div>
              </div>
              <div class="fbi-stat">
                <div class="fbi-stat-label">Voluntary Downgrades</div>
                <div class="fbi-stat-value">${(churn.voluntary && churn.voluntary.total) || 0}</div>
                <div class="fbi-stat-sub">PRO→FREE ${(churn.voluntary && churn.voluntary.proToFree) || 0} · TRADER→FREE ${(churn.voluntary && churn.voluntary.traderToFree) || 0}</div>
              </div>
            </div>
            <div class="fbi-meta" style="margin-top:10px">failure ${fmtPct(conv.failureRatePct)} · stuck-pending ${fmtPct(conv.stuckRatePct)} (${conv.stuckPendingCount || 0}) · activation ${fmtPct(conv.activationRatePct)}</div>
          </div>

          <div class="fbi-section">
            <h3>Product Mix</h3>
            ${(() => {
              if (!mixRows.length) return '<div class="fbi-empty">Нет данных за окно.</div>';
              return `
                <table class="fbi-table">
                  <thead><tr>
                    <th>Product</th>
                    <th style="text-align:right">Count</th>
                    <th style="text-align:right">Gross</th>
                    <th style="text-align:right">Count Share</th>
                    <th style="text-align:right">Rev Share</th>
                  </tr></thead>
                  <tbody>
                    ${mixRows.map(r => `
                      <tr>
                        <td>${escapeHtml(String(r.productCode || '—').toUpperCase())}</td>
                        <td style="text-align:right">${r.count || 0}</td>
                        <td style="text-align:right">${fmtUsd(r.grossRevenue)}</td>
                        <td style="text-align:right">${fmtPct(r.countShare)}</td>
                        <td style="text-align:right">${fmtPct(r.revShare)}</td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
                <div class="fbi-meta" style="margin-top:10px">total ${mix.totalPaidPlusRefunded || 0} · gross ${fmtUsd(mix.totalGrossRevenue)}</div>
              `;
            })()}
          </div>

          <div class="fbi-section">
            <h3>Refund Rate · per product</h3>
            ${(() => {
              const codes = Object.keys(refundRate).filter(k => refundRate[k] && typeof refundRate[k] === 'object' && 'paidCount' in refundRate[k]);
              if (!codes.length) return '<div class="fbi-empty">Нет данных за окно.</div>';
              return `
                <table class="fbi-table">
                  <thead><tr>
                    <th>Product</th>
                    <th style="text-align:right">Paid</th>
                    <th style="text-align:right">Refunded</th>
                    <th style="text-align:right">Refund Rate</th>
                  </tr></thead>
                  <tbody>
                    ${codes.map(c => {
                      const v = refundRate[c];
                      return `<tr>
                        <td>${escapeHtml(c.toUpperCase())}</td>
                        <td style="text-align:right">${v.paidCount || 0}</td>
                        <td style="text-align:right">${v.refundedCount || 0}</td>
                        <td style="text-align:right">${fmtPct(v.refundRatePct)}</td>
                      </tr>`;
                    }).join('')}
                  </tbody>
                </table>
              `;
            })()}
          </div>

          <div class="fbi-meta">Computed at ${fmtTs(data.computedAt)} · окно ${fmtTs(data.windowStart)} → ${fmtTs(data.windowEnd)}</div>
        `;
      } catch (e) {
        body.className = '';
        body.innerHTML = '<div class="fbi-error">Analytics недоступны: ' + escapeHtml(e.message) + '</div>';
      }
    }
    winSel.addEventListener('change', load);
    refresh.addEventListener('click', load);
    load();
  }

  const RENDERERS = {
    invoices:       renderInvoices,
    reconciliation: renderReconciliation,
    analytics:      renderAnalytics,
  };

  // ── Activation / Teardown ──────────────────────────────────────────
  let snapshot = null; // { activeClass, inactiveClass, activeStyle, inactiveStyle, sampleTab }

  function applyTabStyle(btn, active) {
    if (!snapshot) return;
    if (active) {
      if (snapshot.activeClass)  btn.className = snapshot.activeClass;
      if (snapshot.activeStyle)  btn.setAttribute('style', snapshot.activeStyle);
    } else {
      if (snapshot.inactiveClass)  btn.className = snapshot.inactiveClass;
      if (snapshot.inactiveStyle)  btn.setAttribute('style', snapshot.inactiveStyle);
    }
  }

  function deactivate() {
    currentMountedKey = null;
    FomoInject.destroyMountedPanel(PANEL_ID);
    TABS.forEach(t => {
      const b = document.getElementById(t.id);
      if (b) applyTabStyle(b, false);
    });
  }

  function findNativeContentArea(tabBar) {
    // The native tab strip lives in a container; the content area is the
    // next big sibling block beneath it. We walk up until we find a container
    // whose nextElementSibling is the content card.
    let n = tabBar;
    for (let i = 0; i < 6 && n && n.parentElement; i++) {
      if (n.nextElementSibling && n.nextElementSibling.offsetHeight > 80) return n;
      n = n.parentElement;
    }
    return tabBar;
  }

  async function activate(key, btn, tabBar) {
    // Visually mark all tabs (native + injected): injected = active, others reset.
    // We cannot mutate React tabs' classes (it would re-render them), so we
    // only flip our injected tabs. React's own active state remains, but the
    // native content gets hidden behind our panel, so the user sees what
    // they expect.
    TABS.forEach(t => {
      const b = document.getElementById(t.id);
      if (b) applyTabStyle(b, t.id === btn.id);
    });
    currentMountedKey = key;

    // Tear down any existing injected panel first (in case switching).
    FomoInject.destroyMountedPanel(PANEL_ID);

    const anchor = findNativeContentArea(tabBar);
    const panel = FomoInject.createPanelShell({
      id: PANEL_ID,
      anchorAfter: anchor,
      build: (p) => { p.innerHTML = '<div class="fbi-loading">Подгружаю…</div>'; },
    });

    // Hide the native content sibling while our panel is mounted.
    let sib = anchor.nextElementSibling;
    while (sib) {
      if (sib.id !== PANEL_ID) sib.classList.add('fomo-inject-hidden');
      sib = sib.nextElementSibling;
    }
    // Restore on next native tab click — handled by wireNativeTabTeardown().

    const renderer = RENDERERS[key];
    if (renderer) {
      try { await renderer(panel); }
      catch (e) {
        panel.innerHTML = '<div class="fbi-error">Ошибка рендера: ' + escapeHtml(e.message) + '</div>';
      }
    }
  }

  function wireNativeTabTeardown(tabBar) {
    Array.from(tabBar.children).forEach(child => {
      if (!child || child.tagName !== 'BUTTON') return;
      if (child.id && /^fomo-billing-tab-/.test(child.id)) return;
      if (child.__fomoBillingTeardownWired) return;
      child.__fomoBillingTeardownWired = true;
      child.addEventListener('click', () => {
        // Native tab clicked → tear down injected panel & un-hide native content.
        FomoInject.destroyMountedPanel(PANEL_ID);
        currentMountedKey = null;
        TABS.forEach(t => {
          const b = document.getElementById(t.id);
          if (b) applyTabStyle(b, false);
        });
        // Un-hide native siblings.
        document.querySelectorAll('.fomo-inject-hidden').forEach(n => n.classList.remove('fomo-inject-hidden'));
      }, { capture: true });
    });
  }

  function injectTabs() {
    if (!isBillingRoute()) return false;
    const tabBar = findNativeTabBar();
    if (!tabBar) return false;

    injectCSS();
    snapshot = snapshotTabClasses(tabBar);

    // Filter out injected tabs from snapshot (paranoia in self-healing).
    if (snapshot.sampleTab && snapshot.sampleTab.id && /^fomo-billing-tab-/.test(snapshot.sampleTab.id)) {
      const native = Array.from(tabBar.querySelectorAll('button')).find(b => !b.id || !/^fomo-billing-tab-/.test(b.id));
      if (native) {
        snapshot.sampleTab = native;
        snapshot.inactiveClass = native.className || snapshot.inactiveClass;
        snapshot.inactiveStyle = native.getAttribute('style') || snapshot.inactiveStyle;
      }
    }

    TABS.forEach(t => {
      FomoInject.createSidebarTab({
        tabBar:    tabBar,
        sampleTab: snapshot.sampleTab,
        id:        t.id,
        label:     t.label,
        icon:      t.icon,
        onActivate: (btn) => activate(t.key, btn, tabBar),
      });
    });

    wireNativeTabTeardown(tabBar);
    return true;
  }

  // ── Lifecycle ───────────────────────────────────────────────────────
  let attempts = 0;
  function tick() {
    if (!isBillingRoute()) {
      // Different page — clean up our panel if we left behind.
      FomoInject.destroyMountedPanel(PANEL_ID);
      currentMountedKey = null;
      return;
    }
    if (injectTabs()) return;
    if (++attempts < 80) setTimeout(tick, 350);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }

  // SPA-aware: re-attempt on path change and heal if React wipes our tabs.
  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      attempts = 0;
      // Tear down panel if we navigated away
      if (!isBillingRoute()) {
        FomoInject.destroyMountedPanel(PANEL_ID);
        currentMountedKey = null;
      }
      setTimeout(tick, 350);
    }
    if (!isBillingRoute()) return;
    const tabBar = findNativeTabBar();
    if (!tabBar) return;
    // Heal: if any of our tabs got removed, re-inject.
    const missing = TABS.some(t => !document.getElementById(t.id));
    if (missing) {
      attempts = 0;
      injectTabs();
    } else {
      // Make sure teardown wiring is still in place if React re-rendered.
      wireNativeTabTeardown(tabBar);
    }
  }, 700);
})();
