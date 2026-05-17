/**
 * attribution-inject.js — T11 Epistemic Observatory (Forensic Surface)
 *
 * Adds a single sidebar nav entry «Атрибуция» to the FOMO Intelligence
 * Terminal admin shell. Activation mounts a read-only forensic
 * observatory panel inside <main>, hiding native React content beneath.
 *
 * Architectural invariants (locked by user — DO NOT VIOLATE):
 *   1. NO mutation semantics — every API consumed is GET, append-only.
 *   2. NO "winner-picking" framing — positive pnl rendered with the same
 *      muted neutral palette as negative pnl. No green/gold celebration.
 *   3. NO trading CTAs — forbidden wording: execute, retry, enable,
 *      loosen gate, recommended, optimal, alpha, edge.
 *   4. Canonical layer order frozen: RAW → CALIBRATED → SIZED → GATED.
 *      No sortable headers. No reordering.
 *   5. pipelineVersion always visible — calm, persistent, not chrome.
 *   6. Mixed lineage honesty — if raw layer not yet supported, surface
 *      the "raw lineage accumulation in progress" note, do not hide it.
 *   7. Lost Opportunity framed STRICTLY as risk containment observation,
 *      never as "missed gains" / "could have earned".
 *   8. Reuses canonical injection primitives from window.__fomoAdminInject
 *      (created by billing-inject.js). Does NOT redefine helpers.
 *   9. No second router. No SPA-inside-SPA. Mounts/teardowns DOM only.
 *  10. No state framework. No store. Each render is a fresh fetch.
 */
(function () {
  'use strict';

  if (window.__fomoAttributionInjectLoaded) return;
  window.__fomoAttributionInjectLoaded = true;

  // Reuse canonical primitives. Wait until they exist (billing-inject
  // creates them on the same page). If absent, install minimal fallbacks
  // so this inject still works in isolation.
  const FomoInject = (window.__fomoAdminInject = window.__fomoAdminInject || {});
  if (!FomoInject.getAdminToken) {
    FomoInject.getAdminToken = function () {
      try {
        const v = localStorage.getItem('admin_token');
        if (v) return v.replace(/^"|"$/g, '');
      } catch (_) {}
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
      if (!res.ok) {
        const err = new Error(res.status + ' ' + res.statusText);
        err.status = res.status; err.body = body;
        throw err;
      }
      return body;
    };
  }
  if (!FomoInject.destroyMountedPanel) {
    FomoInject.destroyMountedPanel = function (id) {
      const p = document.getElementById(id);
      if (p && p.parentElement) p.parentElement.removeChild(p);
    };
  }

  // ── IDs / Constants ────────────────────────────────────────────────
  const NAV_ID    = 'fomo-attribution-nav';
  const PANEL_ID  = 'fomo-attribution-panel';
  const CSS_ID    = 'fomo-attribution-css';
  const HIDE_CLS  = 'fomo-attribution-native-hidden';

  // Sub-tabs inside attribution panel
  const SUBTABS = [
    { key: 'observatory',    label: 'Observatory'      },
    { key: 'drilldowns',     label: 'Drilldowns'       },
    { key: 'lostOpportunity',label: 'Lost Opportunity' },
  ];

  // Sidebar nav labels — used as anchor points + teardown wiring set.
  // We append «Атрибуция» right after «Billing» if present, otherwise
  // before «Referrals».
  const ANCHOR_LABELS_AFTER = ['Billing'];
  const ANCHOR_LABELS_BEFORE = ['Referrals', 'Intel System'];

  // ── CSS ────────────────────────────────────────────────────────────
  function injectCSS() {
    if (document.getElementById(CSS_ID)) return;
    const s = document.createElement('style');
    s.id = CSS_ID;
    s.textContent = `
.${HIDE_CLS}{display:none !important}
#${PANEL_ID}{
  padding:24px 28px 48px;background:#f8fafc;min-height:calc(100vh - 3rem);
  color:#0f172a;font-size:13px;line-height:1.55;
}
#${PANEL_ID} *{box-sizing:border-box}
#${PANEL_ID} .fai-header{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:6px;flex-wrap:wrap}
#${PANEL_ID} .fai-title{font-size:22px;font-weight:700;letter-spacing:-0.01em;color:#0f172a;margin:0;display:flex;align-items:center;gap:10px}
#${PANEL_ID} .fai-title::before{content:"";width:3px;height:18px;background:#475569;display:inline-block;border-radius:2px}
#${PANEL_ID} .fai-subtitle{font-size:12px;color:#64748b;margin:4px 0 0;max-width:780px;line-height:1.55}
#${PANEL_ID} .fai-pipeline-chip{
  display:inline-flex;align-items:center;gap:6px;padding:6px 10px;
  background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;
  font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:11px;color:#334155;
}
#${PANEL_ID} .fai-pipeline-chip::before{content:"⊞";color:#94a3b8;font-family:inherit}
#${PANEL_ID} .fai-disclaimer{
  margin-top:14px;padding:10px 14px;background:#f1f5f9;border-left:3px solid #94a3b8;
  border-radius:6px;font-size:11.5px;color:#475569;line-height:1.55;
}
#${PANEL_ID} .fai-tabbar{
  margin-top:22px;display:flex;gap:2px;border-bottom:1px solid #e2e8f0;
}
#${PANEL_ID} .fai-tabbar button{
  background:transparent;border:none;cursor:pointer;
  padding:10px 16px;margin-bottom:-1px;font-size:12.5px;font-weight:600;
  letter-spacing:0.02em;color:#64748b;border-bottom:2px solid transparent;
  transition:color .12s,border-color .12s;
}
#${PANEL_ID} .fai-tabbar button:hover{color:#334155}
#${PANEL_ID} .fai-tabbar button.on{color:#0f172a;border-bottom-color:#475569}
#${PANEL_ID} .fai-body{margin-top:18px}
#${PANEL_ID} h3{font-size:10.5px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#475569;margin:0 0 12px;display:flex;align-items:center;gap:10px}
#${PANEL_ID} h3::before{content:"";width:14px;height:1px;background:#94a3b8;display:inline-block}
#${PANEL_ID} .fai-card{padding:18px 20px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;margin-bottom:14px}
#${PANEL_ID} .fai-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
#${PANEL_ID} .fai-stat{padding:14px 16px;background:#f8fafc;border:1px solid #e5e7eb;border-radius:10px}
#${PANEL_ID} .fai-stat-label{font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px}
#${PANEL_ID} .fai-stat-value{font-size:20px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums}
#${PANEL_ID} .fai-stat-sub{font-size:11px;color:#64748b;margin-top:4px;line-height:1.45}
#${PANEL_ID} .fai-stat.neutral .fai-stat-value{color:#0f172a}
#${PANEL_ID} .fai-stat.muted .fai-stat-value{color:#475569}
#${PANEL_ID} .fai-layers{display:grid;grid-template-columns:repeat(4,1fr);gap:0;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden}
#${PANEL_ID} .fai-layer{padding:18px 20px;border-right:1px solid #e5e7eb}
#${PANEL_ID} .fai-layer:last-child{border-right:none}
#${PANEL_ID} .fai-layer-head{font-size:10px;font-weight:800;letter-spacing:0.14em;color:#94a3b8;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:6px}
#${PANEL_ID} .fai-layer-head .fai-layer-idx{display:inline-block;width:18px;height:18px;line-height:18px;text-align:center;background:#e2e8f0;color:#475569;border-radius:4px;font-size:9px;font-weight:800}
#${PANEL_ID} .fai-layer-row{display:flex;justify-content:space-between;padding:5px 0;font-size:12px;color:#334155}
#${PANEL_ID} .fai-layer-row .fai-k{color:#64748b;font-size:11px}
#${PANEL_ID} .fai-layer-row .fai-v{font-variant-numeric:tabular-nums;color:#0f172a;font-weight:600}
#${PANEL_ID} table.fai-table{width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden;font-size:12px}
#${PANEL_ID} .fai-table th{text-align:left;padding:10px 14px;font-size:10px;letter-spacing:0.12em;text-transform:uppercase;color:#64748b;background:#f8fafc;border-bottom:1px solid #e5e7eb;font-weight:700}
#${PANEL_ID} .fai-table td{padding:10px 14px;border-bottom:1px solid #f1f5f9;color:#0f172a;font-variant-numeric:tabular-nums;vertical-align:top}
#${PANEL_ID} .fai-table tr:last-child td{border-bottom:none}
#${PANEL_ID} .fai-table tr:hover td{background:#f8fafc}
#${PANEL_ID} .fai-meta{font-size:11px;color:#94a3b8;font-variant-numeric:tabular-nums;font-family:'JetBrains Mono',ui-monospace,monospace}
#${PANEL_ID} .fai-empty{padding:32px 16px;text-align:center;color:#64748b;font-size:13px}
#${PANEL_ID} .fai-loading{padding:24px;text-align:center;color:#94a3b8;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;font-weight:700}
#${PANEL_ID} .fai-error{padding:14px 16px;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;color:#991b1b;font-size:13px;margin-bottom:14px}
#${PANEL_ID} .fai-toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap}
#${PANEL_ID} .fai-select{padding:6px 10px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;font-size:12px;color:#0f172a}
#${PANEL_ID} .fai-btn{padding:6px 12px;border:1px solid #e5e7eb;border-radius:8px;background:#ffffff;font-size:12px;font-weight:600;color:#0f172a;cursor:pointer;transition:background .12s,border-color .12s}
#${PANEL_ID} .fai-btn:hover{background:#f8fafc;border-color:#cbd5e1}
#${PANEL_ID} .fai-key{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:11px;color:#334155}
#${PANEL_ID} .fai-collapse{border:1px solid #e5e7eb;border-radius:10px;background:#ffffff;margin-bottom:10px;overflow:hidden}
#${PANEL_ID} .fai-collapse-head{padding:12px 16px;background:#f8fafc;cursor:pointer;display:flex;align-items:center;justify-content:space-between;font-size:12.5px;font-weight:600;color:#0f172a;user-select:none;transition:background .12s}
#${PANEL_ID} .fai-collapse-head:hover{background:#f1f5f9}
#${PANEL_ID} .fai-collapse-head .fai-collapse-sub{font-size:11px;color:#64748b;font-weight:500}
#${PANEL_ID} .fai-collapse-arrow{font-size:10px;color:#94a3b8;transition:transform .15s;display:inline-block;margin-left:8px}
#${PANEL_ID} .fai-collapse.open .fai-collapse-arrow{transform:rotate(90deg)}
#${PANEL_ID} .fai-collapse-body{display:none;padding:16px;border-top:1px solid #f1f5f9}
#${PANEL_ID} .fai-collapse.open .fai-collapse-body{display:block}
#${PANEL_ID} .fai-banner{padding:10px 14px;background:#fffbeb;border:1px solid #fde68a;border-radius:8px;color:#78350f;font-size:11.5px;line-height:1.5;margin-bottom:14px}
#${PANEL_ID} .fai-banner.calm{background:#f1f5f9;border-color:#e2e8f0;color:#475569}
#${PANEL_ID} .fai-bar{height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-top:6px}
#${PANEL_ID} .fai-bar-fill{height:100%;background:#94a3b8;border-radius:3px}
#${PANEL_ID} .fai-pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;background:#e2e8f0;color:#334155}
#${PANEL_ID} .fai-pill.allowed{background:#e2e8f0;color:#475569}
#${PANEL_ID} .fai-pill.blocked{background:#f1f5f9;color:#475569}
`;
    document.head.appendChild(s);
  }

  // ── Formatters ─────────────────────────────────────────────────────
  const fmt = {
    int: (n) => (n == null || isNaN(n) ? '—' : Number(n).toLocaleString('en-US')),
    pct: (n) => (n == null || isNaN(n) ? '—' : Number(n).toFixed(2) + '%'),
    usd: (n) => (n == null || isNaN(n) ? '—' : '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })),
    num: (n, d) => (n == null || isNaN(n) ? '—' : Number(n).toFixed(d == null ? 3 : d)),
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
  };

  // ── Sidebar nav injection ──────────────────────────────────────────
  function findSidebar() {
    return document.querySelector('aside[data-testid="admin-sidebar"]')
      || document.querySelector('aside.admin-sidebar')
      || document.querySelector('aside');
  }

  function findMainArea() {
    return document.querySelector('main')
      || document.querySelector('[data-testid="platform-admin-layout"] main')
      || null;
  }

  // Find a native sidebar nav item by label (textContent contains).
  function findSidebarItemByLabel(sidebar, label) {
    const candidates = sidebar.querySelectorAll('a, button');
    for (const el of candidates) {
      const t = (el.textContent || '').trim();
      // exact-ish match (label may be wrapped in a span)
      if (t === label || t.startsWith(label + ' ') || t.endsWith(' ' + label) || t.indexOf(label) === 0) {
        // sanity: must look like a nav item (has icon+text, not a header)
        if (el.children.length <= 4 && el.offsetHeight < 60) return el;
      }
    }
    return null;
  }

  // Take a snapshot of a representative inactive sidebar nav item for
  // visual cloning (we won't mutate its class, just copy at injection time).
  function snapshotInactiveNavSample(sidebar) {
    // Prefer a top-level nav <a> like "Billing", "Referrals" — they sit at
    // level 0 and look uniform.
    const samples = ['Billing', 'Referrals', 'Intel System', 'News', 'Signals'];
    for (const label of samples) {
      const el = findSidebarItemByLabel(sidebar, label);
      if (el && el.tagName === 'A') return el;
    }
    // fallback: any anchor that has 'flex items-center gap-2'
    return sidebar.querySelector('a[class*="flex"][class*="items-center"]') || null;
  }

  function applyNavActiveStyles(navEl, active) {
    if (active) {
      navEl.style.background = '#eef2ff';
      navEl.style.color = '#3730a3';
      navEl.style.borderLeft = '2px solid #6366f1';
      navEl.style.paddingLeft = '10px'; // compensate for the 2px border
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
    nav.setAttribute('data-testid', 'admin-nav-attribution');
    // Clone classes from sample so visually it sits inside the same column.
    if (sample.className) nav.className = sample.className;
    // Remove "selected" / "active" markers if the sample happens to be active.
    nav.className = (nav.className || '').replace(/bg-indigo-50|text-indigo-700|border-l-2|border-indigo-600/g, '').trim();

    // Build inner content: small icon + label, matching native pattern.
    // The icon is a simple ledger glyph in muted gray.
    nav.innerHTML =
      '<svg class="w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M3 6.5C3 5.12 4.12 4 5.5 4H18a3 3 0 0 1 3 3v11a2 2 0 0 1-2 2H6a3 3 0 0 1-3-3V6.5Z"/>' +
      '<path d="M7 9h8M7 12h8M7 15h5"/>' +
      '<path d="M3 17a3 3 0 0 0 3 3"/>' +
      '</svg>' +
      '<span class="flex-1 truncate">Атрибуция</span>';

    // Insert position: after Billing if present, else before Referrals.
    let inserted = false;
    for (const label of ANCHOR_LABELS_AFTER) {
      const target = findSidebarItemByLabel(sidebar, label);
      if (target && target.parentElement) {
        target.parentElement.insertBefore(nav, target.nextElementSibling);
        inserted = true;
        break;
      }
    }
    if (!inserted) {
      for (const label of ANCHOR_LABELS_BEFORE) {
        const target = findSidebarItemByLabel(sidebar, label);
        if (target && target.parentElement) {
          target.parentElement.insertBefore(nav, target);
          inserted = true;
          break;
        }
      }
    }
    if (!inserted) {
      sample.parentElement.appendChild(nav);
    }

    nav.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      activate();
    });

    return nav;
  }

  // ── Panel mount / teardown ─────────────────────────────────────────
  let currentSubtab = 'observatory';
  let currentWindow = '30d';
  let cachedPipelineVersion = null;

  function teardownPanel() {
    FomoInject.destroyMountedPanel(PANEL_ID);
    // Un-hide any native main children we hid.
    document.querySelectorAll('.' + HIDE_CLS).forEach(n => n.classList.remove(HIDE_CLS));
    const nav = document.getElementById(NAV_ID);
    if (nav) applyNavActiveStyles(nav, false);
  }

  function wireSidebarTeardown(sidebar) {
    Array.from(sidebar.querySelectorAll('a, button')).forEach(item => {
      if (item.id === NAV_ID) return;
      if (item.__fomoAttrTeardownWired) return;
      item.__fomoAttrTeardownWired = true;
      item.addEventListener('click', () => {
        teardownPanel();
      }, { capture: true });
    });
  }

  function mountPanel() {
    const main = findMainArea();
    if (!main) return null;
    // Hide all direct children of <main>.
    Array.from(main.children).forEach(c => {
      if (c.id === PANEL_ID) return;
      c.classList.add(HIDE_CLS);
    });
    let panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement('div');
      panel.id = PANEL_ID;
      panel.setAttribute('data-testid', 'fomo-attribution-panel');
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
    panel.innerHTML = '<div class="fai-loading">Поднимаю forensic-наблюдатель…</div>';
    await render(panel);
  }

  // ── Renderers ──────────────────────────────────────────────────────
  async function render(panel) {
    // First fetch summary so we can lock pipelineVersion + dataAvailability
    // banners at the top regardless of which subtab is active.
    let summary = null;
    try {
      summary = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/summary?window=' + encodeURIComponent(currentWindow));
      cachedPipelineVersion = summary.pipelineVersion || cachedPipelineVersion;
    } catch (e) {
      panel.innerHTML = '<div class="fai-error">Observatory недоступен: ' + fmt.h(e.message) + (e.status === 401 ? ' — переавторизуйтесь как админ.' : '') + '</div>';
      return;
    }

    panel.innerHTML = `
      <div class="fai-header">
        <div>
          <h1 class="fai-title">Атрибуция</h1>
          <p class="fai-subtitle">Эпистемическая обсерватория T11 — read-only продольный срез решений по слоям конвейера. Нет переписи истории, нет рекомендаций, нет execution-вызовов.</p>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px">
          <span class="fai-pipeline-chip" id="fai-pipeline">${fmt.h(cachedPipelineVersion || '—')}</span>
          <div style="display:flex;gap:6px;align-items:center">
            <label class="fai-meta">Окно:</label>
            <select id="fai-window" class="fai-select">
              <option value="7d"  ${currentWindow === '7d'  ? 'selected' : ''}>7d</option>
              <option value="30d" ${currentWindow === '30d' ? 'selected' : ''}>30d</option>
              <option value="90d" ${currentWindow === '90d' ? 'selected' : ''}>90d</option>
              <option value="all" ${currentWindow === 'all' ? 'selected' : ''}>all</option>
            </select>
            <button class="fai-btn" id="fai-refresh">Обновить</button>
          </div>
        </div>
      </div>
      <div class="fai-disclaimer">
        Наблюдательный слой. Каждая цифра — апостериорная фотография уже закрытых решений. Положительный pnl не зелёный, отрицательный не красный — это не оценочные суждения, а forensic-сводка. Capital preservation (заблокированные сделки) рассматривается отдельно от «упущенной выгоды» — это не одно и то же.
      </div>
      ${renderDataAvailabilityBanner(summary.dataAvailability)}
      <div class="fai-tabbar">
        ${SUBTABS.map(t => `<button data-fai-subtab="${t.key}" class="${t.key === currentSubtab ? 'on' : ''}">${fmt.h(t.label)}</button>`).join('')}
      </div>
      <div class="fai-body" id="fai-body"><div class="fai-loading">Загружаю…</div></div>
    `;

    panel.querySelector('#fai-window').addEventListener('change', (e) => {
      currentWindow = e.target.value;
      render(panel);
    });
    panel.querySelector('#fai-refresh').addEventListener('click', () => render(panel));
    panel.querySelectorAll('[data-fai-subtab]').forEach(btn => {
      btn.addEventListener('click', () => {
        currentSubtab = btn.getAttribute('data-fai-subtab');
        panel.querySelectorAll('[data-fai-subtab]').forEach(b => b.classList.toggle('on', b === btn));
        renderBody(panel, summary);
      });
    });

    await renderBody(panel, summary);
  }

  function renderDataAvailabilityBanner(da) {
    if (!da) return '';
    if (da.rawLayerSupported) {
      return `<div class="fai-banner calm">Raw lineage: ${fmt.int(da.rawSamples)} образцов в окне · gate-decisions: ${fmt.int(da.gateDecisionsInWindow)} · outcomes: ${fmt.int(da.outcomesInWindow)}.</div>`;
    }
    return `<div class="fai-banner">Raw lineage accumulation in progress — pre-T11.1 outcomes не содержат rawVerdictSnapshot. Атрибуция накапливается forward-only по мере новых сделок, ретроактивный пересчёт не выполняется.<br/><span class="fai-meta">${fmt.h(da.note || '')}</span></div>`;
  }

  async function renderBody(panel, summary) {
    const body = panel.querySelector('#fai-body');
    body.innerHTML = '<div class="fai-loading">Загружаю…</div>';
    try {
      if (currentSubtab === 'observatory')      return await renderObservatory(body, summary);
      if (currentSubtab === 'drilldowns')       return await renderDrilldowns(body);
      if (currentSubtab === 'lostOpportunity')  return await renderLostOpportunity(body);
    } catch (e) {
      body.innerHTML = '<div class="fai-error">Сбой подзагрузки: ' + fmt.h(e.message) + '</div>';
    }
  }

  // ── Observatory ────────────────────────────────────────────────────
  function layerCard(idx, key, label, layer) {
    layer = layer || {};
    return `
      <div class="fai-layer">
        <div class="fai-layer-head"><span class="fai-layer-idx">${idx}</span>${fmt.h(label)}</div>
        <div class="fai-layer-row"><span class="fai-k">Trades</span><span class="fai-v">${fmt.int(layer.tradeCount)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Wins / Losses</span><span class="fai-v">${fmt.int(layer.winCount)} / ${fmt.int(layer.lossCount)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Hit rate</span><span class="fai-v">${fmt.pct(layer.hitRatePct)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Mean return</span><span class="fai-v">${fmt.pct(layer.meanReturnPct)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Cumulative pnl</span><span class="fai-v">${fmt.usd(layer.cumulativePnlUsd)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Max drawdown</span><span class="fai-v">${fmt.pct(layer.maxDrawdownPct)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Sharpe-like</span><span class="fai-v">${fmt.num(layer.sharpeLike)}</span></div>
        <div class="fai-layer-row"><span class="fai-k">Bars held</span><span class="fai-v">${fmt.num(layer.meanBarsHeld, 1)}</span></div>
      </div>
    `;
  }

  async function renderObservatory(body, summary) {
    const layers = summary.layers || {};
    const gb = summary.gateBlocks || {};
    const cp = gb.capitalPreservation || {};
    body.innerHTML = `
      <section class="fai-card" style="margin-bottom:16px;background:transparent;border:none;padding:0">
        <h3>Слои конвейера · канонический порядок</h3>
        <div class="fai-layers">
          ${layerCard(1, 'raw',        'Raw',        layers.raw)}
          ${layerCard(2, 'calibrated', 'Calibrated', layers.calibrated)}
          ${layerCard(3, 'sized',      'Sized',      layers.sized)}
          ${layerCard(4, 'gated',      'Gated',      layers.gated)}
        </div>
        <div class="fai-meta" style="margin-top:8px">Порядок зафиксирован контрактом T11. Сортировки нет — слои не сравниваются как «лучше/хуже».</div>
      </section>

      <section style="margin-top:18px">
        <h3>Capital preservation · gate observation</h3>
        <div class="fai-card">
          <div class="fai-grid">
            <div class="fai-stat muted">
              <div class="fai-stat-label">Decisions observed</div>
              <div class="fai-stat-value">${fmt.int(gb.totalDecisionsObserved)}</div>
              <div class="fai-stat-sub">всего gate-решений в окне</div>
            </div>
            <div class="fai-stat muted">
              <div class="fai-stat-label">Allowed</div>
              <div class="fai-stat-value">${fmt.int(gb.allowed)}</div>
              <div class="fai-stat-sub">прошли gate</div>
            </div>
            <div class="fai-stat muted">
              <div class="fai-stat-label">Blocked</div>
              <div class="fai-stat-value">${fmt.int(gb.blocked)}</div>
              <div class="fai-stat-sub">contained by gate</div>
            </div>
            <div class="fai-stat muted">
              <div class="fai-stat-label">Prevented notional</div>
              <div class="fai-stat-value">${fmt.usd(cp.preventedNotionalUsd)}</div>
              <div class="fai-stat-sub">capital, не отправленный в риск</div>
            </div>
          </div>
          ${cp.byRule ? `
            <div style="margin-top:14px">
              <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-bottom:8px">By rule</div>
              <table class="fai-table">
                <thead><tr>
                  <th>Rule</th><th style="text-align:right">Blocked</th>
                </tr></thead>
                <tbody>
                  ${Object.entries(cp.byRule).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`
                    <tr><td class="fai-key">${fmt.h(k)}</td><td style="text-align:right">${fmt.int(v)}</td></tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          ` : ''}
          <div class="fai-meta" style="margin-top:12px">${fmt.h(cp.framingNote || 'Capital preservation is not winner-picking.')}</div>
        </div>
      </section>

      <section style="margin-top:18px">
        <h3>Δ Layer transitions</h3>
        <div class="fai-card">
          ${renderDeltaRow('Calibrated vs Raw', summary.deltas && summary.deltas.calibratedVsRaw)}
          ${renderDeltaRow('Sized vs Calibrated', summary.deltas && summary.deltas.sizedVsCalibrated)}
          ${renderDeltaRow('Gated vs Sized', summary.deltas && summary.deltas.gatedVsSized)}
          <div class="fai-meta" style="margin-top:8px">Дельта — это перенос ущерба/польза между слоями. Положительные/отрицательные значения окрашены одинаково — мы наблюдаем, не оцениваем.</div>
        </div>
      </section>

      <div class="fai-meta" style="margin-top:18px">Computed at ${fmt.ts(summary.computedAt)} · окно ${fmt.ts(summary.windowStart)} → ${fmt.ts(summary.windowEnd)}</div>
    `;
  }

  function renderDeltaRow(label, d) {
    if (d == null) {
      return `<div class="fai-layer-row"><span class="fai-k">${fmt.h(label)}</span><span class="fai-v">— ещё нет двух заполненных слоёв</span></div>`;
    }
    // Try common shapes: { meanReturnPctDelta, cumulativePnlUsdDelta, ... }
    const parts = [];
    if (d.hitRatePctDelta != null) parts.push('hit Δ ' + (d.hitRatePctDelta > 0 ? '+' : '') + fmt.num(d.hitRatePctDelta, 2) + 'pp');
    if (d.meanReturnPctDelta != null) parts.push('mean Δ ' + (d.meanReturnPctDelta > 0 ? '+' : '') + fmt.pct(d.meanReturnPctDelta));
    if (d.cumulativePnlUsdDelta != null) parts.push('pnl Δ ' + (d.cumulativePnlUsdDelta >= 0 ? '+' : '') + fmt.usd(Math.abs(d.cumulativePnlUsdDelta)));
    if (!parts.length) parts.push(JSON.stringify(d));
    return `<div class="fai-layer-row"><span class="fai-k">${fmt.h(label)}</span><span class="fai-v">${parts.join(' · ')}</span></div>`;
  }

  // ── Drilldowns (collapsed by default) ──────────────────────────────
  async function renderDrilldowns(body) {
    body.innerHTML = `
      <div class="fai-collapse" data-section="assets">
        <div class="fai-collapse-head">
          <span>Per-asset slice <span class="fai-collapse-sub">/attribution/assets</span></span>
          <span class="fai-collapse-arrow">▶</span>
        </div>
        <div class="fai-collapse-body"><div class="fai-loading">Загрузка по запросу…</div></div>
      </div>
      <div class="fai-collapse" data-section="gateRule">
        <div class="fai-collapse-head">
          <span>Gate-rule breakdown <span class="fai-collapse-sub">/attribution/gate-rule-breakdown</span></span>
          <span class="fai-collapse-arrow">▶</span>
        </div>
        <div class="fai-collapse-body"><div class="fai-loading">Загрузка по запросу…</div></div>
      </div>
      <div class="fai-collapse" data-section="confidence">
        <div class="fai-collapse-head">
          <span>Confidence distribution <span class="fai-collapse-sub">/attribution/confidence-distribution</span></span>
          <span class="fai-collapse-arrow">▶</span>
        </div>
        <div class="fai-collapse-body"><div class="fai-loading">Загрузка по запросу…</div></div>
      </div>
      <div class="fai-collapse" data-section="exposure">
        <div class="fai-collapse-head">
          <span>Exposure histograms <span class="fai-collapse-sub">/attribution/exposure-histograms</span></span>
          <span class="fai-collapse-arrow">▶</span>
        </div>
        <div class="fai-collapse-body"><div class="fai-loading">Загрузка по запросу…</div></div>
      </div>
      <div class="fai-meta" style="margin-top:14px">Drilldowns свёрнуты по умолчанию — это медленный forensic-режим, не дашборд.</div>
    `;

    body.querySelectorAll('.fai-collapse').forEach(box => {
      const head = box.querySelector('.fai-collapse-head');
      const bodyEl = box.querySelector('.fai-collapse-body');
      const section = box.getAttribute('data-section');
      head.addEventListener('click', async () => {
        const wasOpen = box.classList.contains('open');
        box.classList.toggle('open');
        if (wasOpen) return;
        if (bodyEl.dataset.loaded === '1') return;
        try {
          if (section === 'assets')      await loadAssets(bodyEl);
          else if (section === 'gateRule')  await loadGateRule(bodyEl);
          else if (section === 'confidence')await loadConfidence(bodyEl);
          else if (section === 'exposure')  await loadExposure(bodyEl);
          bodyEl.dataset.loaded = '1';
        } catch (e) {
          bodyEl.innerHTML = '<div class="fai-error">' + fmt.h(e.message) + '</div>';
        }
      });
    });
  }

  async function loadAssets(host) {
    const data = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/assets?window=' + encodeURIComponent(currentWindow));
    const rows = data.rows || [];
    if (!rows.length) { host.innerHTML = '<div class="fai-empty">Нет ассетов в окне.</div>'; return; }
    host.innerHTML = `
      <table class="fai-table">
        <thead><tr>
          <th>Symbol</th>
          <th style="text-align:right">Trades</th>
          <th style="text-align:right">Hit rate</th>
          <th style="text-align:right">Mean return</th>
          <th style="text-align:right">Cum pnl</th>
          <th style="text-align:right">Gate blocks</th>
          <th style="text-align:right">Prevented</th>
        </tr></thead>
        <tbody>
          ${rows.map(r => {
            const o = r.outcomes || {};
            const g = r.gateBlocks || {};
            return `<tr>
              <td class="fai-key">${fmt.h(r.symbol || '—')}</td>
              <td style="text-align:right">${fmt.int(o.tradeCount)}</td>
              <td style="text-align:right">${fmt.pct(o.hitRatePct)}</td>
              <td style="text-align:right">${fmt.pct(o.meanReturnPct)}</td>
              <td style="text-align:right">${fmt.usd(o.cumulativePnlUsd)}</td>
              <td style="text-align:right">${fmt.int(g.blockedCount)}</td>
              <td style="text-align:right">${fmt.usd(g.preventedNotionalUsd)}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      <div class="fai-meta" style="margin-top:8px">${rows.length} ассетов · per-asset slice</div>
    `;
  }

  async function loadGateRule(host) {
    const data = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/gate-rule-breakdown?window=' + encodeURIComponent(currentWindow));
    const rules = data.rules || [];
    if (!rules.length) { host.innerHTML = '<div class="fai-empty">Нет gate-блокировок в окне.</div>'; return; }
    const maxCount = Math.max.apply(null, rules.map(r => r.count || 0).concat([1]));
    host.innerHTML = `
      <table class="fai-table">
        <thead><tr>
          <th>Rule</th>
          <th style="text-align:right">Blocks</th>
          <th style="text-align:right">Prevented notional</th>
          <th>Distribution</th>
          <th>Top symbols</th>
        </tr></thead>
        <tbody>
          ${rules.map(r => `
            <tr>
              <td class="fai-key">${fmt.h(r.rule || '—')}</td>
              <td style="text-align:right">${fmt.int(r.count)}</td>
              <td style="text-align:right">${fmt.usd(r.preventedNotionalUsd)}</td>
              <td><div class="fai-bar"><div class="fai-bar-fill" style="width:${Math.round((r.count || 0) / maxCount * 100)}%"></div></div></td>
              <td>${(r.topSymbols || []).slice(0, 3).map(s => '<span class="fai-pill">' + fmt.h(s.symbol) + ' · ' + fmt.int(s.count) + '</span>').join(' ')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div class="fai-meta" style="margin-top:8px">${rules.length} правил · totalBlocks ${fmt.int(data.totalBlocks)}</div>
    `;
  }

  async function loadConfidence(host) {
    const data = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/confidence-distribution?window=' + encodeURIComponent(currentWindow));
    const buckets = data.buckets || [];
    if (!buckets.length) { host.innerHTML = '<div class="fai-empty">Нет outcomes в окне.</div>'; return; }
    host.innerHTML = `
      <table class="fai-table">
        <thead><tr>
          <th>Confidence bucket</th>
          <th style="text-align:right">Trades</th>
          <th style="text-align:right">Hit rate</th>
          <th style="text-align:right">Mean return</th>
          <th style="text-align:right">Cum pnl</th>
          <th style="text-align:right">Share</th>
        </tr></thead>
        <tbody>
          ${buckets.map(b => `
            <tr>
              <td class="fai-key">${fmt.h(b.bucket || '—')}</td>
              <td style="text-align:right">${fmt.int(b.tradeCount)}</td>
              <td style="text-align:right">${fmt.pct(b.hitRatePct)}</td>
              <td style="text-align:right">${fmt.pct(b.meanReturnPct)}</td>
              <td style="text-align:right">${fmt.usd(b.cumulativePnlUsd)}</td>
              <td style="text-align:right">${fmt.pct(b.sharePct)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div class="fai-meta" style="margin-top:8px">${buckets.length} buckets · totalOutcomes ${fmt.int(data.totalOutcomes)}</div>
    `;
  }

  async function loadExposure(host) {
    const data = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/exposure-histograms?window=' + encodeURIComponent(currentWindow));
    const bands = data.bands || [];
    if (!bands.length) { host.innerHTML = '<div class="fai-empty">Нет данных по экспозиции в окне.</div>'; return; }
    host.innerHTML = `
      <table class="fai-table">
        <thead><tr>
          <th>Band (USD)</th>
          <th style="text-align:right">Trades</th>
          <th style="text-align:right">Hit rate</th>
          <th style="text-align:right">Mean return</th>
          <th style="text-align:right">Cum pnl</th>
          <th style="text-align:right">Mean size</th>
        </tr></thead>
        <tbody>
          ${bands.map(b => `
            <tr>
              <td class="fai-key">${fmt.h(b.band || '—')}</td>
              <td style="text-align:right">${fmt.int(b.tradeCount)}</td>
              <td style="text-align:right">${fmt.pct(b.hitRatePct)}</td>
              <td style="text-align:right">${fmt.pct(b.meanReturnPct)}</td>
              <td style="text-align:right">${fmt.usd(b.cumulativePnlUsd)}</td>
              <td style="text-align:right">${fmt.usd(b.meanSizeUsd)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div class="fai-meta" style="margin-top:8px">${bands.length} bands · totalOutcomes ${fmt.int(data.totalOutcomes)}</div>
    `;
  }

  // ── Lost Opportunity (Risk Containment, NOT missed gains) ──────────
  async function renderLostOpportunity(body) {
    const data = await FomoInject.fetchWithAdminJWT('/api/admin/attribution/lost-opportunity?window=' + encodeURIComponent(currentWindow));
    const rows = data.rows || [];
    body.innerHTML = `
      <div class="fai-banner calm">
        <strong>Это не «упущенная выгода».</strong>
        Это reflective observation — какие решения gate отказал, по какой причине, и какой условный notional не был отправлен в риск. Counterfactual-блоки append-only, не пересчитываются. Здесь нет рекомендаций «ослабить gate» или «следовало бы исполнить».
      </div>
      <div class="fai-meta" style="margin-bottom:14px">n=${fmt.int(data.n)} · окно ${fmt.h(data.window)} · pipelineVersion ${fmt.h(data.pipelineVersion)}</div>
      ${rows.length === 0 ? '<div class="fai-empty">В окне нет gate-блокировок с counterfactual-следом.</div>' : `
        <table class="fai-table">
          <thead><tr>
            <th>Decision ID</th>
            <th>Time</th>
            <th>Account</th>
            <th>Symbol</th>
            <th>Permission</th>
            <th>Block reason</th>
            <th style="text-align:right">Sized notional</th>
            <th>Action</th>
          </tr></thead>
          <tbody>
            ${rows.slice(0, 100).map(r => {
              const v = r.verdictPreGate || {};
              const sz = (v.sizing || {}).final;
              return `<tr>
                <td class="fai-key">${fmt.h(r.decisionId)}</td>
                <td class="fai-meta">${fmt.ts(r.ts)}</td>
                <td class="fai-key">${fmt.h(r.accountId)}</td>
                <td>${fmt.h(r.symbol)}</td>
                <td><span class="fai-pill ${fmt.h((r.permission || '').toLowerCase())}">${fmt.h(r.permission)}</span></td>
                <td class="fai-meta">${fmt.h(r.blockReason || '—')}${(r.blockReasons && r.blockReasons.length > 1) ? ' (+' + (r.blockReasons.length - 1) + ')' : ''}</td>
                <td style="text-align:right">${sz != null ? fmt.usd(sz) : '—'}</td>
                <td>${fmt.h(v.action || '—')}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
        ${rows.length > 100 ? `<div class="fai-meta" style="margin-top:8px">Показаны первые 100 из ${fmt.int(rows.length)} строк. Forensic-режим — без бесконечной прокрутки.</div>` : ''}
      `}
    `;
  }

  // ── Lifecycle / Self-healing ───────────────────────────────────────
  function isAdminRoute() {
    return /\/admin(\/|$)/.test(window.location.pathname);
  }

  let attempts = 0;
  function tick() {
    if (!isAdminRoute()) {
      teardownPanel();
      return;
    }
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
      if (!isAdminRoute()) {
        teardownPanel();
      } else {
        setTimeout(tick, 350);
      }
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
