/**
 * info-inject.js — v2 (full-width dark band layout)
 *
 * Adds a "Get the FOMO App" section to the /info landing page.
 * Injected as a FULL-WIDTH BLACK BAND between the hero section and
 * the "Product Ecosystem" section. Solves two problems at once:
 *
 *   1) Cards now sit on a deliberate dark surface — brand icons
 *      (Android green robot, iOS white apple, Telegram blue kite)
 *      have proper contrast instead of floating on the white hero.
 *   2) The band doubles as a visual bridge between the half-white
 *      hero and the pure-black ecosystem section below, so the
 *      left hero column no longer feels "cut off".
 *
 * Links are pulled from window.__FOMO_APP_LINKS__ when provided;
 * otherwise defaults below are used. Swap to real Play / App Store
 * URLs once live — only the `url` and `status` fields change.
 */
(function () {
  'use strict';

  const matchesInfoRoute = () => {
    const p = (window.location.pathname || '').replace(/\/+$/, '');
    return p === '/info' || p.endsWith('/api/panel/info') || p.endsWith('/panel/info');
  };
  if (!matchesInfoRoute()) return;

  // ---------- Config -----------------------------------------------------
  // Defaults used while the API fetch is in flight / if it fails.
  let cfg = Object.assign(
    {
      android: { url: '', status: 'soon' },
      ios:     { url: '', status: 'soon' },
      telegram:{ url: 'https://t.me/FOMO_mini_bot/app', status: 'live' },
    },
    (typeof window !== 'undefined' && window.__FOMO_APP_LINKS__) || {}
  );
  let socials = {};  // twitter / discord / telegram / linkedin

  // Fire-and-forget: hydrate from CMS. When it lands, re-render the strip.
  const loadRemoteConfig = async () => {
    try {
      const r = await fetch('/api/info-cms/public', { credentials: 'omit' });
      if (!r.ok) return;
      const data = await r.json();
      if (data && data.app_links) {
        cfg = {
          android:  data.app_links.android  || cfg.android,
          ios:      data.app_links.ios      || cfg.ios,
          telegram: data.app_links.telegram || cfg.telegram,
        };
      }
      if (data && data.social_links) socials = data.social_links;
      // If strip already on screen, re-render it in place
      const existing = document.getElementById(INJECT_ID);
      if (existing && existing.parentNode) {
        const fresh = buildStrip();
        existing.parentNode.replaceChild(fresh, existing);
      }
    } catch (_) { /* ignore — defaults stay */ }
  };

  const INJECT_ID = 'fomo-apps-strip';

  // ---------- Styles -----------------------------------------------------
  const css = `
#${INJECT_ID}{
  position:relative;width:100%;box-sizing:border-box;
  padding:72px 32px 64px;
  background:#000;color:#fafafa;
  display:flex;flex-direction:column;align-items:center;gap:28px;
  animation:fomoAppsIn .7s ease-out both;
  border-top:1px solid rgba(255,255,255,.08);
  border-bottom:1px solid rgba(255,255,255,.08);
}
#${INJECT_ID} .fa-inner{
  width:100%;max-width:960px;display:flex;flex-direction:column;gap:28px;
}
#${INJECT_ID} .fa-head{display:flex;flex-direction:column;gap:8px}
#${INJECT_ID} .fa-eyebrow{
  display:inline-flex;align-items:center;gap:8px;
  font-size:10.5px;font-weight:700;letter-spacing:2.4px;
  color:#f59e0b;text-transform:uppercase;
}
#${INJECT_ID} .fa-eyebrow::before{
  content:"";width:14px;height:1px;background:#f59e0b;display:inline-block;
}
#${INJECT_ID} .fa-h2{
  font-size:32px;font-weight:600;letter-spacing:-.4px;line-height:1.15;color:#fafafa;
}
#${INJECT_ID} .fa-h2 em{font-style:normal;color:#f59e0b}
#${INJECT_ID} .fa-sub{font-size:14px;color:#71717a;max-width:560px;line-height:1.5}
#${INJECT_ID} .fa-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
@media (max-width:720px){
  #${INJECT_ID}{padding:48px 20px 44px}
  #${INJECT_ID} .fa-h2{font-size:24px}
  #${INJECT_ID} .fa-row{grid-template-columns:1fr;gap:10px}
}
#${INJECT_ID} .fa-card{
  position:relative;display:flex;align-items:center;gap:14px;
  padding:18px 20px;min-height:80px;box-sizing:border-box;
  background:#0f0f12;border:1px solid rgba(255,255,255,.08);border-radius:16px;
  text-decoration:none;color:inherit;cursor:pointer;
  transition:border-color .2s ease, background .2s ease, transform .2s ease;
  -webkit-tap-highlight-color:transparent;
}
#${INJECT_ID} .fa-card:hover{
  border-color:rgba(255,255,255,.22);
  background:#17171c;transform:translateY(-2px);
}
#${INJECT_ID} .fa-card.is-soon{cursor:default;opacity:.92}
#${INJECT_ID} .fa-card.is-soon:hover{transform:none;border-color:rgba(255,255,255,.08);background:#0f0f12}
#${INJECT_ID} .fa-ico{
  flex:0 0 44px;width:44px;height:44px;
  display:flex;align-items:center;justify-content:center;
  border-radius:12px;
  background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.06);
}
#${INJECT_ID} .fa-ico.android{background:rgba(52,211,153,.08);border-color:rgba(52,211,153,.18)}
#${INJECT_ID} .fa-ico.ios{background:rgba(255,255,255,.05);border-color:rgba(255,255,255,.10)}
#${INJECT_ID} .fa-ico.telegram{background:rgba(56,189,248,.10);border-color:rgba(56,189,248,.22)}
#${INJECT_ID} .fa-body{display:flex;flex-direction:column;gap:3px;min-width:0;flex:1;padding-right:40px}
#${INJECT_ID} .fa-title{
  font-size:14.5px;font-weight:600;letter-spacing:.1px;color:#fafafa;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
#${INJECT_ID} .fa-meta{
  font-size:11.5px;color:#8a8a93;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}
#${INJECT_ID} .fa-badge{
  position:absolute;top:12px;right:14px;
  font-size:9px;font-weight:700;letter-spacing:.9px;
  padding:3px 7px;border-radius:999px;text-transform:uppercase;
}
#${INJECT_ID} .fa-badge.live{color:#34d399;background:rgba(16,185,129,.14);border:1px solid rgba(16,185,129,.38)}
#${INJECT_ID} .fa-badge.soon{color:#fbbf24;background:rgba(245,158,11,.12);border:1px solid rgba(245,158,11,.30)}
#${INJECT_ID} .fa-arrow{
  position:absolute;right:14px;bottom:12px;
  opacity:.45;color:#a1a1aa;transition:opacity .18s ease,transform .18s ease,color .18s ease;
}
#${INJECT_ID} .fa-card.is-live:hover .fa-arrow{opacity:1;transform:translateX(2px);color:#38bdf8}
#${INJECT_ID} .fa-card.is-soon .fa-arrow{display:none}
#${INJECT_ID} .fa-socials{
  margin-top:28px;padding-top:22px;border-top:1px solid rgba(255,255,255,.06);
  display:flex;flex-direction:column;align-items:flex-start;gap:10px;
}
#${INJECT_ID} .fa-soc-label{
  font-size:10px;font-weight:700;letter-spacing:2px;
  color:#a1a1aa;text-transform:uppercase;
}
#${INJECT_ID} .fa-soc-row{display:flex;gap:10px;flex-wrap:wrap}
#${INJECT_ID} .fa-soc-btn{
  width:38px;height:38px;border-radius:10px;
  display:inline-flex;align-items:center;justify-content:center;
  background:#0f0f12;border:1px solid rgba(255,255,255,.08);
  color:#a1a1aa;text-decoration:none;
  transition:background .18s ease,border-color .18s ease,color .18s ease,transform .18s ease;
}
#${INJECT_ID} .fa-soc-btn:hover{background:#17171c;border-color:rgba(255,255,255,.22);color:#fafafa;transform:translateY(-1px)}
@keyframes fomoAppsIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
.fa-toast{
  position:fixed;bottom:28px;left:50%;transform:translateX(-50%) translateY(6px);
  background:#18181b;border:1px solid #3f3f46;color:#fafafa;
  font-size:13px;padding:10px 16px;border-radius:12px;
  box-shadow:0 10px 30px rgba(0,0,0,.45);
  z-index:99999;opacity:0;pointer-events:none;
  transition:opacity .2s ease, transform .2s ease;
}
.fa-toast.on{opacity:1;transform:translateX(-50%) translateY(0);pointer-events:auto}
`;

  // ---------- Icons ------------------------------------------------------
  // Android robot (official green #3ddc84)
  const ICON_ANDROID =
    '<svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true"><path fill="#3ddc84" d="M17.52 15.8h-11c-.28 0-.5.22-.5.5V20c0 1.1.9 2 2 2h1v2.5c0 .83.67 1.5 1.5 1.5S12 25.33 12 24.5V22h2v2.5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5V22h1c1.1 0 2-.9 2-2v-3.7c0-.28-.23-.5-.5-.5ZM4.5 14c-.83 0-1.5.67-1.5 1.5v5c0 .83.67 1.5 1.5 1.5S6 21.33 6 20.5v-5c0-.83-.67-1.5-1.5-1.5Zm15 0c-.83 0-1.5.67-1.5 1.5v5c0 .83.67 1.5 1.5 1.5s1.5-.67 1.5-1.5v-5c0-.83-.67-1.5-1.5-1.5Zm-3.36-10.88 1.3-2.17a.44.44 0 0 0-.15-.6.44.44 0 0 0-.6.15l-1.3 2.2a8.8 8.8 0 0 0-7.18 0l-1.3-2.2a.44.44 0 0 0-.6-.15.44.44 0 0 0-.16.6l1.3 2.17A8.08 8.08 0 0 0 4 10.44c0 .3.23.56.53.56h15c.3 0 .53-.26.53-.56a8.07 8.07 0 0 0-3.92-7.32ZM8.73 7.9a.88.88 0 0 1-.88-.88c0-.48.4-.87.88-.87.49 0 .88.39.88.87 0 .49-.4.88-.88.88Zm7.03 0a.88.88 0 0 1-.88-.88c0-.48.4-.87.88-.87.49 0 .88.39.88.87 0 .49-.4.88-.88.88Z"/></svg>';
  // iOS Apple (white, with proper glyph)
  const ICON_IOS =
    '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path fill="#fafafa" d="M17.05 20.28c-.98.95-2.05.8-3.08.35-1.09-.46-2.09-.48-3.24 0-1.44.62-2.2.44-3.06-.35C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.08ZM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25Z"/></svg>';
  // Telegram paper-plane (proper brand blue gradient)
  const ICON_TG =
    '<svg width="26" height="26" viewBox="0 0 240 240" aria-hidden="true"><defs><linearGradient id="fa-tg-g" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#37aee2"/><stop offset="1" stop-color="#1e96c8"/></linearGradient></defs><circle cx="120" cy="120" r="120" fill="url(#fa-tg-g)"/><path fill="#fff" d="m81.23 128.78 47.7 17.63 18.43-57.12c1.33-4.13 4.85-5.07 7.84-3.1.01 0 .02.01.03.02l-81.86 51.76c-4.4 2.78-12.02 2.9-13.42-1.47l-17.65-20.3c-3.2-4.14 2.9-6.8 10-9.1l122.63-47.3c2.33-.89 4.58.69 3.88 4.02l-20.9 98.35c-1.47 6.92-5.51 8.62-11.16 5.38l-30.6-22.63-14.73 14.23c-1.53 1.53-2.82 2.82-5.77 2.82Z"/></svg>';
  const ARROW_SVG =
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 17 17 7M9 7h8v8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  const ICONS = { android: ICON_ANDROID, ios: ICON_IOS, telegram: ICON_TG };

  // ---------- Toast ------------------------------------------------------
  let toastEl = null;
  let toastTimer = null;
  const ensureToast = () => {
    if (toastEl) return;
    toastEl = document.createElement('div');
    toastEl.className = 'fa-toast';
    toastEl.setAttribute('role', 'status');
    document.body.appendChild(toastEl);
  };
  const showToast = (msg) => {
    ensureToast();
    toastEl.textContent = msg;
    toastEl.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl && toastEl.classList.remove('on'), 2600);
  };

  // ---------- DOM --------------------------------------------------------
  const buildCard = (platform, meta, onSoon) => {
    const isLive = meta.status === 'live' && meta.url;
    const a = document.createElement(isLive ? 'a' : 'div');
    a.className = 'fa-card ' + (isLive ? 'is-live' : 'is-soon');
    if (isLive) {
      a.href = meta.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
    } else {
      a.setAttribute('role', 'button');
      a.addEventListener('click', () => onSoon(platform));
    }

    const labels = {
      android: { title: 'Android',  meta: 'Google Play' },
      ios:     { title: 'iOS',      meta: 'App Store'   },
      telegram:{ title: 'Telegram', meta: 'Mini App · @FOMO_mini_bot' },
    }[platform];

    a.innerHTML =
      '<div class="fa-ico ' + platform + '">' + ICONS[platform] + '</div>' +
      '<div class="fa-body">' +
        '<div class="fa-title">' + labels.title + '</div>' +
        '<div class="fa-meta">' + labels.meta + '</div>' +
      '</div>' +
      '<span class="fa-badge ' + (isLive ? 'live' : 'soon') + '">' +
        (isLive ? 'Open' : 'Soon') +
      '</span>' +
      '<span class="fa-arrow">' + ARROW_SVG + '</span>';

    a.addEventListener('click', () => {
      try {
        if (window.posthog && typeof window.posthog.capture === 'function') {
          window.posthog.capture('info_app_card_click', { platform, status: meta.status, url: meta.url || null });
        }
      } catch (_) {}
    });
    return a;
  };

  const buildStrip = () => {
    const root = document.createElement('section');
    root.id = INJECT_ID;
    root.setAttribute('data-testid', 'fomo-apps-strip');

    const inner = document.createElement('div');
    inner.className = 'fa-inner';

    const head = document.createElement('div');
    head.className = 'fa-head';
    head.innerHTML =
      '<span class="fa-eyebrow">Get the FOMO app</span>' +
      '<h2 class="fa-h2">Same intelligence, <em>anywhere you are.</em></h2>' +
      '<p class="fa-sub">Three surfaces, one 10-layer engine. Sign in once and your signals, predictions and watchlists follow you everywhere.</p>';
    inner.appendChild(head);

    const row = document.createElement('div');
    row.className = 'fa-row';
    row.appendChild(buildCard('android',  cfg.android,  () => showToast('Android app launches soon — try the Telegram Mini App meanwhile')));
    row.appendChild(buildCard('ios',      cfg.ios,      () => showToast('iOS app launches soon — try the Telegram Mini App meanwhile')));
    row.appendChild(buildCard('telegram', cfg.telegram, () => {}));
    inner.appendChild(row);

    // Footer socials (rendered only if at least one URL is configured)
    const socialRow = buildSocials();
    if (socialRow) inner.appendChild(socialRow);

    root.appendChild(inner);
    return root;
  };

  // ---------- Socials footer --------------------------------------------
  const SOCIAL_META = {
    twitter: { title: 'Twitter',  icon:
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231L18.244 2.25Zm-1.161 17.52h1.833L7.084 4.126H5.117l11.966 15.644Z"/></svg>' },
    discord: { title: 'Discord',  icon:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.317 4.37a19.79 19.79 0 0 0-4.885-1.515.074.074 0 0 0-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 0 0-5.487 0 12.64 12.64 0 0 0-.617-1.25.077.077 0 0 0-.079-.037A19.736 19.736 0 0 0 3.677 4.37a.07.07 0 0 0-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 0 0 .031.057 19.9 19.9 0 0 0 5.993 3.03.078.078 0 0 0 .084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 0 0-.041-.106 13.107 13.107 0 0 1-1.872-.892.077.077 0 0 1-.008-.128c.126-.094.252-.192.371-.291a.074.074 0 0 1 .077-.01c3.927 1.793 8.18 1.793 12.062 0a.074.074 0 0 1 .078.009c.12.099.246.198.372.292a.077.077 0 0 1-.006.127 12.3 12.3 0 0 1-1.873.892.077.077 0 0 0-.041.107c.36.698.772 1.362 1.226 1.993a.076.076 0 0 0 .084.028 19.839 19.839 0 0 0 6.002-3.03.077.077 0 0 0 .032-.054c.5-5.177-.838-9.674-3.548-13.66a.06.06 0 0 0-.031-.028ZM8.02 15.33c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.956-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.956 2.418-2.157 2.418Zm7.975 0c-1.183 0-2.157-1.085-2.157-2.419 0-1.333.955-2.419 2.157-2.419 1.21 0 2.176 1.095 2.157 2.42 0 1.333-.946 2.418-2.157 2.418Z"/></svg>' },
    telegram:{ title: 'Telegram', icon:
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M21.944 4.116 2.9 11.4c-1 .38-1 1.75 0 2.14l4.6 1.78 1.73 5.17c.2.6.96.79 1.43.37l2.65-2.41 4.9 3.6c.87.64 2.1.13 2.27-.92l2.7-15.1c.18-1.06-.85-1.89-1.84-1.51Zm-11.9 10.2 8.14-6.08-6.5 6.8.1 3.11-1.74-3.83Z"/></svg>' },
    linkedin:{ title: 'LinkedIn', icon:
      '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.452 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.446-2.136 2.94v5.666H9.355V9h3.415v1.561h.046c.477-.9 1.637-1.852 3.37-1.852 3.602 0 4.268 2.37 4.268 5.456v6.287ZM5.337 7.433a2.062 2.062 0 0 1-2.063-2.063 2.062 2.062 0 1 1 2.063 2.063ZM7.113 20.452H3.555V9h3.558v11.452ZM22.225 0H1.771C.792 0 0 .775 0 1.729v20.542C0 23.226.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .775 23.2 0 22.222 0h.003Z"/></svg>' },
  };

  const buildSocials = () => {
    const keys = ['twitter','telegram','discord','linkedin'].filter(k => (socials[k] || '').trim());
    if (!keys.length) return null;
    const wrap = document.createElement('div');
    wrap.className = 'fa-socials';
    wrap.innerHTML = '<div class="fa-soc-label">Follow us</div>';
    const row = document.createElement('div');
    row.className = 'fa-soc-row';
    keys.forEach(k => {
      const meta = SOCIAL_META[k];
      const a = document.createElement('a');
      a.href = socials[k];
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.className = 'fa-soc-btn';
      a.title = meta.title;
      a.setAttribute('aria-label', meta.title);
      a.innerHTML = meta.icon;
      a.addEventListener('click', () => {
        try {
          if (window.posthog && typeof window.posthog.capture === 'function') {
            window.posthog.capture('info_social_click', { network: k, url: socials[k] });
          }
        } catch (_) {}
      });
      row.appendChild(a);
    });
    wrap.appendChild(row);
    return wrap;
  };

  // ---------- Anchor discovery ------------------------------------------
  // Preferred anchor: "Product Ecosystem" / "One brain. Four surfaces." block,
  // which lives in a full-width black section right below the hero. We insert
  // our strip AS A SIBLING BEFORE that section, so it becomes a dark band
  // that naturally bridges the half-white hero into the full-black ecosystem.
  const findEcosystemSection = () => {
    const candidates = document.querySelectorAll('section, div, main > *');
    for (const el of candidates) {
      const t = (el.textContent || '').toLowerCase();
      // Heuristic: this section references both phrases
      if (t.includes('product ecosystem') && t.includes('one brain') && t.length < 4000) {
        // Climb to the nearest section-sized container
        let node = el;
        let safety = 0;
        while (node && node !== document.body && safety < 10) {
          const parentBig = node.parentElement && node.parentElement.offsetHeight > node.offsetHeight;
          // Stop when the element fills the viewport width (full-width section)
          if (node.offsetWidth >= (window.innerWidth - 4) && node.offsetHeight > 120) return node;
          if (!parentBig) break;
          node = node.parentElement;
          safety++;
        }
        return el;
      }
    }
    return null;
  };

  // Fallback anchor: hero's "Continue with Google" button's nearest SECTION.
  // We insert the strip AS NEXT SIBLING of that section (below the hero).
  const findHeroSection = () => {
    const btns = document.querySelectorAll('button');
    for (const b of btns) {
      const t = (b.textContent || '').toLowerCase();
      if (t.includes('continue with google')) {
        let node = b;
        while (node && node !== document.body) {
          if (node.tagName === 'SECTION' && node.offsetWidth >= (window.innerWidth - 4)) return node;
          node = node.parentElement;
        }
        // Also acceptable: the button's main container
        return b.closest('div') || b.parentElement;
      }
    }
    return null;
  };

  const injectStyle = () => {
    if (document.getElementById(INJECT_ID + '-css')) return;
    const style = document.createElement('style');
    style.id = INJECT_ID + '-css';
    style.textContent = css;
    document.head.appendChild(style);
  };

  const inject = () => {
    if (document.getElementById(INJECT_ID)) return true;
    injectStyle();

    const ecosystem = findEcosystemSection();
    if (ecosystem && ecosystem.parentNode) {
      const strip = buildStrip();
      ecosystem.parentNode.insertBefore(strip, ecosystem);
      return true;
    }

    const hero = findHeroSection();
    if (hero && hero.parentNode) {
      const strip = buildStrip();
      hero.parentNode.insertBefore(strip, hero.nextSibling);
      return true;
    }
    return false;
  };

  // ---------- Lifecycle --------------------------------------------------
  let attempts = 0;
  const maxAttempts = 80;
  const tick = () => {
    if (!matchesInfoRoute()) return;
    if (inject()) return;
    attempts += 1;
    if (attempts < maxAttempts) setTimeout(tick, 250);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }

  // Hydrate cfg from CMS (once)
  loadRemoteConfig();

  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      if (matchesInfoRoute()) {
        attempts = 0;
        setTimeout(tick, 500);
      }
    }
  }, 500);
})();
