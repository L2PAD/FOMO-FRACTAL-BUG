/* Truth Layer + Partial Reveal injection for MiniApp signal pages */
(function(){
var truthDone=false;
function dk(){if(window.Telegram&&Telegram.WebApp)return Telegram.WebApp.colorScheme!=='light';return true}

function injectTruth(){
  if(truthDone||document.getElementById('_truth_layer'))return;
  // Find the signal decision card — contains BUY/SELL/WAIT + confidence bar
  var cards=document.querySelectorAll('div');
  var signalCard=null;
  for(var i=0;i<cards.length;i++){
    var d=cards[i],t=d.textContent||'';
    if((t.indexOf('BUY')!==-1||t.indexOf('SELL')!==-1||t.indexOf('WAIT')!==-1)&&
       t.indexOf('Confidence')!==-1&&d.offsetHeight>100&&d.offsetWidth>200){
      signalCard=d;break;
    }
  }
  if(!signalCard)return;

  // Fetch signal with truth data
  var assetEl=document.getElementById?document.getElementById('current-asset')||document.querySelector('[data-testid="asset-selector"]'):null;
  var asset='BTC';
  if(assetEl)asset=(assetEl.textContent||'BTC').trim().toUpperCase();
  // Also try getting from URL
  var p=new URLSearchParams(location.search);
  if(p.get('asset'))asset=p.get('asset').toUpperCase();

  fetch('/api/mobile/signals/'+asset+'?horizon=swing').then(function(r){return r.json()}).then(function(data){
    if(!data.ok||!data.signal)return;
    var sig=data.signal;
    var truth=sig.truth||{};
    var pr=sig.partialReveal||{};
    var d=dk();
    var mt=d?'#71717a':'#64748b';
    var tx=d?'#fafafa':'#0f172a';
    var gn=d?'#22c55e':'#16a34a';
    var rd=d?'#ef4444':'#dc2626';
    var accent='#6366f1';
    var cd=d?'#18181b':'#ffffff';
    var bd=d?'#27272a':'#e2e8f0';
    var sb=d?'rgba(39,39,42,0.4)':'rgba(0,0,0,0.04)';

    var h='<div id="_truth_layer" style="margin:0 16px 12px">';

    // ═══ DECISION FRAMEWORK STRIP ═══
    var df=sig.decisionFramework||{};
    var stage_=df.stage||'EARLY';
    var alignment=df.alignment||'0 of 6 aligned';
    var stageC=stage_==='SIGNAL'?gn:stage_==='CONFIRMING'?'#eab308':stage_==='FORMING'?'#f97316':mt;
    h+='<div style="background:'+cd+';border:1px solid '+stageC+'30;border-radius:12px;padding:12px;margin-bottom:8px">';
    h+='<div style="display:flex;justify-content:space-between;align-items:center">';
    h+='<span style="font-size:14px;font-weight:800;color:'+stageC+';letter-spacing:1px">'+stage_+'</span>';
    h+='<span style="font-size:11px;color:'+mt+'">'+alignment+'</span>';
    h+='</div>';
    if(df.stageLabel)h+='<div style="font-size:11px;color:'+mt+';margin-top:4px">'+df.stageLabel+'</div>';
    // What matters now
    var matters=sig.decisionFramework&&sig.decisionFramework.mattersPoints||[];
    if(matters.length>0){
      h+='<div style="margin-top:8px;border-top:1px solid '+bd+';padding-top:8px">';
      matters.slice(0,3).forEach(function(p){h+='<div style="font-size:11px;color:'+tx+';padding:2px 0">• '+p+'</div>';});
      h+='</div>';
    }
    h+='</div>';

    // ═══ ENTRY WINDOW ═══
    var ew=sig.entryWindow||{};
    if(ew.state&&ew.state!=='SCANNING'){
      var ewC=ew.state==='ACTIVE'||ew.state==='OPEN'?gn:ew.state==='CLOSING'?'#f97316':ew.state==='CLOSED'?rd:mt;
      h+='<div style="background:'+cd+';border:1px solid '+ewC+'30;border-radius:12px;padding:12px;margin-bottom:8px">';
      h+='<div style="display:flex;justify-content:space-between;align-items:center">';
      h+='<span style="font-size:13px;font-weight:800;color:'+ewC+'">'+ew.label+'</span>';
      h+='<span style="font-size:11px;color:'+mt+'">'+ew.urgency+'</span>';
      h+='</div>';
      if(ew.moneyFrame)h+='<div style="font-size:12px;color:'+tx+';margin-top:6px">'+ew.moneyFrame+'</div>';
      if(ew.topTraders)h+='<div style="font-size:11px;color:'+accent+';margin-top:4px;font-style:italic">'+ew.topTraders+'</div>';
      h+='</div>';
    }

    // ═══ CONFLICT ENGINE ═══
    var cf=sig.conflict||{};
    if(cf.hasConflict&&cf.summary){
      h+='<div style="background:'+cd+';border:1px solid #f9731630;border-radius:12px;padding:12px;margin-bottom:8px">';
      h+='<div style="font-size:10px;font-weight:700;color:#f97316;text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px">⚡ MARKET CONFLICT</div>';
      h+='<div style="font-size:12px;color:'+tx+'">'+cf.summary+'</div>';
      h+='</div>';
    }

    // ═══ TRUTH STRIP ═══
    if(truth.totalTrades>0&&!truth.learning){
      h+='<div style="background:'+cd+';border:1px solid '+bd+';border-radius:12px;padding:12px;margin-bottom:8px">';
      h+='<div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">SYSTEM PERFORMANCE</div>';
      // Win rate + streak row
      h+='<div style="display:flex;align-items:center;gap:12px;margin-bottom:8px">';
      h+='<div style="font-size:13px;color:'+tx+'">Last '+truth.totalTrades+' signals: <b style="color:'+gn+'">'+Math.round(truth.winRate*100)+'%</b> profitable</div>';
      if(truth.streak>0)h+='<span style="font-size:11px;font-weight:700;color:'+gn+'">'+truth.streak+' win streak</span>';
      else if(truth.streak<0)h+='<span style="font-size:11px;color:'+mt+'">Next setup forming</span>';
      h+='</div>';
      // Recent outcome chips
      if(truth.recent&&truth.recent.length>0){
        h+='<div style="display:flex;gap:4px;flex-wrap:wrap">';
        truth.recent.slice(0,6).forEach(function(pnl){
          var c=pnl>0?gn:rd;
          var bg=pnl>0?(d?'rgba(34,197,94,0.15)':'#dcfce7'):(d?'rgba(239,68,68,0.15)':'#fee2e2');
          h+='<span style="padding:2px 6px;border-radius:4px;background:'+bg+';font-size:10px;font-weight:700;color:'+c+'">'+(pnl>0?'+':'')+pnl+'%</span>';
        });
        h+='</div>';
      }
      h+='</div>';
    } else if(truth.learning){
      h+='<div style="background:'+cd+';border:1px solid '+bd+';border-radius:12px;padding:12px;margin-bottom:8px;text-align:center">';
      h+='<div style="font-size:12px;color:'+mt+'">System initializing — tracking live market performance</div>';
      h+='</div>';
    }

    // ═══ PARTIAL REVEAL (FREE users) ═══
    if(pr.locked&&sig.accessLevel==='FREE'&&(sig.action==='BUY'||sig.action==='SELL')){
      h+='<div style="background:'+cd+';border:1px solid '+accent+'30;border-radius:12px;padding:14px;margin-bottom:8px">';
      h+='<div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">TRADE SETUP</div>';
      // Direction
      if(pr.direction)h+='<div style="font-size:15px;font-weight:800;color:'+accent+';margin-bottom:8px">'+pr.direction+' setup '+(pr.stage==='CONFIRMED'?'confirmed':pr.stage==='FORMING'?'forming':'detected')+'</div>';
      // Entry
      h+='<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid '+bd+'"><span style="font-size:12px;color:'+tx+'">Entry</span><span style="font-size:12px;font-weight:600;color:'+accent+'">'+(pr.entryTeaser||'Zone detected')+'</span></div>';
      // Target
      h+='<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid '+bd+'"><span style="font-size:12px;color:'+tx+'">Target</span><span style="font-size:12px;font-weight:600;color:'+gn+'">'+(pr.potentialRange||'Upside detected')+'</span></div>';
      // Risk
      h+='<div style="display:flex;justify-content:space-between;padding:6px 0"><span style="font-size:12px;color:'+tx+'">Risk</span><span style="font-size:12px;font-weight:600;color:'+rd+'">'+(pr.stopTeaser||'Level defined')+'</span></div>';
      // Truth line
      if(pr.truthLine)h+='<div style="margin-top:8px;padding:6px 10px;background:'+(d?'rgba(34,197,94,0.1)':'#dcfce7')+';border-radius:6px;border:1px solid '+(d?'rgba(34,197,94,0.2)':'#bbf7d0')+'"><div style="font-size:11px;font-weight:600;color:'+gn+'">'+pr.truthLine+'</div></div>';
      // Pressure
      if(pr.pressureLine)h+='<div style="font-size:12px;font-weight:700;color:'+tx+';text-align:center;margin-top:8px">'+pr.pressureLine+'</div>';
      // CTA
      h+='<button onclick="window._prCTA&&window._prCTA()" style="display:flex;align-items:center;justify-content:center;padding:12px;background:'+accent+';color:#fff;border:none;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;width:100%;margin-top:10px">Continue in app → see entry</button>';
      // Micro-FOMO
      if(pr.microFomo)h+='<div style="font-size:10px;color:'+mt+';text-align:center;margin-top:6px;font-style:italic">'+pr.microFomo+'</div>';
      // Timing
      if(pr.timing)h+='<div style="font-size:10px;font-weight:600;color:'+accent+';text-align:center;margin-top:4px">'+pr.timing+'</div>';
      // Almost line
      if(pr.almostLine)h+='<div style="font-size:11px;font-weight:600;color:'+(d?'#a1a1aa':'#334155')+';text-align:center;margin-top:6px">'+pr.almostLine+'</div>';
      h+='</div>';
    }

    h+='</div>';

    // Insert after signal card
    var wrapper=document.createElement('div');
    wrapper.innerHTML=h;
    if(signalCard.nextSibling){
      signalCard.parentNode.insertBefore(wrapper,signalCard.nextSibling);
    }else{
      signalCard.parentNode.appendChild(wrapper);
    }
    truthDone=true;
  }).catch(function(){});
}

// CTA handler
window._prCTA=function(){
  if(window.Telegram&&Telegram.WebApp){
    Telegram.WebApp.openTelegramLink('https://t.me/FOMO_mini_bot?start=upgrade');
  }
};

var obs2=new MutationObserver(function(){
  if(!document.getElementById('_truth_layer'))truthDone=false;
  if(!truthDone)injectTruth();
});
function startTruth(){
  obs2.observe(document.body,{childList:true,subtree:true});
  injectTruth();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(startTruth,3500)});
else setTimeout(startTruth,3500);
})();
