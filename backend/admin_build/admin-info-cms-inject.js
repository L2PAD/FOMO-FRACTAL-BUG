/**
 * admin-info-cms-inject.js
 *
 * Adds a new "Info" tab to the Intel System page of the admin panel.
 * Clicking it hides Intel System's native content and renders a full
 * CMS for the /info landing page:
 *
 *   • App Distribution Links (Android / iOS / Telegram URL + status)
 *   • Legal Pages   (Terms / Privacy / Cookies — rich HTML editor)
 *   • Social Networks (Twitter / Discord / Telegram / LinkedIn)
 *
 * Admin JWT is taken from localStorage (admin panel stores it under
 * well-known keys after login).  All calls go to /api/admin/info-cms.
 */
(function () {
  'use strict';

  const INJECT_ID  = 'fomo-info-cms';
  const TAB_ID     = 'fomo-info-cms-tab';
  const PANEL_ID   = 'fomo-info-cms-panel';
  const HIDE_CLASS = 'fomo-info-cms-hidden';

  // ── Match Intel System route ───────────────────────────────────────
  const isIntelRoute = () => {
    const p = (window.location.pathname || '');
    return /(intel|settings)/i.test(p);
  };

  // ── Admin token discovery ──────────────────────────────────────────
  const getAdminToken = () => {
    const keys = ['admin_token', 'adminToken', 'admin_jwt', 'fomo_admin_token'];
    for (const k of keys) {
      try {
        const v = localStorage.getItem(k);
        if (v) return v.replace(/^"|"$/g, '');
      } catch (_) {}
    }
    // fallback: look inside any JSON blob carrying a token
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        const v = localStorage.getItem(k) || '';
        if (/^eyJ[\w-]+\.[\w-]+\.[\w-]+$/.test(v)) return v;
        if (v.startsWith('{')) {
          try {
            const parsed = JSON.parse(v);
            const t = parsed.token || parsed.jwt || parsed.access_token;
            if (t && /^eyJ/.test(t)) return t;
          } catch (_) {}
        }
      }
    } catch (_) {}
    return null;
  };

  const apiFetch = async (path, opts = {}) => {
    const token = getAdminToken();
    const headers = Object.assign(
      { 'Content-Type': 'application/json' },
      token ? { Authorization: 'Bearer ' + token } : {},
      opts.headers || {}
    );
    const res = await fetch(path, { ...opts, headers, credentials: 'include' });
    if (!res.ok) {
      const txt = await res.text().catch(() => '');
      throw new Error(`${res.status} ${res.statusText} — ${txt}`);
    }
    return res.json();
  };

  // ── Styles ─────────────────────────────────────────────────────────
  const css = `
#${TAB_ID} svg{width:16px;height:16px}
#${TAB_ID} .fomo-info-dot{
  display:inline-block;width:6px;height:6px;border-radius:50%;
  background:#6366f1;margin-right:8px;vertical-align:middle;
}

.${HIDE_CLASS}{display:none !important}

#${PANEL_ID}{
  margin-top:22px;padding:28px;border-radius:18px;
  background:#ffffff;border:1px solid #e5e7eb;
  box-shadow:0 1px 3px rgba(0,0,0,.04);
  color:#111827;font-size:14px;
}
@media (prefers-color-scheme: dark){
  #${PANEL_ID}{background:#0f0f12;border-color:#27272a;color:#fafafa}
  #${PANEL_ID} .cms-card{background:#16161a;border-color:#27272a}
  #${PANEL_ID} input, #${PANEL_ID} select, #${PANEL_ID} .cms-editor{
    background:#0b0b0d;border-color:#27272a;color:#fafafa;
  }
  #${PANEL_ID} .cms-toolbar{background:#0b0b0d;border-color:#27272a}
  #${PANEL_ID} .cms-toolbar button{color:#d4d4d8}
  #${PANEL_ID} .cms-tabs button{color:#a1a1aa}
  #${PANEL_ID} .cms-tabs button.on{color:#fafafa;border-bottom-color:#6366f1}
}
#${PANEL_ID} h2{font-size:22px;font-weight:600;margin:0 0 4px}
#${PANEL_ID} .cms-desc{color:#6b7280;font-size:13px;margin:0 0 22px}
#${PANEL_ID} .cms-section{margin-bottom:28px}
#${PANEL_ID} .cms-section-title{
  display:flex;align-items:center;gap:10px;
  font-size:11px;font-weight:700;letter-spacing:1.5px;
  color:#6366f1;text-transform:uppercase;margin:0 0 12px;
}
#${PANEL_ID} .cms-section-title::before{
  content:"";width:14px;height:1px;background:#6366f1;display:inline-block;
}
#${PANEL_ID} .cms-card{
  padding:20px;border:1px solid #e5e7eb;border-radius:14px;background:#fafafa;
}
#${PANEL_ID} .cms-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
@media (max-width:900px){#${PANEL_ID} .cms-grid{grid-template-columns:1fr}}
#${PANEL_ID} .cms-field{display:flex;flex-direction:column;gap:6px}
#${PANEL_ID} .cms-field label{font-size:12px;font-weight:600;color:inherit;opacity:.8}
#${PANEL_ID} input, #${PANEL_ID} select{
  padding:10px 12px;border:1px solid #d1d5db;border-radius:10px;
  font-size:14px;background:#fff;color:inherit;
  transition:border-color .15s ease,box-shadow .15s ease;
  box-sizing:border-box;width:100%;
}
#${PANEL_ID} input:focus, #${PANEL_ID} select:focus{
  outline:none;border-color:#6366f1;box-shadow:0 0 0 3px rgba(99,102,241,.15);
}
#${PANEL_ID} .cms-row{display:grid;grid-template-columns:120px 1fr;gap:10px;align-items:end}
#${PANEL_ID} .cms-status{display:flex;gap:8px}
#${PANEL_ID} .cms-footer{
  display:flex;justify-content:flex-end;gap:10px;margin-top:16px;
  padding-top:14px;border-top:1px dashed rgba(99,102,241,.25);
}
#${PANEL_ID} .cms-btn{
  padding:10px 20px;border-radius:10px;border:none;cursor:pointer;
  font-weight:600;font-size:13px;letter-spacing:.2px;
  transition:background .15s ease,transform .1s ease;
}
#${PANEL_ID} .cms-btn.primary{background:#6366f1;color:#fff}
#${PANEL_ID} .cms-btn.primary:hover{background:#4f46e5}
#${PANEL_ID} .cms-btn.primary:active{transform:translateY(1px)}
#${PANEL_ID} .cms-btn:disabled{opacity:.6;cursor:not-allowed}

/* Legal editor tabs */
#${PANEL_ID} .cms-tabs{display:flex;gap:2px;border-bottom:1px solid #e5e7eb;margin-bottom:14px}
#${PANEL_ID} .cms-tabs button{
  padding:10px 18px;background:none;border:none;cursor:pointer;
  font-weight:500;font-size:13px;color:#6b7280;
  border-bottom:2px solid transparent;margin-bottom:-1px;
  text-transform:uppercase;letter-spacing:1px;
}
#${PANEL_ID} .cms-tabs button.on{color:#111827;border-bottom-color:#6366f1}

/* Rich editor */
#${PANEL_ID} .cms-editor-wrap{border:1px solid #d1d5db;border-radius:12px;overflow:hidden}
#${PANEL_ID} .cms-toolbar{
  display:flex;flex-wrap:wrap;gap:2px;
  padding:8px;background:#f9fafb;border-bottom:1px solid #e5e7eb;
}
#${PANEL_ID} .cms-toolbar button{
  display:inline-flex;align-items:center;justify-content:center;
  min-width:32px;height:30px;padding:0 8px;
  background:transparent;border:1px solid transparent;border-radius:6px;
  font-size:13px;cursor:pointer;color:#374151;
  transition:background .1s ease,border-color .1s ease;
}
#${PANEL_ID} .cms-toolbar button:hover{background:rgba(99,102,241,.1)}
#${PANEL_ID} .cms-toolbar button.on{background:#6366f1;color:#fff}
#${PANEL_ID} .cms-toolbar .sep{width:1px;background:#e5e7eb;margin:2px 4px}
#${PANEL_ID} .cms-editor{
  min-height:320px;max-height:560px;overflow:auto;
  padding:16px 20px;outline:none;font-size:15px;line-height:1.6;background:#fff;
}
#${PANEL_ID} .cms-editor h1{font-size:26px;font-weight:700;margin:16px 0 8px}
#${PANEL_ID} .cms-editor h2{font-size:21px;font-weight:600;margin:14px 0 8px}
#${PANEL_ID} .cms-editor h3{font-size:17px;font-weight:600;margin:12px 0 6px}
#${PANEL_ID} .cms-editor p{margin:6px 0}
#${PANEL_ID} .cms-editor ul,#${PANEL_ID} .cms-editor ol{padding-left:28px;margin:8px 0}
#${PANEL_ID} .cms-editor li{margin:3px 0}
#${PANEL_ID} .cms-editor a{color:#6366f1;text-decoration:underline}
#${PANEL_ID} .cms-editor blockquote{
  border-left:3px solid #6366f1;padding:4px 12px;margin:10px 0;
  color:#6b7280;font-style:italic;
}
#${PANEL_ID} .cms-editor code{background:rgba(99,102,241,.12);padding:1px 4px;border-radius:4px;font-size:.92em}
#${PANEL_ID} .cms-editor hr{border:none;border-top:1px solid #e5e7eb;margin:14px 0}
#${PANEL_ID} .cms-editor:empty::before{
  content:attr(data-placeholder);color:#9ca3af;pointer-events:none;
}

/* Toast */
.cms-toast{
  position:fixed;bottom:32px;left:50%;transform:translateX(-50%) translateY(10px);
  padding:12px 20px;background:#111827;color:#fff;border-radius:12px;
  font-size:13px;font-weight:500;opacity:0;pointer-events:none;
  z-index:999999;transition:opacity .25s ease,transform .25s ease;
  box-shadow:0 10px 30px rgba(0,0,0,.35);
}
.cms-toast.on{opacity:1;transform:translateX(-50%) translateY(0);pointer-events:auto}
.cms-toast.err{background:#dc2626}
.cms-toast.ok{background:#059669}
`;

  // ── SVG icon for the tab ───────────────────────────────────────────
  const INFO_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>';

  // ── Toast ──────────────────────────────────────────────────────────
  let toastEl = null;
  let toastTimer = null;
  const toast = (msg, kind = 'ok') => {
    if (!toastEl) {
      toastEl = document.createElement('div');
      toastEl.className = 'cms-toast';
      document.body.appendChild(toastEl);
    }
    toastEl.className = 'cms-toast on ' + kind;
    toastEl.textContent = msg;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl && toastEl.classList.remove('on'), 2800);
  };

  // ── Tab injection ──────────────────────────────────────────────────
  // Find the actual tab bar by locating the "Profile" button (always the
  // very last tab in Intel System) and grabbing its DOM parent. We insert
  // Info immediately after Profile in the SAME container so it inherits
  // the exact same flex layout as every other tab and doesn't look like a
  // floating duplicate.
  const findProfileTab = () => {
    const btns = Array.from(document.querySelectorAll('button'));
    // Exact match on visible tab label "Profile" (some buttons contain the
    // same substring so we trim and match strictly).
    return btns.find(b => {
      const t = (b.textContent || '').trim();
      return t === 'Profile' || t === 'Profil' || t === 'Profile ';
    }) || null;
  };

  // Also detect native "currently-active" tab to mirror its inline styles
  // when Info becomes active / inactive.
  const findActiveTab = () => {
    const btns = Array.from(document.querySelectorAll('button'));
    // Heuristic: the active tab has a solid background (accent). Scan the
    // tab bar buttons for the one with the most saturated background.
    let best = null;
    for (const b of btns) {
      const txt = (b.textContent || '').trim();
      if (!/^(Proxy Pool|API Keys|LLM Keys|Sentiment|Provider Pool|Health Monitor|Discovery System|Webhooks|Entity Merge|Profile)$/.test(txt)) continue;
      const cs = window.getComputedStyle(b);
      const bg = cs.backgroundColor || '';
      const m = bg.match(/rgba?\(([^)]+)\)/);
      if (!m) continue;
      const parts = m[1].split(',').map(s => parseFloat(s.trim()));
      const a = parts[3] === undefined ? 1 : parts[3];
      if (a < 0.2) continue;
      // Skip near-white/near-black surface colors (those are inactive tabs)
      const [r, g, bl] = parts;
      const mx = Math.max(r, g, bl), mn = Math.min(r, g, bl);
      const sat = mx === 0 ? 0 : (mx - mn) / mx;
      if (sat > 0.3) { best = b; break; }
    }
    return best;
  };

  const injectStyle = () => {
    if (document.getElementById(INJECT_ID + '-css')) return;
    const s = document.createElement('style');
    s.id = INJECT_ID + '-css';
    s.textContent = css;
    document.head.appendChild(s);
  };

  const findIntelContent = () => {
    // The content right below the tab bar on Intel System — we'll hide it
    // while Info mode is active.  We walk UP from the Profile tab until
    // finding a container large enough to be the Intel System section,
    // then collect its following-sibling blocks.
    const profile = findProfileTab();
    if (!profile) return null;
    let container = profile.parentElement;
    while (container && container.parentElement) {
      if (container.offsetWidth >= 600 && container.nextElementSibling) break;
      container = container.parentElement;
    }
    if (!container) return null;
    const out = [];
    let sib = container.nextElementSibling;
    while (sib) { out.push(sib); sib = sib.nextElementSibling; }
    return out;
  };

  // ── Rich editor ────────────────────────────────────────────────────
  const makeEditor = (initialHtml, placeholder) => {
    const wrap = document.createElement('div');
    wrap.className = 'cms-editor-wrap';

    const tb = document.createElement('div');
    tb.className = 'cms-toolbar';

    const editor = document.createElement('div');
    editor.className = 'cms-editor';
    editor.contentEditable = 'true';
    editor.setAttribute('data-placeholder', placeholder || 'Start writing…');
    editor.innerHTML = initialHtml || '';

    const exec = (cmd, val = null) => {
      editor.focus();
      try { document.execCommand(cmd, false, val); } catch (_) {}
      updateToolbarState();
    };

    const tools = [
      { cmd: 'bold',         label: '<b>B</b>',      title: 'Bold (⌘/Ctrl+B)' },
      { cmd: 'italic',       label: '<i>I</i>',      title: 'Italic (⌘/Ctrl+I)' },
      { cmd: 'underline',    label: '<u>U</u>',      title: 'Underline (⌘/Ctrl+U)' },
      { cmd: 'strikeThrough',label: '<s>S</s>',      title: 'Strikethrough' },
      { sep: true },
      { block: 'H1',         label: 'H1',            title: 'Heading 1' },
      { block: 'H2',         label: 'H2',            title: 'Heading 2' },
      { block: 'H3',         label: 'H3',            title: 'Heading 3' },
      { block: 'P',          label: '¶',             title: 'Paragraph' },
      { sep: true },
      { cmd: 'insertUnorderedList', label: '•',      title: 'Bulleted list' },
      { cmd: 'insertOrderedList',   label: '1.',     title: 'Numbered list' },
      { block: 'BLOCKQUOTE', label: '❝',             title: 'Blockquote' },
      { sep: true },
      { link: true,          label: '🔗',            title: 'Insert link' },
      { unlink: true,        label: '⌀',             title: 'Remove link' },
      { cmd: 'insertHorizontalRule', label: '—',     title: 'Divider' },
      { sep: true },
      { cmd: 'removeFormat', label: '⨯',             title: 'Clear formatting' },
      { sep: true },
      { cmd: 'undo',         label: '↶',             title: 'Undo' },
      { cmd: 'redo',         label: '↷',             title: 'Redo' },
    ];

    const buttons = [];
    tools.forEach(t => {
      if (t.sep) {
        const s = document.createElement('span');
        s.className = 'sep';
        tb.appendChild(s);
        return;
      }
      const b = document.createElement('button');
      b.type = 'button';
      b.innerHTML = t.label;
      b.title = t.title;
      b.dataset.cmd = t.cmd || (t.block ? 'block:' + t.block : (t.link ? 'link' : t.unlink ? 'unlink' : ''));
      b.addEventListener('mousedown', e => { e.preventDefault(); });
      b.addEventListener('click', (e) => {
        e.preventDefault();
        if (t.block) return exec('formatBlock', t.block);
        if (t.link) {
          const url = prompt('Enter URL (https://…):', 'https://');
          if (url && /^(https?:|mailto:|tel:|\/)/i.test(url)) exec('createLink', url);
          return;
        }
        if (t.unlink) return exec('unlink');
        exec(t.cmd);
      });
      buttons.push(b);
      tb.appendChild(b);
    });

    const updateToolbarState = () => {
      buttons.forEach(b => {
        const cmd = b.dataset.cmd;
        if (!cmd) return;
        try {
          if (cmd.startsWith('block:')) {
            const block = cmd.split(':')[1].toLowerCase();
            const cur = (document.queryCommandValue('formatBlock') || '').toLowerCase();
            b.classList.toggle('on', cur === block);
          } else if (cmd === 'link' || cmd === 'unlink') {
            // no persistent state
          } else {
            b.classList.toggle('on', !!document.queryCommandState(cmd));
          }
        } catch (_) {}
      });
    };

    editor.addEventListener('keyup', updateToolbarState);
    editor.addEventListener('mouseup', updateToolbarState);
    editor.addEventListener('focus', updateToolbarState);

    wrap.appendChild(tb);
    wrap.appendChild(editor);

    return {
      el: wrap,
      getHtml: () => editor.innerHTML.trim(),
      setHtml: (h) => { editor.innerHTML = h || ''; updateToolbarState(); },
    };
  };

  // ── Main CMS Panel ─────────────────────────────────────────────────
  const buildPanel = async () => {
    const panel = document.createElement('div');
    panel.id = PANEL_ID;
    panel.innerHTML = `
      <h2>Info page CMS</h2>
      <p class="cms-desc">Configure the public /info landing page — app links, legal pages and footer socials. Changes are applied live.</p>
      <div class="cms-loading">Loading configuration…</div>
    `;

    let cfg;
    try {
      cfg = await apiFetch('/api/admin/info-cms');
    } catch (e) {
      panel.querySelector('.cms-loading').textContent =
        'Failed to load: ' + (e.message || e) + '. Are you signed in as admin?';
      return panel;
    }
    panel.querySelector('.cms-loading').remove();

    // ========== App Links ==========
    const appSection = document.createElement('div');
    appSection.className = 'cms-section';
    appSection.innerHTML = `
      <div class="cms-section-title">App Distribution Links</div>
      <div class="cms-card">
        <div class="cms-grid" id="cms-app-grid"></div>
        <div class="cms-footer">
          <button class="cms-btn primary" id="cms-app-save">Save links</button>
        </div>
      </div>
    `;
    const appGrid = appSection.querySelector('#cms-app-grid');

    const appFields = {};
    [
      { k: 'android',  label: 'Android — Google Play' },
      { k: 'ios',      label: 'iOS — App Store' },
      { k: 'telegram', label: 'Telegram — Mini App' },
    ].forEach(p => {
      const f = document.createElement('div');
      f.className = 'cms-field';
      f.innerHTML = `
        <label>${p.label}</label>
        <input type="url" placeholder="https://…" value="${(cfg.app_links?.[p.k]?.url || '').replace(/"/g, '&quot;')}">
        <div class="cms-status">
          <select>
            <option value="soon" ${cfg.app_links?.[p.k]?.status !== 'live' ? 'selected' : ''}>Soon (badge)</option>
            <option value="live" ${cfg.app_links?.[p.k]?.status === 'live' ? 'selected' : ''}>Live (Open badge)</option>
          </select>
        </div>
      `;
      appGrid.appendChild(f);
      appFields[p.k] = { url: f.querySelector('input'), status: f.querySelector('select') };
    });

    appSection.querySelector('#cms-app-save').addEventListener('click', async (e) => {
      const btn = e.currentTarget; btn.disabled = true; btn.textContent = 'Saving…';
      try {
        const payload = { app_links: {} };
        for (const k of Object.keys(appFields)) {
          payload.app_links[k] = {
            url: appFields[k].url.value.trim(),
            status: appFields[k].status.value,
          };
        }
        await apiFetch('/api/admin/info-cms', { method: 'PUT', body: JSON.stringify(payload) });
        toast('App links saved', 'ok');
      } catch (err) {
        toast('Save failed: ' + err.message, 'err');
      } finally {
        btn.disabled = false; btn.textContent = 'Save links';
      }
    });

    panel.appendChild(appSection);

    // ========== Legal Pages ==========
    const legalSection = document.createElement('div');
    legalSection.className = 'cms-section';
    legalSection.innerHTML = `
      <div class="cms-section-title">Legal Pages</div>
      <div class="cms-card">
        <div class="cms-tabs" id="cms-legal-tabs"></div>
        <div id="cms-legal-editor-host"></div>
        <div class="cms-footer">
          <span style="flex:1;color:#6b7280;font-size:12px" id="cms-legal-info">Editing: Terms of Service</span>
          <button class="cms-btn primary" id="cms-legal-save">Save page</button>
        </div>
      </div>
    `;
    const LEGAL_TABS = [
      { k: 'terms',    label: 'Terms of Service' },
      { k: 'privacy',  label: 'Privacy Policy' },
      { k: 'cookies',  label: 'Cookie Policy' },
    ];
    const tabsEl = legalSection.querySelector('#cms-legal-tabs');
    const editorHost = legalSection.querySelector('#cms-legal-editor-host');
    const legalInfo = legalSection.querySelector('#cms-legal-info');

    const legalDrafts = Object.fromEntries(
      LEGAL_TABS.map(t => [t.k, cfg.legal_pages?.[t.k] || ''])
    );
    let activeLegal = 'terms';
    let editor = makeEditor(legalDrafts.terms, 'Write the full body of this legal page — use headings, links, lists.');
    editorHost.appendChild(editor.el);

    LEGAL_TABS.forEach((t, idx) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = t.label;
      b.className = idx === 0 ? 'on' : '';
      b.addEventListener('click', () => {
        // persist current draft
        legalDrafts[activeLegal] = editor.getHtml();
        activeLegal = t.k;
        legalInfo.textContent = 'Editing: ' + t.label;
        // rebuild editor with new content (execCommand-undo per page)
        editorHost.innerHTML = '';
        editor = makeEditor(legalDrafts[t.k], 'Write the full body of this legal page — use headings, links, lists.');
        editorHost.appendChild(editor.el);
        tabsEl.querySelectorAll('button').forEach(x => x.classList.remove('on'));
        b.classList.add('on');
      });
      tabsEl.appendChild(b);
    });

    legalSection.querySelector('#cms-legal-save').addEventListener('click', async (e) => {
      const btn = e.currentTarget; btn.disabled = true; btn.textContent = 'Saving…';
      try {
        legalDrafts[activeLegal] = editor.getHtml();
        const payload = { legal_pages: { [activeLegal]: legalDrafts[activeLegal] } };
        await apiFetch('/api/admin/info-cms', { method: 'PUT', body: JSON.stringify(payload) });
        toast(LEGAL_TABS.find(t => t.k === activeLegal).label + ' saved', 'ok');
      } catch (err) {
        toast('Save failed: ' + err.message, 'err');
      } finally {
        btn.disabled = false; btn.textContent = 'Save page';
      }
    });

    panel.appendChild(legalSection);

    // ========== Social Networks ==========
    const socialSection = document.createElement('div');
    socialSection.className = 'cms-section';
    socialSection.innerHTML = `
      <div class="cms-section-title">Social Networks (Footer)</div>
      <div class="cms-card">
        <div class="cms-grid" id="cms-soc-grid" style="grid-template-columns:1fr 1fr"></div>
        <div class="cms-footer">
          <button class="cms-btn primary" id="cms-soc-save">Save socials</button>
        </div>
      </div>
    `;
    const socGrid = socialSection.querySelector('#cms-soc-grid');
    const socialFields = {};
    [
      { k: 'twitter',  label: 'Twitter / X',  ph: 'https://twitter.com/fomo_ai' },
      { k: 'telegram', label: 'Telegram',     ph: 'https://t.me/fomo_channel' },
      { k: 'discord',  label: 'Discord',      ph: 'https://discord.gg/…' },
      { k: 'linkedin', label: 'LinkedIn',     ph: 'https://linkedin.com/company/fomo' },
    ].forEach(p => {
      const f = document.createElement('div');
      f.className = 'cms-field';
      f.innerHTML = `
        <label>${p.label}</label>
        <input type="url" placeholder="${p.ph}" value="${(cfg.social_links?.[p.k] || '').replace(/"/g, '&quot;')}">
      `;
      socGrid.appendChild(f);
      socialFields[p.k] = f.querySelector('input');
    });

    socialSection.querySelector('#cms-soc-save').addEventListener('click', async (e) => {
      const btn = e.currentTarget; btn.disabled = true; btn.textContent = 'Saving…';
      try {
        const payload = { social_links: {} };
        for (const k of Object.keys(socialFields)) {
          payload.social_links[k] = socialFields[k].value.trim();
        }
        await apiFetch('/api/admin/info-cms', { method: 'PUT', body: JSON.stringify(payload) });
        toast('Social links saved', 'ok');
      } catch (err) {
        toast('Save failed: ' + err.message, 'err');
      } finally {
        btn.disabled = false; btn.textContent = 'Save socials';
      }
    });

    panel.appendChild(socialSection);
    return panel;
  };

  // ── Activate / deactivate Info mode ───────────────────────────────
  let currentPanel = null;
  // Persist Profile's original inline style so we can restore it after
  // toggling Info back off.
  let lastInactiveStyleSnapshot = null;
  let lastActiveStyleSnapshot = null;

  const snapshotTabStyles = () => {
    if (lastActiveStyleSnapshot && lastInactiveStyleSnapshot) return;
    // inactive sample: Profile tab when it's inactive (by default)
    const profile = findProfileTab();
    if (profile && !lastInactiveStyleSnapshot) {
      lastInactiveStyleSnapshot = {
        bg: window.getComputedStyle(profile).backgroundColor,
        color: window.getComputedStyle(profile).color,
      };
    }
    // active sample: whatever is currently active in the bar
    const active = findActiveTab();
    if (active && !lastActiveStyleSnapshot) {
      lastActiveStyleSnapshot = {
        bg: window.getComputedStyle(active).backgroundColor,
        color: window.getComputedStyle(active).color,
      };
    }
  };

  const paintTab = (tab, isActive) => {
    snapshotTabStyles();
    const s = isActive ? lastActiveStyleSnapshot : lastInactiveStyleSnapshot;
    if (!s) return;
    tab.style.backgroundColor = s.bg;
    tab.style.color = s.color;
  };

  const activate = async (tabBtn) => {
    paintTab(tabBtn, true);
    // Hide native content siblings (everything below the tab bar)
    const siblings = findIntelContent() || [];
    siblings.forEach(s => {
      if (s.id !== PANEL_ID) s.classList.add(HIDE_CLASS);
    });
    // Mount panel
    if (!currentPanel) currentPanel = await buildPanel();
    if (!currentPanel.parentElement) {
      const host = tabBtn.closest('div') || tabBtn.parentElement;
      // Place panel AFTER the whole tabs container (not inside).
      // Walk up until we hit a block whose nextElementSibling is a content
      // card; insert our panel as its sibling after it.
      let anchor = host;
      for (let i = 0; i < 6 && anchor && anchor.parentElement; i++) {
        if (anchor.nextElementSibling && anchor.nextElementSibling.offsetHeight > 100) break;
        anchor = anchor.parentElement;
      }
      (anchor.parentElement || document.body).insertBefore(currentPanel, anchor.nextElementSibling);
    } else {
      currentPanel.classList.remove(HIDE_CLASS);
    }
  };

  const deactivate = () => {
    const tab = document.getElementById(TAB_ID);
    if (tab) paintTab(tab, false);
    const siblings = findIntelContent() || [];
    siblings.forEach(s => {
      if (s.id !== PANEL_ID) s.classList.remove(HIDE_CLASS);
    });
    if (currentPanel) currentPanel.classList.add(HIDE_CLASS);
  };

  const injectTab = () => {
    if (document.getElementById(TAB_ID)) return true;
    const profile = findProfileTab();
    if (!profile || !profile.parentElement) return false;

    injectStyle();

    const tab = document.createElement('button');
    tab.id = TAB_ID;
    tab.type = 'button';
    // Clone Profile's class + inline style so Info is visually indistinguishable.
    if (profile.className) tab.className = profile.className;
    const profileInlineStyle = profile.getAttribute('style') || '';
    if (profileInlineStyle) tab.setAttribute('style', profileInlineStyle);
    // Match content shape (icon + label). Use Profile's SVG as template if present.
    tab.innerHTML = INFO_ICON + '<span>Info</span>';
    tab.title = 'Configure /info landing page';

    snapshotTabStyles();
    paintTab(tab, false);

    tab.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      activate(tab);
    });

    // Insert Info immediately after Profile in the same container
    profile.parentElement.insertBefore(tab, profile.nextElementSibling);

    // When user clicks ANY other tab in the same parent, deactivate our mode
    Array.from(profile.parentElement.children).forEach(sib => {
      if (sib === tab || sib.tagName !== 'BUTTON') return;
      sib.addEventListener('click', deactivate, { capture: true });
    });

    return true;
  };

  // ── Lifecycle ──────────────────────────────────────────────────────
  let attempts = 0;
  const maxAttempts = 100;
  const tick = () => {
    if (!isIntelRoute()) return;
    if (injectTab()) return;
    attempts += 1;
    if (attempts < maxAttempts) setTimeout(tick, 300);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }

  // Re-attempt on SPA navigation + heal if React re-rendered the tab bar.
  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      if (isIntelRoute()) { attempts = 0; setTimeout(tick, 500); }
    }
    // Heal: if our tab got wiped by a React re-render (or we see a Profile
    // tab but no Info next to it), re-inject exactly once per pass.
    if (!isIntelRoute()) return;
    const ours = document.getElementById(TAB_ID);
    const profile = findProfileTab();
    if (profile && !ours) { attempts = 0; injectTab(); }
    // Guard against accidental duplicates — keep only the first one
    const dupes = document.querySelectorAll('#' + TAB_ID);
    if (dupes.length > 1) {
      for (let i = 1; i < dupes.length; i++) dupes[i].remove();
    }
  }, 700);
})();
