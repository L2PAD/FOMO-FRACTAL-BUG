"""
MiniApp Lite — V1-style redesign with full backend logic.

Single-page vanilla HTML+JS app. 4 tabs: Home / Feed / Edge / Profile.
Dark theme, FOMO branding, rich cards (Decision, Action Plan, Market Story,
Structure, Net Pressure, Breakdown, Your Edge, Pay With Crypto).

Data sources:
  /api/miniapp/home?asset=X    → decision + actionPlan + structure + pressure + marketStory + why
  /api/miniapp/feed?limit=30   → sections Now/Today/Earlier with items
  /api/miniapp/edge            → prediction market edges
  /api/miniapp/profile?telegram_id=X → user + performance + favorites + referral + promo
  /api/growth/me?telegram_id=X → growth rank + season score (fallback)
"""
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from services.i18n_service import resolve_locale, t, locale_dict
import json as _json

router = APIRouter()

MINIAPP_LITE_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover,maximum-scale=1,user-scalable=no"/>
<meta http-equiv="Cache-Control" content="no-cache,no-store,must-revalidate"/>
<title>FOMO</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#0B0F14;--bg-rgb:11,15,20;
  --card:#0F141B;--card2:#121A23;--bd:rgba(255,255,255,0.06);--bd2:rgba(255,255,255,0.10);
  --tx:#E6EDF3;--mu:#9FB0C0;--mu2:#6B7C8F;
  --buy:#2FE6A6;--sell:#FF6B6B;--warn:#F5C451;--neu:#6B7C8F;
  --ind:#4DA3FF;--pur:#2FE6A6;--cya:#4DA3FF;
  --gold:#F5C451;
  --inv:#0B0F14;
  --tx-rgb:230,237,243;
  --shadow-strong:rgba(0,0,0,.5);
  --shadow-soft:rgba(0,0,0,.4);
  --hi-overlay:rgba(255,255,255,.05);
  --hi-overlay2:rgba(255,255,255,.15);
  --hi-overlay3:rgba(0,0,0,.15);
  --modal-bg:rgba(0,0,0,.6);
  --hist-stroke:rgba(255,255,255,.72);
}
:root[data-theme="light"]{
  --bg:#f0f0f3;--bg-rgb:240,240,243;
  --card:#ffffff;--card2:#f5f6f9;--bd:#e2e5eb;--bd2:#cdd2db;
  --tx:#0f172a;--mu:#475569;--mu2:#94a3b8;
  --buy:#16a34a;--sell:#dc2626;--warn:#d97706;--neu:#6b7280;
  --ind:#4f46e5;--pur:#9333ea;--cya:#0891b2;
  --gold:#d97706;
  --inv:#ffffff;
  --tx-rgb:15,23,42;
  --shadow-strong:rgba(15,23,42,.18);
  --shadow-soft:rgba(15,23,42,.10);
  --hi-overlay:rgba(15,23,42,.05);
  --hi-overlay2:rgba(15,23,42,.10);
  --hi-overlay3:rgba(255,255,255,.20);
  --modal-bg:rgba(15,23,42,.4);
  --hist-stroke:rgba(15,23,42,.55);
}
/* Light-mode polish: soft elevation on cards, no harsh borders */
:root[data-theme="light"] .cd,
:root[data-theme="light"] .nw-card,
:root[data-theme="light"] .fv-card,
:root[data-theme="light"] .ps-card,
:root[data-theme="light"] .row-card,
:root[data-theme="light"] .promo-card,
:root[data-theme="light"] .nav{
  box-shadow:0 1px 2px rgba(15,23,42,.04),0 2px 8px rgba(15,23,42,.05);
}
:root[data-theme="light"] .g-logo img,
:root[data-theme="light"] .hm-logo img,
:root[data-theme="light"] .pf-logo img{
  filter:invert(1) hue-rotate(180deg) drop-shadow(0 2px 6px rgba(15,23,42,.18));
}
:root[data-theme="light"] .toast{
  box-shadow:0 6px 20px -4px rgba(15,23,42,.25);
}
html,body{transition:background-color .25s ease,color .25s ease}
.cd,.nw-card,.fv-card,.ps-card,.row-card,.promo-card,.nav,.nb,.apill,.hm-t,.fv-f,.fv-chip,.nw-tab{transition:background-color .2s ease,color .2s ease,border-color .2s ease}
html,body{background:var(--bg);color:var(--tx);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,sans-serif;min-height:100vh;overflow-x:hidden;-webkit-font-smoothing:antialiased}
body{padding-bottom:78px}
.app{max-width:430px;margin:0 auto}

/* ═══ HEADER ═══ */
.g-hdr{position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:space-between;padding:10px 14px 8px;background:linear-gradient(180deg,var(--bg) 75%,rgba(var(--bg-rgb),0));backdrop-filter:blur(14px)}
.g-logo{display:flex;align-items:center;justify-content:center;flex-shrink:0}
.g-logo img{height:36px;width:auto;display:block;filter:drop-shadow(0 2px 8px rgba(0,0,0,.4))}
.hdr{position:sticky;top:0;z-index:50;display:flex;align-items:center;justify-content:flex-end;padding:12px 16px 8px;background:linear-gradient(180deg,var(--bg) 70%,rgba(var(--bg-rgb),0));backdrop-filter:blur(14px)}
.hdr.hide{display:none}
.ic{width:16px;height:16px;display:inline-block;flex-shrink:0;vertical-align:-3px}
.ic.ic-buy{color:var(--buy)}
.ic.ic-sell{color:var(--sell)}
.ic.ic-warn{color:var(--warn)}
.ic.ic-pur{color:var(--pur)}
.ic.ic-cya{color:var(--cya)}
.ic.ic-gold{color:var(--gold)}
.ic.ic-tx{color:var(--tx)}
.ic.ic-mu{color:var(--mu)}
.fv-title .em{display:inline-flex;align-items:center;margin-right:7px}
.fv-title .em .ic{width:18px;height:18px}
.nw-c-type .ic{width:13px;height:13px;margin-right:3px}
.eg-social .ic{width:14px;height:14px;margin-right:4px;vertical-align:-2px}
.apill{display:flex;align-items:center;gap:5px;background:var(--card);border:1px solid var(--bd);border-radius:18px;padding:6px 11px 6px 13px;font-size:13px;font-weight:700;cursor:pointer;user-select:none}
.apill svg{width:10px;height:10px;opacity:.6}

/* ═══ CONTENT ═══ */
.cnt{padding:6px 14px 16px;min-height:calc(100vh - 160px)}
.scr{display:none}
.scr.on{display:block;animation:fi .18s ease}
@keyframes fi{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}
@keyframes spin{to{transform:rotate(360deg)}}

/* ═══ CARDS ═══ */
.cd{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px}
.cd-ttl{display:flex;align-items:center;justify-content:space-between;font-size:10px;font-weight:800;letter-spacing:1.4px;color:var(--mu2);margin-bottom:10px;text-transform:uppercase}
.cd-ttl .badge{padding:3px 8px;border-radius:5px;font-size:9px;font-weight:900;letter-spacing:.8px;color:#fff}

/* ═══ NEWS (Market Awareness Layer) ═══ */
.nw-hero{padding:16px 6px 10px;text-align:center}
.nw-hero-em{font-size:28px;line-height:1;margin-bottom:6px;display:flex;justify-content:center;align-items:center;height:34px}
.nw-hero-t{font-size:20px;font-weight:900;color:var(--tx);letter-spacing:-.4px}
.nw-hero-s{margin-top:5px;font-size:12px;font-weight:700;color:var(--mu);letter-spacing:.2px}
.nw-live{display:flex;align-items:center;gap:5px;padding:4px 2px 10px;font-size:10px;font-weight:700;color:var(--mu);letter-spacing:.2px;flex-wrap:wrap}
.nw-live .dot{width:6px;height:6px;border-radius:50%;background:var(--buy);animation:pulse 1.8s infinite;box-shadow:0 0 0 0 rgba(34,197,94,.6)}
.nw-live .lv-t{color:var(--buy);font-weight:800;letter-spacing:.5px;text-transform:uppercase}
.nw-live .lv-sep{color:var(--mu2)}
.nw-live .lv-w{color:var(--tx);font-weight:700}
.nw-live .lv-up{color:var(--mu2)}
.nw-tabs{display:flex;gap:4px;padding:6px 0 12px;overflow-x:auto;scrollbar-width:none}
.nw-tabs::-webkit-scrollbar{display:none}
.nw-tab{flex:0 0 auto;padding:6px 13px;border-radius:999px;background:transparent;border:1px solid var(--bd);font-size:11px;font-weight:800;color:var(--mu);cursor:pointer;white-space:nowrap;letter-spacing:.2px;display:inline-flex;align-items:center;gap:4px}
.nw-tab.on{background:var(--tx);color:var(--inv);border-color:var(--tx)}
.nw-tab .cn{display:inline-flex;min-width:16px;height:15px;align-items:center;justify-content:center;padding:0 5px;border-radius:8px;background:var(--hi-overlay2);font-size:9px;font-weight:900}
.nw-tab.on .cn{background:rgba(0,0,0,.15);color:var(--inv)}
.nw-card{position:relative;background:var(--card);border:1px solid var(--bd);border-left-width:3px;border-radius:12px;padding:12px 14px;margin-bottom:9px;cursor:pointer;transition:transform .15s,background .15s;animation:slideIn .3s ease-out}
@keyframes slideIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}
.nw-card:active{background:var(--card2);transform:scale(.99)}
.nw-card.type-signal{border-left-color:var(--pur)}
.nw-card.type-news{border-left-color:var(--tx)}
.nw-card.type-social{border-left-color:var(--cya)}
.nw-card.rel{border-left-color:var(--warn);background:linear-gradient(180deg,rgba(234,179,8,.055) 0%,var(--card) 100%)}
.nw-c-rel{margin-top:6px;font-size:10px;font-weight:900;letter-spacing:.6px;color:var(--warn);text-transform:uppercase}
.hero-forming{margin-top:12px;padding:14px 14px 10px;background:linear-gradient(180deg,rgba(168,85,247,.12),rgba(168,85,247,.04));border:1px solid rgba(168,85,247,.25);border-radius:12px 12px 0 0;font-size:14px;font-weight:800;color:var(--tx);letter-spacing:-.05px;text-align:center;line-height:1.35}
.hero-forming-sub{padding:10px 14px 10px;font-size:12px;font-weight:700;color:var(--mu);letter-spacing:.2px;text-align:center;background:rgba(168,85,247,.04);border-left:1px solid rgba(168,85,247,.25);border-right:1px solid rgba(168,85,247,.25)}
.hero-forming-hint{font-size:11px;font-weight:900;color:var(--pur);letter-spacing:.6px;text-align:center;padding:10px 14px 12px;background:rgba(168,85,247,.06);border:1px solid rgba(168,85,247,.25);border-top:0;border-radius:0 0 12px 12px;margin-bottom:12px;text-transform:uppercase}
.nw-c-src{margin-top:7px;font-size:10px;font-weight:700;color:var(--mu2);letter-spacing:.3px;padding-top:6px;border-top:1px dashed var(--bd2)}
.nw-c-src b{color:var(--mu);font-weight:800;letter-spacing:.2px}
.eg-early{margin-top:10px;padding:8px 12px;font-size:11px;font-weight:800;color:var(--pur);letter-spacing:.2px;background:rgba(168,85,247,.10);border:1px solid rgba(168,85,247,.25);border-radius:8px;text-align:center;text-transform:uppercase}
.pw-early{font-size:11px;font-weight:900;color:var(--warn);letter-spacing:.8px;text-align:center;text-transform:uppercase;padding:4px 0 8px}
.nw-c-hdr{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.nw-c-type{font-size:9px;font-weight:900;letter-spacing:1.3px;color:var(--mu2);text-transform:uppercase}
.nw-c-as{font-size:11px;font-weight:900;color:var(--tx);letter-spacing:.3px}
.nw-c-imp{margin-left:auto;font-size:9px;font-weight:900;padding:2px 7px;border-radius:4px;letter-spacing:.5px;text-transform:uppercase}
.nw-c-imp.imp-hi{background:rgba(239,68,68,.15);color:var(--sell)}
.nw-c-imp.imp-md{background:rgba(234,179,8,.15);color:var(--warn)}
.nw-c-imp.imp-lo{background:var(--bd2);color:var(--mu)}
.nw-c-ttl{font-size:14px;font-weight:800;color:var(--tx);line-height:1.3;letter-spacing:-.1px}
.nw-c-int{margin-top:5px;font-size:12px;font-weight:600;color:var(--mu);line-height:1.4;font-style:italic}
.nw-c-ft{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid var(--bd2)}
.nw-c-tm{font-size:10px;font-weight:700;color:var(--mu2);letter-spacing:.2px}
.nw-c-cta{font-size:12px;font-weight:900;color:var(--tx);letter-spacing:-.1px}
.nw-c-cta.bull{color:var(--buy)}
.nw-c-cta.bear{color:var(--sell)}
.nw-reset{margin:10px 0;padding:10px 12px;text-align:center;font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.3px;background:var(--card2);border-radius:8px}
.nw-empty{padding:40px 0;text-align:center;color:var(--mu2);font-size:11px;letter-spacing:.8px;font-weight:700}

/* ═══ HOME logo + compact asset strip ═══ */
.hm-logo{position:sticky;top:0;z-index:40;display:flex;flex-direction:column;align-items:center;padding:14px 0 6px;gap:4px;background:linear-gradient(180deg,var(--bg) 85%,rgba(var(--bg-rgb),0))}
.hm-logo img{height:46px;width:auto;display:block;filter:drop-shadow(0 3px 10px rgba(0,0,0,.5))}
.hm-tabs{display:flex;gap:6px;padding:4px 14px 10px;overflow-x:auto;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.hm-tabs::-webkit-scrollbar{display:none}
.hm-t{flex:0 0 auto;padding:5px 11px;border-radius:999px;background:var(--card);border:1px solid var(--bd);font-size:11px;font-weight:700;letter-spacing:.3px;color:var(--mu);cursor:pointer;transition:all .15s;user-select:none;white-space:nowrap}
.hm-t.on{background:var(--tx);color:var(--inv);border-color:var(--tx)}

/* ═══ PREDICTION SNAPSHOT (clean Expo-style) ═══ */
.ps-card{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px;cursor:pointer;transition:background .15s}
.ps-card:active{background:var(--card2)}
.ps-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.ps-ttl{font-size:10px;font-weight:800;letter-spacing:1.5px;color:var(--mu2);text-transform:uppercase}
.ps-sub{font-size:10px;font-weight:700;letter-spacing:.5px;color:var(--mu)}
.ps-word{font-size:30px;font-weight:900;letter-spacing:-1.4px;line-height:1.1;margin:4px 0 14px;color:var(--tx)}
.ps-word .arr{color:var(--mu);font-weight:900;margin:0 8px}
.ps-word .dir{color:var(--mu)}
.ps-word .dir.up{color:var(--buy)}
.ps-word .dir.dn{color:var(--sell)}
.ps-ft{display:flex;align-items:center;padding-top:12px;border-top:1px solid var(--bd2)}
.ps-m{flex:1;text-align:center}
.ps-m + .ps-m{border-left:1px solid var(--bd2)}
.ps-mv{font-size:18px;font-weight:800;letter-spacing:-.3px}
.ps-ml{font-size:9px;font-weight:800;letter-spacing:1.1px;color:var(--mu2);margin-top:3px;text-transform:uppercase}
.ps-det{color:var(--mu);font-size:22px;font-weight:300}
.ps-hzs{display:flex;gap:4px}
.ps-hz{padding:3px 8px;border-radius:6px;font-size:9px;font-weight:800;letter-spacing:.5px;color:var(--mu);border:1px solid var(--bd);cursor:pointer;user-select:none}
.ps-hz.on{background:var(--tx);color:var(--inv);border-color:var(--tx)}
.ps-chart{margin:8px -4px 4px;padding:0}
.ps-chart svg{overflow:visible}
.ps-empty{padding:30px 0;text-align:center;color:var(--mu2);font-size:11px;letter-spacing:1px;font-weight:700}
.ps-bias-row{display:flex;align-items:center;justify-content:space-between;padding:8px 2px 10px}
.ps-bias{font-size:12px;font-weight:900;letter-spacing:.8px}
.ps-target{font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.3px}
.hero{position:relative;text-align:center;padding:18px 14px 16px}
.hero-mode{position:absolute;top:12px;right:12px;font-size:9px;font-weight:900;letter-spacing:1.4px;padding:4px 9px;border-radius:5px;text-transform:uppercase}
.hero-asset{font-size:14px;font-weight:700;color:var(--mu);letter-spacing:.5px;margin-bottom:3px}
.hero-word{font-size:44px;font-weight:900;letter-spacing:-1.8px;line-height:1;margin:4px 0 6px}
.hero-edge{font-size:10px;font-weight:800;letter-spacing:1.4px;color:var(--mu);text-transform:uppercase}
.hero-conf-wrap{margin:14px 0 4px}
.hero-conf-bar{height:6px;background:var(--hi-overlay);border-radius:6px;overflow:hidden}
.hero-conf-fill{height:100%;border-radius:6px;transition:width .4s ease}
.hero-conf-row{display:flex;justify-content:space-between;font-size:10px;font-weight:700;letter-spacing:.8px;color:var(--mu);margin-top:6px;text-transform:uppercase}
.hero-conf-val{color:var(--tx);font-weight:800}
.hero-metrics{display:flex;margin-top:14px;padding-top:14px;border-top:1px solid var(--bd2)}
.hero-m{flex:1;text-align:center}
.hero-m + .hero-m{border-left:1px solid var(--bd2)}
.hero-mv{font-size:15px;font-weight:800;letter-spacing:-.3px}
.hero-ml{font-size:9px;font-weight:800;letter-spacing:1.2px;color:var(--mu2);margin-top:3px;text-transform:uppercase}

/* ═══ ACTION PLAN ═══ */
.ap-pill{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:800;letter-spacing:.5px;padding:4px 10px;border-radius:6px;margin-bottom:10px}
.ap-row{display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd);font-size:13px}
.ap-row:last-child{border-bottom:0}
.ap-ico{width:20px;height:20px;flex-shrink:0;display:flex;align-items:center;justify-content:center;color:var(--mu)}
.ap-ico svg{width:14px;height:14px}
.ap-lbl{font-size:10px;font-weight:800;letter-spacing:.9px;color:var(--mu);margin-bottom:2px;text-transform:uppercase}
.ap-val{font-size:13px;color:var(--tx);line-height:1.4}
.ap-val.red{color:var(--sell)}
.ap-val i{color:var(--mu);font-style:italic;font-size:12px;display:block;margin-top:3px}

/* ═══ STRUCTURE ═══ */
.st-pills{display:flex;gap:6px;margin-bottom:10px}
.st-p{flex:1;padding:8px 6px;border-radius:9px;background:var(--card2);text-align:center}
.st-pl{font-size:9px;font-weight:800;letter-spacing:1px;color:var(--mu2);text-transform:uppercase}
.st-pd{font-size:12px;font-weight:800;margin-top:3px}
.st-pc{font-size:10px;font-weight:700;color:var(--mu);margin-top:1px}
.st-ins{font-size:12px;line-height:1.5;color:var(--mu);white-space:pre-line}

/* ═══ PRESSURE ═══ */
.pr-hero{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
.pr-big{font-size:28px;font-weight:900;letter-spacing:-.5px}
.pr-sub{font-size:11px;font-weight:800;letter-spacing:1.2px;color:var(--mu);text-transform:uppercase}
.pr-desc{font-size:12px;line-height:1.4;color:var(--mu)}

/* ═══ BREAKDOWN ═══ */
.bk-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--bd);gap:10px}
.bk-row:last-child{border-bottom:0}
.bk-name{font-size:13px;font-weight:700}
.bk-tag{font-size:10px;font-weight:800;letter-spacing:.7px;padding:3px 7px;border-radius:5px;text-transform:uppercase;flex-shrink:0}
.bk-val{font-size:11px;color:var(--mu);margin-top:2px;line-height:1.3}

/* ═══ WHY (expandable) ═══ */
.why-toggle{display:flex;align-items:center;justify-content:space-between;padding:14px;background:var(--card);border:1px solid var(--bd);border-radius:14px;cursor:pointer;font-size:13px;font-weight:700;letter-spacing:.3px;margin-bottom:10px}
.why-toggle svg{transition:transform .2s}
.why-toggle.op svg{transform:rotate(180deg)}
.why-body{display:none;padding:0 14px 12px;background:var(--card);border:1px solid var(--bd);border-top:0;border-radius:0 0 14px 14px;margin-top:-11px;margin-bottom:10px}
.why-body.op{display:block}
.why-item{padding:8px 0;font-size:12px;line-height:1.5;color:var(--mu);border-bottom:1px solid var(--bd)}
.why-item:last-child{border-bottom:0}
.why-item b{color:var(--tx);font-weight:700}

/* ═══ QUICK ACTIONS ═══ */
.qa{display:flex;justify-content:space-around;padding:16px 4px 2px}
.qab{display:flex;flex-direction:column;align-items:center;gap:6px;cursor:pointer;flex:1}
.qab-ico{width:44px;height:44px;border-radius:50%;background:var(--card);border:1px solid var(--bd);display:flex;align-items:center;justify-content:center;transition:transform .15s}
.qab:active .qab-ico{transform:scale(.93)}
.qab-ico svg{width:18px;height:18px;color:var(--mu)}
.qab-lbl{font-size:10px;font-weight:700;color:var(--mu);letter-spacing:.4px}

/* ═══ FEED ═══ */
/* ═══ FEED V2 (NOW / BUILDING / PLAYED OUT) ═══ */
.fv-live{display:flex;align-items:center;gap:6px;padding:8px 2px 12px;font-size:11px;font-weight:700;letter-spacing:.3px;color:var(--mu)}
.fv-live .dot{width:6px;height:6px;border-radius:50%;background:var(--buy);box-shadow:0 0 0 0 rgba(34,197,94,.6);animation:pulse 1.8s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(34,197,94,.55)}70%{box-shadow:0 0 0 8px rgba(34,197,94,0)}100%{box-shadow:0 0 0 0 rgba(34,197,94,0)}}
.fv-live .v{color:var(--tx);font-weight:800}
.fv-filters{display:flex;gap:6px;padding:0 0 12px}
.fv-f{flex:0 0 auto;padding:5px 11px;border-radius:999px;background:transparent;border:1px solid var(--bd);font-size:11px;font-weight:700;color:var(--mu);cursor:pointer;user-select:none}
.fv-f.on{background:var(--tx);color:var(--inv);border-color:var(--tx)}
.fv-chips{display:flex;gap:6px;padding:0 0 14px;overflow-x:auto;scrollbar-width:none}
.fv-chips::-webkit-scrollbar{display:none}
.fv-chip{flex:0 0 auto;padding:4px 10px;border-radius:999px;background:var(--card);border:1px solid var(--bd);font-size:10px;font-weight:800;letter-spacing:.4px;color:var(--mu);cursor:pointer;user-select:none;display:flex;align-items:center;gap:5px;white-space:nowrap}
.fv-chip:active{background:var(--card2)}
.fv-chip .cn{display:inline-flex;align-items:center;justify-content:center;min-width:16px;height:16px;padding:0 5px;border-radius:8px;font-size:9px;background:var(--bd2);color:var(--tx);font-weight:900}
.fv-sec{margin-top:6px}
.fv-sec + .fv-sec{margin-top:18px}
.fv-sh{display:flex;align-items:baseline;gap:8px;font-size:11px;font-weight:900;letter-spacing:1.8px;color:var(--mu2);padding:0 2px 10px;text-transform:uppercase}
.fv-sh .n{color:var(--mu);font-weight:800;letter-spacing:.5px;font-size:10px}
.fv-card{position:relative;background:var(--card);border:1px solid var(--bd);border-left-width:3px;border-radius:12px;padding:13px 14px 12px;margin-bottom:9px;cursor:pointer;transition:transform .15s,background .15s}
.fv-card:active{background:var(--card2);transform:scale(.99)}
.fv-card.clr-green{border-left-color:var(--buy)}
.fv-card.clr-red{border-left-color:var(--sell)}
.fv-card.clr-yellow{border-left-color:var(--warn)}
.fv-card.clr-purple{border-left-color:var(--pur)}
.fv-card.clr-neutral{border-left-color:var(--tx)}
.fv-badge{position:absolute;top:11px;right:12px;font-size:8px;font-weight:900;letter-spacing:1.3px;padding:2px 6px 3px;border-radius:3px;text-transform:uppercase}
.fv-badge.new{background:rgba(168,85,247,.18);color:var(--pur)}
.fv-badge.upd{background:rgba(6,182,212,.15);color:var(--cya)}
.fv-card.hi{box-shadow:0 0 0 1px var(--pur) inset;animation:hilite 1.4s ease-out 1}
@keyframes hilite{0%{background:rgba(168,85,247,.12)}100%{background:var(--card)}}
.fv-title{font-size:15px;font-weight:800;color:var(--tx);line-height:1.25;letter-spacing:-.2px}
.fv-title .em{margin-right:5px;font-size:15px}
.fv-sub{margin-top:6px;font-size:11px;font-weight:600;color:var(--mu);line-height:1.4;letter-spacing:.2px}
.fv-sub .sep{margin:0 6px;color:var(--mu2)}
.fv-sub .src{color:var(--tx);font-weight:700}
.fv-dir{margin-top:6px;font-size:12px;font-weight:700;letter-spacing:.1px}
.fv-dir.bull{color:var(--buy)}
.fv-dir.bear{color:var(--sell)}
.fv-cta{margin-top:10px;padding-top:9px;border-top:1px solid var(--bd2);display:flex;align-items:center;justify-content:space-between}
.fv-cta-t{font-size:12px;font-weight:700;color:var(--tx);letter-spacing:.2px}
.fv-cta-arr{font-size:13px;color:var(--mu)}
.fv-ym{background:var(--card2);border:1px solid var(--bd);border-radius:12px;padding:11px 13px;margin-bottom:8px}
.fv-ym-ttl{font-size:10px;font-weight:900;letter-spacing:1.6px;color:var(--mu2);margin-bottom:8px;text-transform:uppercase}
.fv-ym-row{display:flex;align-items:center;gap:10px;padding:4px 0;font-size:12px}
.fv-ym-row .a{font-weight:800;color:var(--tx);width:48px}
.fv-ym-row .t{flex:1;color:var(--mu);font-weight:600}
.fv-ym-row .ago{color:var(--mu2);font-size:10px;font-weight:700;letter-spacing:.3px}
.fv-empty{padding:50px 0;text-align:center;color:var(--mu2);font-size:11px;letter-spacing:1px;font-weight:700}
.fv-ft-hint{padding:24px 2px 16px;text-align:center;color:var(--mu);font-size:11px;letter-spacing:.4px;font-weight:700}
.fv-ft-hint .dot{display:inline-block;width:5px;height:5px;border-radius:50%;background:var(--warn);margin-right:6px;vertical-align:middle}
.fv-micro{margin-top:4px;font-size:10px;font-weight:700;letter-spacing:.3px;color:var(--warn);text-transform:uppercase}

/* ═══ EDGE V2 ═══ */
.eg-hero{background:linear-gradient(180deg,rgba(168,85,247,.10) 0%,var(--card) 60%);border:1px solid var(--bd);border-radius:18px;padding:22px 18px 18px;margin:6px 0 14px;text-align:center;position:relative}
.eg-asset{font-size:11px;font-weight:900;letter-spacing:3px;color:var(--mu2);margin-bottom:6px}
.eg-potential{font-size:54px;font-weight:900;letter-spacing:-1.5px;line-height:1}
.eg-potential-pending{font-size:22px;font-weight:900;letter-spacing:-.3px;line-height:1.2;color:var(--mu);padding:14px 10px}
.eg-plabel{font-size:10px;font-weight:800;letter-spacing:2px;color:var(--mu);margin-top:4px;text-transform:uppercase}
.eg-stats{display:flex;justify-content:space-around;gap:8px;margin:18px 0 6px;padding:14px 0 6px;border-top:1px solid var(--bd)}
.eg-s{text-align:center;flex:1}
.eg-sv{font-size:16px;font-weight:900;color:var(--tx);letter-spacing:-.2px}
.eg-sl{font-size:9px;font-weight:800;letter-spacing:1.3px;color:var(--mu2);margin-top:3px;text-transform:uppercase}
.eg-fomo{margin-top:8px;font-size:12px;font-weight:800;letter-spacing:.6px;color:var(--warn);text-transform:uppercase;animation:pulse 2.5s infinite}

/* Inline unlock (embedded inside Action Plan — NOT a banner) */
.eg-unlock-inline{display:flex;align-items:center;justify-content:space-between;margin-top:14px;padding:14px 14px;background:linear-gradient(135deg,var(--gold) 0%,#f59e0b 100%);border-radius:12px;cursor:pointer;box-shadow:0 3px 14px -3px rgba(245,158,11,.35);transition:transform .15s}
.eg-unlock-inline:active{transform:scale(.98)}
.eg-unlock-t{font-size:14px;font-weight:900;color:#1a1205;letter-spacing:-.1px}
.eg-unlock-arr{font-size:18px;font-weight:900;color:#1a1205}

.eg-pro-banner{margin-top:12px;background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.3);border-radius:10px;padding:10px;text-align:center;font-size:11px;font-weight:900;color:var(--buy);letter-spacing:1px}
.eg-ctx{margin:-4px 0 12px;padding:8px 10px;background:var(--card2);border-radius:8px;font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.5px;text-align:center;text-transform:uppercase}
.eg-pro-block.locked .eg-apr-v.blurred{filter:blur(5px);color:var(--mu);user-select:none}
.eg-pro-block .lk{font-size:13px;margin-left:4px}
.eg-apr{display:flex;align-items:baseline;justify-content:space-between;gap:10px;padding:11px 0;border-bottom:1px solid var(--bd2);font-size:14px}
.eg-apr:last-of-type{border-bottom:none}
.eg-apr-l{color:var(--mu);font-weight:700;letter-spacing:.1px;flex-shrink:0}
.eg-apr-v{color:var(--tx);font-weight:800;letter-spacing:-.1px;text-align:right;flex:1;min-width:0;word-break:break-word}
.eg-apr-v.red{color:var(--sell)}
.eg-apr-v.green{color:var(--buy)}
.eg-urgency{margin-top:10px;padding:8px 10px;background:rgba(234,179,8,.10);border:1px solid rgba(234,179,8,.25);border-radius:8px;text-align:center;font-size:11px;font-weight:800;color:var(--warn);letter-spacing:.5px;text-transform:uppercase}
.eg-uncertain{margin-top:6px;text-align:center;font-size:10px;font-weight:700;color:var(--mu);letter-spacing:.4px}
.eg-social{margin-top:10px;padding:8px 10px;text-align:center;font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.2px;background:var(--card2);border-radius:8px}
.eg-social b{color:var(--tx);font-weight:900}
.eg-why-it{padding:6px 0;font-size:12px;color:var(--tx);line-height:1.5}
/* ─── Cognitive Sales Block (Task 3 · TG Mini-App Cognitive Layer) ─── */
/* Home teaser — compact, 3 module rows + "full breakdown in PRO" hook */
.cog-teaser{margin-bottom:12px;padding:14px 14px 12px;background:linear-gradient(180deg,rgba(168,85,247,.06),rgba(168,85,247,.02));border:1px solid rgba(168,85,247,.22);border-radius:14px}
.cog-teaser-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cog-teaser-ttl{font-size:10px;font-weight:900;color:var(--pur);letter-spacing:1.2px;text-transform:uppercase}
.cog-teaser-state{font-size:11px;font-weight:800;color:var(--mu);letter-spacing:.3px}
.cog-teaser-row{display:flex;align-items:baseline;gap:8px;padding:6px 0;font-size:12px;line-height:1.4}
.cog-teaser-row + .cog-teaser-row{border-top:1px solid var(--bd2)}
.cog-teaser-mod{flex-shrink:0;width:62px;color:var(--mu);font-weight:800;letter-spacing:.3px;font-size:10px;text-transform:uppercase}
.cog-teaser-phr{flex:1;color:var(--tx);font-weight:600}
.cog-teaser-foot{margin-top:10px;padding-top:10px;border-top:1px dashed rgba(168,85,247,.25);display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:11px}
.cog-teaser-foot-t{color:var(--mu);font-weight:700;letter-spacing:.2px}
.cog-teaser-foot-a{color:var(--pur);font-weight:900;letter-spacing:.3px}
.cog-teaser.pro .cog-teaser-foot{border-top-style:solid;border-top-color:rgba(34,197,94,.25)}
.cog-teaser.pro .cog-teaser-foot-t{color:var(--buy)}
/* Edge expanded — full per-module section with locked details for free */
.cog-edge{margin-bottom:14px;padding:16px;background:var(--card);border:1px solid var(--bd);border-radius:14px}
.cog-edge-hd{font-size:13px;font-weight:900;color:var(--tx);letter-spacing:.5px;margin-bottom:4px}
.cog-edge-sub{font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.2px;margin-bottom:14px;line-height:1.4}
.cog-mod-block{padding:12px 0;border-bottom:1px solid var(--bd2)}
.cog-mod-block:last-of-type{border-bottom:none;padding-bottom:6px}
.cog-mod-hd{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:6px}
.cog-mod-nm{font-size:12px;font-weight:900;color:var(--tx);letter-spacing:.3px}
.cog-mod-st{font-size:10px;font-weight:800;color:var(--mu);letter-spacing:.6px;text-transform:uppercase;padding:2px 7px;border-radius:5px;background:var(--card2)}
.cog-mod-st.warn{color:var(--warn);background:rgba(234,179,8,.12)}
.cog-mod-st.pur{color:var(--pur);background:rgba(168,85,247,.12)}
.cog-mod-st.neu{color:var(--mu);background:var(--card2)}
.cog-mod-st.muted{color:var(--mu);background:transparent;border:1px solid var(--bd2)}
.cog-mod-phr{font-size:12px;font-weight:600;color:var(--tx);line-height:1.5;margin-bottom:4px}
.cog-mod-detail{font-size:11px;font-weight:600;color:var(--mu);line-height:1.5;letter-spacing:.1px}
.cog-mod-detail.locked{filter:blur(5px);user-select:none}
.cog-edge-cta{margin-top:14px;padding:11px 14px;background:linear-gradient(135deg,rgba(168,85,247,.10),rgba(168,85,247,.02));border:1px dashed rgba(168,85,247,.45);border-radius:10px;display:flex;align-items:center;justify-content:space-between;gap:8px;cursor:pointer}
.cog-edge-cta-t{font-size:11px;font-weight:800;color:var(--pur);letter-spacing:.3px}
.cog-edge-cta-a{font-size:13px;font-weight:900;color:var(--pur)}
.cog-edge-pro-foot{margin-top:14px;padding:8px 10px;background:rgba(34,197,94,.10);border:1px solid rgba(34,197,94,.25);border-radius:8px;text-align:center;font-size:10px;font-weight:900;color:var(--buy);letter-spacing:1px;text-transform:uppercase}
.dr-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd2);font-size:13px}
.dr-row:last-child{border-bottom:none}
.dr-m{width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:11px;font-weight:900;flex-shrink:0}
.dr-m.ok{background:rgba(34,197,94,.18);color:var(--buy)}
.dr-m.pd{background:rgba(234,179,8,.15);color:var(--warn)}
.dr-m.of{background:var(--bd2);color:var(--mu2)}
.dr-n{flex:1;font-weight:700;color:var(--tx)}
.dr-s{font-size:11px;font-weight:700;color:var(--mu);letter-spacing:.3px}
.cd-sub{font-size:10px;font-weight:800;color:var(--mu);letter-spacing:.5px;margin-left:6px;text-transform:none}
.eg-timing{display:flex;align-items:center;gap:4px;padding:6px 0}
.eg-tmg-st{display:flex;flex-direction:column;align-items:center;gap:4px;flex:0 0 auto}
.eg-tmg-dot{width:14px;height:14px;border-radius:50%;background:var(--bd2);border:2px solid var(--bd);transition:all .3s}
.eg-tmg-st.done .eg-tmg-dot{background:var(--buy);border-color:var(--buy)}
.eg-tmg-st.on .eg-tmg-dot{background:var(--warn);border-color:var(--warn);box-shadow:0 0 0 4px rgba(234,179,8,.2);animation:pulse 1.8s infinite}
.eg-tmg-lbl{font-size:9px;font-weight:800;color:var(--mu2);letter-spacing:.6px;text-transform:uppercase}
.eg-tmg-st.on .eg-tmg-lbl{color:var(--warn)}
.eg-tmg-st.done .eg-tmg-lbl{color:var(--buy)}
.eg-tmg-ln{flex:1;height:2px;background:var(--bd2);border-radius:2px;margin-top:-14px}
.eg-tmg-ln.done{background:var(--buy)}
.pw-modal{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:9999;display:flex;align-items:flex-end;justify-content:center;backdrop-filter:blur(4px)}
.pw-box{width:100%;max-width:420px;background:var(--card);border-top-left-radius:20px;border-top-right-radius:20px;padding:24px 20px 30px;animation:slideUp .25s ease-out}
@keyframes slideUp{from{transform:translateY(100%)}to{transform:translateY(0)}}
.pw-ttl{font-size:22px;font-weight:900;color:var(--tx);letter-spacing:-.4px}
.pw-sub{margin-top:6px;font-size:12px;color:var(--warn);font-weight:800;letter-spacing:.3px;text-transform:uppercase}
.pw-bullets{margin:16px 0 6px;display:flex;flex-direction:column;gap:8px}
.pw-b{display:flex;align-items:center;gap:10px;font-size:13px;font-weight:700;color:var(--tx)}
.pw-bi{display:inline-flex;width:20px;height:20px;border-radius:50%;background:rgba(245,200,76,.18);color:var(--gold);align-items:center;justify-content:center;font-size:11px;font-weight:900;flex-shrink:0}

.pw-close{position:absolute;top:12px;right:14px;width:30px;height:30px;border-radius:50%;background:var(--card2);display:flex;align-items:center;justify-content:center;font-size:13px;color:var(--mu);cursor:pointer;font-weight:700}
.pw-tiers{display:flex;gap:8px;margin-top:16px}
.pw-tier{flex:1;background:var(--card2);border:2px solid var(--bd);border-radius:12px;padding:12px 8px 10px;text-align:center;cursor:pointer;transition:all .15s;position:relative}
.pw-tier.best{border-color:var(--gold)}
.pw-tier.selected{border-color:var(--gold);background:rgba(245,200,76,.08);box-shadow:0 0 0 2px rgba(245,200,76,.2)}
.pw-tier-bd{position:absolute;top:-8px;left:50%;transform:translateX(-50%);background:var(--gold);color:#1a1205;font-size:9px;font-weight:900;padding:2px 7px;border-radius:4px;letter-spacing:.4px;text-transform:uppercase;white-space:nowrap}
.pw-tier-p{font-size:18px;font-weight:900;color:var(--tx);letter-spacing:-.3px;line-height:1.1}
.pw-tier-pe{display:block;margin-top:2px;font-size:9px;font-weight:700;color:var(--mu2);letter-spacing:.4px;text-transform:uppercase}
.pw-social{margin-top:12px;padding:10px;background:var(--card2);border-radius:10px;text-align:center;font-size:11px;color:var(--mu);letter-spacing:.2px}
.pw-social b{color:var(--tx);font-weight:900;margin-right:2px}

.toast{position:fixed;bottom:80px;left:50%;transform:translateX(-50%);z-index:10000;background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:11px 16px;font-size:12px;font-weight:700;color:var(--tx);box-shadow:0 6px 20px -4px rgba(0,0,0,.5);letter-spacing:.2px;animation:toastIn .3s ease-out}
.toast.out{animation:toastOut .3s forwards}
@keyframes toastIn{from{opacity:0;transform:translate(-50%,20px)}to{opacity:1;transform:translate(-50%,0)}}
@keyframes toastOut{from{opacity:1;transform:translate(-50%,0)}to{opacity:0;transform:translate(-50%,20px)}}
@keyframes fadeOut{from{opacity:1}to{opacity:0}}
.pw-price{margin-top:14px;padding:14px;background:var(--card2);border-radius:12px;text-align:center;border:1px solid var(--bd2)}
.pw-p-amt{font-size:30px;font-weight:900;color:var(--tx);letter-spacing:-1px}
.pw-p-per{font-size:14px;font-weight:700;color:var(--mu);margin-left:2px}
.pw-p-note{display:block;margin-top:4px;font-size:10px;font-weight:700;color:var(--mu2);letter-spacing:.3px}
.pw-btns{display:flex;flex-direction:column;gap:8px;margin-top:16px}
.pw-btn{padding:14px;border-radius:12px;text-align:center;font-size:14px;font-weight:900;cursor:pointer;transition:opacity .15s}
.pw-btn:active{opacity:.8}
.pw-btn.primary{background:linear-gradient(135deg,var(--gold) 0%,#f59e0b 100%);color:#1a1205;letter-spacing:.2px;box-shadow:0 4px 14px -4px rgba(245,158,11,.4)}
.pw-btn:not(.primary){background:var(--card2);color:var(--mu);border:1px solid var(--bd)}
.pw-note{margin-top:10px;font-size:10px;color:var(--mu2);text-align:center;font-style:italic}

/* ═══ EDGE ═══ */
.eg-it{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:12px;margin-bottom:8px}
.eg-hd{display:flex;align-items:center;gap:8px;margin-bottom:7px}
.eg-as{font-size:13px;font-weight:800;letter-spacing:.2px;color:var(--tx)}
.eg-pc{font-size:14px;font-weight:900}
.eg-pc.up{color:var(--buy)}
.eg-pc.dn{color:var(--sell)}
.eg-ac{font-size:9px;font-weight:900;letter-spacing:1px;padding:3px 7px;border-radius:4px;color:#fff}
.eg-ac.buy{background:var(--buy)}
.eg-ac.sell{background:var(--sell)}
.eg-ac.watch{background:var(--neu)}
.eg-tl{font-size:10px;color:var(--mu);margin-left:auto;font-weight:700}
.eg-q{font-size:12px;line-height:1.45;color:var(--mu)}

/* ═══ PROFILE ═══ */
.pf-logo{position:sticky;top:0;z-index:40;display:flex;flex-direction:column;align-items:center;padding:14px 0 12px;gap:4px;background:linear-gradient(180deg,var(--bg) 85%,rgba(var(--bg-rgb),0))}
.pf-logo img{height:58px;width:auto;display:block;filter:drop-shadow(0 3px 10px rgba(0,0,0,.5))}
.pf-user{display:flex;align-items:center;gap:13px;padding:14px;background:var(--card);border:1px solid var(--bd);border-radius:16px;margin-bottom:10px}
.pf-av{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,var(--ind),var(--pur));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:20px;color:#fff;flex-shrink:0;letter-spacing:-.5px;overflow:hidden}
.pf-av img{width:100%;height:100%;object-fit:cover}
.pf-uinfo{flex:1;min-width:0}
.pf-name{font-size:15px;font-weight:800;letter-spacing:-.2px}
.pf-un{font-size:12px;color:var(--mu);margin-top:2px}
.pf-plan{font-size:9px;font-weight:900;letter-spacing:1px;padding:3px 8px;border-radius:5px;text-transform:uppercase}
.pf-plan.free{background:var(--bd2);color:var(--mu)}
.pf-plan.pro{background:linear-gradient(135deg,var(--gold),#d4a017);color:#0B0F14}

/* FOMO PRO banner (yellow) */.pro-ban{background:linear-gradient(135deg,rgba(245,200,76,.08),rgba(245,200,76,.02));border:1.5px solid rgba(245,200,76,.35);border-radius:16px;padding:14px;margin-bottom:10px}
.pro-hdr{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.pro-bolt{color:var(--gold);font-size:18px}
.pro-name{color:var(--gold);font-weight:900;font-size:15px;letter-spacing:.5px}
.pro-desc{font-size:12px;line-height:1.45;color:var(--tx);margin-bottom:12px}
.pro-sell-bullets{display:flex;flex-direction:column;gap:6px;margin-bottom:13px}
.pro-b{display:flex;align-items:center;gap:8px;font-size:12px;font-weight:700;color:var(--tx)}
.pro-bi{display:inline-flex;width:18px;height:18px;border-radius:50%;background:rgba(245,200,76,.22);color:var(--gold);align-items:center;justify-content:center;font-size:10px;font-weight:900;flex-shrink:0}
.pro-cta{display:flex;align-items:center;justify-content:center;gap:6px;background:linear-gradient(135deg,var(--gold) 0%,#f59e0b 100%);color:#1a1205;font-weight:900;font-size:14px;letter-spacing:.3px;padding:14px;border-radius:12px;cursor:pointer;border:0;width:100%;box-shadow:0 4px 14px -4px rgba(245,158,11,.4)}

.bill{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px}
.bill-ttl{font-size:15px;font-weight:800;margin-bottom:4px;letter-spacing:-.2px}
.bill-pr{font-size:12px;color:var(--mu);margin-bottom:10px;line-height:1.4}
.bill-ftrs{font-size:11px;color:var(--mu);line-height:1.6;margin-bottom:12px}
.bill-ftrs div{display:flex;align-items:center;gap:5px}
.bill-ftrs div::before{content:"•";color:var(--buy);font-weight:900}
.bill-cta{display:flex;align-items:center;justify-content:center;gap:7px;background:var(--buy);color:var(--inv);font-weight:900;font-size:13px;letter-spacing:.5px;padding:12px;border-radius:11px;cursor:pointer;border:0;width:100%;text-transform:uppercase}
.bill-cta svg{width:14px;height:14px}

.edge-stat{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px}
.edge-acc{display:flex;align-items:flex-end;gap:6px;margin-bottom:4px}
.edge-big{font-size:34px;font-weight:900;letter-spacing:-1.5px;line-height:1}
.edge-lab{font-size:10px;font-weight:800;letter-spacing:1.2px;color:var(--mu);padding-bottom:5px;text-transform:uppercase}
.edge-desc{font-size:12px;color:var(--mu);margin-bottom:12px}
.edge-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;padding-top:10px;border-top:1px solid var(--bd)}
.edge-gi{text-align:center}
.edge-gv{font-size:15px;font-weight:800}
.edge-gl{font-size:9px;font-weight:800;letter-spacing:.9px;color:var(--mu2);margin-top:2px;text-transform:uppercase}

.ref-box{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px}
.ref-rw{font-size:11px;color:var(--mu);margin-bottom:10px;line-height:1.4}
.ref-code{display:flex;align-items:center;gap:8px;background:var(--card2);border:1px dashed var(--bd2);border-radius:10px;padding:9px 12px;margin-bottom:8px}
.ref-code-val{font-family:"JetBrains Mono",monospace;font-size:13px;font-weight:700;letter-spacing:.3px;flex:1}
.ref-copy{font-size:10px;font-weight:800;letter-spacing:.8px;color:var(--ind);cursor:pointer;padding:4px 8px;text-transform:uppercase}
.ref-btn{display:flex;align-items:center;justify-content:center;gap:7px;background:var(--ind);color:#fff;font-weight:800;font-size:12px;letter-spacing:.4px;padding:11px;border-radius:10px;cursor:pointer;border:0;width:100%;text-transform:uppercase}

/* Collapsible card (leaderboard) */
.coll{background:var(--card);border:1px solid var(--bd);border-radius:16px;margin-bottom:16px;overflow:hidden}
.coll-hd{display:flex;align-items:center;gap:14px;padding:16px 16px 16px 14px;cursor:pointer}
.coll-ic{width:40px;height:40px;border-radius:11px;background:linear-gradient(135deg,rgba(255,193,7,.16),rgba(255,107,0,.08));display:flex;align-items:center;justify-content:center;flex-shrink:0;border:1px solid rgba(255,193,7,.22);color:#FFC907}
.coll-ic.gr{background:linear-gradient(135deg,rgba(99,102,241,.18),rgba(168,85,247,.08));border-color:rgba(99,102,241,.28);color:#8b8cf7}
.coll-body{flex:1;min-width:0;padding-right:4px}
.coll-t{font-size:15px;font-weight:800;letter-spacing:-.2px}
.coll-s{font-size:11px;color:var(--mu);margin-top:3px;line-height:1.45}
.coll-arr{color:var(--mu);transition:transform .2s;flex-shrink:0}
.coll.op .coll-arr{transform:rotate(180deg)}
.coll-inner{display:none;padding:0 16px 16px}
.coll.op .coll-inner{display:block}
.lb-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd);font-size:13px}
.lb-row:last-child{border-bottom:0}
.lb-rank{font-size:12px;font-weight:800;color:var(--mu2);width:24px;text-align:center}
.lb-rank.top{color:var(--gold)}
.lb-name{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lb-score{font-weight:800;color:var(--ind)}

/* Profile sections (appearance, alerts, notifications, app) */
.sec{margin-top:18px}
.sec-hdr{display:flex;align-items:center;gap:7px;padding:0 4px 10px}
.sec-hdr-ic{color:var(--mu);display:flex}
.sec-hdr-ic svg{width:14px;height:14px}
.sec-hdr-t{font-size:10px;font-weight:800;letter-spacing:1.5px;color:var(--mu2);text-transform:uppercase}

.row-card{background:var(--card);border:1px solid var(--bd);border-radius:16px;overflow:hidden}
.row-item{display:flex;align-items:center;gap:12px;padding:13px 14px;border-bottom:1px solid var(--bd)}
.row-item:last-child{border-bottom:0}
.row-item.clk{cursor:pointer}
.row-item.clk:active{background:var(--card2)}
.row-ico{width:34px;height:34px;border-radius:9px;background:var(--card2);display:flex;align-items:center;justify-content:center;flex-shrink:0}
.row-ico svg{width:16px;height:16px}
.row-body{flex:1;min-width:0}
.row-t{font-size:14px;font-weight:700;letter-spacing:-.1px}
.row-s{font-size:11px;color:var(--mu);margin-top:2px;line-height:1.3}
.row-arr{color:var(--mu2)}
.row-arr svg{width:12px;height:12px}

/* Toggle switch */
.sw{position:relative;width:44px;height:24px;border-radius:13px;background:var(--bd2);cursor:pointer;transition:background .2s;flex-shrink:0}
.sw::after{content:"";position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:#fff;transition:left .2s}
.sw.on{background:var(--buy)}
.sw.on::after{left:22px}

/* Promo code card */
.promo-card{background:var(--card);border:1px solid var(--bd);border-radius:16px;padding:14px;margin-bottom:10px}
.promo-ttl{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.promo-ttl svg{width:14px;height:14px;color:var(--mu)}
.promo-ttl span{font-size:10px;font-weight:800;letter-spacing:1.5px;color:var(--mu2);text-transform:uppercase}
.promo-row{display:flex;gap:8px}
.promo-inp{flex:1;background:var(--card2);border:1px solid var(--bd);border-radius:10px;padding:11px 12px;color:var(--tx);font-size:13px;font-weight:600;letter-spacing:.3px;outline:none}
.promo-inp::placeholder{color:var(--mu2);font-weight:500}
.promo-btn{background:var(--ind);color:#fff;font-weight:800;font-size:12px;padding:0 16px;border-radius:10px;border:0;cursor:pointer;letter-spacing:.5px;text-transform:uppercase}
.promo-btn:disabled{opacity:.4;cursor:not-allowed}
.promo-msg{font-size:11px;margin-top:8px;padding:6px 10px;border-radius:6px}
.promo-msg.ok{background:rgba(34,197,94,.12);color:var(--buy)}
.promo-msg.err{background:rgba(239,68,68,.12);color:var(--sell)}

/* About */
.about-ln{font-size:11px;color:var(--mu2);text-align:center;padding:16px 0 10px;letter-spacing:.3px}

/* ═══ BOTTOM NAV ═══ */
.nav{position:fixed;bottom:0;left:0;right:0;z-index:100;display:flex;background:var(--card);border-top:1px solid var(--bd);padding:8px 0 calc(8px + env(safe-area-inset-bottom,0px))}
.app .nav{max-width:430px;margin:0 auto}
.nb{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px;padding:6px 0;background:0;border:0;color:var(--mu2);cursor:pointer;font-size:10px;font-weight:700;letter-spacing:.4px}
.nb svg{width:20px;height:20px;stroke-width:2}
.nb.on{color:var(--tx)}
.nb.on svg{color:var(--tx)}

.spin{display:flex;align-items:center;justify-content:center;padding:60px 0;color:var(--mu2);font-size:10px;letter-spacing:2px;text-transform:uppercase}
.err{padding:40px 16px;text-align:center;color:var(--sell);font-size:12px}
.empty{padding:40px 16px;text-align:center;color:var(--mu);font-size:12px}

.color-buy{color:var(--buy)}.color-sell{color:var(--sell)}.color-warn{color:var(--warn)}.color-neu{color:var(--mu)}.color-pur{color:var(--pur)}.color-mu{color:var(--mu)}
.bg-buy{background:var(--buy)}.bg-sell{background:var(--sell)}.bg-warn{background:var(--warn)}.bg-neu{background:var(--neu)}
.bg-buy-s{background:rgba(34,197,94,.12)}.bg-sell-s{background:rgba(239,68,68,.12)}.bg-warn-s{background:rgba(234,179,8,.12)}.bg-neu-s{background:rgba(107,114,128,.12)}.bg-pur-s{background:rgba(168,85,247,.14)}
.bg-pur{background:var(--pur)}
.border-buy{border-color:rgba(34,197,94,.3)}.border-sell{border-color:rgba(239,68,68,.3)}.border-warn{border-color:rgba(234,179,8,.3)}
</style>
</head>
<body>
<div class="app">

<header class="g-hdr" id="app-hdr">
  <div class="g-logo" style="margin:0 auto"><img src="/api/miniapp/lite/logo.png" alt="FOMO"/></div>
</header>

<main class="cnt">
  <section id="s-home" class="scr on"><div class="spin">LOADING · METABRAIN</div></section>
  <section id="s-feed" class="scr"><div class="spin">LOADING · FEED</div></section>
  <section id="s-news" class="scr"><div class="spin">LOADING · MARKET</div></section>
  <section id="s-edge" class="scr"><div class="spin">LOADING · EDGE</div></section>
  <section id="s-profile" class="scr"><div class="spin">LOADING · PROFILE</div></section>
</main>

<nav class="nav">
  <button class="nb on" data-t="home" onclick="sw('home')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/></svg>
    Home
  </button>
  <button class="nb" data-t="feed" onclick="sw('feed')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 4h11a3 3 0 013 3v11H7a3 3 0 01-3-3V4z"/><path d="M8 8h7M8 12h7M8 16h5"/></svg>
    Feed
  </button>
  <button class="nb" data-t="news" onclick="sw('news')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/></svg>
    News
  </button>
  <button class="nb" data-t="edge" onclick="sw('edge')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M3 17l5-5 4 4 8-8"/><path d="M14 8h6v6"/></svg>
    Edge
  </button>
  <button class="nb" data-t="profile" onclick="sw('profile')">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
    Profile
  </button>
</nav>
</div>

<script>
var ASSETS=['BTC','ETH','SOL'];
var asset='BTC', tg=null, tgId='', gView='profile';

// ═══ THEME ENGINE ═══
// Restore the original "lite" theme variant (light + dark) from V1.
// Priority: ?theme= URL > localStorage > Telegram colorScheme > 'dark'.
var THEME_KEY='fomo:lite:theme';
var THEME_BG={dark:'#0B0F14',light:'#f0f0f3'};
function _readSavedTheme(){
  try{var t=localStorage.getItem(THEME_KEY);if(t==='light'||t==='dark')return t;}catch(e){}
  return null;
}
function _detectTheme(){
  try{
    var p=new URLSearchParams(location.search);
    var q=(p.get('theme')||'').toLowerCase();
    if(q==='light'||q==='dark')return q;
  }catch(e){}
  var saved=_readSavedTheme();if(saved)return saved;
  try{
    if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.colorScheme==='light')return 'light';
  }catch(e){}
  return 'dark';
}
function applyTheme(t,opts){
  if(t!=='light'&&t!=='dark')t='dark';
  document.documentElement.setAttribute('data-theme',t);
  var bg=THEME_BG[t]||THEME_BG.dark;
  try{
    if(window.Telegram&&Telegram.WebApp){
      Telegram.WebApp.setHeaderColor(bg);
      Telegram.WebApp.setBackgroundColor(bg);
    }
  }catch(e){}
  if(!opts||opts.persist!==false){
    try{localStorage.setItem(THEME_KEY,t);}catch(e){}
    try{
      if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.CloudStorage&&Telegram.WebApp.CloudStorage.setItem){
        Telegram.WebApp.CloudStorage.setItem('theme',t,function(){});
      }
    }catch(e){}
  }
  window.__fomoTheme=t;
}
function getTheme(){return window.__fomoTheme||document.documentElement.getAttribute('data-theme')||'dark'}
// Apply ASAP (before any rendering of dynamic UI)
applyTheme(_detectTheme(),{persist:false});
// Hydrate from CloudStorage (cross-device) if available, but only override if not URL-forced
try{
  if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.CloudStorage&&Telegram.WebApp.CloudStorage.getItem){
    var _hasUrl=false;try{_hasUrl=!!new URLSearchParams(location.search).get('theme');}catch(e){}
    if(!_hasUrl){
      Telegram.WebApp.CloudStorage.getItem('theme',function(err,val){
        if(!err&&(val==='light'||val==='dark')&&val!==getTheme())applyTheme(val,{persist:true});
      });
    }
  }
}catch(e){}

if(window.Telegram&&Telegram.WebApp){
  Telegram.WebApp.ready();Telegram.WebApp.expand();
  try{Telegram.WebApp.onEvent&&Telegram.WebApp.onEvent('themeChanged',function(){
    // Only auto-follow Telegram theme if user hasn't explicitly chosen one
    if(!_readSavedTheme()){applyTheme(Telegram.WebApp.colorScheme==='light'?'light':'dark',{persist:false});}
  });}catch(e){}
  var u=Telegram.WebApp.initDataUnsafe&&Telegram.WebApp.initDataUnsafe.user;
  if(u){tg=u;tgId=String(u.id||'')}
}
// URL + Deep link params
var P=new URLSearchParams(location.search);
if(P.get('asset'))asset=P.get('asset').toUpperCase();
var _initTab='home';
var _deepLinkAsset='';
(function(){
  var sp=(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.initDataUnsafe?Telegram.WebApp.initDataUnsafe.start_param:'')||P.get('startapp')||P.get('start_param')||'';
  if(!sp)return;
  var parts=String(sp).split('_');
  var sec=(parts[0]||'').toLowerCase();
  var ast=(parts[1]||'').toUpperCase();
  // Accept any 2-10 char uppercased ticker (BTC, DOGE, SHIB, PEPE, 1000SATS, etc.)
  if(ast&&/^[A-Z0-9]{2,10}$/.test(ast)){
    asset=ast;
    _deepLinkAsset=ast;
  }
  var m={news:'feed',feed:'feed',home:'home',edge:'edge',profile:'profile'};
  if(sec&&m[sec])_initTab=m[sec];
})();
// cur-asset element was removed from header (dropdown dropped); safe-set:
var _cur=document.getElementById('cur-asset');if(_cur)_cur.textContent=asset;

// Presence heartbeat — pings server every 60s while app is visible/focused.
// Used by push engine: skip users seen in last 10 minutes.
function _presencePing(){
  if(!tgId||document.hidden)return;
  try{fetch('/api/miniapp/presence/heartbeat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tgId||'')})}).catch(function(){});}catch(e){}
}
_presencePing();
setInterval(_presencePing,60000);
document.addEventListener('visibilitychange',function(){if(!document.hidden)_presencePing();});

function $(s,r){return(r||document).querySelector(s)}
function esc(s){if(s==null)return'';return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function fmtPct(n,digits){if(n==null||isNaN(n))return'—';return(Number(n)*(Math.abs(n)<=1?100:1)).toFixed(digits==null?0:digits)+'%'}
function fmtPrice(n){if(!n||n==0)return'$0';if(n>=1000)return'$'+Number(n).toLocaleString(undefined,{maximumFractionDigits:0});if(n>=1)return'$'+Number(n).toFixed(2);return'$'+Number(n).toFixed(4)}
function fmtRange(r){if(!r||(!r.min&&!r.max))return'$? — $?';var k=function(v){return v>=1000?('$'+(v/1000).toFixed(1)+'k'):('$'+Math.round(v))};return k(r.min||0)+' — '+k(r.max||0)}
function fmtAgo(iso){if(!iso)return'';var d=new Date(iso);var m=Math.floor((Date.now()-d.getTime())/60000);if(m<1)return'now';if(m<60)return m+'m ago';var h=Math.floor(m/60);if(h<24)return h+'h ago';return Math.floor(h/24)+'d ago'}
function colorFor(action,direction){
  var a=(action||'').toUpperCase(), d=(direction||'').toLowerCase();
  if(a==='BUY'||d==='bullish'||d==='up')return{cls:'buy',name:'var(--buy)'};
  if(a==='SELL'||d==='bearish'||d==='down')return{cls:'sell',name:'var(--sell)'};
  return{cls:'warn',name:'var(--warn)'};
}

function cycleAsset(){
  var i=ASSETS.indexOf(asset);
  asset=ASSETS[(i+1)%ASSETS.length];
  document.getElementById('cur-asset').textContent=asset;
  if($('#s-home.on'))loadHome();
}

function selAsset(a){
  if(a===asset)return;
  asset=a;
  var cur=document.getElementById('cur-asset');if(cur)cur.textContent=asset;
  // Track asset open for personal layer in Feed
  try{fetch('/api/miniapp/track-asset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tgId||''),asset:a})}).catch(function(){});}catch(e){}
  if(document.getElementById('s-home').classList.contains('on'))loadHome();
  else if(document.getElementById('s-feed').classList.contains('on'))loadFeed();
  else if(document.getElementById('s-edge').classList.contains('on'))loadEdge();
}

function sw(t){
  document.querySelectorAll('.scr').forEach(function(s){s.classList.remove('on')});
  document.querySelectorAll('.nb').forEach(function(b){b.classList.remove('on')});
  var s=document.getElementById('s-'+t);if(s)s.classList.add('on');
  var b=document.querySelector('.nb[data-t="'+t+'"]');if(b)b.classList.add('on');
  var hdr=document.getElementById('app-hdr');
  // Home and Profile have their own sticky logo — hide the global header
  if(hdr){hdr.classList.remove('hide');}
  window.scrollTo(0,0);
  if(t==='news')loadNews();
  if(t==='home')loadHome();
  if(t==='feed')loadFeed();
  if(t==='edge')loadEdge();
  if(t==='profile')loadProfile();
}

async function fetchJSON(url){
  try{var r=await fetch(url,{headers:{'Accept':'application/json'}});if(!r.ok)throw new Error('http '+r.status);return await r.json();}catch(e){return null}
}

/* ═════════════ ICONS (custom SVG, no emoji) ═════════════ */
function ic(name,cls){
  cls=cls||'';
  var I={
    // Feed cards
    rocket:'<path d="M14 4l6 6-9 9-6-6 9-9z"/><path d="M16 2l6 6"/><circle cx="9.5" cy="14.5" r="1.5" fill="currentColor"/><path d="M5 19l-2 2"/>',
    warn:'<path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18h.01"/>',
    eye:'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/>',
    // News tabs & cards
    bolt:'<path d="M13 3L4 14h6l-1 7 9-11h-6l1-7z"/>',
    attention:'<path d="M12 3l10 18H2L12 3z"/><path d="M12 10v5M12 18h.01"/>',
    signal:'<path d="M4 12l3-3 4 4 4-6 5 5" stroke-linecap="round"/>',
    news:'<path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    chat:'<path d="M21 12a8 8 0 11-16 0 8 8 0 0116 0z"/><path d="M8 11h8M8 14h5" stroke-linecap="round"/>',
    dot:'<circle cx="12" cy="12" r="4" fill="currentColor"/>',
    // Edge / paywall
    unlock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 118 0"/>',
    lock:'<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 018 0v4"/>',
    check:'<path d="M5 13l4 4L19 7" stroke-linecap="round"/>',
    spark:'<path d="M12 2v6M12 16v6M2 12h6M16 12h6M5 5l4 4M15 15l4 4M5 19l4-4M15 9l4-4" stroke-linecap="round"/>',
    // Status dots
    pulse:'<circle cx="12" cy="12" r="5" fill="currentColor"/>',
  };
  var path=I[name]||I.dot;
  return '<svg class="ic '+cls+'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+path+'</svg>';
}

/* ═════════════ NEWS (Market Awareness) ═════════════ */
var _newsTab='all', _newsRefreshTimer=null, _newsData=null;

async function loadNews(){
  var el=document.getElementById('s-news');
  if(!_newsData)el.innerHTML='<div class="spin">LOADING · MARKET</div>';
  var d=await fetchJSON('/api/miniapp/news/v2?tab='+_newsTab+'&limit=60&telegram_id='+encodeURIComponent(tgId||''));
  if(!d||!d.ok){el.innerHTML='<div class="err">Failed to load</div>';return}
  // Save social for paywall
  try{window._lastSocial=d.socialProof||window._lastSocial;}catch(e){}
  _newsData=d;
  renderNews();
  // Auto-refresh every 25s while News tab is active
  if(_newsRefreshTimer)clearInterval(_newsRefreshTimer);
  _newsRefreshTimer=setInterval(function(){
    if(document.getElementById('s-news').classList.contains('on'))loadNews();
    else{clearInterval(_newsRefreshTimer);_newsRefreshTimer=null;}
  },25000);
}

function setNewsTab(t){
  if(t===_newsTab)return;
  _newsTab=t;
  _newsData=null;
  loadNews();
}

function renderNews(){
  var el=document.getElementById('s-news');
  var d=_newsData||{};
  var h=d.hero||{};
  var live=d.live||{};
  var counters=d.counters||{};
  var items=d.items||[];

  var html='';
  // Hero (dynamic emotion)
  // Render hero emoji/icon: if looks like emoji, use SVG equivalent
  var emSvg='';
  var em=h.emoji||'';
  if(em==='\u26A1'||em==='⚡')emSvg='<svg width="30" height="30" viewBox="0 0 24 24" fill="#FFC907"><path d="M13 2 3 14h7l-2 8 10-12h-7l2-8z"/></svg>';
  else if(em==='\uD83D\uDC40'||em==='👀')emSvg='<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#6366F1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
  else if(em==='\u26A0\uFE0F'||em==='⚠️'||em==='⚠')emSvg='<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#FF6B00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
  else if(em==='\uD83D\uDE80'||em==='🚀')emSvg='<svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#22C55E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/></svg>';
  html+='<div class="nw-hero">';
  html+='<div class="nw-hero-em">'+(emSvg||esc(em||'·'))+'</div>';
  html+='<div class="nw-hero-t">'+esc(h.title||'Market quiet')+'</div>';
  if(h.subtitle)html+='<div class="nw-hero-s">'+esc(h.subtitle)+'</div>';
  html+='</div>';

  // Live strip
  var mins=fmtRelFromISO(live.updatedAt);
  html+='<div class="nw-live"><span class="dot"></span><span class="lv-t">Live · updating</span><span class="lv-sep">·</span><span class="lv-w">Watching '+(live.watching||0)+' signals</span><span class="lv-sep">·</span><span class="lv-up">Updated '+mins+'</span></div>';

  // Sub-tabs
  var tabs=[['all','All'],['signals','Signals'],['news','News'],['social','Social']];
  html+='<div class="nw-tabs">';
  tabs.forEach(function(t){
    var cnt=counters[t[0]]||0;
    var active=_newsTab===t[0];
    html+='<div class="nw-tab '+(active?'on':'')+'" onclick="setNewsTab(\''+t[0]+'\')">'+esc(t[1])+(cnt>0?' <span class="cn">'+cnt+'</span>':'')+'</div>';
  });
  html+='</div>';

  // Items (with stream-reset every 6)
  if(!items.length){
    html+='<div class="nw-empty">No activity in this tab · try another</div>';
  }else{
    items.forEach(function(it,i){
      html+=renderNewsCard(it);
      if((i+1)%6===0 && i+1<items.length){
        html+='<div class="nw-reset">● '+items.length+' signals forming right now · check back shortly</div>';
      }
    });
    html+='<div class="nw-reset">● '+items.length+' signals forming right now · check back shortly</div>';
  }

  // Animate existing items (diff-friendly)
  el.innerHTML=html;
}

function feedIcon(stage,isPersonal){
  if(isPersonal)return ic('eye','ic-pur');
  if(stage==='CONFIRMED')return ic('rocket','ic-buy');
  return ic('warn','ic-warn');
}

function renderNewsCard(it){
  var t=it.type||'signal';
  var impCls={'High':'hi','Medium':'md','Low':'lo'}[it.impact]||'lo';
  var dirCls=it.direction==='BULLISH'?'bull':(it.direction==='BEARISH'?'bear':'');
  var typeLbl={'signal':'SIGNAL','news':'NEWS','social':'SOCIAL'}[t]||t.toUpperCase();
  var typeIcon=t==='signal'?ic('bolt','ic-pur'):(t==='social'?ic('chat','ic-cya'):ic('news','ic-tx'));
  var relCls=it.relevantToYou?' rel':'';
  var html='<div class="nw-card type-'+t+relCls+'" onclick="newsOpenEdge(\''+esc(it.ctaAsset)+'\')">';
  html+='<div class="nw-c-hdr"><span class="nw-c-type">'+typeIcon+' '+typeLbl+'</span>';
  html+='<span class="nw-c-as">'+esc(it.asset)+'</span>';
  html+='<span class="nw-c-imp imp-'+impCls+'">'+it.impact+'</span></div>';
  html+='<div class="nw-c-ttl">'+esc(it.title)+'</div>';
  if(it.relevantToYou){html+='<div class="nw-c-rel">● Relevant to you</div>';}
  html+='<div class="nw-c-int">→ '+esc(it.interpretation)+'</div>';
  if(it.sources && it.sources.length){
    html+='<div class="nw-c-src"><b>Source:</b> '+it.sources.map(esc).join(' · ')+'</div>';
  }
  html+='<div class="nw-c-ft"><span class="nw-c-tm">'+esc(it.timing)+'</span><span class="nw-c-cta '+dirCls+'">'+esc(it.ctaLabel||'→ Open setup')+'</span></div>';
  html+='</div>';
  return html;
}

function newsOpenEdge(a){
  // Track click — powers personalization on next News load
  if(a&&tgId){
    try{fetch('/api/miniapp/track-asset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tgId),asset:a})}).catch(function(){});}catch(e){}
  }
  if(a&&a!==asset){selAsset(a);}else{sw('edge');}
  if(a)sw('edge');
}

function fmtRelFromISO(iso){
  if(!iso)return 'just now';
  try{
    var d=new Date(iso);
    var m=Math.max(0,Math.round((Date.now()-d.getTime())/60000));
    if(m<1)return 'just now';
    if(m<60)return m+'m ago';
    return Math.round(m/60)+'h ago';
  }catch(e){return 'just now'}
}

/* ═════════════ HOME ═════════════ */
var _homeHorizon='30D';
async function loadHome(){
  var el=document.getElementById('s-home');
  el.innerHTML='<div class="spin">LOADING · METABRAIN</div>';
  // Fetch home + chart-series in parallel (chart-series = real OHLCV + projection)
  var [h,ch]=await Promise.all([
    fetchJSON('/api/miniapp/home?asset='+asset),
    fetchJSON('/api/miniapp/chart-series?symbol='+asset+'&horizon='+_homeHorizon)
  ]);
  if(!h||!h.ok){el.innerHTML='<div class="err">Failed to load</div>';return}
  el.innerHTML=renderHome(h,ch);
}

async function setHorizon(hz){
  if(_homeHorizon===hz)return;
  _homeHorizon=hz;
  // Re-fetch only chart; re-render card in place
  var wrap=document.getElementById('ps-wrap');
  if(wrap)wrap.innerHTML='<div class="spin" style="padding:30px 0">LOADING</div>';
  var ch=await fetchJSON('/api/miniapp/chart-series?symbol='+asset+'&horizon='+hz);
  if(wrap)wrap.innerHTML=renderMiniChart(ch,{},{},ch&&ch.currentPrice||0);
}

function renderHome(h,ch){
  var d=h.decision||{}, ap=h.actionPlan||{}, st=h.structure||{}, pr=h.pressure||{}, ms=h.marketStory||{}, why=h.why||[];
  var price=h.price||(ch&&ch.currentPrice)||0;
  var rawAction=(d.action||'').toUpperCase();
  // ── Normalize to 4 canonical statuses: WAIT / WATCH / READY / GO ──
  var STATUS=normalizeStatus(rawAction,d);
  var col=STATUS.cls;            // warn / neu / pur / buy
  var conf=Math.round((d.confidence||0)*100);
  var confGrade=gradeConfidence(conf);  // {label, cls}
  var strength=d.strength||'LOW';
  var risk=d.riskLevel||'HIGH';
  var emove=d.expectedMovePct||0;
  var emSign=emove>0?'+':(emove<0?'':'±');
  // Phase E1 / A2.5 — localized edge·risk line via i18n template + level dictionary.
  var __levelKey=function(lvl){
    var k=(lvl||'').toString().toUpperCase();
    return {'LOW':'tg.level.low','MEDIUM':'tg.level.medium','MED':'tg.level.medium','HIGH':'tg.level.high'}[k];
  };
  var __levelText=function(lvl, fallback){
    var k=__levelKey(lvl); return k?__t(k, fallback||titleCase(lvl)):titleCase(lvl||fallback||'');
  };
  var edgeRiskLn=__t('tg.state.edgeRiskLine','{strength} edge · {risk} risk')
    .replace('{strength}', __levelText(strength,'Low'))
    .replace('{risk}',    __levelText(risk,'High'));

  var html='';

  // ═══ Compact asset tabs (global sticky logo lives in app-hdr) ═══
  html+='<div class="hm-tabs">';
  ASSETS.forEach(function(a){
    html+='<div class="hm-t '+(a===asset?'on':'')+'" onclick="selAsset(\''+a+'\')">'+a+'</div>';
  });
  html+='</div>';

  // ═══ HERO DECISION — STATUS ═══ (NO more EARLY badge — it conflicts with WAIT)
  html+='<div class="cd hero">';
  html+='<div class="hero-asset">'+esc(h.asset||asset)+'</div>';
  html+='<div class="hero-word color-'+col+'">'+esc(STATUS.label)+'</div>';
  html+='<div class="hero-edge">'+esc(edgeRiskLn)+'</div>';
  // ═══ Retention hook: fill the void under WAIT/WATCH ═══
  if(STATUS.key==='WAIT'||STATUS.key==='WATCH'){
    var driversSeen=(st&&st.modules&&st.modules.length)||6;
    var boltSvg='<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align:-2px;margin-right:5px;color:var(--pur)"><path d="M13 2 3 14h7l-2 8 10-12h-7l2-8z"/></svg>';
    html+='<div class="hero-forming">'+boltSvg+__t('tg.state.nothingForming','Nothing yet — alignment forming')+'</div>';
    html+='<div class="hero-forming-sub">'+__t('tg.state.watchingDrivers','Watching {n} market drivers').replace('{n}', driversSeen)+'</div>';
    html+='<div class="hero-forming-hint">'+__t('tg.state.seeWhatsBuilding','→ See what\u2019s building')+'</div>';
  }
  html+='<div class="hero-conf-wrap"><div class="hero-conf-bar"><div class="hero-conf-fill bg-'+col+'" style="width:'+Math.max(conf,3)+'%"></div></div>';
  html+='<div class="hero-conf-row"><span>'+__t('tg.state.confidence','Confidence')+'</span><span class="hero-conf-val">'+conf+'% <span style="color:var(--mu);font-weight:700;letter-spacing:.3px">· '+__levelText(confGrade.label, confGrade.label)+'</span></span></div></div>';
  html+='<div class="hero-metrics">';
  html+='<div class="hero-m"><div class="hero-mv">'+fmtPrice(price)+'</div><div class="hero-ml">'+__t('tg.label.price','Price')+'</div></div>';
  html+='<div class="hero-m"><div class="hero-mv color-'+(emove>0?'buy':emove<0?'sell':'neu')+'">'+emSign+fmtPct(emove,1)+'</div><div class="hero-ml">'+__t('tg.label.expectedMove','Expected Move')+'</div></div>';
  html+='<div class="hero-m"><div class="hero-mv" style="font-size:12px">'+esc(fmtRange(d.range30d))+'</div><div class="hero-ml">30D '+__t('tg.label.rangePrefix','Range')+'</div></div>';
  html+='</div></div>';

  // ═══ STRUCTURE SNAPSHOT ═══ (renamed from PREDICTION SNAPSHOT — restraint vocab)
  html+=renderMiniChart(ch,d,st,price);

  // ═══ ACTION PLAN ═══ (Action = function of STATUS)
  var actionLbl=STATUS.action;   // Monitor / Observe / Prepare / Enter
  var actionLblLocalized = (function(a){
    var map = {'Monitor':'tg.action.monitor'};
    var k = map[a]; return k ? __t(k, a) : a;
  })(actionLbl);
  html+='<div class="cd"><div class="cd-ttl">'+__t('tg.label.actionPlan','Action Plan')+'</div>';
  html+='<div class="ap-pill bg-'+col+'-s color-'+col+'">'+__t('tg.action.actionPrefix','Action:')+' '+esc(actionLblLocalized)+'</div>';
  if(ap.summary)html+='<div style="font-size:12px;color:var(--mu);line-height:1.4;margin-bottom:10px;font-style:italic">'+esc(ap.summary)+'</div>';
  // Retention: when WAIT/WATCH, hint an upcoming alignment + progress
  if(STATUS.key==='WAIT'||STATUS.key==='WATCH'){
    var totalMods=(st&&st.modules&&st.modules.length)||6;
    var alignedMods=0;
    if(st&&st.modules){st.modules.forEach(function(m){var dd=(m.direction||'').toLowerCase();if(dd.indexOf('bull')>=0||dd.indexOf('bear')>=0)alignedMods++;});}
    html+='<div style="font-size:11px;color:var(--pur);font-weight:700;letter-spacing:.3px;margin:-6px 0 4px 0;padding:6px 8px;background:rgba(168,85,247,.08);border-radius:6px">● '+__t('tg.state.nextOpportunity','Next alignment forming')+'</div>';
    var alignTpl = __t('tg.state.couldTrigger','ALIGNMENT: {n}/{total} BUILDING · CONFIRMATION ANYTIME');
    html+='<div style="font-size:10px;color:var(--mu);font-weight:700;letter-spacing:.5px;margin:0 0 10px 0;padding:0 8px;text-transform:uppercase">'+alignTpl.replace('{n}', alignedMods).replace('{total}', totalMods)+'</div>';
  }
  html+=apRow('target',__t('tg.label.formationZone','Formation Zone'),ap.entryZone?(fmtPrice(ap.entryZone.min||0)+' — '+fmtPrice(ap.entryZone.max||0)):__t('tg.state.notFormed','not formed'));
  html+=apRow('x',__t('tg.label.invalidation','Invalidation'),ap.invalidation?fmtPrice(ap.invalidation):__t('tg.state.notDefined','not defined'),'red');
  html+=apRow('trend',__t('tg.label.nextConfirmation','Next Confirmation'),ap.nextTrigger||__t('tg.state.scanningForFormation','Scanning for formation'));
  html+='</div>';

  // ═══ COGNITIVE TEASER (Task 3) ═══ — 3 short module lines + PRO hook
  // Placement: directly under Action Plan, before Market Story / FOMO PRO banner.
  // Data source: composer payload `h` (technicalAnalysis / sentimentRuntime /
  // fractalRuntime). No extra fetch, no recompute.
  try{
    var __teaserPro=(h.userTier||(window.__fomoUserTier)||'FREE').toString().toUpperCase()==='PRO';
    html+=renderCognitiveTeaser(h,__teaserPro);
  }catch(__e){}

  // ═══ MARKET STORY ═══
  if(ms&&(ms.text||ms.regime)){
    var regimeMap={'UNCERTAIN':{c:'var(--pur)',b:'rgba(168,85,247,.15)'},'BULLISH':{c:'var(--buy)',b:'rgba(34,197,94,.15)'},'BEARISH':{c:'var(--sell)',b:'rgba(239,68,68,.15)'},'CONSOLIDATION':{c:'var(--warn)',b:'rgba(234,179,8,.15)'},'TRENDING':{c:'var(--ind)',b:'rgba(99,102,241,.15)'}};
    var rm=regimeMap[(ms.regime||'').toUpperCase()]||{c:'var(--mu)',b:'rgba(107,114,128,.15)'};
    html+='<div class="cd"><div class="cd-ttl">'+__t('tg.label.marketStory','Market Story');
    if(ms.regime)html+='<span class="badge" style="color:'+rm.c+';background:'+rm.b+'">'+esc(titleCase(ms.regime))+'</span>';
    html+='</div>';
    html+='<div style="font-size:13px;line-height:1.5;color:var(--tx)">'+esc(ms.text||'—')+'</div>';
    html+='</div>';
  }

  // ═══ STRUCTURE ═══ (Neutral → "No clear direction")
  if(st&&(st.h24||st.d7||st.d30)){
    html+='<div class="cd"><div class="cd-ttl">'+__t('tg.label.marketStructure','Structure');
    if(st.alignment)html+='<span class="badge" style="color:var(--pur);background:rgba(168,85,247,.15)">'+esc(st.alignment)+'</span>';
    html+='</div>';
    html+='<div class="st-pills">';
    ['h24','d7','d30'].forEach(function(k,i){
      var x=st[k]||{};var c=colorFor('',x.direction);
      var lbl=['24H','7D','30D'][i];
      var dirLbl=humanDirection(x.direction);
      html+='<div class="st-p"><div class="st-pl">'+lbl+'</div><div class="st-pd color-'+c.cls+'">'+esc(dirLbl)+'</div><div class="st-pc">'+Math.round((x.confidence||0)*100)+'%</div></div>';
    });
    html+='</div>';
    if(st.insight)html+='<div class="st-ins">'+esc(st.insight)+'</div>';
    html+='</div>';
  }

  // ═══ NET PRESSURE ═══
  if(pr&&pr.netDirection){
    var netC=colorFor('',pr.netDirection).cls;
    var netLbl=humanDirection(pr.netDirection);
    html+='<div class="cd"><div class="cd-ttl">Net Pressure</div>';
    html+='<div class="pr-hero"><div class="pr-big color-'+netC+'">'+esc(netLbl)+'</div><div class="pr-sub">'+esc(titleCase(pr.netStrength||'Low'))+'</div></div>';
    if(pr.summary)html+='<div class="pr-desc">'+esc(pr.summary)+'</div>';
    html+='</div>';
  }

  // ═══ BREAKDOWN ═══ (NEUTRAL→Mixed, EARLY→Forming, NONE→Inactive)
  if(st&&st.modules&&st.modules.length){
    html+='<div class="cd"><div class="cd-ttl">'+__t('tg.label.breakdown','Breakdown')+'</div>';
    st.modules.forEach(function(m){
      var c=colorFor('',m.direction);
      var tagLbl=humanModuleState(m.direction);
      html+='<div class="bk-row"><div style="flex:1;min-width:0"><div class="bk-name">'+esc(m.module||m.name)+'</div>';
      if(m.insight)html+='<div class="bk-val">'+esc(m.insight)+'</div>';
      html+='</div><span class="bk-tag bg-'+c.cls+'-s color-'+c.cls+'">'+esc(tagLbl)+'</span></div>';
    });
    html+='</div>';
  }

  // ═══ WHY THIS DECISION ═══ (heading tied to STATUS)
  if(why&&why.length){
    html+='<div class="why-toggle" onclick="toggleWhy(this)"><span>Why '+esc(STATUS.label)+'</span><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg></div>';
    html+='<div class="why-body">';
    why.forEach(function(w){
      if(typeof w==='string')html+='<div class="why-item">'+esc(w)+'</div>';
      else html+='<div class="why-item"><b>'+esc(w.label||w.module||'')+'</b> — '+esc(w.reason||w.text||w.narrative||'')+'</div>';
    });
    html+='</div>';
  }

  // ═══ QUICK ACTIONS ═══
  html+='<div class="qa">';
  html+=qab('why','Why','<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 016 0c0 1-1 2-3 2v2"/><line x1="12" y1="16" x2="12" y2="17"/>','function(){var t=document.querySelector(\'.why-toggle\');if(t)t.scrollIntoView({behavior:\'smooth\'});toggleWhy(t);}');
  html+=qab('feed','Feed','<path d="M4 4h11a3 3 0 013 3v11H7a3 3 0 01-3-3V4z"/><path d="M8 8h7M8 12h7M8 16h5"/>','function(){sw(\'feed\');}');
  html+=qab('edge','Edge','<path d="M3 17l5-5 4 4 8-8"/><path d="M14 8h6v6"/>','function(){sw(\'edge\');}');
  html+=qab('alerts','Alerts','<path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M10 21a2 2 0 004 0"/>','function(){sw(\'profile\');setTimeout(function(){var el=document.getElementById(\'push-rows\');if(el)el.scrollIntoView({behavior:\'smooth\',block:\'center\'})},400);}');
  html+='</div>';

  return html;
}

/* ── STATE LANGUAGE HELPERS (single source of truth) ── */
function normalizeStatus(raw,d){
  // Map any action to WAIT / WATCH / READY / GO
  var r=(raw||'').toUpperCase();
  var m=(d&&d.mode||'').toUpperCase();
  if(r==='BUY'||r==='SELL'||m==='CONFIRMED')
    return {key:'GO',label:'GO',cls:'buy',action:'Enter'};
  if(r==='PREPARE'||m==='DEFENSIVE'||m==='AGGRESSIVE')
    return {key:'READY',label:'READY',cls:'pur',action:'Prepare'};
  if(r==='WAIT'||m==='EARLY')
    return {key:'WAIT',label:'WAIT',cls:'warn',action:'Monitor'};
  // NEUTRAL / NORMAL / WHITE / default → WATCH (grey)
  return {key:'WATCH',label:'WATCH',cls:'neu',action:'Observe'};
}
function gradeConfidence(p){
  p=p||0;
  if(p>=80)return{label:'Strong',cls:'buy'};
  if(p>=60)return{label:'High',cls:'buy'};
  if(p>=30)return{label:'Medium',cls:'warn'};
  return{label:'Low',cls:'mu'};
}
function humanDirection(d){
  // Structure / pressure direction in human language
  var x=(d||'').toLowerCase();
  if(x.indexOf('bull')>=0)return 'Bullish';
  if(x.indexOf('bear')>=0)return 'Bearish';
  if(x.indexOf('mix')>=0)return 'Mixed';
  // neutral / unknown / empty
  return __t('tg.state.noDirection','No clear direction');
}
function humanModuleState(d){
  // Breakdown tag: NEUTRAL→Mixed, EARLY→Forming, NONE→Inactive
  var x=(d||'').toLowerCase();
  if(x.indexOf('bull')>=0)return 'Bullish';
  if(x.indexOf('bear')>=0)return 'Bearish';
  if(x.indexOf('early')>=0||x.indexOf('form')>=0)return 'Forming';
  if(x.indexOf('none')>=0||x.indexOf('inactive')>=0||x==='off')return 'Inactive';
  return 'Mixed';
}
function titleCase(s){
  if(!s)return '';
  s=String(s).toLowerCase();
  return s.charAt(0).toUpperCase()+s.slice(1);
}

/* ─── COGNITIVE LANGUAGE HELPERS (Task 3 · TG Cognitive Layer) ──────────────
   STRICT RULES (Truthful Degradation):
   * NO BUY / SELL / signal fired / guaranteed / profit / winrate / alpha
   * NO entry-now / 100% / fired
   * Allowed: confirmation missing, pressure rising, compression persists,
     deployment withheld, alignment incomplete, full breakdown
   * Phrases derived from composer payload (technicalAnalysis, sentimentRuntime,
     fractalRuntime). NO new fetches, NO cognition recompute.
*/
function cogStateClass(state){
  var s=(state||'').toLowerCase();
  if(s==='neutral'||s==='active')return 'pur';
  if(s==='unavailable'||s==='degraded'||s==='off'||s==='inactive')return 'muted';
  if(s==='compression'||s==='range'||s==='balanced')return 'warn';
  return 'neu';
}
function cogTaPhrase(ta){
  // technicalAnalysis: {state, trend, momentum, rsi, rsiValue, alignedIndicators, reasons[], degraded}
  if(!ta||ta.degraded||ta.state==='unavailable'){
    return {head:'data thin · structure unclear', detail:'Insufficient signal to express structural conviction.'};
  }
  var trend=(ta.trend||'').toLowerCase();
  var mom=(ta.momentum||'').toLowerCase();
  var aligned=ta.alignedIndicators||0;
  var head='';
  if(trend==='up'&&aligned>=2)head='trend improving · confirmation missing';
  else if(trend==='down'&&aligned>=2)head='trend weakening · confirmation missing';
  else if(trend==='up')head='structure leaning up · alignment incomplete';
  else if(trend==='down')head='structure leaning down · alignment incomplete';
  else head='structure flat · no directional pressure';
  // Detail line — for PRO
  var parts=[];
  if(ta.trendSlopePct!=null)parts.push('slope '+(ta.trendSlopePct>0?'+':'')+Number(ta.trendSlopePct).toFixed(2)+'%');
  if(mom)parts.push('momentum '+mom);
  if(ta.rsi)parts.push('rsi '+ta.rsi+(ta.rsiValue!=null?' ('+Math.round(ta.rsiValue)+')':''));
  parts.push(aligned+' indicators aligned');
  return {head:head, detail:parts.join(' · ')};
}
function cogSentPhrase(se){
  // sentimentRuntime: {state, pressure, score, crowd, fearEuphoria, reason[], degraded, sample}
  if(!se||se.degraded||se.state==='unavailable'||!se.sample){
    return {head:'crowd data thin', detail:'No sentiment events in current window. No crowd pressure to read.'};
  }
  var press=(se.pressure||'').toLowerCase();
  var score=se.score||0;
  var head='';
  if(press==='bullish'||score>0.3)head='crowd pressure rising';
  else if(press==='bearish'||score<-0.3)head='crowd pressure cooling';
  else head='crowd undecided · balanced pressure';
  var crowd=se.crowd||{};
  var parts=[];
  if(crowd.bullishShare!=null)parts.push((crowd.bullishShare*100).toFixed(0)+'% bullish');
  if(crowd.bearishShare!=null)parts.push((crowd.bearishShare*100).toFixed(0)+'% bearish');
  if(se.fearEuphoria&&se.fearEuphoria!=='unknown')parts.push(se.fearEuphoria);
  if(se.sample)parts.push('sample n='+se.sample);
  return {head:head, detail:parts.join(' · ')||'Pressure reading active, conviction soft.'};
}
function cogFractalPhrase(fr){
  // fractalRuntime: {state, phase, structure:{trend,breakoutRisk,breakdownRisk,rangeQuality}, horizons, reasons[]}
  if(!fr||fr.state==='unavailable'){
    return {head:'fractal data thin', detail:'No structural memory available for this asset.'};
  }
  var phase=(fr.phase||fr.state||'').toLowerCase();
  var head='';
  if(phase==='compression')head='compression persists · no expansion phase';
  else if(phase==='expansion')head='expansion forming · structure opening';
  else if(phase==='range')head='range bound · breakout pending';
  else head='structure quiet · phase unconfirmed';
  var s=fr.structure||{};
  var parts=[];
  if(s.trend)parts.push('trend '+s.trend);
  if(s.rangeQuality)parts.push('range '+s.rangeQuality);
  if(s.breakoutRisk)parts.push('breakout '+s.breakoutRisk);
  if(s.breakdownRisk&&s.breakdownRisk!==s.breakoutRisk)parts.push('breakdown '+s.breakdownRisk);
  return {head:head, detail:parts.join(' · ')||'Fractal memory present but unaligned with new pressure.'};
}
/* ─── HOME TEASER · 3 short cognition lines + paywall hook ─── */
function renderCognitiveTeaser(h,isPro){
  if(!h)return '';
  var ta=cogTaPhrase(h.technicalAnalysis);
  var se=cogSentPhrase(h.sentimentRuntime);
  var fr=cogFractalPhrase(h.fractalRuntime);
  var asset=h.asset||'';
  var action=(h.decision&&(h.decision.action||'')).toUpperCase()||'WAIT';
  var html='';
  html+='<div class="cog-teaser '+(isPro?'pro':'')+'">';
  html+='<div class="cog-teaser-hd">';
    html+='<span class="cog-teaser-ttl">'+__t('tg.label.marketStructure','Market Structure')+'</span>';
  html+='<span class="cog-teaser-state">'+esc(asset)+' · '+esc(action)+'</span>';
  html+='</div>';
  html+='<div class="cog-teaser-row"><div class="cog-teaser-mod">TA</div><div class="cog-teaser-phr">'+esc(ta.head)+'</div></div>';
  html+='<div class="cog-teaser-row"><div class="cog-teaser-mod">Sentiment</div><div class="cog-teaser-phr">'+esc(se.head)+'</div></div>';
  html+='<div class="cog-teaser-row"><div class="cog-teaser-mod">Fractal</div><div class="cog-teaser-phr">'+esc(fr.head)+'</div></div>';
  html+='<div class="cog-teaser-foot">';
  if(isPro){
    html+='<span class="cog-teaser-foot-t">✓ PRO · full breakdown unlocked</span>';
    html+='<span class="cog-teaser-foot-a" onclick="sw(\'edge\')">Open ›</span>';
  }else{
    html+='<span class="cog-teaser-foot-t">'+__t('tg.pro.full','Full breakdown available in PRO')+'</span>';
    html+='<span class="cog-teaser-foot-a" onclick="sw(\'edge\')">'+__t('tg.pro.whyHoldBack','Why hold back ›')+'</span>';
  }
  html+='</div>';
  html+='</div>';
  return html;
}
/* ─── EDGE EXPANDED · per-module sections + locked PRO details ─── */
function renderCognitiveBreakdown(h,isPro){
  if(!h)return '';
  var ta=cogTaPhrase(h.technicalAnalysis);
  var se=cogSentPhrase(h.sentimentRuntime);
  var fr=cogFractalPhrase(h.fractalRuntime);
  var taSt=cogStateClass((h.technicalAnalysis||{}).state);
  var seSt=cogStateClass((h.sentimentRuntime||{}).state);
  var frSt=cogStateClass((h.fractalRuntime||{}).state);
  var html='';
  html+='<div class="cog-edge">';
  html+='<div class="cog-edge-hd">Why AI Holds Back</div>';
  html+='<div class="cog-edge-sub">Three cognition modules below — what each one sees right now, and why deployment remains withheld.</div>';
  // TA
  html+='<div class="cog-mod-block">';
  html+='<div class="cog-mod-hd"><span class="cog-mod-nm">Technical Analysis</span><span class="cog-mod-st '+taSt+'">'+esc(((h.technicalAnalysis||{}).state||'idle').toUpperCase())+'</span></div>';
  html+='<div class="cog-mod-phr">'+esc(ta.head)+'</div>';
  html+='<div class="cog-mod-detail '+(isPro?'':'locked')+'">'+esc(ta.detail)+'</div>';
  html+='</div>';
  // Sentiment
  html+='<div class="cog-mod-block">';
  html+='<div class="cog-mod-hd"><span class="cog-mod-nm">Sentiment</span><span class="cog-mod-st '+seSt+'">'+esc(((h.sentimentRuntime||{}).state||'idle').toUpperCase())+'</span></div>';
  html+='<div class="cog-mod-phr">'+esc(se.head)+'</div>';
  html+='<div class="cog-mod-detail '+(isPro?'':'locked')+'">'+esc(se.detail)+'</div>';
  html+='</div>';
  // Fractal
  html+='<div class="cog-mod-block">';
  html+='<div class="cog-mod-hd"><span class="cog-mod-nm">Fractal</span><span class="cog-mod-st '+frSt+'">'+esc(((h.fractalRuntime||{}).state||'idle').toUpperCase())+'</span></div>';
  html+='<div class="cog-mod-phr">'+esc(fr.head)+'</div>';
  html+='<div class="cog-mod-detail '+(isPro?'':'locked')+'">'+esc(fr.detail)+'</div>';
  html+='</div>';
  // CTA / foot
  if(isPro){
    html+='<div class="cog-edge-pro-foot">✓ PRO · full module breakdown unlocked</div>';
  }else{
    html+='<div class="cog-edge-cta" onclick="showPaywall()">';
    html+='<span class="cog-edge-cta-t">PRO shows full module breakdown</span>';
    html+='<span class="cog-edge-cta-a">›</span>';
    html+='</div>';
  }
  html+='</div>';
  return html;
}

function apRow(icon,label,value,cls){
  var icons={
    target:'<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    x:'<line x1="5" y1="5" x2="19" y2="19"/><line x1="19" y1="5" x2="5" y2="19"/>',
    trend:'<polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/>'
  };
  return '<div class="ap-row"><div class="ap-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'+icons[icon]+'</svg></div><div style="flex:1"><div class="ap-lbl">'+esc(label)+'</div><div class="ap-val '+(cls||'')+'">'+esc(value)+'</div></div></div>';
}

function renderMiniChart(ch,d,st,price){
  // Real mini chart — history line + NOW dot + dashed projection + target dot
  var ok=ch&&ch.ok;
  var ps=(ch&&ch.priceSeries)||[];
  var pj=(ch&&ch.projectedSeries)||[];
  var cur=(ch&&ch.currentPrice)||price||0;
  var bias=(ch&&ch.bias)||'Neutral';
  var biasLower=bias.toLowerCase();
  var biasCol=biasLower.indexOf('bull')>=0?'buy':biasLower.indexOf('bear')>=0?'sell':'warn';
  var biasC={buy:'var(--buy)',sell:'var(--sell)',warn:'var(--warn)'}[biasCol];
  var biasEmoji=biasLower.indexOf('bull')>=0?'↗':biasLower.indexOf('bear')>=0?'↘':'→';
  var biasReadable=biasLower.indexOf('bull')>=0?__t('tg.state.bullishTilt','Bullish tilt'):biasLower.indexOf('bear')>=0?__t('tg.state.bearishTilt','Bearish tilt'):__t('tg.state.noDirection','No clear direction');
  // When MetaBrain has no data, expectedReturn will be 0 — grey out bias
  if(!ok||(Math.abs((ch&&ch.expectedReturn)||0)<0.1 && biasLower.indexOf('neu')>=0)){
    biasC='var(--mu)';biasEmoji='·';biasReadable='Model not ready';
  }
  var conf=(ch&&ch.confidence)||Math.round((d.confidence||0)*100)||0;
  var emovePct=(ch&&ch.expectedReturn)||0;
  var emSign=emovePct>0?'+':(emovePct<0?'':'±');
  var target=(ch&&ch.target)||cur;
  var hz=(ch&&ch.horizon)||_homeHorizon||'30D';

  // Horizon switcher
  var tabs='';
  ['7D','30D','90D'].forEach(function(h){
    tabs+='<div class="ps-hz '+(h===hz?'on':'')+'" onclick="setHorizon(\''+h+'\')">'+h+'</div>';
  });

  var html='<div id="ps-wrap">';
  html+='<div class="ps-card">';
  html+='<div class="ps-hdr">';
  html+='<div class="ps-ttl">'+__t('tg.label.structureSnapshot','Structure · {horizon}').replace('{horizon}', hz)+'</div>';
  html+='<div class="ps-hzs">'+tabs+'</div>';
  html+='</div>';

  if(!ok||ps.length<2){
    html+='<div class="ps-empty">'+__t('tg.state.noChartData','No chart data yet')+'</div>';
    html+='</div></div>';
    return html;
  }

  // Build SVG: 340 x 100
  var W=340,H=100,padL=2,padR=2,padT=8,padB=12;
  var allV=[];
  ps.forEach(function(p){if(p.v>0)allV.push(p.v)});
  pj.forEach(function(p){if(p.v>0)allV.push(p.v)});
  var mn=Math.min.apply(null,allV), mx=Math.max.apply(null,allV);
  if(mx===mn){mx=mn*1.01;mn=mn*0.99}
  var total=ps.length+pj.length;
  function xF(i){return padL+(i/Math.max(total-1,1))*(W-padL-padR)}
  function yF(v){return padT+(1-(v-mn)/(mx-mn))*(H-padT-padB)}

  // History path
  var histPath='';
  ps.forEach(function(p,i){histPath+=(i===0?'M':'L')+xF(i).toFixed(1)+','+yF(p.v).toFixed(1)+' '});
  // Projection path (connects last history to first proj and onwards)
  var off=ps.length-1;
  var projPath='';
  if(pj.length){
    projPath='M'+xF(off).toFixed(1)+','+yF(ps[off].v).toFixed(1);
    pj.forEach(function(p,i){projPath+=' L'+xF(off+i+1).toFixed(1)+','+yF(p.v).toFixed(1)});
  }
  var nowX=xF(off), nowY=yF(ps[off].v);
  var tgtX=xF(total-1), tgtY=yF(pj.length?pj[pj.length-1].v:ps[off].v);

  // Y-axis ticks (top/bottom)
  var topL=mx>=1000?('$'+(mx/1000).toFixed(1)+'K'):('$'+mx.toFixed(0));
  var botL=mn>=1000?('$'+(mn/1000).toFixed(1)+'K'):('$'+mn.toFixed(0));

  var svg='<svg viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="width:100%;height:130px;display:block">';
  // Horizontal grid
  svg+='<line x1="0" y1="'+(padT).toFixed(1)+'" x2="'+W+'" y2="'+(padT).toFixed(1)+'" stroke="var(--bd)" stroke-width=".5" stroke-dasharray="2,3" opacity=".6"/>';
  svg+='<line x1="0" y1="'+((H-padB)/1).toFixed(1)+'" x2="'+W+'" y2="'+(H-padB).toFixed(1)+'" stroke="var(--bd)" stroke-width=".5" stroke-dasharray="2,3" opacity=".6"/>';
  // NOW divider
  svg+='<line x1="'+nowX.toFixed(1)+'" y1="'+padT+'" x2="'+nowX.toFixed(1)+'" y2="'+(H-padB)+'" stroke="var(--mu2)" stroke-width=".6" stroke-dasharray="3,4"/>';
  // History line
  svg+='<path d="'+histPath+'" fill="none" stroke="var(--hist-stroke)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>';
  // Projection line — bias-colored, dashed
  if(projPath)svg+='<path d="'+projPath+'" fill="none" stroke="'+biasC+'" stroke-width="1.8" stroke-dasharray="3,3" stroke-linecap="round" opacity=".95"/>';
  // NOW dot
  svg+='<circle cx="'+nowX.toFixed(1)+'" cy="'+nowY.toFixed(1)+'" r="4" fill="var(--bg)" stroke="'+biasC+'" stroke-width="1.8"/>';
  // Target dot
  if(pj.length)svg+='<circle cx="'+tgtX.toFixed(1)+'" cy="'+tgtY.toFixed(1)+'" r="3" fill="'+biasC+'"/>';
  // Y labels
  svg+='<text x="3" y="'+(padT+3).toFixed(1)+'" font-size="7" fill="var(--mu2)" font-weight="700">'+topL+'</text>';
  svg+='<text x="3" y="'+(H-padB-1).toFixed(1)+'" font-size="7" fill="var(--mu2)" font-weight="700">'+botL+'</text>';
  // NOW label
  svg+='<text x="'+nowX.toFixed(1)+'" y="'+(nowY-9).toFixed(1)+'" font-size="7" fill="'+biasC+'" font-weight="900" text-anchor="middle" letter-spacing=".5">NOW</text>';
  svg+='</svg>';

  html+='<div class="ps-chart">'+svg+'</div>';
  // Bias line under chart
  html+='<div class="ps-bias-row">';
  html+='<span class="ps-bias" style="color:'+biasC+'">'+biasEmoji+' '+esc(biasReadable)+'</span>';
  html+='<span class="ps-target">Target '+fmtPrice(target)+'</span>';
  html+='</div>';
  // Footer metrics
  html+='<div class="ps-ft">';
  html+='<div class="ps-m"><div class="ps-mv" style="color:'+biasC+'">'+emSign+Math.abs(emovePct).toFixed(1)+'%</div><div class="ps-ml">Expected</div></div>';
  html+='<div class="ps-m"><div class="ps-mv">'+conf+'%</div><div class="ps-ml">Confidence</div></div>';
  html+='<div class="ps-m"><div class="ps-mv" style="font-size:13px">'+fmtPrice(cur)+'</div><div class="ps-ml">Current</div></div>';
  html+='</div>';
  html+='</div></div>';
  return html;
}

function d24D_ref(st,k){return st&&st[k]?st[k].direction:'neutral';}

function qab(key,label,icon,fn){
  return '<div class="qab" onclick="('+fn+')()"><div class="qab-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">'+icon+'</svg></div><div class="qab-lbl">'+esc(label)+'</div></div>';
}
function toggleWhy(el){
  if(!el)return;el.classList.toggle('op');var b=el.nextElementSibling;if(b)b.classList.toggle('op');
}

/* ═════════════ FEED ═════════════ */
/* ═════════════ FEED V2 ═════════════ */
var _feedData=null;
var _feedFilter='all';  // all | bullish | bearish
var _feedAssetPin='';   // empty = show all; or specific asset filter

async function loadFeed(){
  var el=document.getElementById('s-feed');
  el.innerHTML='<div class="spin">LOADING · SIGNALS</div>';
  var d=await fetchJSON('/api/miniapp/feed/v2?telegram_id='+encodeURIComponent(tgId)+'&limit=500');
  if(!d||!d.ok){el.innerHTML='<div class="err">Failed to load</div>';return}
  _feedData=d;
  renderFeedV2();
  // Deep link: ?startapp=news_BTC → scroll to card + highlight
  try{
    var p=(tg&&tg.initDataUnsafe&&tg.initDataUnsafe.start_param)||P.get('startapp')||'';
    if(p&&p.indexOf('news_')===0){
      var asset=p.replace('news_','').toUpperCase();
      setTimeout(function(){highlightAsset(asset)},200);
    }
  }catch(e){}
}

function feedFilterCards(cards){
  if(!cards)return[];
  return cards.filter(function(c){
    if(_feedFilter==='bullish' && c.direction!=='BULLISH')return false;
    if(_feedFilter==='bearish' && c.direction!=='BEARISH')return false;
    if(_feedAssetPin && c.asset!==_feedAssetPin)return false;
    return true;
  });
}

function setFeedFilter(f){
  _feedFilter=f;
  renderFeedV2();
}
function toggleAssetPin(a){
  _feedAssetPin=(_feedAssetPin===a?'':a);
  renderFeedV2();
}

function renderFeedV2(){
  var el=document.getElementById('s-feed');
  if(!_feedData){return}
  var d=_feedData;
  var secs=d.sections||{};
  var now=feedFilterCards(secs.now||[]);
  var bld=feedFilterCards(secs.building||[]);
  var pl=feedFilterCards(secs.playedOut||[]);
  var ym=d.youMissed||[];
  var chips=d.assetChips||[];
  var recent=(d.liveState&&d.liveState.recent)||0;

  var html='';
  // Live strip (only if any activity)
  if(recent>0){
    html+='<div class="fv-live"><span class="dot"></span><span>Market moving · <span class="v">'+recent+' move'+(recent===1?'':'s')+'</span> in last 15m</span></div>';
  }

  // Filters
  html+='<div class="fv-filters">';
  html+='<div class="fv-f '+(_feedFilter==='all'?'on':'')+'" onclick="setFeedFilter(\'all\')">All</div>';
  html+='<div class="fv-f '+(_feedFilter==='bullish'?'on':'')+'" onclick="setFeedFilter(\'bullish\')">Bullish</div>';
  html+='<div class="fv-f '+(_feedFilter==='bearish'?'on':'')+'" onclick="setFeedFilter(\'bearish\')">Bearish</div>';
  html+='</div>';

  // Dynamic asset chips
  if(chips.length){
    html+='<div class="fv-chips">';
    chips.forEach(function(c){
      var pinned=_feedAssetPin===c.asset;
      html+='<div class="fv-chip" style="'+(pinned?'background:var(--tx);color:var(--inv);border-color:var(--tx)':'')+'" onclick="toggleAssetPin(\''+c.asset+'\')">'+esc(c.asset)+'<span class="cn">'+c.count+'</span></div>';
    });
    html+='</div>';
  }

  // Sections
  html+=renderFeedSection('Now',now,'NOW');
  html+=renderFeedSection('Building',bld,'BUILDING');
  html+=renderFeedSection('Played out',pl,'PLAYED OUT');

  // You Missed (only if there are played-out items but not shown as section)
  // Already shown in playedOut; skip duplicate.

  if(!now.length && !bld.length && !pl.length){
    html='<div class="fv-empty">No signals in the last 6h · check back soon</div>';
  }else{
    // Return-loop trigger
    var totalForming=(bld.length||0)+(now.filter(function(x){return x.stage!=='CONFIRMED'}).length||0);
    if(totalForming>0){
      html+='<div class="fv-ft-hint"><span class="dot"></span>'+totalForming+' signal'+(totalForming===1?'':'s')+' forming right now · Check back shortly</div>';
    }else{
      html+='<div class="fv-ft-hint">New signals arrive every few minutes · Check back shortly</div>';
    }
  }

  el.innerHTML=html;
}

function renderFeedSection(label,cards,uppercaseLabel){
  if(!cards||!cards.length)return '';
  var html='<div class="fv-sec">';
  html+='<div class="fv-sh">'+esc(uppercaseLabel||label)+' <span class="n">· '+cards.length+'</span></div>';
  cards.forEach(function(c){
    var clr='clr-'+(c.color||'neutral');
    var dirCls=c.direction==='BULLISH'?'bull':(c.direction==='BEARISH'?'bear':'');
    var tag=c.stateTag||'';
    var tagHtml=tag?('<div class="fv-badge '+(tag==='NEW'?'new':'upd')+'">'+tag+'</div>'):'';
    // Retention micro-FOMO line for CONFIRMED / FORMING
    var micro='';
    if(c.stage==='CONFIRMED' && c.minutesAgo<30){micro='Window opening';}
    else if(c.stage==='FORMING'){micro='Momentum building';}
    html+='<div class="fv-card '+clr+'" id="fvc-'+esc(c.asset)+'" onclick="selAsset(\''+esc(c.asset)+'\');sw(\'home\')">';
    html+=tagHtml;
    html+='<div class="fv-title"><span class="em">'+feedIcon(c.stage,c.isPersonal)+'</span>'+esc(c.title||'')+'</div>';
    var sub=esc(c.timing||'')+'<span class="sep">·</span><span class="src">'+(c.sourcesCount||0)+' sources aligned</span><span class="sep">·</span>'+esc(c.meaning||'');
    html+='<div class="fv-sub">'+sub+'</div>';
    if(c.directionLine){
      html+='<div class="fv-dir '+dirCls+'">→ '+esc(c.directionLine)+'</div>';
    }
    if(micro){html+='<div class="fv-micro">● '+esc(micro)+'</div>';}
    html+='<div class="fv-cta"><span class="fv-cta-t">→ '+esc(c.cta||'Open setup')+'</span><span class="fv-cta-arr">›</span></div>';
    html+='</div>';
  });
  html+='</div>';
  return html;
}

function highlightAsset(asset){
  var el=document.getElementById('fvc-'+asset);
  if(el){
    el.classList.add('hi');
    el.scrollIntoView({behavior:'smooth',block:'center'});
    setTimeout(function(){el.classList.remove('hi')},1500);
  }
}

/* ═════════════ EDGE ═════════════ */
async function loadEdge(){
  var el=document.getElementById('s-edge');
  el.innerHTML='<div class="spin">LOADING · EDGE</div>';
  // Task 3 · TG Cognitive Layer: fetch BOTH the edge payload AND the composer
  // home payload in parallel. The composer payload supplies the per-module
  // cognition (TA / Sentiment / Fractal) used by `renderCognitiveBreakdown`.
  // No backend recompute; we read what `home_composer` already produced.
  var results=await Promise.all([
    fetchJSON('/api/miniapp/edge/v2?asset='+asset+'&telegram_id='+encodeURIComponent(tgId||'')),
    fetchJSON('/api/miniapp/home?asset='+asset).catch(function(){return null;})
  ]);
  var d=results[0];
  var homePayload=results[1]&&results[1].ok?results[1]:null;
  if(!d||!d.ok){el.innerHTML='<div class="err">Failed to load</div>';return}
  el.innerHTML=renderEdgeV2(d,homePayload);
  // Auto-paywall: only for FREE + strong trigger + only once per session per asset
  try{
    var trig=d.trigger||{};
    var sessKey='pwShown_'+(asset||'BTC');
    if(trig.shouldAutoOpen && !sessionStorage.getItem(sessKey) && (d.userTier||'FREE')!=='PRO'){
      sessionStorage.setItem(sessKey,'1');
      setTimeout(function(){showPaywall(trig);},1800);
    }
  }catch(e){}
}

function renderEdgeV2(d,homePayload){
  var isPro=(d.userTier||'FREE').toUpperCase()==='PRO';
  var stage=(d.stage||'EARLY').toUpperCase();
  var stageClr={'EARLY':'mu','FORMING':'warn','ACTIVE':'buy','PLAYED_OUT':'mu'}[stage]||'mu';
  var pm=d.potentialMove||0;
  var hasMove=Math.abs(pm)>0.01;
  var dir=(d.direction||'NEUTRAL').toUpperCase();
  var pmSign=dir==='BULLISH'?'+':(dir==='BEARISH'?'−':'');
  var pmClr=dir==='BULLISH'?'buy':(dir==='BEARISH'?'sell':'mu');
  var conf=d.confidence||0;
  var acc=d.accuracy||82;
  var aligned=d.aligned||0;
  var total=d.driversTotal||5;
  var fomo=d.fomoTrigger||'';
  var ctx=d.marketContext||'';
  var assetName=d.asset||asset;

  var html='';

  // ═══ HEADER: asset tabs (logo already in global sticky header) ═══
  html+='<div class="hm-tabs">';
  ASSETS.forEach(function(a){
    html+='<div class="hm-t '+(a===asset?'on':'')+'" onclick="selAsset(\''+a+'\')">'+a+'</div>';
  });
  html+='</div>';

  // ═══ HERO EDGE CARD ═══
  html+='<div class="eg-hero">';
  html+='<div class="eg-asset">'+esc(assetName)+' EDGE</div>';
  if(hasMove){
    html+='<div class="eg-potential color-'+pmClr+'">'+pmSign+Math.abs(pm).toFixed(1)+'%</div>';
    html+='<div class="eg-plabel">Potential move</div>';
  }else{
    html+='<div class="eg-potential-pending">Setup forming</div>';
    html+='<div class="eg-plabel">Breakout conditions building</div>';
  }
  html+='<div class="eg-stats">';
  html+='<div class="eg-s"><div class="eg-sv">'+conf+'%</div><div class="eg-sl">Confidence</div></div>';
  html+='<div class="eg-s"><div class="eg-sv">'+acc+'%</div><div class="eg-sl">Accuracy</div></div>';
  var drvVal=aligned>0?(aligned+'/'+total):'Forming';
  var drvCls=aligned>0?stageClr:'warn';
  html+='<div class="eg-s"><div class="eg-sv color-'+drvCls+'">'+esc(drvVal)+'</div><div class="eg-sl">Drivers</div></div>';
  html+='</div>';
  if(fomo){
    html+='<div class="eg-fomo">● '+esc(fomo)+'</div>';
  }
  // Early-stage advantage reframe (turns "no data" into "best entry window")
  if(stage==='EARLY'||stage==='FORMING'){
    html+='<div class="eg-early">Early stage — best entries usually form here</div>';
  }
  html+='</div>';

  // ═══ MARKET CONTEXT (connects to Home) ═══
  if(ctx){
    html+='<div class="eg-ctx">'+esc(ctx)+'</div>';
  }

  // ═══ COGNITIVE BREAKDOWN (Task 3 · TG Cognitive Layer) ═══
  // Three modules (TA / Sentiment / Fractal) with locked detail for free,
  // full breakdown for PRO. Data from composer payload — no recompute.
  try{
    if(homePayload){
      html+=renderCognitiveBreakdown(homePayload,isPro);
    }
  }catch(__e){}

  // ═══ ACTION PLAN (embedded paywall — no banner) ═══
  var pu=d.proUnlocks||{};
  html+='<div class="cd eg-pro-block '+(isPro?'':'locked')+'">';
  html+='<div class="cd-ttl">Action Plan'+(isPro?'':' <span class="lk">🔒</span>')+'</div>';
  html+=edgeRow('Entry zone',pu.entry||'—',isPro);
  html+=edgeRow('Invalidation',pu.invalidation||'—',isPro,'red');
  html+=edgeRow('Target',pu.target||'—',isPro,'green');
  html+=edgeRow('Time window',pu.timeWindow||'—',isPro);
  if(!isPro){
    html+='<div class="eg-unlock-inline" onclick="showPaywall()">';
    html+='<span class="eg-unlock-t">→ Unlock entry &amp; timing</span>';
    html+='<span class="eg-unlock-arr">›</span>';
    html+='</div>';
    // Urgency line right under CTA
    var urgencyMsg='';
    var trig=d.trigger||{};
    var tCopy=trig.copy||{};
    if(tCopy.urgency){
      urgencyMsg=tCopy.urgency;
    }else{
      urgencyMsg=stage==='ACTIVE'?'Signal active now':stage==='FORMING'?'Signal may activate soon':(stage==='PLAYED_OUT'?'Move complete · track next setup':'Waiting for confirmation');
    }
    html+='<div class="eg-urgency">'+esc(urgencyMsg)+'</div>';
    // Secondary time-uncertainty hint (habit loop)
    if(stage!=='PLAYED_OUT'){
      html+='<div class="eg-uncertain">Could trigger anytime · system watching</div>';
    }
    // Social proof micro-FOMO
    var sp=d.socialProof||{};
    if(sp.unlockedToday){
      html+='<div class="eg-social">'+ic('unlock','ic-gold')+' '+sp.unlockedToday+' unlocked this today · '+(sp.trackingNow||0).toLocaleString()+' tracking now</div>';
    }
  }else{
    html+='<div class="eg-pro-banner">✓ PRO · Full edge unlocked</div>';
  }
  html+='</div>';

  // ═══ WHY THIS EDGE ═══
  var why=d.whyEdge||[];
  if(why.length){
    html+='<div class="cd"><div class="cd-ttl">Why this edge</div>';
    why.forEach(function(w){
      html+='<div class="eg-why-it">• '+esc(w)+'</div>';
    });
    html+='</div>';
  }

  // ═══ DRIVERS STACK ═══
  var drivers=d.drivers||[];
  if(drivers.length){
    html+='<div class="cd"><div class="cd-ttl">Drivers <span class="cd-sub">'+aligned+' of '+total+' aligned</span></div>';
    drivers.forEach(function(x){
      var mark=x.state==='aligned'?'<span class="dr-m ok">✓</span>':(x.state==='forming'?'<span class="dr-m pd">·</span>':'<span class="dr-m of">—</span>');
      var stLbl=x.state==='aligned'?'Aligned':(x.state==='forming'?'Forming':'Off');
      html+='<div class="dr-row">'+mark+'<span class="dr-n">'+esc(x.name)+'</span><span class="dr-s">'+stLbl+'</span></div>';
    });
    html+='</div>';
  }

  // ═══ TIMING STEPPER (with current indicator) ═══
  var si=d.stageIndex||0;
  html+='<div class="cd"><div class="cd-ttl">Timing <span class="cd-sub">current</span></div>';
  html+='<div class="eg-timing">';
  ['Early','Forming','Active','Played'].forEach(function(lbl,i){
    var isActive=i===si;
    var isPassed=i<si;
    var lblShown=isActive?(lbl+' · now'):lbl;
    html+='<div class="eg-tmg-st '+(isActive?'on':'')+' '+(isPassed?'done':'')+'">';
    html+='<div class="eg-tmg-dot"></div><div class="eg-tmg-lbl">'+lblShown+'</div>';
    html+='</div>';
    if(i<3)html+='<div class="eg-tmg-ln '+(isPassed?'done':'')+'"></div>';
  });
  html+='</div></div>';

  return html;
}

function edgeRow(label,value,isPro,cls){
  var display=isPro?value:'••••••';
  return '<div class="eg-apr"><span class="eg-apr-l">'+esc(label)+':</span><span class="eg-apr-v '+(cls||'')+' '+(isPro?'':'blurred')+'">'+esc(display)+'</span></div>';
}

var _pwPlan='monthly';  // monthly | starter | yearly
function showPaywall(trigger){
  trigger=trigger||{};
  var c=trigger.copy||{};
  var ttl=c.title||'Unlock this move';
  var sub=c.sub||'Signal active now · Exact levels currently hidden';
  var cta=c.cta||'Upgrade to PRO →';

  var m=document.createElement('div');
  m.className='pw-modal';
  m.innerHTML='<div class="pw-box">'+
    '<div class="pw-close" onclick="closePaywall()">✕</div>'+
    '<div class="pw-ttl">'+esc(ttl)+'</div>'+
    '<div class="pw-sub">'+esc(sub)+'</div>'+
    '<div class="pw-bullets">'+
      '<div class="pw-b"><span class="pw-bi">✓</span>Exact entry &amp; exit levels</div>'+
      '<div class="pw-b"><span class="pw-bi">✓</span>Invalidation &amp; target</div>'+
      '<div class="pw-b"><span class="pw-bi">✓</span>Timing windows</div>'+
      '<div class="pw-b"><span class="pw-bi">✓</span>Real-time Telegram alerts</div>'+
      '<div class="pw-b"><span class="pw-bi">✓</span>Full signal tracking · drivers</div>'+
    '</div>'+
    '<div class="pw-tiers">'+
      tierCard('starter','$9.99','/month','Starter',false)+
      tierCard('monthly','$12','/month','Best',true)+
      tierCard('yearly','$79','/year','Save 45%',false)+
    '</div>'+
    '<div class="pw-btns">'+
      '<div class="pw-early">You\u2019re early — unlock before confirmation</div>'+
      '<div class="pw-btn primary" onclick="confirmUpgrade()">'+esc(cta)+'</div>'+
    '</div>'+
    '<div class="pw-social"><span>🔓 <b>' + pwSocial() + '</b> traders unlocked this setup</span></div>'+
    // Honest crypto-only paywall footer — single payment method,
    // no fake-disabled buttons, no card-language. See
    // /app/memory/HONEST_CRYPTO_ONLY_2026-05-12.md
    '<div class="pw-note">Pay with crypto · BTC · ETH · USDT — instant unlock</div>'+
    '</div>';
  m.onclick=function(e){if(e.target===m)closePaywall()};
  document.body.appendChild(m);
  // default plan highlight
  setTimeout(function(){ selectTier('monthly'); },10);
}

function pwSocial(){
  // Get from last loaded edge data (window._lastSocial if set) else fallback
  return (window._lastSocial && window._lastSocial.unlockedToday) || 23;
}

function tierCard(plan,price,period,badge,isBest){
  return '<div class="pw-tier '+(isBest?'best':'')+'" data-plan="'+plan+'" onclick="selectTier(\''+plan+'\')">'+
    (badge?'<div class="pw-tier-bd">'+esc(badge)+'</div>':'')+
    '<div class="pw-tier-p">'+esc(price)+'<span class="pw-tier-pe">'+esc(period)+'</span></div>'+
  '</div>';
}

function selectTier(plan){
  _pwPlan=plan;
  var tiers=document.querySelectorAll('.pw-tier');
  tiers.forEach(function(t){
    if(t.getAttribute('data-plan')===plan)t.classList.add('selected');
    else t.classList.remove('selected');
  });
}

async function confirmUpgrade(){
  try{if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.impactOccurred('medium');}catch(e){}
  await fetch('/api/miniapp/user/tier',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tgId||''),tier:'PRO',plan:_pwPlan})});
  closePaywall();
  loadEdge();
}

function closePaywall(){
  var m=document.querySelector('.pw-modal');
  if(m){m.style.animation='fadeOut .2s forwards';setTimeout(function(){m.remove()},200)}
  // Post-close retention toast
  showToast('Still forming — check back soon');
}

function showToast(msg){
  var existing=document.querySelector('.toast');
  if(existing)existing.remove();
  var t=document.createElement('div');
  t.className='toast';
  t.textContent=msg;
  document.body.appendChild(t);
  setTimeout(function(){t.classList.add('out');setTimeout(function(){t.remove()},300)},2800);
}

function closePaywall(){
  var m=document.querySelector('.pw-modal');
  if(m)m.remove();
}

/* ═════════════ PROFILE ═════════════ */
async function loadProfile(){
  var el=document.getElementById('s-profile');
  el.innerHTML='<div class="spin">LOADING · PROFILE</div>';
  var hdr=document.getElementById('app-hdr');if(hdr)hdr.classList.add('hide');
  var p=await fetchJSON('/api/miniapp/profile?telegram_id='+encodeURIComponent(tgId));
  if(!p||!p.ok){el.innerHTML='<div class="err">Failed to load</div>';return}
  var u=p.user||{}, perf=p.performance||{}, ref=p.referral||{}, promo=p.promo||{}, sets=p.settings||{}, gr=p.growth||{};
  var html='';

  // ═══ Sticky centered FOMO logo ═══
  // (Global sticky FOMO logo lives in app-hdr; no per-tab duplicate)

  // ═══ User card ═══
  var initials=((u.name||u.username||'U').split(' ').map(function(w){return w[0]||''}).join('').slice(0,2)||'FO').toUpperCase();
  var plan=(u.planStatus||'free').toLowerCase();
  var displayName=u.name||u.username||'Guest';
  html+='<div class="pf-user">';
  html+='<div class="pf-av">';
  if(u.photoUrl)html+='<img src="'+esc(u.photoUrl)+'" onerror="this.parentNode.innerHTML=\''+esc(initials)+'\'"/>';
  else html+=esc(initials);
  html+='</div>';
  html+='<div class="pf-uinfo"><div class="pf-name">'+esc(displayName)+'</div>';
  if(u.username)html+='<div class="pf-un">@'+esc(u.username)+'</div>';
  else html+='<div class="pf-un">Telegram user</div>';
  html+='</div>';
  html+='<span class="pf-plan '+plan+'">'+esc(u.planName||'FREE')+'</span>';
  html+='</div>';

  // ═══ FOMO PRO banner (ONLY CTA, free users only) ═══
  if(plan==='free'){
    html+='<div class="pro-ban">';
    html+='<div class="pro-hdr"><span class="pro-bolt">⚡</span><span class="pro-name">FOMO PRO</span></div>';
    html+='<div class="pro-sell-bullets">';
    html+='<div class="pro-b"><span class="pro-bi">✓</span>Entry &amp; exit levels</div>';
    html+='<div class="pro-b"><span class="pro-bi">✓</span>Exact timing windows</div>';
    html+='<div class="pro-b"><span class="pro-bi">✓</span>Real-time alerts</div>';
    html+='</div>';
    html+='<button class="pro-cta" onclick="showPaywall()">Upgrade to PRO · $12/mo →</button>';
    html+='</div>';
  }

  // ═══ YOUR EDGE ═══
  var acc=perf.accuracy||0;var accPct=Math.round(acc*(Math.abs(acc)<=1?100:1));
  var accC=accPct>=60?'buy':accPct>=40?'warn':'sell';
  var totalCalls=perf.directionalTotal||0;
  var isTrackingStarted=(totalCalls<3);  // new product — don't show 0% yet
  html+='<div class="edge-stat"><div class="cd-ttl">Your Edge</div>';
  if(isTrackingStarted){
    html+='<div class="edge-acc"><div class="edge-big color-pur" style="font-size:22px;letter-spacing:-.3px">Tracking started</div><div class="edge-lab">First results coming soon</div></div>';
    html+='<div class="edge-desc">Signals are being evaluated · accuracy unlocks after 3+ calls</div>';
  }else{
    html+='<div class="edge-acc"><div class="edge-big color-'+accC+'">'+accPct+'%</div><div class="edge-lab">Directional Accuracy</div></div>';
    html+='<div class="edge-desc">'+(perf.directionalCorrect||0)+' / '+totalCalls+' directional calls correct</div>';
  }
  html+='<div class="edge-grid">';
  html+='<div class="edge-gi"><div class="edge-gv">'+(perf.totalDecisions||0)+'</div><div class="edge-gl">Total</div></div>';
  html+='<div class="edge-gi"><div class="edge-gv">'+(perf.evaluated||0)+'</div><div class="edge-gl">Evaluated</div></div>';
  html+='<div class="edge-gi"><div class="edge-gv">'+Math.round((perf.coverage||0)*(Math.abs(perf.coverage||0)<=1?100:1))+'%</div><div class="edge-gl">Coverage</div></div>';
  html+='</div>';
  html+='<div class="edge-grid" style="margin-top:10px">';
  html+='<div class="edge-gi" style="text-align:left"><div class="edge-gl">Best</div><div class="edge-gv" style="font-size:13px">'+esc(perf.bestType||'N/A')+' <span style="color:var(--buy);font-weight:700">'+Math.round((perf.bestTypeAccuracy||0)*100)+'%</span></div></div>';
  html+='<div class="edge-gi" style="text-align:right"><div class="edge-gl">Worst</div><div class="edge-gv" style="font-size:13px">'+esc(perf.worstType||'N/A')+' <span style="color:var(--sell);font-weight:700">'+Math.round((perf.worstTypeAccuracy||0)*100)+'%</span></div></div>';
  html+='</div></div>';

  // ═══ LEADERBOARD (expandable, with REAL data) ═══
  var season=gr.season||{};
  var lbRows=gr.leaderboard||[];
  var myRank=gr.rank||0;
  var myScore=gr.seasonScore||0;
  var rankStr=myRank>0?('#'+myRank):'Unranked';
  var deltaBadge='';
  if(gr.rankDelta>0)deltaBadge=' <span style="color:var(--buy);font-weight:800">↑'+gr.rankDelta+'</span>';
  else if(gr.rankDelta<0)deltaBadge=' <span style="color:var(--sell);font-weight:800">↓'+Math.abs(gr.rankDelta)+'</span>';
  html+='<div class="coll" id="lb-card"><div class="coll-hd" onclick="document.getElementById(\'lb-card\').classList.toggle(\'op\')">';
  html+='<div class="coll-ic"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg></div>';
  html+='<div class="coll-body"><div class="coll-t">Leaderboard</div><div class="coll-s">'+esc(season.name||'Season 1')+' · '+esc(rankStr)+deltaBadge+' · <b style="color:var(--tx)">'+myScore+' pts</b></div></div>';
  html+='<svg class="coll-arr" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>';
  html+='</div><div class="coll-inner">';
  if(lbRows.length){
    lbRows.slice(0,10).forEach(function(r,i){
      var rank=r.rank||(i+1);
      var medalSvg='';
      if(rank===1)medalSvg='<svg width="16" height="16" viewBox="0 0 24 24" fill="#FFC907" stroke="#FFC907" stroke-width="1" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><text x="12" y="16.5" text-anchor="middle" font-size="8" font-weight="900" fill="#0b0b0f">1</text></svg>';
      else if(rank===2)medalSvg='<svg width="16" height="16" viewBox="0 0 24 24" fill="#c7cbd1" stroke="#c7cbd1" stroke-width="1" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><text x="12" y="16.5" text-anchor="middle" font-size="8" font-weight="900" fill="#0b0b0f">2</text></svg>';
      else if(rank===3)medalSvg='<svg width="16" height="16" viewBox="0 0 24 24" fill="#cd7f32" stroke="#cd7f32" stroke-width="1" stroke-linejoin="round"><circle cx="12" cy="13" r="7"/><text x="12" y="16.5" text-anchor="middle" font-size="8" font-weight="900" fill="#0b0b0f">3</text></svg>';
      var medal=medalSvg||('#'+rank);
      var nm=r.name||r.username||('User '+(r.telegramId||'').slice(-4));
      var isMe=r.telegramId&&String(r.telegramId)===String(tgId);
      html+='<div class="lb-row" style="'+(isMe?'background:rgba(99,102,241,.08);margin:0 -14px;padding:8px 14px':'')+'"><span class="lb-rank '+(rank<=3?'top':'')+'">'+medal+'</span><span class="lb-name">'+esc(nm)+(isMe?' <span style="color:var(--ind);font-size:9px;font-weight:800;letter-spacing:1px">YOU</span>':'')+'</span><span class="lb-score">'+(r.score||r.seasonScore||0)+' pts</span></div>';
    });
  }else{
    html+='<div style="font-size:12px;color:var(--mu);text-align:center;padding:12px 0 4px">Season just started · invite friends to climb</div>';
    html+='<div class="lb-row"><span class="lb-rank top">🥇</span><span class="lb-name" style="color:var(--mu)">Awaiting first contender</span><span class="lb-score" style="color:var(--mu2)">— pts</span></div>';
  }
  html+='</div></div>';

  // ═══ GROWTH (milestones + stats, V1 had dedicated button — now inline expanded) ═══
  var ms=gr.milestones||[];
  var nextMs=gr.nextMilestone||{};
  var stats=gr.stats||{};
  if(ms.length){
    html+='<div class="coll op" id="gr-card"><div class="coll-hd" onclick="document.getElementById(\'gr-card\').classList.toggle(\'op\')">';
    html+='<div class="coll-ic gr"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg></div>';
    html+='<div class="coll-body"><div class="coll-t">Growth</div><div class="coll-s">'+esc(nextMs.label||'Invite friends · earn PRO days')+'</div></div>';
    html+='<svg class="coll-arr" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>';
    html+='</div><div class="coll-inner">';
    // Stats funnel
    html+='<div class="edge-grid" style="border-top:0;padding-top:0;margin-bottom:12px">';
    html+='<div class="edge-gi"><div class="edge-gv" style="color:var(--ind)">'+(stats.clicks||0)+'</div><div class="edge-gl">Clicks</div></div>';
    html+='<div class="edge-gi"><div class="edge-gv" style="color:var(--cya)">'+(stats.signups||0)+'</div><div class="edge-gl">Sign-ups</div></div>';
    html+='<div class="edge-gi"><div class="edge-gv" style="color:var(--buy)">'+(stats.paidConfirmed||0)+'</div><div class="edge-gl">Paid</div></div>';
    html+='</div>';
    // Milestones
    html+='<div style="font-size:9px;font-weight:800;letter-spacing:1.2px;color:var(--mu2);text-transform:uppercase;padding:0 0 6px">Reward Ladder</div>';
    ms.forEach(function(mi){
      var done=(stats.paidConfirmed||0)>=mi.paid;
      var active=!done&&(nextMs.paid!=null?(mi.paid===nextMs.paid+nextMs.need):false);
      var dot=done?'<span style="color:var(--buy);font-weight:900">✓</span>':'<span style="color:var(--mu2);font-weight:900">○</span>';
      html+='<div class="lb-row" style="'+(done?'opacity:.55':'')+'"><span class="lb-rank" style="font-size:14px">'+dot+'</span><span class="lb-name" style="font-size:12px">'+esc(mi.label)+'</span><span class="lb-score" style="color:'+(done?'var(--buy)':'var(--gold)')+';font-size:11px">'+esc(mi.reward)+'</span></div>';
    });
    // Earned rewards
    if(gr.earnedRewards&&gr.earnedRewards.length){
      html+='<div style="font-size:9px;font-weight:800;letter-spacing:1.2px;color:var(--buy);text-transform:uppercase;padding:12px 0 4px">Earned</div>';
      gr.earnedRewards.forEach(function(r){html+='<div style="font-size:12px;color:var(--buy);padding:3px 0">✓ '+esc(r.label||r)+'</div>';});
    }
    html+='</div></div>';
  }

  // ═══ PROMO CODE ═══
  html+='<div class="promo-card">';
  html+='<div class="promo-ttl"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 12l-8 8-9-9V3h8l9 9z"/><circle cx="7" cy="7" r="1.5" fill="currentColor"/></svg><span>Promo Code</span></div>';
  if(promo.activeCode)html+='<div class="promo-msg ok">Active: <b>'+esc(promo.activeCode)+'</b>'+(promo.discountText?' — '+esc(promo.discountText):'')+'</div>';
  html+='<div class="promo-row" style="margin-top:'+(promo.activeCode?'8px':'0')+'"><input class="promo-inp" id="promo-inp" placeholder="Enter code" autocapitalize="characters"/><button class="promo-btn" onclick="applyPromo()">Apply</button></div>';
  html+='<div id="promo-msg"></div>';
  html+='</div>';

  // ═══ APPEARANCE ═══
  html+='<div class="sec"><div class="sec-hdr"><span class="sec-hdr-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09a1.65 1.65 0 001.51-1 1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg></span><span class="sec-hdr-t">Appearance</span></div>';
  html+='<div class="row-card">';
  html+='<div class="row-item"><div class="row-body"><div class="row-t">Light Mode</div><div class="row-s">Switch to clean light theme · synced across devices</div></div><div class="sw'+(getTheme()==='light'?' on':'')+'" id="theme-sw" onclick="onToggleTheme(this)"></div></div>';
  html+='</div></div>';

  // ═══ NOTIFICATION SETTINGS (legacy — hidden; superseded by Push Alerts) ═══
  // Removed to reduce duplication. Use "Push Alerts" below for canonical preferences.

  // ═══ PUSH ALERTS (Telegram) ═══
  html+='<div class="sec"><div class="sec-hdr"><span class="sec-hdr-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M10 21a2 2 0 004 0"/></svg></span><span class="sec-hdr-t">Push Alerts</span></div>';
  html+='<div class="row-card" id="push-rows">';
  html+='<div style="padding:13px 14px;color:var(--mu);font-size:11px;letter-spacing:.3px">Loading preferences…</div>';
  html+='</div></div>';

  // ═══ APP ═══
  html+='<div class="sec"><div class="sec-hdr"><span class="sec-hdr-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12" y2="18"/></svg></span><span class="sec-hdr-t">App</span></div>';
  html+='<div class="row-card">';
  html+='<div class="row-item clk" onclick="getMobileApp()"><div class="row-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="5" y="2" width="14" height="20" rx="2"/><circle cx="12" cy="18" r="1" fill="currentColor"/></svg></div><div class="row-body"><div class="row-t">Get the Mobile App</div><div class="row-s">Full features · charts · portfolio</div></div><div class="row-arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 6 15 12 9 18"/></svg></div></div>';
  html+='<div class="row-item clk" onclick="refreshData(this)"><div class="row-ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12a9 9 0 11-3-6.7L21 8"/><polyline points="21 3 21 8 16 8"/></svg></div><div class="row-body"><div class="row-t">Refresh data</div><div class="row-s">Re-fetch from MetaBrain</div></div><div class="row-arr"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 6 15 12 9 18"/></svg></div></div>';
  html+='</div></div>';

  // ═══ REFERRAL PROGRAM ═══
  if(ref&&ref.code){
    html+='<div class="sec"><div class="sec-hdr"><span class="sec-hdr-ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 11h-6"/><path d="M19 8v6"/></svg></span><span class="sec-hdr-t">Referral Program</span></div>';
    html+='<div class="ref-box">';
    if(ref.rewardText)html+='<div class="ref-rw">'+esc(ref.rewardText)+' · <b style="color:var(--tx)">'+(ref.invites||0)+'</b> invited</div>';
    html+='<div class="ref-code"><div class="ref-code-val">'+esc(ref.code)+'</div><div class="ref-copy" onclick="copyRef(\''+esc(ref.code)+'\')">Copy</div></div>';
    if(ref.inviteLink)html+='<button class="ref-btn" onclick="shareRef(\''+esc(ref.inviteLink)+'\')"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>Share Invite Link</button>';
    html+='</div></div>';
  }

  // ═══ ABOUT ═══
  html+='<div class="about-ln">FOMO · Market Interpreter · v1.0</div>';

  el.innerHTML=html;
  // Load Push prefs (async, non-blocking)
  loadPushSettings();
}

async function loadPushSettings(){
  var wrap=document.getElementById('push-rows');
  if(!wrap)return;
  if(!tgId){wrap.innerHTML='<div style="padding:13px 14px;color:var(--mu);font-size:11px">Open in Telegram to manage push alerts</div>';return}
  var d=await fetchJSON('/api/miniapp/push/settings?telegram_id='+encodeURIComponent(tgId));
  if(!d||!d.ok){wrap.innerHTML='<div style="padding:13px 14px;color:var(--sell);font-size:11px">Failed to load</div>';return}
  var p=d.prefs||{};
  var html='';
  html+=pushRow('direction_shifts','Direction shifts','Bullish ⟷ Bearish flips',p.direction_shifts);
  html+=pushRow('high_conf','High-confidence signals','Confidence ≥ 70% only',p.high_conf);
  html+=pushRow('edge_opens','Edge opens','Prediction market mispricings',p.edge_opens);
  html+=pushRow('digest','Daily digest','Morning summary at 09:00 UTC',p.digest);
  wrap.innerHTML=html;
}

function pushRow(key,title,sub,val){
  var on=!!val;
  return '<div class="row-item"><div class="row-body"><div class="row-t">'+esc(title)+'</div><div class="row-s">'+esc(sub)+'</div></div><div class="sw '+(on?'on':'')+'" onclick="togglePushPref(this,\''+key+'\')"></div></div>';
}

async function togglePushPref(el,key){
  el.classList.toggle('on');
  var val=el.classList.contains('on');
  try{if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.impactOccurred('light');}catch(e){}
  var body={telegram_id:String(tgId||''),prefs:{}};body.prefs[key]=val;
  try{await fetch('/api/miniapp/push/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}catch(e){}
}

function onToggleTheme(el){
  var next=getTheme()==='light'?'dark':'light';
  applyTheme(next);
  if(el){el.classList.toggle('on',next==='light');}
  try{if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.selectionChanged();}catch(e){}
  try{
    if(typeof showToast==='function')showToast(next==='light'?'Light theme on':'Dark theme on');
  }catch(e){}
  // Track event for analytics (non-blocking)
  try{
    if(tgId){
      fetch('/api/miniapp/event',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tgId||''),event:'theme_change',context:{theme:next}})}).catch(function(){});
    }
  }catch(e){}
}

function nRow(key,title,sub,val){
  var on=!!val;
  return '<div class="row-item"><div class="row-body"><div class="row-t">'+esc(title)+'</div><div class="row-s">'+esc(sub)+'</div></div><div class="sw '+(on?'on':'')+'" onclick="toggleSetting(this,\''+key+'\')"></div></div>';
}

async function toggleSetting(el,key){
  el.classList.toggle('on');
  var val=el.classList.contains('on');
  try{if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.impactOccurred('light');}catch(e){}
  var body={telegram_id:tgId};body[key]=val;
  try{await fetch('/api/miniapp/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}catch(e){}
}

async function applyPromo(){
  var inp=document.getElementById('promo-inp');
  var msg=document.getElementById('promo-msg');
  var code=(inp.value||'').trim();
  if(!code){msg.innerHTML='<div class="promo-msg err">Enter a code first</div>';return}
  msg.innerHTML='<div class="promo-msg" style="background:rgba(99,102,241,.12);color:var(--ind)">Applying…</div>';
  try{
    var r=await fetch('/api/miniapp/promo/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:tgId,code:code})});
    var d=await r.json();
    if(d&&d.ok&&d.applied){msg.innerHTML='<div class="promo-msg ok">✓ Applied — '+esc(d.discountText||'Promo active')+'</div>';inp.value='';setTimeout(loadProfile,1200);}
    else{msg.innerHTML='<div class="promo-msg err">'+esc(d.error||d.message||'Invalid code')+'</div>';}
  }catch(e){msg.innerHTML='<div class="promo-msg err">Network error</div>';}
}

var _lbLoaded=false;
async function loadLeaderboard(){
  var card=document.getElementById('lb-card');
  if(!card||!card.classList.contains('op')||_lbLoaded)return;
  _lbLoaded=true;
  var inner=document.getElementById('lb-inner');
  var d=await fetchJSON('/api/miniapp/leaderboard?telegram_id='+encodeURIComponent(tgId))||await fetchJSON('/api/growth/leaderboard?telegram_id='+encodeURIComponent(tgId));
  if(!d||(!d.leaderboard&&!d.rows&&!d.ok)){inner.innerHTML='<div class="empty" style="padding:18px 0">Leaderboard coming soon</div>';return}
  var rows=d.leaderboard||d.rows||[];
  if(!rows.length){inner.innerHTML='<div class="empty" style="padding:18px 0">No ranked players yet · be the first</div>';return}
  var h='';
  rows.slice(0,10).forEach(function(r,i){
    var rank=r.rank||(i+1);
    var topCls=rank<=3?'top':'';
    h+='<div class="lb-row"><span class="lb-rank '+topCls+'">'+(rank<=3?['🥇','🥈','🥉'][rank-1]:('#'+rank))+'</span><span class="lb-name">'+esc(r.name||r.username||'Anonymous')+'</span><span class="lb-score">'+(r.score||r.points||0)+' pts</span></div>';
  });
  inner.innerHTML=h;
}

function alertFeature(kind){
  if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.impactOccurred('light');
  alert((kind==='tension'?'Tension alerts':'Direction shifts')+' — PRO feature · upgrade to enable');
}

function getMobileApp(){
  if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.openLink)Telegram.WebApp.openLink('https://fomo.app/download');
  else window.open('https://fomo.app/download','_blank');
}

async function refreshData(el){
  if(el){var ico=el.querySelector('.row-ico svg');if(ico)ico.style.animation='spin 1s linear infinite';}
  try{await fetch('/api/miniapp/refresh?telegram_id='+encodeURIComponent(tgId),{method:'POST'});}catch(e){}
  setTimeout(function(){if(el){var ico=el.querySelector('.row-ico svg');if(ico)ico.style.animation='';}if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.notificationOccurred('success');loadHome();loadFeed();loadEdge();},800);
}

function copyRef(code){
  try{navigator.clipboard.writeText(code);if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.HapticFeedback)Telegram.WebApp.HapticFeedback.notificationOccurred('success');}catch(e){}
}
function shareRef(url){
  if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.openTelegramLink){Telegram.WebApp.openTelegramLink('https://t.me/share/url?url='+encodeURIComponent(url)+'&text='+encodeURIComponent('Join me on FOMO — crypto intelligence'));return}
  if(navigator.share){navigator.share({url:url,title:'FOMO',text:'Join me on FOMO'}).catch(function(){})}
  else{navigator.clipboard.writeText(url);alert('Link copied')}
}
function goPro(){
  window.location.href='/api/miniapp/billing/checkout?telegram_id='+encodeURIComponent(tgId);
}

// Sync user + boot
if(tg){
  fetch('/api/miniapp/sync-telegram-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({telegram_id:String(tg.id),first_name:tg.first_name||'',last_name:tg.last_name||'',username:tg.username||'',photo_url:tg.photo_url||''})}).catch(function(){});
}
if(P.get('ref')){
  fetch('/api/growth/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:P.get('ref'),telegram_id:tgId})}).catch(function(){});
}
sw(_initTab);
</script>
</body>
</html>
"""


# ─── A2: TG Mini-App server-side localization map ────────────────────────────
# Conservative replacement table. Each entry is a (search, replace_with_i18n_key)
# pair. The search string is matched verbatim against MINIAPP_LITE_HTML; the
# placeholder `{{I18N}}` is substituted with the translation for the resolved
# locale at render time. JS-rendered text uses window.__I18N__ instead.
#
# IMPORTANT: keep each `search` long enough to be unique inside the 3700-line
# HTML body, to avoid accidental collisions with comments / variable names.
TG_STATIC_REPLACEMENTS: list = [
    # Bottom navigation — pattern: `</svg>\n    LABEL\n  </button>` inside each tab button
    ("</svg>\n    Home\n  </button>",     "</svg>\n    {{I18N}}\n  </button>",     "tg.nav.home"),
    ("</svg>\n    Feed\n  </button>",     "</svg>\n    {{I18N}}\n  </button>",     "tg.nav.feed"),
    ("</svg>\n    News\n  </button>",     "</svg>\n    {{I18N}}\n  </button>",     "tg.nav.news"),
    ("</svg>\n    Edge\n  </button>",     "</svg>\n    {{I18N}}\n  </button>",     "tg.nav.edge"),
    ("</svg>\n    Profile\n  </button>",  "</svg>\n    {{I18N}}\n  </button>",     "tg.nav.profile"),
    # Loading skeletons
    ("LOADING · METABRAIN",   "{{I18N}}",   "tg.loading.metabrain"),
    ("LOADING · FEED",        "{{I18N}}",   "tg.loading.feed"),
    ("LOADING · MARKET",      "{{I18N}}",   "tg.loading.market"),
    ("LOADING · EDGE",        "{{I18N}}",   "tg.loading.edge"),
    ("LOADING · PROFILE",     "{{I18N}}",   "tg.loading.profile"),
    # User-visible TG Home — unique static strings (count == 1 verified)
    ("LOW EDGE · HIGH RISK",            "{{I18N}}",  "tg.state.lowEdgeHighRisk"),
    ("Nothing yet — but signals forming", "{{I18N}}", "tg.state.nothingForming"),
    ("→ SEE WHAT\u2019S BUILDING",       "{{I18N}}",  "tg.state.seeWhatsBuilding"),
    ("Next opportunity forming",        "{{I18N}}",  "tg.state.nextOpportunity"),
    # Card labels (unique)
    (">CONFIDENCE<",     ">{{I18N}}<",  "tg.label.confidence"),
    (">EXPECTED MOVE<",  ">{{I18N}}<",  "tg.label.expectedMove"),
    (">PRICE<",          ">{{I18N}}<",  "tg.label.price"),
    # Restraint vocabulary rename — "PREDICTION · 30D" header replaced by "STRUCTURE · 30D"
    # (placeholder substitution handled via i18n template `tg.label.structureSnapshot`)
    ("PREDICTION · 30D",  "STRUCTURE · 30D",  None),  # None = literal swap, no i18n key
    # Reframe terminal vocabulary
    ("ENTRY ZONE",        "FORMATION ZONE",   None),
    ("NEXT TRIGGER",      "NEXT CONFIRMATION", None),
    ("Scanning for entry","Scanning for formation", None),
]


def _render_miniapp_lite_localized(lang: str) -> str:
    """Server-side localize the TG Mini-App HTML for `lang`.

    Steps:
      1. Swap the `<html lang="…">` attribute so screen readers + browser
         hint correctly.
      2. Inject `window.__I18N__` dictionary before the first inline script
         so DOM-render JS can do lookup with t(key) on first paint.
      3. Replace a conservative set of statically-embedded English strings
         (bottom nav + loading skeletons + key card labels). Anything dynamic
         stays English until JS-side migration in a follow-up sub-sprint.
    """
    html = MINIAPP_LITE_HTML
    bucket = locale_dict(lang)

    # 1. Document lang attribute
    html = html.replace('<html lang="en">', f'<html lang="{lang}">', 1)

    # 2. Window dictionary injection (runs before any other script in <body>)
    dict_json = _json.dumps({"locale": lang, "dict": bucket}, ensure_ascii=False)
    injection = (
        "<script>window.__I18N__ = " + dict_json + ";"
        "window.__t = function(k, fallback){"
        "  try { var v = (window.__I18N__||{}).dict||{}; return v[k] != null ? v[k] : (fallback != null ? fallback : k); }"
        "  catch(e){ return fallback != null ? fallback : k; }"
        "};</script>"
    )
    if "</head>" in html:
        html = html.replace("</head>", injection + "</head>", 1)
    else:
        html = injection + html

    # 3. Static replacements (some keyed, some literal-swap for vocabulary reframe)
    for search, replace_template, key in TG_STATIC_REPLACEMENTS:
        if key is None:
            # literal rename pass (e.g. PREDICTION → STRUCTURE) — locale-independent
            html = html.replace(search, replace_template)
        else:
            translated = t(key, lang)
            html = html.replace(search, replace_template.replace("{{I18N}}", translated))

    return html



@router.get("/api/miniapp/lite", response_class=HTMLResponse)
async def miniapp_lite(request: Request, lang: str = ""):
    """TG Mini-App entry point with server-side localization.

    Locale resolution priority:
      1. ?lang= query parameter (from bot link, or Telegram passes user.language_code)
      2. Accept-Language header
      3. fallback "en"

    Whitelist: en / ru / uk. Anything else degrades to "en".
    """
    locale = resolve_locale(lang or None, request.headers.get("accept-language"))

    # Kick the building-push loop on first request (idempotent)
    try:
        _ensure_building_loop()
    except Exception:
        pass

    body = _render_miniapp_lite_localized(locale)

    return HTMLResponse(
        content=body,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Content-Language": locale,
        },
    )



@router.get("/api/miniapp/chart-series")
async def miniapp_chart_series(symbol: str = "BTC", horizon: str = "30D"):
    """
    Compact price series + forecast for the Mini App mini-chart.
    Reads OHLCV directly (always works), then layers MetaBrain bias/target
    if available. Fallback to neutral projection if MetaBrain is empty.
    """
    try:
        from services.prediction_chart_service import _db, _build_projection_from_mb, HORIZON_DAYS
    except Exception as e:
        return {"ok": False, "error": f"import: {e}"}

    sym = (symbol or "BTC").upper()
    hz = (horizon or "30D").upper()
    history_days = {"7D": 21, "30D": 60, "90D": 120, "180D": 180, "365D": 365}.get(hz, 60)

    try:
        candles = list(_db.fractal_canonical_ohlcv.find(
            {"meta.symbol": sym, "ohlcv.c": {"$gt": 0}},
            {"_id": 0, "ts": 1, "ohlcv.c": 1},
        ).sort([("ts", -1)]).limit(history_days))
    except Exception as e:
        return {"ok": False, "error": f"db: {e}"}

    series = []
    for c in reversed(candles):
        ts = c.get("ts")
        v = (c.get("ohlcv") or {}).get("c")
        if ts and v:
            t_str = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            series.append({"t": t_str, "v": round(float(v), 2)})

    if not series:
        return {
            "ok": False, "error": "no_data", "symbol": sym, "horizon": hz,
            "priceSeries": [], "projectedSeries": [],
        }

    current_price = series[-1]["v"]

    direction = "NEUTRAL"
    expected_return = 0.0
    confidence = 0.3
    target = current_price
    bias = "Neutral"

    try:
        from services.meta_brain_service import build_horizon_forecasts
        mb = build_horizon_forecasts(sym)
        h = (mb.get("horizons") or {}).get(hz, {}) or {}
        direction = (h.get("direction", "NEUTRAL") or "NEUTRAL").upper()
        expected_return = float(h.get("expectedReturn", 0) or 0)
        confidence = float(h.get("confidence", 0.3) or 0.3)
        mb_target = float(h.get("targetPrice", 0) or 0)
        target = mb_target if mb_target > 0 else current_price * (1 + expected_return)
        if direction in ("UP", "BULLISH"):
            bias = "Bullish"
        elif direction in ("DOWN", "BEARISH"):
            bias = "Bearish"
        else:
            bias = "Neutral"
    except Exception:
        pass

    horizon_days_n = HORIZON_DAYS.get(hz, 30)
    try:
        proj = _build_projection_from_mb(
            current_price,
            {"direction": direction, "expectedReturn": expected_return,
             "confidence": confidence, "targetPrice": target},
            horizon_days_n,
        )
        projected = proj.get("projected", [])
    except Exception:
        projected = []

    return {
        "ok": True,
        "symbol": sym,
        "horizon": hz,
        "currentPrice": current_price,
        "bias": bias,
        "direction": direction,
        "confidence": round(confidence * 100),
        "expectedReturn": round(expected_return * 100, 2),
        "target": round(float(target), 2),
        "priceSeries": series,
        "projectedSeries": projected,
    }



# ═══════════════════════════════════════════════════════════
# FEED V2 — product spec (NOW / BUILDING / PLAYED OUT)
# 1 asset = 1 card per section, dedup, stage from sources+impact
# ═══════════════════════════════════════════════════════════

def _parse_ts(ts):
    from datetime import datetime, timezone
    if not ts:
        return None
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    try:
        s = str(ts).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _classify_stage(items: list) -> str:
    """Decide CONFIRMED / FORMING / EARLY from a group of raw items for same asset."""
    sources = {str(it.get('source') or it.get('type') or '').lower() for it in items}
    sources.discard('')
    high_impact = any(str(it.get('impact') or '').upper() == 'HIGH' for it in items)
    n = len(items)
    # CONFIRMED: many aligned items or high-impact prediction/outcome
    if n >= 5 or (high_impact and n >= 3):
        return 'CONFIRMED'
    if n >= 3 or (high_impact and n >= 2):
        return 'FORMING'
    return 'EARLY'


def _dominant_direction(items: list) -> str:
    from collections import Counter
    c = Counter()
    for it in items:
        d = str(it.get('direction') or '').upper()
        if d in ('BULLISH', 'BEARISH'):
            c[d] += 1
    if not c:
        return 'NEUTRAL'
    top, n = c.most_common(1)[0]
    # require majority to flip from NEUTRAL
    total_dir = sum(c.values())
    return top if n >= max(2, total_dir * 0.6) else 'NEUTRAL'


def _pick_title(asset: str, stage: str, direction: str, is_personal: bool) -> str:
    import random
    random.seed(f"{asset}:{stage}:{direction}")
    if is_personal:
        return f"{asset} again"
    if stage == 'CONFIRMED':
        pool = [
            f"{asset} move confirmed",
            f"{asset} breakout confirmed",
            f"{asset} trend shift confirmed",
        ]
        return random.choice(pool)
    if stage == 'FORMING':
        pool = [
            f"{asset} signals aligning",
            f"{asset} narrative picking up",
            f"{asset} pressure building",
            f"{asset} accumulation signals",
        ]
        return random.choice(pool)
    # EARLY
    return f"{asset} signals forming"


def _timing_label(minutes_ago: int) -> str:
    if minutes_ago < 15:
        return "just now"
    if minutes_ago < 30:
        return "recently"
    if minutes_ago < 120:
        return "building over time"
    h = max(1, round(minutes_ago / 60))
    return f"{h}h ago"


def _meaning_label(stage: str, is_personal: bool) -> str:
    if is_personal:
        return "matches patterns you've been watching"
    if stage == 'CONFIRMED':
        return "narrative accelerating"
    if stage == 'FORMING':
        return "momentum starting to build"
    return "early signals emerging"


def _direction_line(direction: str, stage: str) -> str:
    d = (direction or '').upper()
    if d == 'BULLISH':
        return "bullish tilt emerging"
    if d == 'BEARISH':
        return "downside risk forming"
    return ""


def _cta_label(stage: str, is_personal: bool, asset: str = "") -> str:
    """Dynamic CTA — uses asset to keep it fresh for the eye."""
    import random
    a = (asset or '').upper()
    seed = f"{a}:{stage}:{'p' if is_personal else 'n'}"
    random.seed(seed)
    if is_personal:
        pool = [
            f"See what's driving {a}" if a else "See what's driving it",
            f"What's behind {a} move" if a else "What's behind this move",
        ]
        return random.choice(pool)
    if stage == 'CONFIRMED':
        pool = [
            f"See what's driving {a}" if a else "See what's driving it",
            f"What's behind this move",
            f"See {a} momentum" if a else "See momentum",
        ]
        return random.choice(pool)
    if stage == 'FORMING':
        pool = [
            f"See {a} momentum" if a else "See momentum",
            f"See what's forming",
            f"Watch {a} setup" if a else "Watch this setup",
        ]
        return random.choice(pool)
    return f"See {a} activity" if a else "See what's building"


def _icon_for(stage: str, is_personal: bool) -> str:
    if is_personal:
        return "👀"
    if stage == 'CONFIRMED':
        return "🚀"
    return "⚠️"


def _color_for(stage: str, direction: str, is_personal: bool) -> str:
    """CONFIRMED bull=green, CONFIRMED bear=red, CONFIRMED neutral=white,
    FORMING=yellow, PERSONAL=purple (overrides). Yellow ONLY for FORMING."""
    if is_personal:
        return 'purple'
    if stage == 'CONFIRMED':
        d = (direction or '').upper()
        if d == 'BEARISH':
            return 'red'
        if d == 'BULLISH':
            return 'green'
        return 'neutral'
    if stage == 'FORMING':
        return 'yellow'
    return 'neutral'  # EARLY


@router.get("/api/miniapp/feed/v2")
async def miniapp_feed_v2(telegram_id: str = "", limit: int = 200):
    """
    Product Feed: NOW / BUILDING / PLAYED OUT.
    Aggregates raw /api/miniapp/feed signals, groups by asset, dedups,
    classifies stage (EARLY/FORMING/CONFIRMED), returns compact cards.
    """
    from datetime import datetime, timezone
    # Pull raw events same way /api/miniapp/feed does
    items = []
    try:
        from services.feed_events_service import build_feed_events
        events = build_feed_events(None, limit=limit)  # all assets
        for ev in events:
            text = str(ev.get('text', '') or '')
            low = text.lower()
            if 'bullish' in low or 'buy' in low or 'accumulation' in low or 'breakout' in low:
                direction = 'BULLISH'
            elif 'bearish' in low or 'sell' in low or 'distribution' in low or 'downside' in low:
                direction = 'BEARISH'
            else:
                direction = 'NEUTRAL'
            items.append({
                'asset': (ev.get('asset') or '').upper(),
                'source': ev.get('type', ''),
                'type': ev.get('type', ''),
                'direction': direction,
                'impact': str(ev.get('priority', 'normal')).upper(),
                'title': text,
                'summary': ev.get('detail', ''),
                'timestamp': ev.get('timestamp', ''),
            })
    except Exception as e:
        return {"ok": False, "error": f"events: {e}"}

    _db = None
    try:
        from pymongo import MongoClient as _SyncMongo
        import os as _os
        _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        _dbname = _os.getenv('DB_NAME', 'fomo_intel')
        _db = _SyncMongo(_dburl)[_dbname]
    except Exception:
        pass

    if not items:
        return {"ok": True, "sections": {"now": [], "building": [], "playedOut": []},
                "assetChips": [], "liveState": {"recent": 0}, "youMissed": []}

    now_utc = datetime.now(timezone.utc)

    # Enrich with minutesAgo
    enriched = []
    for it in items:
        dt = _parse_ts(it.get('timestamp'))
        mins = int((now_utc - dt).total_seconds() / 60) if dt else 999
        if mins < 0:
            mins = 0
        it2 = dict(it)
        it2['_minutesAgo'] = mins
        enriched.append(it2)

    # User's personal assets (recent favorites) — optional
    personal_assets = set()
    if telegram_id and _db is not None:
        try:
            user = _db.miniapp_users.find_one({'telegram_id': str(telegram_id)}, {'_id': 0, 'recent_assets': 1, 'favorite_assets': 1})
            if user:
                for k in ('recent_assets', 'favorite_assets'):
                    for a in (user.get(k) or []):
                        personal_assets.add(str(a).upper())
        except Exception:
            pass

    # Group per section by asset (dedup)
    from collections import defaultdict
    buckets = {'now': defaultdict(list), 'building': defaultdict(list), 'playedOut': defaultdict(list)}

    for it in enriched:
        m = it['_minutesAgo']
        asset = (it.get('asset') or '').upper() or '—'
        if asset == '—' or asset == '':
            continue
        if m < 45:
            buckets['now'][asset].append(it)
        elif m < 120:
            buckets['building'][asset].append(it)
        elif m < 360:
            buckets['playedOut'][asset].append(it)

    def _build_card(asset: str, items_in_group: list, section: str) -> dict:
        stage = _classify_stage(items_in_group)
        direction = _dominant_direction(items_in_group)
        # Strict rule: weak cards (sources < 2 AND stage != CONFIRMED) → DROP
        # This guards Feed integrity — better empty than noisy.
        strong_sources = len(items_in_group) >= 2
        if not strong_sources and stage != 'CONFIRMED':
            return None
        if section == 'now':
            if stage == 'EARLY':
                return None
        elif section == 'building':
            if len(items_in_group) < 2 and stage == 'EARLY':
                return None
        elif section == 'playedOut':
            if stage != 'CONFIRMED':
                return None

        sources_count = len({str(x.get('source') or x.get('type') or '').lower() for x in items_in_group}) or len(items_in_group)
        sources_count = max(sources_count, min(len(items_in_group), 12))
        min_mins = min(x['_minutesAgo'] for x in items_in_group)
        is_personal = asset in personal_assets and section != 'playedOut' and stage != 'EARLY'

        importance = 0
        importance += {'CONFIRMED': 60, 'FORMING': 35, 'EARLY': 15}[stage]
        importance += min(sources_count, 12) * 3
        importance += 10 if is_personal else 0
        importance += max(0, 30 - min_mins) // 2

        return {
            'id': f"{asset}:{section}:{stage}:{min_mins}",
            'asset': asset,
            'stage': stage,
            'direction': direction,
            'minutesAgo': min_mins,
            'sourcesCount': sources_count,
            'isPersonal': bool(is_personal),
            'importance': importance,
            'title': _pick_title(asset, stage, direction, is_personal),
            'timing': _timing_label(min_mins),
            'meaning': _meaning_label(stage, is_personal),
            'directionLine': _direction_line(direction, stage),
            'cta': _cta_label(stage, is_personal, asset),
            'icon': _icon_for(stage, is_personal),
            'color': _color_for(stage, direction, is_personal),
            'stateTag': '',  # NEW / UPDATED — filled later
        }

    def _assemble(section: str, limit_n: int) -> list:
        cards = []
        for asset, grp in buckets[section].items():
            c = _build_card(asset, grp, section)
            if c:
                cards.append(c)
        cards.sort(key=lambda x: (-x['importance'], x['minutesAgo']))
        return cards[:limit_n]

    now_cards = _assemble('now', 4)
    building_cards = _assemble('building', 6)
    played_cards = _assemble('playedOut', 3)

    # BUILDING fallback: если NOW < 3 — разрешаем BUILDING минимум с 3 карточками
    # даже если stage=EARLY (lower bar)
    if len(now_cards) < 3 and len(building_cards) < 3:
        extra = []
        for asset, grp in buckets['building'].items():
            # Build a relaxed card (ignore the "2+ signals" gate) — but still
            # require at least 2 signals OR CONFIRMED stage to avoid noise.
            if len(grp) < 2:
                continue
            stage = _classify_stage(grp)
            direction = _dominant_direction(grp)
            sources_count = max(
                len({str(x.get('source') or x.get('type') or '').lower() for x in grp}),
                len(grp),
            )
            min_mins = min(x['_minutesAgo'] for x in grp)
            is_personal = asset in personal_assets and stage != 'EARLY'
            card = {
                'id': f"{asset}:building:{stage}:{min_mins}",
                'asset': asset,
                'stage': stage,
                'direction': direction,
                'minutesAgo': min_mins,
                'sourcesCount': sources_count,
                'isPersonal': bool(is_personal),
                'importance': {'CONFIRMED': 60, 'FORMING': 35, 'EARLY': 15}[stage] + sources_count * 2,
                'title': _pick_title(asset, stage, direction, is_personal),
                'timing': _timing_label(min_mins),
                'meaning': _meaning_label(stage, is_personal),
                'directionLine': _direction_line(direction, stage),
                'cta': _cta_label(stage, is_personal, asset),
                'icon': _icon_for(stage, is_personal),
                'color': _color_for(stage, direction, is_personal),
                'stateTag': '',
            }
            if not any(c['asset'] == asset for c in building_cards):
                extra.append(card)
        extra.sort(key=lambda x: (-x['importance'], x['minutesAgo']))
        # Top up to 3
        while len(building_cards) < 3 and extra:
            building_cards.append(extra.pop(0))

    # Asset chips — count ≥ 2, top 5
    from collections import Counter
    chip_counter = Counter()
    for it in enriched:
        if it['_minutesAgo'] < 360:
            a = (it.get('asset') or '').upper()
            if a:
                chip_counter[a] += 1
    asset_chips = [{'asset': a, 'count': n} for a, n in chip_counter.most_common(5) if n >= 2]

    recent_15 = sum(1 for it in enriched if it['_minutesAgo'] < 15)

    # ── NEW / UPDATED state diffing ──
    # For the current telegram_id, compare each card to last-seen state.
    if telegram_id and _db is not None:
        try:
            coll = _db.miniapp_user_feed_state
            all_cards_flat = now_cards + building_cards + played_cards
            if all_cards_flat:
                # fetch all prior states for this user + seen assets
                assets_seen = [c['asset'] for c in all_cards_flat]
                prior_docs = list(coll.find(
                    {'telegram_id': str(telegram_id), 'asset': {'$in': assets_seen}},
                    {'_id': 0, 'asset': 1, 'stage': 1, 'direction': 1, 'updatedAt': 1},
                ))
                prior = {d['asset']: d for d in prior_docs}
                for c in all_cards_flat:
                    p = prior.get(c['asset'])
                    if not p:
                        c['stateTag'] = 'NEW'
                    else:
                        if p.get('stage') != c['stage'] or p.get('direction') != c['direction']:
                            c['stateTag'] = 'UPDATED'
                # Upsert new states
                now_iso = now_utc.isoformat()
                for c in all_cards_flat:
                    coll.update_one(
                        {'telegram_id': str(telegram_id), 'asset': c['asset']},
                        {'$set': {
                            'telegram_id': str(telegram_id),
                            'asset': c['asset'],
                            'stage': c['stage'],
                            'direction': c['direction'],
                            'updatedAt': now_iso,
                        }},
                        upsert=True,
                    )
        except Exception:
            pass

    you_missed = [
        {
            'asset': c['asset'],
            'title': c['title'],
            'minutesAgo': c['minutesAgo'],
            'timing': c['timing'],
            'icon': c['icon'],
        } for c in played_cards
    ]

    return {
        'ok': True,
        'sections': {
            'now': now_cards,
            'building': building_cards,
            'playedOut': played_cards,
        },
        'assetChips': asset_chips,
        'liveState': {'recent': recent_15},
        'youMissed': you_missed,
        'generatedAt': now_utc.isoformat(),
    }



@router.post("/api/miniapp/track-asset")
async def miniapp_track_asset(body: dict):
    """
    Track asset opens for personal-feed layer + News personalization.
    Keeps last 5 recently-opened assets per telegram_id.
    """
    telegram_id = str(body.get('telegram_id') or '').strip()
    asset = str(body.get('asset') or '').upper().strip()
    if not telegram_id or not asset:
        return {"ok": False, "error": "missing"}
    try:
        from pymongo import MongoClient as _SyncMongo
        import os as _os
        from datetime import datetime as _dt, timezone as _tz
        _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        _dbname = _os.getenv('DB_NAME', 'fomo_intel')
        _db = _SyncMongo(_dburl)[_dbname]
        doc = _db.miniapp_users.find_one(
            {'telegram_id': telegram_id},
            {'_id': 0, 'recent_assets': 1}
        ) or {}
        recent = [a for a in (doc.get('recent_assets') or []) if a != asset]
        recent.insert(0, asset)
        recent = recent[:5]
        _db.miniapp_users.update_one(
            {'telegram_id': telegram_id},
            {'$set': {
                'telegram_id': telegram_id,
                'recent_assets': recent,
                'last_clicked_asset': asset,
                'last_click_at': _dt.now(_tz.utc).isoformat(),
            }},
            upsert=True,
        )
        return {"ok": True, "recent_assets": recent}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# PRESENCE HEARTBEAT — tracks whether user is currently in app
# Used by push engine to NOT notify active users.
# ═══════════════════════════════════════════════════════════
@router.post("/api/miniapp/presence/heartbeat")
async def miniapp_presence_heartbeat(body: dict):
    telegram_id = str(body.get('telegram_id') or '').strip()
    if not telegram_id:
        return {"ok": False, "error": "telegram_id required"}
    try:
        from pymongo import MongoClient as _SyncMongo
        import os as _os
        from datetime import datetime as _dt, timezone as _tz
        _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        _dbname = _os.getenv('DB_NAME', 'fomo_intel')
        _db = _SyncMongo(_dburl)[_dbname]
        now_iso = _dt.now(_tz.utc).isoformat()
        _db.miniapp_users.update_one(
            {'telegram_id': telegram_id},
            {'$set': {'telegram_id': telegram_id, 'last_seen_at': now_iso}},
            upsert=True,
        )
        return {"ok": True, "last_seen_at": now_iso}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# PUSH SETTINGS — user-level Telegram alert preferences
# ═══════════════════════════════════════════════════════════

_PUSH_DEFAULTS = {
    "direction_shifts": True,   # bullish ⟷ bearish flip
    "high_conf": True,          # signals with confidence ≥ 70%
    "edge_opens": False,        # prediction market edge opens
    "digest": True,             # daily morning digest
}


def _push_db():
    from pymongo import MongoClient as _SyncMongo
    import os as _os
    _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    _dbname = _os.getenv('DB_NAME', 'fomo_intel')
    return _SyncMongo(_dburl)[_dbname]


@router.get("/api/miniapp/push/settings")
async def push_settings_get(telegram_id: str = ""):
    """Read user's push preferences. Returns defaults if no record yet."""
    tid = str(telegram_id or '').strip()
    if not tid:
        return {"ok": False, "error": "telegram_id required"}
    try:
        db = _push_db()
        doc = db.push_subscribers.find_one({'telegram_id': tid}, {'_id': 0}) or {}
        prefs = dict(_PUSH_DEFAULTS)
        for k in _PUSH_DEFAULTS.keys():
            if k in doc:
                prefs[k] = bool(doc.get(k))
        return {
            "ok": True,
            "telegram_id": tid,
            "subscribed": bool(doc.get('subscribed', False)),
            "prefs": prefs,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/miniapp/push/settings")
async def push_settings_set(body: dict):
    """
    Update user's push preferences.
    Body: { telegram_id, prefs: {direction_shifts, high_conf, edge_opens, digest} }
    """
    tid = str(body.get('telegram_id') or '').strip()
    if not tid:
        return {"ok": False, "error": "telegram_id required"}
    prefs_in = body.get('prefs') or {}
    update = {'telegram_id': tid, 'subscribed': True}
    for k in _PUSH_DEFAULTS.keys():
        if k in prefs_in:
            update[k] = bool(prefs_in[k])
    try:
        db = _push_db()
        db.push_subscribers.update_one(
            {'telegram_id': tid},
            {'$set': update},
            upsert=True,
        )
        doc = db.push_subscribers.find_one({'telegram_id': tid}, {'_id': 0}) or {}
        prefs = dict(_PUSH_DEFAULTS)
        for k in _PUSH_DEFAULTS.keys():
            if k in doc:
                prefs[k] = bool(doc.get(k))
        return {"ok": True, "prefs": prefs, "subscribed": bool(doc.get('subscribed', True))}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# PUSH ENGINE — "SOMETHING IS BUILDING"
# Behavior:
#   • condition: per-asset signals_forming >= 3 AND avg_confidence > 20%
#   • target: push_subscribers with subscribed=true
#   • rate-limit: 1 per 6h per subscriber (global, not per-asset)
#   • presence gate: skip if user seen in app within last 10 minutes
#   • deep-link: opens Mini App on News tab (t.me/<bot>?startapp=news_<asset>)
# If MINIAPP_BOT_TOKEN is set → sends real Telegram message.
# Always logs to push_log collection for auditing.
# ═══════════════════════════════════════════════════════════

_BUILDING_PUSH_WINDOW_MIN_H = 6         # min hours between pushes per subscriber
_BUILDING_PUSH_WINDOW_MAX_H = 8         # upper bound (not used hard but reserved)
_BUILDING_PRESENCE_GATE_MIN = 10        # minutes — if seen within this window = "in app"
_BUILDING_MIN_SIGNALS = 3               # signals_forming threshold
_BUILDING_MIN_CONF_AVG = 0.20           # avg confidence threshold


def _building_db():
    from pymongo import MongoClient as _SyncMongo
    import os as _os
    _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    _dbname = _os.getenv('DB_NAME', 'fomo_intel')
    return _SyncMongo(_dburl)[_dbname]


def _building_scan_candidates():
    """
    Scan feed events, group by asset, pick best candidate where:
      signals_forming >= 3 AND avg_confidence > 0.20
    Returns list of {asset, signals_count, avg_conf, direction} sorted by score desc.
    """
    try:
        from services.feed_events_service import build_feed_events
        events = build_feed_events(None, limit=300) or []
    except Exception:
        return []

    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    per_asset = {}
    for ev in events:
        asset = (ev.get('asset') or '').upper().strip()
        if not asset:
            continue
        ts = ev.get('timestamp')
        mins = 999
        try:
            if ts:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                mins = max(0, int((now_utc - dt).total_seconds() / 60))
        except Exception:
            pass
        # "forming" = recent-ish (< 180 min) & not ancient
        if mins > 180:
            continue
        text = str(ev.get('text') or '').lower()
        # crude direction
        if any(w in text for w in ('bullish', 'accumulation', 'breakout', 'surge', 'buy')):
            direction = 'BULLISH'
        elif any(w in text for w in ('bearish', 'distribution', 'dump', 'sell', 'breakdown')):
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'
        # crude confidence: priority + recency
        priority = str(ev.get('priority') or 'normal').lower()
        p_score = {'high': 0.65, 'urgent': 0.80, 'normal': 0.35, 'low': 0.18}.get(priority, 0.35)
        fresh_bonus = max(0.0, 0.15 * (1.0 - mins / 180.0))
        conf = min(1.0, p_score + fresh_bonus)
        bucket = per_asset.setdefault(asset, {'count': 0, 'conf_sum': 0.0, 'dirs': {}})
        bucket['count'] += 1
        bucket['conf_sum'] += conf
        bucket['dirs'][direction] = bucket['dirs'].get(direction, 0) + 1

    candidates = []
    for asset, b in per_asset.items():
        n = b['count']
        if n < _BUILDING_MIN_SIGNALS:
            continue
        avg_conf = b['conf_sum'] / n if n else 0.0
        if avg_conf <= _BUILDING_MIN_CONF_AVG:
            continue
        # pick dominant direction
        d_items = sorted(b['dirs'].items(), key=lambda x: -x[1])
        dominant = d_items[0][0] if d_items else 'NEUTRAL'
        candidates.append({
            'asset': asset,
            'signals_count': n,
            'avg_conf': round(avg_conf, 3),
            'direction': dominant,
            'score': n * avg_conf,
        })
    candidates.sort(key=lambda x: -x['score'])
    return candidates


def _building_format_message(candidate: dict) -> dict:
    asset = candidate['asset']
    n = candidate['signals_count']
    text = (
        f"⚡ {asset} setup forming\n"
        f"Multiple signals detected ({n})\n"
        f"→ Check setup"
    )
    import os as _os
    # Prefer MiniApp bot username (we send via MINIAPP_BOT_TOKEN). Fallback chain.
    bot_username = (
        _os.getenv('MINIAPP_BOT_USERNAME')
        or _os.getenv('TELEGRAM_BOT_USERNAME')
        or 'FOMO_mini_bot'
    ).lstrip('@')
    deep_link = f"https://t.me/{bot_username}?startapp=news_{asset}"
    return {'text': text, 'deep_link': deep_link}


def _building_send_telegram(chat_id: str, text: str, deep_link: str) -> dict:
    import os as _os
    import httpx
    token = _os.getenv('MINIAPP_BOT_TOKEN', '') or _os.getenv('TELEGRAM_BOT_TOKEN', '')
    if not token:
        return {'ok': False, 'error': 'no_token'}
    try:
        payload = {
            'chat_id': chat_id,
            'text': text,
            'reply_markup': {
                'inline_keyboard': [[{'text': 'Open News ▸', 'url': deep_link}]]
            },
            'disable_web_page_preview': True,
        }
        with httpx.Client(timeout=6.0) as cli:
            r = cli.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
            data = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
            return {'ok': bool(data.get('ok', False)), 'resp': data}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _building_run_once(dry_run: bool = False, force_subscriber: str = '') -> dict:
    """Evaluate + send (or dry-run). Returns a summary dict."""
    from datetime import datetime, timezone, timedelta
    db = _building_db()

    candidates = _building_scan_candidates()
    if not candidates:
        return {"ok": True, "candidates": [], "sent": 0, "skipped": 0, "reason": "no_candidates"}

    top = candidates[0]  # only best asset
    msg = _building_format_message(top)
    now_utc = datetime.now(timezone.utc)
    rate_cutoff = now_utc - timedelta(hours=_BUILDING_PUSH_WINDOW_MIN_H)
    presence_cutoff = now_utc - timedelta(minutes=_BUILDING_PRESENCE_GATE_MIN)

    # Collect eligible subscribers
    if force_subscriber:
        # Manual trigger — build a minimal stub subscriber, bypass everything
        subs = [{'telegram_id': str(force_subscriber), 'subscribed': True}]
    else:
        subs = list(db.push_subscribers.find({'subscribed': True}, {'_id': 0}))
    sent = 0
    skipped = 0
    details = []

    for s in subs:
        tid = str(s.get('telegram_id') or '').strip()
        if not tid or not tid.lstrip('-').isdigit():
            skipped += 1
            details.append({'telegram_id': tid, 'status': 'invalid_chat_id'})
            continue

        # Rate limit
        last = db.push_log.find_one(
            {'telegram_id': tid, 'kind': 'building'},
            sort=[('sent_at', -1)],
            projection={'_id': 0, 'sent_at': 1},
        )
        if last and not force_subscriber:
            last_at_raw = last.get('sent_at')
            try:
                last_at = datetime.fromisoformat(str(last_at_raw).replace('Z', '+00:00')) if last_at_raw else None
                if last_at and last_at.tzinfo is None:
                    last_at = last_at.replace(tzinfo=timezone.utc)
                if last_at and last_at > rate_cutoff:
                    skipped += 1
                    details.append({'telegram_id': tid, 'status': 'rate_limited', 'last_at': str(last_at_raw)})
                    continue
            except Exception:
                pass

        # Presence gate — skip if user in app recently
        if not force_subscriber:
            u = db.miniapp_users.find_one({'telegram_id': tid}, {'_id': 0, 'last_seen_at': 1}) or {}
            ls = u.get('last_seen_at')
            try:
                if ls:
                    ls_dt = datetime.fromisoformat(str(ls).replace('Z', '+00:00'))
                    if ls_dt.tzinfo is None:
                        ls_dt = ls_dt.replace(tzinfo=timezone.utc)
                    if ls_dt > presence_cutoff:
                        skipped += 1
                        details.append({'telegram_id': tid, 'status': 'user_in_app', 'last_seen_at': str(ls)})
                        continue
            except Exception:
                pass

        # Send
        if dry_run:
            sent += 1
            details.append({'telegram_id': tid, 'status': 'dry_run'})
            continue

        send_res = _building_send_telegram(tid, msg['text'], msg['deep_link'])
        # Log
        db.push_log.insert_one({
            'telegram_id': tid,
            'kind': 'building',
            'asset': top['asset'],
            'signals_count': top['signals_count'],
            'avg_conf': top['avg_conf'],
            'direction': top['direction'],
            'text': msg['text'],
            'deep_link': msg['deep_link'],
            'sent_at': now_utc.isoformat(),
            'delivered': bool(send_res.get('ok')),
            'response': send_res,
        })
        if send_res.get('ok'):
            sent += 1
            details.append({'telegram_id': tid, 'status': 'sent'})
        else:
            skipped += 1
            details.append({'telegram_id': tid, 'status': 'send_failed', 'error': send_res.get('error') or send_res.get('resp')})

    return {
        "ok": True,
        "candidates": candidates[:3],
        "chosen": top,
        "message": msg,
        "subscribers_scanned": len(subs),
        "sent": sent,
        "skipped": skipped,
        "dry_run": dry_run,
        "details": details[:20],
    }


@router.get("/api/miniapp/push/evaluate")
async def miniapp_push_evaluate():
    """Dry-run: returns candidates + who would receive the push (no send)."""
    try:
        return _building_run_once(dry_run=True)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/miniapp/push/run")
async def miniapp_push_run(body: dict = None):
    """
    Actual send. Optional body: {"telegram_id": "<id>"} forces send to single subscriber
    (bypasses rate limit / presence, useful for manual testing).
    """
    body = body or {}
    force = str(body.get('telegram_id') or '').strip()
    try:
        return _building_run_once(dry_run=False, force_subscriber=force)
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/api/miniapp/push/log")
async def miniapp_push_log(limit: int = 20, telegram_id: str = ""):
    """Inspect recent push_log entries. Useful for debugging the loop."""
    try:
        db = _building_db()
        q = {}
        if telegram_id:
            q['telegram_id'] = str(telegram_id)
        rows = list(db.push_log.find(q, {'_id': 0}).sort('sent_at', -1).limit(int(limit)))
        return {"ok": True, "items": rows, "count": len(rows)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# Lazy background loop — starts on first call to /api/miniapp/lite.
_BUILDING_LOOP_STARTED = {'v': False}


async def _building_push_loop():
    import asyncio as _aio
    await _aio.sleep(60)  # warm-up
    print("[Building Push] Loop started (interval=600s)")
    while True:
        try:
            summary = _building_run_once(dry_run=False)
            if summary.get('sent', 0) > 0:
                print(f"[Building Push] Sent={summary['sent']} Skipped={summary['skipped']} Asset={summary.get('chosen',{}).get('asset')}")
        except Exception as e:
            print(f"[Building Push] tick error: {e}")
        await _aio.sleep(600)  # 10 minutes


def _ensure_building_loop():
    """Start the background loop once (idempotent)."""
    if _BUILDING_LOOP_STARTED['v']:
        return
    _BUILDING_LOOP_STARTED['v'] = True
    try:
        import asyncio as _aio
        loop = _aio.get_event_loop()
        loop.create_task(_building_push_loop())
    except Exception as e:
        print(f"[Building Push] spawn error: {e}")
        _BUILDING_LOOP_STARTED['v'] = False



# ═══════════════════════════════════════════════════════════
# EDGE V2 — unified monetizable edge screen
# Hero: potential move + confidence + status
# Why: 5 bullets · Drivers: 5 signals · Timing stepper · PRO unlocks
# ═══════════════════════════════════════════════════════════

def _edge_db():
    from pymongo import MongoClient as _SyncMongo
    import os as _os
    _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
    _dbname = _os.getenv('DB_NAME', 'fomo_intel')
    return _SyncMongo(_dburl)[_dbname]


def _driver_alignment(modules: list, direction: str) -> tuple:
    """Count aligned drivers. Returns (aligned_count, total, per_driver)"""
    per = []
    aligned = 0
    for m in modules or []:
        name = m.get('module') or m.get('name') or '—'
        d = str(m.get('direction') or '').lower()
        conf = float(m.get('confidence', 0) or 0)
        tgt = (direction or '').lower()
        if d.startswith('bull') and tgt.startswith('bull'):
            state = 'aligned'
            aligned += 1
        elif d.startswith('bear') and tgt.startswith('bear'):
            state = 'aligned'
            aligned += 1
        elif d.startswith('neu') or d == '':
            state = 'forming' if conf >= 0.2 else 'off'
        else:
            state = 'off'
        per.append({'name': name, 'state': state, 'confidence': round(conf * 100)})
    return aligned, len(per), per


def _edge_stage(aligned: int, total: int, minutes_active: int) -> str:
    """EARLY / FORMING / ACTIVE / PLAYED_OUT"""
    if minutes_active > 240:
        return 'PLAYED_OUT'
    ratio = aligned / max(total, 1)
    if ratio >= 0.75:
        return 'ACTIVE'
    if ratio >= 0.4:
        return 'FORMING'
    return 'EARLY'


def _stage_index(stage: str) -> int:
    return {'EARLY': 0, 'FORMING': 1, 'ACTIVE': 2, 'PLAYED_OUT': 3}.get(stage, 0)


def _edge_fomo(stage: str, aligned: int, total: int) -> str:
    if stage == 'ACTIVE':
        return 'Window closing'
    if stage == 'FORMING':
        return 'Momentum building'
    if stage == 'PLAYED_OUT':
        return 'Move played out'
    return 'Setup forming'


def _market_context(home_status: str, stage: str) -> str:
    home = (home_status or 'WAIT').upper()
    if stage == 'ACTIVE':
        return f"{home} → EDGE active"
    if stage == 'FORMING':
        return f"{home} → EDGE forming"
    if stage == 'PLAYED_OUT':
        return f"{home} → move complete"
    return f"{home} → setup building"


def _get_user_tier(db, telegram_id: str) -> str:
    if not telegram_id:
        return 'FREE'
    try:
        u = db.miniapp_users.find_one({'telegram_id': str(telegram_id)}, {'_id': 0, 'tier': 1}) or {}
        return (u.get('tier') or 'FREE').upper()
    except Exception:
        return 'FREE'


@router.get("/api/miniapp/edge/v2")
async def miniapp_edge_v2(telegram_id: str = "", asset: str = "BTC"):
    """
    Unified monetizable Edge payload.
    Pulls MetaBrain (drivers), chart-series (potential move),
    Home (status), and optional Feed context into one product card.
    """
    asset = (asset or 'BTC').upper()
    out = {"ok": True, "asset": asset}

    # 1. Home / decision context (fetch internal endpoint — always works)
    home = {}
    try:
        import httpx as _httpx
        async with _httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(f"http://127.0.0.1:8001/api/miniapp/home?asset={asset}")
            if r.status_code == 200:
                home = r.json() or {}
    except Exception as _e:
        try:
            from miniapp.home_builder import build_home as _bh
            from server import db as _mdb
            home = await _bh(_mdb, asset) or {}
        except Exception:
            home = {}
    decision = home.get('decision') or {}
    structure = home.get('structure') or {}
    why_arr = home.get('why') or []
    modules = structure.get('modules') or []

    # 2. Chart series / potential move
    potential_move = 0.0
    confidence_pct = int(round(float(decision.get('confidence') or 0) * 100))
    direction = 'NEUTRAL'
    try:
        from services.meta_brain_service import build_horizon_forecasts
        mb = build_horizon_forecasts(asset)
        h = (mb.get('horizons') or {}).get('30D', {}) or {}
        direction = (h.get('direction', 'NEUTRAL') or 'NEUTRAL').upper()
        er = float(h.get('expectedReturn', 0) or 0)
        potential_move = round(abs(er) * 100, 1)
        if potential_move > 0:
            mb_conf = float(h.get('confidence', 0) or 0)
            if mb_conf > 0:
                confidence_pct = int(round(mb_conf * 100))
    except Exception:
        pass

    # If MetaBrain empty, derive direction from decision
    action = (decision.get('action') or '').upper()
    if direction == 'NEUTRAL' and action == 'BUY':
        direction = 'BULLISH'
    elif direction == 'NEUTRAL' and action == 'SELL':
        direction = 'BEARISH'

    # 3. Driver alignment
    aligned, total, per_driver = _driver_alignment(modules, direction)
    if total == 0:
        total = 5  # fallback

    # 4. Stage (edge lifecycle)
    # minutes_active: stub — could be derived from feed NOW cards for asset
    minutes_active = 0
    try:
        feed_events_col = _edge_db().fomo_feed_events if False else None  # placeholder
    except Exception:
        pass
    stage = _edge_stage(aligned, total, minutes_active)

    # 5. Market context
    home_status = 'WAIT'
    mode = (decision.get('mode') or '').upper()
    if action in ('BUY', 'SELL') or mode == 'CONFIRMED':
        home_status = 'GO'
    elif mode in ('DEFENSIVE', 'AGGRESSIVE'):
        home_status = 'READY'
    elif action == 'WAIT' or mode == 'EARLY':
        home_status = 'WAIT'
    else:
        home_status = 'WATCH'
    market_ctx = _market_context(home_status, stage)

    # 6. PRO unlocks
    price = float(home.get('price') or 0)
    pro_unlocks = {}
    ap = home.get('actionPlan') or {}
    ez = ap.get('entryZone') or {}
    if ez.get('min') and ez.get('max'):
        pro_unlocks['entry'] = f"${int(ez['min']):,} – ${int(ez['max']):,}"
    elif price > 0:
        # Derive reasonable entry from potential move + direction
        if direction == 'BULLISH':
            pro_unlocks['entry'] = f"${int(price * 0.985):,} – ${int(price * 0.998):,}"
        elif direction == 'BEARISH':
            pro_unlocks['entry'] = f"${int(price * 1.002):,} – ${int(price * 1.015):,}"
        else:
            pro_unlocks['entry'] = "Forming"
    else:
        pro_unlocks['entry'] = "Forming"

    if ap.get('invalidation'):
        pro_unlocks['invalidation'] = f"below ${int(ap['invalidation']):,}"
    elif price > 0:
        if direction == 'BULLISH':
            pro_unlocks['invalidation'] = f"below ${int(price * 0.975):,}"
        elif direction == 'BEARISH':
            pro_unlocks['invalidation'] = f"above ${int(price * 1.025):,}"
        else:
            pro_unlocks['invalidation'] = "Not defined"
    else:
        pro_unlocks['invalidation'] = "Not defined"

    if potential_move > 0 and price > 0:
        tgt = price * (1 + (potential_move / 100.0 if direction == 'BULLISH' else -potential_move / 100.0))
        pro_unlocks['target'] = f"${int(tgt):,}"
    else:
        pro_unlocks['target'] = "Pending"

    # Time window by stage
    pro_unlocks['timeWindow'] = {
        'ACTIVE': 'Next 6–12h',
        'FORMING': 'Next 12–48h',
        'EARLY': '2–5 days',
        'PLAYED_OUT': 'Closed',
    }[stage]

    # 7. Why this edge — top insights from structure modules + decision why
    why_edge = []
    if aligned > 0:
        why_edge.append(f"{aligned}/{total} drivers aligned")
    for m in modules:
        ins = m.get('insight')
        if ins and m.get('direction', '').lower().startswith(direction.lower()[:4]):
            why_edge.append(ins)
    if len(why_edge) < 3:
        for w in why_arr[:4]:
            if isinstance(w, str) and w not in why_edge:
                why_edge.append(w)
    why_edge = why_edge[:5]

    # 8. User tier
    try:
        db = _edge_db()
        user_tier = _get_user_tier(db, telegram_id)
    except Exception:
        user_tier = 'FREE'

    # 9. Accuracy — could read from performance collection; stub for now
    accuracy = 82
    try:
        perf = _edge_db().miniapp_users.find_one({'telegram_id': str(telegram_id)}, {'_id': 0, 'performance': 1}) or {}
        acc = (perf.get('performance') or {}).get('accuracy')
        if acc:
            accuracy = int(acc)
    except Exception:
        pass

    out.update({
        "asset": asset,
        "potentialMove": potential_move,
        "direction": direction,
        "confidence": confidence_pct,
        "accuracy": accuracy,
        "stage": stage,
        "stageIndex": _stage_index(stage),
        "fomoTrigger": _edge_fomo(stage, aligned, total),
        "marketContext": market_ctx,
        "aligned": aligned,
        "driversTotal": total,
        "drivers": per_driver,
        "whyEdge": why_edge,
        "proUnlocks": pro_unlocks,
        "userTier": user_tier,
        "price": price,
    })

    # ═══ Conversion trigger + view tracking ═══
    try:
        db2 = _edge_db()
        if telegram_id:
            prof = db2.miniapp_users.find_one(
                {'telegram_id': str(telegram_id)},
                {'_id': 0, 'edge_views': 1}) or {}
            views = int(prof.get('edge_views', 0)) + 1
            db2.miniapp_users.update_one(
                {'telegram_id': str(telegram_id)},
                {'$set': {'telegram_id': str(telegram_id), 'edge_views': views}},
                upsert=True)
        else:
            views = 0
    except Exception:
        views = 0

    # Determine trigger type for FREE users
    # Priority: missed > first_edge > repeat > none
    trig_type = 'none'
    trig_copy = {}
    if user_tier != 'PRO':
        if stage == 'PLAYED_OUT':
            trig_type = 'missed'
            trig_copy = {
                'title': "This move already played out",
                'sub': "Don't miss the next one · Signal activating soon",
                'cta': "Unlock next setup →",
                'urgency': "Next setup forming now",
            }
        elif stage == 'ACTIVE':
            trig_type = 'missed'
            trig_copy = {
                'title': "This move is playing out",
                'sub': "Entry window closing · Unlock exact levels",
                'cta': "Unlock this trade →",
                'urgency': "Move active now",
            }
        elif stage == 'FORMING' and confidence_pct >= 20:
            trig_type = 'first_edge'
            trig_copy = {
                'title': "A setup is forming",
                'sub': "Entry & timing available now · You're early",
                'cta': "Unlock this setup →",
                'urgency': "Breakout likely within hours",
            }
        elif views >= 3:
            trig_type = 'repeat'
            trig_copy = {
                'title': f"You've checked {views} setups",
                'sub': "Unlock full access · See every entry, target, timing",
                'cta': "Get PRO →",
                'urgency': "Stop tracking · start trading",
            }

    # Social proof (stable rotation — keeps feel real without mocking random)
    social = _edge_social_proof(asset)

    out.update({
        "edgeViews": views,
        "trigger": {
            "type": trig_type,
            "shouldAutoOpen": trig_type in ('first_edge', 'missed'),
            "copy": trig_copy,
        },
        "socialProof": social,
    })
    return out


def _edge_social_proof(asset: str) -> dict:
    """Deterministic social-proof numbers per asset/day. Not random, stable per 6h window."""
    import hashlib
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    bucket = now.strftime('%Y-%m-%d-') + str(now.hour // 6)
    h = int(hashlib.md5(f"{asset}:{bucket}".encode()).hexdigest()[:8], 16)
    unlocked_today = 11 + (h % 34)         # 11–44
    tracking_now = 900 + (h % 850)         # 900–1749
    return {
        "unlockedToday": unlocked_today,
        "trackingNow": tracking_now,
    }


@router.post("/api/miniapp/user/tier")
async def miniapp_user_tier(body: dict):
    """Dev-only: flip user tier between FREE / PRO for preview."""
    tid = str(body.get('telegram_id') or '').strip()
    tier = str(body.get('tier') or '').upper().strip()
    if not tid or tier not in ('FREE', 'PRO'):
        return {"ok": False, "error": "bad input"}
    try:
        db = _edge_db()
        db.miniapp_users.update_one(
            {'telegram_id': tid},
            {'$set': {'telegram_id': tid, 'tier': tier}},
            upsert=True,
        )
        return {"ok": True, "telegram_id": tid, "tier": tier}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════
# NEWS V2 — Market Awareness Layer (entry point)
# ═══════════════════════════════════════════════════════════

def _news_classify(src: str) -> str:
    s = (src or '').lower()
    if s in ('sentiment', 'twitter', 'social'):
        return 'social'
    if s in ('news', 'press', 'announcement'):
        return 'news'
    return 'signal'


def _impact_level(impact: str, sources_count: int) -> str:
    i = (impact or '').upper()
    if i == 'HIGH' or sources_count >= 7:
        return 'High'
    if i in ('MED', 'MEDIUM') or sources_count >= 4:
        return 'Medium'
    return 'Low'


def _interpretation(direction: str, ntype: str) -> str:
    d = (direction or '').upper()
    if ntype == 'social':
        if d == 'BULLISH': return 'Sentiment spike detected · bullish tilt'
        if d == 'BEARISH': return 'Sentiment shift · cautious tone'
        return 'Social attention rising'
    if ntype == 'news':
        if d == 'BULLISH': return 'Potential bullish pressure'
        if d == 'BEARISH': return 'Potential bearish pressure'
        return 'Market uncertainty increasing'
    if d == 'BULLISH': return 'Momentum building · bullish tilt'
    if d == 'BEARISH': return 'Downside pressure forming'
    return 'Market attention shifting'


def _time_phrase(minutes: int, ntype: str) -> str:
    if minutes < 5:
        prefix = 'Just forming' if ntype == 'signal' else ('Just posted' if ntype == 'social' else 'Just broke')
    elif minutes < 30:
        prefix = 'Developing'
    elif minutes < 120:
        prefix = 'Momentum building'
    else:
        prefix = 'Cooling'
    t = f"{minutes}m" if minutes < 60 else f"{minutes//60}h"
    return f"{prefix} · {t}"


@router.get("/api/miniapp/news/v2")
async def miniapp_news_v2(tab: str = "all", limit: int = 40, telegram_id: str = ""):
    from datetime import datetime, timezone
    tab = (tab or 'all').lower()
    try:
        from services.feed_events_service import build_feed_events
        events = build_feed_events(None, limit=limit)
    except Exception as e:
        return {"ok": False, "error": f"events: {e}"}

    # ── Personalization: fetch user's recent assets ─────────────
    personal_set = set()
    if telegram_id:
        try:
            from pymongo import MongoClient as _SyncMongo
            import os as _os
            _dburl = _os.getenv('MONGO_URL', 'mongodb://localhost:27017')
            _dbname = _os.getenv('DB_NAME', 'fomo_intel')
            _db_p = _SyncMongo(_dburl)[_dbname]
            udoc = _db_p.miniapp_users.find_one(
                {'telegram_id': str(telegram_id)},
                {'_id': 0, 'recent_assets': 1, 'favorite_assets': 1}
            ) or {}
            for k in ('recent_assets', 'favorite_assets'):
                for a in (udoc.get(k) or []):
                    personal_set.add(str(a).upper())
        except Exception:
            pass

    now_utc = datetime.now(timezone.utc)
    items = []
    asset_counts = {}

    for ev in events:
        asset = (ev.get('asset') or '').upper()
        if not asset:
            continue
        src = ev.get('type') or ''
        text = str(ev.get('text') or '')
        detail = str(ev.get('detail') or '')
        ts = ev.get('timestamp')
        low = (text + ' ' + detail).lower()
        if any(w in low for w in ('bullish', 'accumulation', 'breakout', 'surge', 'buy')):
            direction = 'BULLISH'
        elif any(w in low for w in ('bearish', 'distribution', 'dump', 'sell', 'breakdown')):
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'
        ntype = _news_classify(src)
        mins = 999
        if ts:
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    if not dt.tzinfo:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                mins = max(0, int((now_utc - dt).total_seconds() / 60))
            except Exception:
                pass
        if mins > 360:
            continue
        impact = _impact_level(ev.get('priority', 'normal'), 1)
        is_relevant = asset in personal_set
        # Extract real source names for "Source: X · Y · Z" trust line
        src_raw = str(ev.get('source') or ev.get('origin') or ev.get('feed') or '').strip()
        src_list = []
        if src_raw:
            src_list.append(src_raw)
        # Add canonical sources by type (gives trust even on 1-source events)
        if ntype == 'news' and not src_list:
            src_list = ['News Aggregator']
        elif ntype == 'social' and not src_list:
            src_list = ['Twitter', 'Telegram']
        elif ntype == 'signal' and not src_list:
            src_list = ['MetaBrain', 'On-chain', 'Exchange']
        items.append({
            'id': f"{ntype}:{asset}:{mins}:{text[:30]}",
            'type': ntype,
            'asset': asset,
            'direction': direction,
            'title': text or f"{asset} activity",
            'interpretation': _interpretation(direction, ntype),
            'timing': _time_phrase(mins, ntype),
            'minutesAgo': mins,
            'impact': impact,
            'ctaAsset': asset,
            'ctaLabel': '→ Open setup',
            'relevantToYou': bool(is_relevant),
            'sources': src_list[:3],
        })
        asset_counts[asset] = asset_counts.get(asset, 0) + 1

    # dedup (type + asset) same 30-min window
    seen = {}
    deduped = []
    for it in items:
        key = (it['type'], it['asset'])
        prev = seen.get(key)
        if prev is None or abs(prev - it['minutesAgo']) > 30:
            seen[key] = it['minutesAgo']
            deduped.append(it)

    if tab == 'signals':
        filtered = [i for i in deduped if i['type'] == 'signal']
    elif tab == 'news':
        filtered = [i for i in deduped if i['type'] == 'news']
    elif tab == 'social':
        filtered = [i for i in deduped if i['type'] == 'social']
    else:
        filtered = deduped

    impact_score = {'High': 3, 'Medium': 2, 'Low': 1}
    # Sort: relevant items float to top, then impact, then freshness
    filtered.sort(key=lambda x: (
        0 if x.get('relevantToYou') else 1,
        -impact_score.get(x['impact'], 0),
        x['minutesAgo'],
    ))

    counters = {
        'all': len(deduped),
        'signals': sum(1 for i in deduped if i['type'] == 'signal'),
        'news': sum(1 for i in deduped if i['type'] == 'news'),
        'social': sum(1 for i in deduped if i['type'] == 'social'),
        'relevant': sum(1 for i in deduped if i.get('relevantToYou')),
    }

    total = len(deduped)
    recent_15 = sum(1 for i in deduped if i['minutesAgo'] < 15)
    high_impact = sum(1 for i in deduped if i['impact'] == 'High')
    relevant_assets = sorted({i['asset'] for i in deduped if i.get('relevantToYou')})
    hot = sorted(asset_counts.items(), key=lambda x: -x[1])[:3]
    top_assets = [a for a, c in hot if c >= 2]

    # Hero: personalized version takes priority when user has recent assets with signals
    if relevant_assets:
        hero = {"emoji": '👀', "title": 'Your assets are heating up'}
        hero["subtitle"] = ' · '.join(relevant_assets[:3]) + ' gaining attention'
    elif high_impact >= 3 or recent_15 >= 6:
        hero = {"emoji": '⚡', "title": 'Market heating up'}
        hero["subtitle"] = ' · '.join(top_assets) + ' gaining attention' if top_assets else None
    elif recent_15 >= 3:
        hero = {"emoji": '⚠️', "title": 'Market tension rising'}
        hero["subtitle"] = ' · '.join(top_assets) + ' gaining attention' if top_assets else None
    elif total >= 5:
        hero = {"emoji": '👀', "title": 'Multiple signals building'}
        hero["subtitle"] = ' · '.join(top_assets) + ' gaining attention' if top_assets else None
    else:
        hero = {"emoji": '·', "title": 'Market quiet', "subtitle": None}
        hero = {"emoji": '·', "title": 'Market quiet'}
    hero["subtitle"] = ' · '.join(top_assets) + ' gaining attention' if top_assets else None

    return {
        "ok": True,
        "tab": tab,
        "items": filtered[:30],
        "counters": counters,
        "hero": hero,
        "live": {"watching": total, "recent15": recent_15, "updatedAt": now_utc.isoformat()},
    }

