/**
 * legal-inject.js — Renders CMS-authored legal page bodies (Terms, Privacy,
 * Cookies) on the SPA /legal/:page and /privacy/chrome-extension routes.
 *
 * The React bundle ships these routes but their bodies are stub / empty,
 * so we:
 *   1) Detect the current legal slug from the URL
 *   2) Fetch /api/info-cms/legal/:slug
 *   3) If content exists, render it inside a consistent container near
 *      the top of <main> (or at the very top of the page).
 *   4) If no custom content — leave SPA default as-is.
 */
(function () {
  'use strict';

  const INJECT_ID = 'fomo-legal-body';

  // Map pathname → CMS slug
  const parseSlug = () => {
    const p = (window.location.pathname || '').replace(/\/+$/, '');
    // /legal/terms, /legal/privacy, /legal/cookies
    let m = p.match(/\/legal\/([a-z-]+)$/i);
    if (m) {
      const s = m[1].toLowerCase();
      if (s === 'terms' || s === 'tos' || s === 'terms-of-service') return 'terms';
      if (s === 'privacy' || s === 'privacy-policy') return 'privacy';
      if (s === 'cookies' || s === 'cookie' || s === 'cookie-policy') return 'cookies';
      return null;
    }
    // /privacy/* — treat everything under /privacy/ as "privacy"
    if (/\/privacy(\/|$)/i.test(p)) return 'privacy';
    return null;
  };

  const slug = parseSlug();
  if (!slug) return;

  const css = `
#${INJECT_ID}{
  max-width:820px;margin:40px auto 60px;padding:36px 40px;
  background:#ffffff;color:#18181b;border:1px solid #e5e7eb;border-radius:20px;
  font-size:15px;line-height:1.7;font-family:inherit;
  box-shadow:0 1px 3px rgba(0,0,0,.04);
}
@media (prefers-color-scheme: dark){
  #${INJECT_ID}{background:#0f0f12;color:#fafafa;border-color:#27272a;box-shadow:none}
  #${INJECT_ID} a{color:#818cf8}
  #${INJECT_ID} blockquote{color:#a1a1aa;border-color:#6366f1}
  #${INJECT_ID} hr{border-color:#27272a}
}
#${INJECT_ID} .legal-eyebrow{
  display:inline-block;font-size:11px;font-weight:700;letter-spacing:1.8px;
  color:#6366f1;text-transform:uppercase;margin:0 0 6px;
}
#${INJECT_ID} .legal-meta{font-size:12px;color:#6b7280;margin:0 0 26px}
#${INJECT_ID} h1{font-size:30px;font-weight:700;margin:0 0 14px;letter-spacing:-.5px}
#${INJECT_ID} h2{font-size:22px;font-weight:600;margin:26px 0 10px}
#${INJECT_ID} h3{font-size:18px;font-weight:600;margin:20px 0 8px}
#${INJECT_ID} p{margin:10px 0}
#${INJECT_ID} ul,#${INJECT_ID} ol{padding-left:26px;margin:10px 0}
#${INJECT_ID} li{margin:4px 0}
#${INJECT_ID} a{color:#4f46e5;text-decoration:underline;word-break:break-word}
#${INJECT_ID} blockquote{
  margin:14px 0;padding:6px 14px;border-left:3px solid #6366f1;color:#52525b;font-style:italic;
}
#${INJECT_ID} hr{border:none;border-top:1px solid #e5e7eb;margin:18px 0}
#${INJECT_ID} code{background:rgba(99,102,241,.12);padding:1px 5px;border-radius:4px;font-size:.92em}
#${INJECT_ID} .legal-empty{color:#9ca3af;font-style:italic;text-align:center;padding:40px 20px}
`;

  const TITLES = {
    terms: 'Terms of Service',
    privacy: 'Privacy Policy',
    cookies: 'Cookie Policy',
  };

  const injectStyle = () => {
    if (document.getElementById(INJECT_ID + '-css')) return;
    const s = document.createElement('style');
    s.id = INJECT_ID + '-css';
    s.textContent = css;
    document.head.appendChild(s);
  };

  const findMountPoint = () => {
    // Prefer the SPA's own legal page container so we replace its stub copy
    // ("… content will be added here.") rather than fighting with React.
    // Strategy: find an H1 whose text matches our page title, then climb
    // to a reasonably-sized ancestor and treat it as our mount target.
    const title = TITLES[slug].toLowerCase();
    const h1s = Array.from(document.querySelectorAll('h1, h2'));
    for (const h of h1s) {
      const t = (h.textContent || '').trim().toLowerCase();
      if (t === title || t.startsWith(title)) {
        let node = h;
        let hops = 0;
        while (node && node !== document.body && hops < 6) {
          if (node.offsetHeight > 140 && node.offsetWidth > 200) return node;
          node = node.parentElement;
          hops += 1;
        }
        return h.parentElement || h;
      }
    }
    return document.querySelector('main') ||
           document.querySelector('#root > div > div') ||
           document.getElementById('root') ||
           document.body;
  };

  const render = (content, updatedAt) => {
    const box = document.createElement('article');
    box.id = INJECT_ID;
    const updated = updatedAt
      ? `<p class="legal-meta">Last updated: ${new Date(updatedAt).toLocaleDateString(undefined,{year:'numeric',month:'long',day:'numeric'})}</p>`
      : '';
    const body = content && content.trim()
      ? content
      : '<div class="legal-empty">This page hasn\u2019t been published yet. Please check back soon.</div>';
    box.innerHTML = `
      <span class="legal-eyebrow">Legal</span>
      <h1>${TITLES[slug]}</h1>
      ${updated}
      ${body}
    `;
    // Remove any prior injected copy (on SPA navigation)
    const prev = document.getElementById(INJECT_ID);
    if (prev && prev.parentNode) prev.parentNode.removeChild(prev);

    const host = findMountPoint();
    // If we found the SPA's own page container, replace its children so the
    // stub text ("content will be added here") disappears. Otherwise just
    // prepend into the generic root.
    const isSpaStub = (host.textContent || '').toLowerCase().includes('content will be added here');
    if (isSpaStub) {
      host.innerHTML = '';
      host.appendChild(box);
    } else {
      host.insertBefore(box, host.firstChild);
    }
  };

  const load = async () => {
    injectStyle();
    try {
      const r = await fetch('/api/info-cms/legal/' + slug, { credentials: 'omit' });
      if (!r.ok) { render('', null); return; }
      const data = await r.json();
      render(data.content || '', data.updated_at || null);
    } catch (_) {
      render('', null);
    }
  };

  let attempts = 0;
  const maxAttempts = 60;
  const tick = () => {
    if (document.getElementById(INJECT_ID)) {
      // Re-verify our content is still in the DOM — React may have re-rendered
      const host = findMountPoint();
      if (host && !host.contains(document.getElementById(INJECT_ID))) {
        // React replaced it, re-inject
        load();
      }
      return;
    }
    // Wait for SPA's H1 to appear so we can mount into its container
    const titleRegex = new RegExp('^' + TITLES[slug].replace(/ /g, '\\s+'), 'i');
    const h1 = Array.from(document.querySelectorAll('h1, h2'))
      .find(h => titleRegex.test((h.textContent || '').trim()));
    if (h1) { load(); return; }
    attempts += 1;
    if (attempts < maxAttempts) setTimeout(tick, 300);
    else load();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', tick);
  } else {
    tick();
  }

  // Re-run on SPA navigation
  let lastPath = window.location.pathname;
  setInterval(() => {
    if (window.location.pathname !== lastPath) {
      lastPath = window.location.pathname;
      const newSlug = parseSlug();
      if (newSlug) { attempts = 0; location.reload(); /* simplest way to swap slug */ }
    }
  }, 700);
})();
