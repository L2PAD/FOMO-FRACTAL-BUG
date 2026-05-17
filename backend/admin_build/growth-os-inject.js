/* Add Rank to main profile + replace referral/promo with Growth & Leaderboard buttons */
(function(){
var injected=false,rankInjected=false;
function tid(){try{return String(window.Telegram?.WebApp?.initDataUnsafe?.user?.id||'')}catch(e){return''}}
function dk(){if(window.Telegram&&Telegram.WebApp)return Telegram.WebApp.colorScheme!=='light';return true}
window._gCopy=function(c){if(navigator.clipboard)navigator.clipboard.writeText(c)};
window._gShare=function(c,u){var s=u||'https://t.me/FOMO_mini_bot?start='+c,t='Join FOMO. Code: '+c;if(window.Telegram&&Telegram.WebApp)Telegram.WebApp.openTelegramLink('https://t.me/share/url?url='+encodeURIComponent(s)+'&text='+encodeURIComponent(t));else if(navigator.share)navigator.share({title:'FOMO',text:t,url:s}).catch(function(){});else if(navigator.clipboard)navigator.clipboard.writeText(s)};

var _gOpen=null;
window._gToggle=function(which){
  var gp=document.getElementById('_growth_body');
  var lp=document.getElementById('_lb_body');
  var ga=document.getElementById('_growth_arrow');
  var la=document.getElementById('_lb_arrow');
  if(which==='growth'){
    if(_gOpen==='growth'){gp.style.display='none';_gOpen=null;if(ga)ga.style.transform='rotate(0)';return}
    gp.style.display='block';if(lp)lp.style.display='none';
    _gOpen='growth';if(ga)ga.style.transform='rotate(180deg)';if(la)la.style.transform='rotate(0)';
    renderGrowth();
  }else{
    if(_gOpen==='lb'){lp.style.display='none';_gOpen=null;if(la)la.style.transform='rotate(0)';return}
    if(gp)gp.style.display='none';lp.style.display='block';
    _gOpen='lb';if(la)la.style.transform='rotate(180deg)';if(ga)ga.style.transform='rotate(0)';
    renderLB();
  }
};

async function renderGrowth(){
  var p=document.getElementById('_growth_body');if(!p)return;
  var d=dk(),a='#6366f1',cs='padding:14px 16px;background:var(--ma-surface,'+(d?'#18181b':'#fff')+');border-radius:16px;border:1px solid var(--ma-border,'+(d?'#27272a':'#cbd5e1')+');margin-bottom:10px',tx='var(--ma-text,'+(d?'#fafafa':'#0f172a')+')',mt='var(--ma-muted,'+(d?'#52525b':'#64748b')+')',bd='var(--ma-border,'+(d?'#27272a':'#cbd5e1')+')',sb='var(--ma-stat-bg,'+(d?'rgba(39,39,42,0.4)':'rgba(0,0,0,0.04)')+')',gn='#22c55e',bg='var(--ma-bg,'+(d?'#09090b':'#f0f0f3')+')';
  var id=tid();
  try{
    var pR=await fetch('/api/miniapp/profile?telegram_id='+id).then(r=>r.json()).catch(()=>({}));
    var g=pR.growth||{},st=g.stats||{},co=g.code||'',su=g.shareUrl||g.telegramLink||'',ms=g.milestones||[],pd=st.paidConfirmed||0,nm=g.nextMilestone;
    var h='<div style="padding:12px 16px">';
    // Next reward
    if(nm){var pt=ms.find(m=>pd<m.paid),pp=pt?Math.min(100,Math.round(pd/pt.paid*100)):100;
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">NEXT REWARD</div><div style="font-size:13px;font-weight:600;color:'+tx+'">'+(nm.need||0)+' more paid referral'+(nm.need>1?'s':'')+'</div><div style="font-size:12px;font-weight:700;color:'+a+';margin-top:2px">\u2192 '+(nm.label||'')+'</div><div style="height:5px;background:'+bd+';border-radius:3px;margin:8px 0;overflow:hidden"><div style="height:100%;border-radius:3px;background:'+a+';width:'+pp+'%"></div></div><div style="font-size:10px;color:'+mt+';text-align:right">'+pp+'%</div></div>'}
    // Referral code
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">YOUR REFERRAL CODE</div><div style="display:flex;align-items:center;gap:8px;margin-bottom:10px"><span style="font-family:monospace;font-size:18px;font-weight:800;letter-spacing:1px;flex:1;color:'+tx+'">'+co+'</span><button onclick="var b=this;window._gCopy(\''+co+'\');b.textContent=\'Copied!\';setTimeout(()=>b.textContent=\'Copy\',1500)" style="padding:6px 12px;background:'+a+'20;border:none;border-radius:8px;font-size:12px;font-weight:600;color:'+a+';cursor:pointer">Copy</button></div><button onclick="window._gShare(\''+co+'\',\''+su+'\')" style="display:flex;align-items:center;justify-content:center;gap:6px;padding:12px;background:'+a+';color:#fff;border:none;border-radius:10px;font-size:13px;font-weight:700;cursor:pointer;width:100%">Share Invite Link</button></div>';
    // Reward ladder
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">REWARD LADDER</div>';
    ms.forEach(function(m){var dn=pd>=m.paid;h+='<div style="display:flex;align-items:center;gap:8px;padding:7px 0"><span style="font-size:14px;width:22px;text-align:center">'+(dn?'\u2705':'\u25CB')+'</span><span style="flex:1;font-size:12px;color:'+(dn?gn:tx)+'">'+m.paid+' referral'+(m.paid>1?'s':'')+'</span><span style="font-size:11px;font-weight:600;color:'+(dn?gn:a)+'">'+m.reward+'</span></div>'});h+='</div>';
    // Stats
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">STATS</div><div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">';
    [{v:st.clicks||0,l:'Clicks',c:tx},{v:st.signups||0,l:'Signups',c:tx},{v:pd,l:'Paid',c:gn}].forEach(function(s){h+='<div style="text-align:center;padding:8px;background:'+sb+';border-radius:8px"><div style="font-size:16px;font-weight:700;color:'+s.c+'">'+s.v+'</div><div style="font-size:9px;color:'+mt+'">'+s.l+'</div></div>'});h+='</div></div>';
    // Apply code
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">APPLY CODE</div><div style="display:flex;gap:6px"><input id="_gpi" placeholder="Enter code" style="flex:1;background:'+bg+';border:1px solid '+bd+';border-radius:8px;padding:8px 10px;color:'+tx+';font-size:13px;outline:none"/><button onclick="var inp=document.getElementById(\'_gpi\'),msg=document.getElementById(\'_gpm\'),c=inp.value.trim();if(!c)return;fetch(\'/api/growth/apply\',{method:\'POST\',headers:{\'Content-Type\':\'application/json\'},body:JSON.stringify({code:c,telegram_id:\''+id+'\'})}).then(r=>r.json()).then(d=>{msg.style.color=d.ok?\''+gn+'\':\'#ef4444\';msg.textContent=d.ok?(d.message||\'Applied!\'):(d.error||\'Invalid\');if(d.ok){inp.value=\'\';renderGrowth()}}).catch(()=>{msg.textContent=\'Error\'})" style="padding:8px 14px;background:'+a+';color:#fff;border:none;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer">Apply</button></div><div id="_gpm" style="font-size:11px;margin-top:4px"></div></div>';
    h+='</div>';
    p.innerHTML=h;
  }catch(e){p.innerHTML='<div style="padding:16px;text-align:center;color:'+mt+'">Failed</div>'}
}

async function renderLB(){
  var p=document.getElementById('_lb_body');if(!p)return;
  var d=dk(),a='#6366f1',cs='padding:14px 16px;background:var(--ma-surface,'+(d?'#18181b':'#fff')+');border-radius:16px;border:1px solid var(--ma-border,'+(d?'#27272a':'#cbd5e1')+');margin-bottom:10px',tx='var(--ma-text,'+(d?'#fafafa':'#0f172a')+')',mt='var(--ma-muted,'+(d?'#52525b':'#64748b')+')',bd='var(--ma-border,'+(d?'#27272a':'#cbd5e1')+')',sb='var(--ma-stat-bg,'+(d?'rgba(39,39,42,0.4)':'rgba(0,0,0,0.04)')+')',wr='#f59e0b',gn='#22c55e';
  var id=tid();
  try{
    var[pR,lR]=await Promise.all([fetch('/api/miniapp/profile?telegram_id='+id).then(r=>r.json()).catch(()=>({})),fetch('/api/growth/leaderboard').then(r=>r.json()).catch(()=>({entries:[]}))]);
    var g=pR.growth||{},lb=lR.entries||lR||[],rk=g.rank||'—',sc=g.seasonScore||0,sn=g.season?.name||'Season 1',nm=g.nextMilestone,co=g.code||'',su=g.shareUrl||'';
    var h='<div style="padding:12px 16px">';
    // Season
    h+='<div style="'+cs+'"><div style="display:flex;align-items:center;gap:8px">\uD83C\uDFC6<span style="font-size:16px;font-weight:800;color:'+tx+'">'+sn+'</span></div><div style="font-size:11px;color:'+mt+';margin-top:4px">Top performers win PRO access</div></div>';
    // Your rank
    h+='<div style="'+cs+';border-color:'+a+'40"><div style="display:flex;justify-content:space-between"><div><div style="font-size:9px;color:'+mt+';text-transform:uppercase">Your Rank</div><div style="font-size:24px;font-weight:800;color:'+a+'">#'+rk+'</div></div><div style="text-align:right"><div style="font-size:9px;color:'+mt+';text-transform:uppercase">Score</div><div style="font-size:24px;font-weight:800;color:'+tx+'">'+sc+'</div></div></div>';
    if(nm)h+='<div style="font-size:11px;font-weight:600;color:'+a+';margin-top:6px">+'+(nm.need||0)+' paid \u2192 '+(nm.label||'')+'</div>';h+='</div>';
    // Board
    h+='<div style="'+cs+'">';
    if(lb.length){lb.forEach(function(e){var me=e.user_id===id,mc=e.rank===1?wr:e.rank===2?'#94a3b8':e.rank===3?'#cd7f32':null;h+='<div style="display:flex;align-items:center;gap:8px;padding:8px 4px;border-bottom:1px solid '+bd+';background:'+(me?a+'08':'transparent')+';border-radius:'+(me?'6px':'0')+'"><div style="width:26px;height:26px;border-radius:13px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:800;background:'+(mc?mc+'20':sb)+';color:'+(mc||mt)+'">'+e.rank+'</div><span style="flex:1;font-size:12px;font-weight:'+(me?'700':'500')+';color:'+tx+'">'+(e.name||'User')+(me?' <span style="background:'+a+';color:#fff;border-radius:3px;padding:0 4px;font-size:8px;font-weight:700">YOU</span>':'')+'</span><span style="font-size:12px;font-weight:700;color:'+tx+'">'+e.score+'</span></div>'})}else h+='<div style="padding:24px;text-align:center;font-size:12px;color:'+mt+'">No entries yet</div>';h+='</div>';
    // Season rewards
    h+='<div style="'+cs+'"><div style="font-size:10px;font-weight:700;color:'+mt+';text-transform:uppercase;letter-spacing:.8px;margin-bottom:8px">SEASON REWARDS</div>';
    [{r:'Top 1',w:'1 year PRO',b:'Champion',c:wr},{r:'Top 3',w:'90 days PRO',b:'Smart Money',c:'#94a3b8'},{r:'Top 10',w:'30 days PRO',b:'Top Performer',c:'#cd7f32'}].forEach(function(sr){h+='<div style="display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid '+bd+'"><span style="color:'+sr.c+'">\uD83C\uDFC5</span><div style="flex:1"><div style="font-size:12px;font-weight:700;color:'+tx+'">'+sr.r+'</div><div style="font-size:10px;color:'+mt+'">'+sr.w+' \u00B7 '+sr.b+'</div></div></div>'});h+='</div>';
    // CTA
    h+='<button onclick="window._gShare(\''+co+'\',\''+su+'\')" style="display:flex;align-items:center;justify-content:center;gap:6px;padding:13px;background:'+a+';color:#fff;border:none;border-radius:12px;font-size:13px;font-weight:700;cursor:pointer;width:100%">\uD83D\uDE80 Invite more</button>';
    h+='</div>';
    p.innerHTML=h;
  }catch(e){p.innerHTML='<div style="padding:16px;text-align:center;color:'+mt+'">Failed</div>'}
}

function inject(){
  if(injected)return;
  // Find referral-card and promo-card
  var ref=null,promo=null;
  var all=document.querySelectorAll('div');
  for(var i=0;i<all.length;i++){var d=all[i],t=d.textContent||'';
    if(!ref&&t.indexOf('Invites')!==-1&&t.indexOf('Copy')!==-1&&d.offsetHeight>40&&d.offsetHeight<250&&d.offsetWidth>200)ref=d;
    if(!promo&&t.indexOf('Enter code')!==-1&&t.indexOf('Apply')!==-1&&d.offsetHeight>40&&d.offsetHeight<200&&d.offsetWidth>200)promo=d;
  }
  if(!ref)return;
  var parent=ref.parentNode;
  // Use CSS variables so buttons match SPA theme automatically
  var a='#6366f1';
  // Create two buttons
  var wrap=document.createElement('div');wrap.id='_gwrap';
  wrap.innerHTML=
    // Growth button
    '<div style="margin:0 16px 8px"><div onclick="window._gToggle(\'growth\')" style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;background:var(--ma-surface,#18181b);border:1px solid var(--ma-border,#27272a);border-radius:14px;cursor:pointer"><div style="display:flex;align-items:center;gap:10px"><span style="font-size:16px">\u26A1</span><div><div style="font-size:13px;font-weight:700;color:var(--ma-text,#fafafa)">Growth</div><div style="font-size:10px;color:var(--ma-muted,#52525b)">Referrals \u00B7 Rewards \u00B7 Stats</div></div></div><svg id="_growth_arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ma-muted,#52525b)" stroke-width="2" style="transition:transform .3s"><polyline points="6 9 12 15 18 9"/></svg></div><div id="_growth_body" style="display:none"></div></div>'+
    // Leaderboard button
    '<div style="margin:0 16px 8px"><div onclick="window._gToggle(\'lb\')" style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;background:var(--ma-surface,#18181b);border:1px solid var(--ma-border,#27272a);border-radius:14px;cursor:pointer"><div style="display:flex;align-items:center;gap:10px"><span style="font-size:16px">\uD83C\uDFC6</span><div><div style="font-size:13px;font-weight:700;color:var(--ma-text,#fafafa)">Leaderboard</div><div style="font-size:10px;color:var(--ma-muted,#52525b)">Season ranking \u00B7 Rewards</div></div></div><svg id="_lb_arrow" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--ma-muted,#52525b)" stroke-width="2" style="transition:transform .3s"><polyline points="6 9 12 15 18 9"/></svg></div><div id="_lb_body" style="display:none"></div></div>';
  parent.insertBefore(wrap,ref);
  try{parent.removeChild(ref)}catch(e){}
  try{if(promo&&promo.parentNode)promo.parentNode.removeChild(promo)}catch(e){}
  injected=true;
}

// Add Rank to main profile card
async function injectRank(){
  if(rankInjected)return;
  // Find the main profile card — contains username and FREE/PRO badge
  var all=document.querySelectorAll('div');
  var profileCard=null;
  for(var i=0;i<all.length;i++){var d=all[i],t=d.textContent||'';
    if(t.indexOf('FREE')!==-1&&t.indexOf('TG')!==-1&&d.offsetHeight>50&&d.offsetHeight<200&&d.offsetWidth>200){profileCard=d;break}
    if(t.indexOf('PRO')!==-1&&t.indexOf('TG')!==-1&&d.offsetHeight>50&&d.offsetHeight<200&&d.offsetWidth>200){profileCard=d;break}
  }
  if(!profileCard||profileCard.querySelector('#_rank_badge'))return;
  var id=tid();
  try{
    var pR=await fetch('/api/miniapp/profile?telegram_id='+id).then(r=>r.json()).catch(()=>({}));
    var g=pR.growth||{},rk=g.rank||'—',sc=g.seasonScore||0,sn=g.season?.name||'Season 1';
    var dd=dk(),a='#6366f1',mt2=dd?'#52525b':'#64748b',tx2=dd?'#fafafa':'#0f172a';
    var badge=document.createElement('div');
    badge.id='_rank_badge';
    badge.style.cssText='display:flex;align-items:center;gap:12px;margin-top:8px;padding:6px 10px;background:'+a+'15;border-radius:8px';
    badge.innerHTML='<div style="display:flex;align-items:center;gap:4px"><span style="font-size:10px;color:'+mt2+'">Rank</span><span style="font-size:14px;font-weight:800;color:'+a+'">#'+rk+'</span></div><div style="width:1px;height:14px;background:'+mt2+'30"></div><div style="display:flex;align-items:center;gap:4px"><span style="font-size:10px;color:'+mt2+'">Score</span><span style="font-size:14px;font-weight:800;color:'+tx2+'">'+sc+'</span></div><div style="width:1px;height:14px;background:'+mt2+'30"></div><span style="font-size:10px;color:'+a+'">'+sn+'</span>';
    profileCard.appendChild(badge);
    rankInjected=true;
  }catch(e){}
}

var obs=new MutationObserver(function(){
  if(!document.getElementById('_gwrap'))injected=false;
  if(!document.getElementById('_rank_badge'))rankInjected=false;
  if(!injected)inject();
  if(!rankInjected)injectRank();
});
function start(){obs.observe(document.body,{childList:true,subtree:true});inject();injectRank()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(start,3000)});
else setTimeout(start,3000);
})();
