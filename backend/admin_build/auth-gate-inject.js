/*
 * P0: Auth Gate Inject — intercepts paywall CTAs on Web and forces Google
 * Sign-In before any checkout is opened.
 * 
 * Targets: "Unlock", "Unlock PRO", "See entry", "Get PRO", "Continue",
 *          "Upgrade", "Open checkout", [data-testid*="unlock"], [data-pro-cta]
 * 
 * Contract:
 *  - On any matched click, checks GET /api/auth/gate
 *  - If authenticated → lets the click pass through (original handler runs)
 *  - If not → shows a Google Sign-In modal and re-triggers the CTA after auth
 */
(function(){
if (window.__authGateInjected) return;
window.__authGateInjected = true;

// Skip on MiniApp surfaces — Telegram users auth via telegram_id, not Google.
try {
  if (location.pathname.indexOf('/miniapp') !== -1) return;
  if (window.Telegram && window.Telegram.WebApp &&
      window.Telegram.WebApp.initDataUnsafe &&
      window.Telegram.WebApp.initDataUnsafe.user) return;
} catch(e) {}

var _gateCache = null;
var _gateCacheTs = 0;
var _pendingCTA = null;
var _googleClientId = '';

function ajc(){
  var d=true; // dark first; auto-detect below
  try{
    var bg = window.getComputedStyle(document.body).backgroundColor;
    var m = bg && bg.match(/\d+/g);
    if (m && m.length >= 3) {
      var lum = (+m[0]*299 + +m[1]*587 + +m[2]*114) / 1000;
      d = lum < 128;
    }
  }catch(e){}
  return {
    dark: d,
    bg: d ? '#18181b' : '#ffffff',
    border: d ? '#27272a' : '#e5e7eb',
    text: d ? '#fafafa' : '#0f172a',
    muted: d ? '#a1a1aa' : '#64748b',
    accent: '#4285F4',
    overlay: d ? 'rgba(0,0,0,0.7)' : 'rgba(15,23,42,0.45)'
  };
}

function fetchGate(cb) {
  if (_gateCache && Date.now() - _gateCacheTs < 10000) return cb(_gateCache);
  fetch('/api/auth/gate?surface=web_paywall', {credentials: 'include'})
    .then(function(r){return r.json()})
    .then(function(d){
      _gateCache = d;
      _gateCacheTs = Date.now();
      _googleClientId = d.google_client_id || _googleClientId;
      cb(d);
    })
    .catch(function(){cb({authenticated: false, google_client_id: _googleClientId})});
}

function loadGoogleSDK(cb) {
  if (window.google && google.accounts && google.accounts.id) return cb();
  var s = document.createElement('script');
  s.src = 'https://accounts.google.com/gsi/client';
  s.async = true; s.defer = true;
  s.onload = function(){cb()};
  s.onerror = function(){cb(new Error('google_sdk_failed'))};
  document.head.appendChild(s);
}

function closeModal(){
  var el = document.getElementById('_authgate_modal');
  if (el) el.parentNode.removeChild(el);
}

function showAuthModal(onSuccess) {
  closeModal();
  var c = ajc();
  var wrap = document.createElement('div');
  wrap.id = '_authgate_modal';
  wrap.setAttribute('style',
    'position:fixed;inset:0;background:'+c.overlay+';z-index:99999;'+
    'display:flex;align-items:center;justify-content:center;padding:20px;'+
    'backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);'+
    'font-family:Manrope,system-ui,-apple-system,sans-serif');
  wrap.innerHTML =
    '<div style="background:'+c.bg+';border:1px solid '+c.border+';'+
    'border-radius:16px;padding:28px 24px;max-width:400px;width:100%;'+
    'box-shadow:0 10px 40px rgba(0,0,0,0.3)">'+
      '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'+
        '<div style="font-size:11px;font-weight:800;color:'+c.muted+';letter-spacing:0.18em;text-transform:uppercase">Secure checkout</div>'+
        '<button id="_ag_close" style="background:transparent;border:0;cursor:pointer;color:'+c.muted+';font-size:22px;line-height:1;padding:0;width:28px;height:28px">×</button>'+
      '</div>'+
      '<div style="font-size:22px;font-weight:800;color:'+c.text+';line-height:1.2;margin-bottom:8px">Sign in to continue</div>'+
      '<div style="font-size:14px;color:'+c.muted+';line-height:1.5;margin-bottom:22px">We need to create your account before payment so your subscription is attached to you — not lost.</div>'+
      '<div id="_ag_google_btn" style="display:flex;justify-content:center;min-height:44px"></div>'+
      '<div id="_ag_status" style="margin-top:14px;font-size:12px;color:'+c.muted+';text-align:center;min-height:16px"></div>'+
      '<div style="margin-top:18px;padding-top:14px;border-top:1px solid '+c.border+';font-size:11px;color:'+c.muted+';line-height:1.5;text-align:center">By continuing you agree to our Terms &amp; Privacy.</div>'+
    '</div>';
  document.body.appendChild(wrap);
  document.getElementById('_ag_close').addEventListener('click', closeModal);
  wrap.addEventListener('click', function(e){ if (e.target === wrap) closeModal(); });

  var statusEl = document.getElementById('_ag_status');
  function setStatus(txt, isError) {
    statusEl.textContent = txt || '';
    statusEl.style.color = isError ? '#ef4444' : c.muted;
  }

  loadGoogleSDK(function(err){
    if (err || !window.google || !google.accounts) {
      setStatus('Could not load Google sign-in. Refresh and try again.', true);
      return;
    }
    if (!_googleClientId) {
      setStatus('Auth not configured. Please contact support.', true);
      return;
    }
    google.accounts.id.initialize({
      client_id: _googleClientId,
      callback: function(resp) {
        setStatus('Signing you in…', false);
        fetch('/api/unified/auth/google', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'include',
          body: JSON.stringify({idToken: resp.credential, platform: 'web'})
        })
        .then(function(r){return r.json().then(function(j){return {status: r.status, body: j}})})
        .then(function(out){
          if (out.status !== 200) {
            setStatus((out.body && out.body.detail) || 'Sign-in failed. Try again.', true);
            return;
          }
          var body = out.body || {};
          var token = body.accessToken || body.access_token || body.token || body.jwt;
          if (token) {
            try { localStorage.setItem('auth_token', token); } catch(e) {}
            try { localStorage.setItem('accessToken', token); } catch(e) {}
            try { localStorage.setItem('jwt', token); } catch(e) {}
          }
          if (body.refreshToken) {
            try { localStorage.setItem('refreshToken', body.refreshToken); } catch(e) {}
          }
          _gateCache = null; _gateCacheTs = 0;
          setStatus('Signed in. Opening checkout…', false);
          closeModal();
          if (typeof onSuccess === 'function') setTimeout(onSuccess, 150);
        })
        .catch(function(){
          setStatus('Network error. Please try again.', true);
        });
      }
    });
    try {
      google.accounts.id.renderButton(document.getElementById('_ag_google_btn'), {
        theme: c.dark ? 'filled_black' : 'outline',
        size: 'large',
        type: 'standard',
        shape: 'pill',
        text: 'continue_with',
        width: 320
      });
    } catch(e) {
      setStatus('Could not render Google button.', true);
    }
  });
}

// ─── Interception ──────────────────────────────────────────
var PAYWALL_KEYWORDS = [
  'unlock pro', 'unlock', 'upgrade to pro', 'upgrade', 'get pro',
  'see entry', 'see full', 'view full', 'open checkout', 'continue to checkout',
  'subscribe now', 'get access', 'get full access', 'buy pro', 'start pro'
];

function isPaywallCTA(el) {
  if (!el) return false;
  // Explicit attribute marker — highest priority
  if (el.hasAttribute('data-pro-cta')) return true;
  var tid = (el.getAttribute('data-testid') || '').toLowerCase();
  if (tid.indexOf('unlock') !== -1 || tid.indexOf('upgrade') !== -1 ||
      tid.indexOf('checkout') !== -1 || tid.indexOf('subscribe') !== -1) return true;
  // Text heuristic — trimmed
  var txt = (el.textContent || '').trim().toLowerCase();
  if (txt.length > 80) return false; // button text is short
  for (var i = 0; i < PAYWALL_KEYWORDS.length; i++) {
    if (txt.indexOf(PAYWALL_KEYWORDS[i]) !== -1) return true;
  }
  return false;
}

function findPaywallButton(target) {
  var node = target;
  var depth = 0;
  while (node && depth < 5) {
    if (node.tagName === 'BUTTON' || node.tagName === 'A' || node.getAttribute('role') === 'button') {
      if (isPaywallCTA(node)) return node;
    }
    node = node.parentElement;
    depth++;
  }
  return null;
}

document.addEventListener('click', function(ev) {
  // Check if the click lands on or bubbles from a paywall CTA
  var btn = findPaywallButton(ev.target);
  if (!btn) return;
  if (btn.getAttribute('data-authgate-passed') === '1') return;

  // Intercept — we need to check auth first.
  ev.preventDefault();
  ev.stopPropagation();
  ev.stopImmediatePropagation && ev.stopImmediatePropagation();

  fetchGate(function(gate) {
    if (gate && gate.authenticated) {
      // Authenticated — let the original handler run.
      btn.setAttribute('data-authgate-passed', '1');
      setTimeout(function(){
        btn.click();
        btn.removeAttribute('data-authgate-passed');
      }, 30);
      return;
    }
    // Not authenticated — show modal. After sign-in, re-trigger the same CTA.
    showAuthModal(function afterAuth() {
      btn.setAttribute('data-authgate-passed', '1');
      setTimeout(function(){
        btn.click();
        btn.removeAttribute('data-authgate-passed');
      }, 50);
    });
  });
}, true); // capture — run before SPA React handlers

// Warm up the gate cache once on load so the first click is snappy.
try { fetchGate(function(){}); } catch(e) {}

})();
