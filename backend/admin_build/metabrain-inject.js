/*
 * MetaBrain Prediction Snapshot — injected on MiniApp Home.
 * Mirrors the Expo mobile app card (compact dark card + details overlay).
 */
(function(){
var mbDone=false;
var mbPayload=null;
var mbHorizon='30D';
var HORIZONS=['7D','30D','90D','180D','365D'];

// ─── Theme detection — reads SPA's actual background colour ───
// Body/html are often transparent/white — we climb from the Hero card to the
// first ancestor with a real background and use its luminance.
function _detectThemeDark(){
  try{
    var node=document.querySelector('[data-testid="decision-hero-card"]')||document.body;
    var bg=null,probes=0;
    while(node&&probes<8){
      var cs=window.getComputedStyle(node).backgroundColor;
      if(cs&&cs!=='rgba(0, 0, 0, 0)'&&cs!=='transparent'){bg=cs;break;}
      node=node.parentElement;probes++;
    }
    if(!bg)return true;
    var m=bg.match(/\d+(?:\.\d+)?/g);
    if(!m||m.length<3)return true;
    var r=+m[0],g=+m[1],b=+m[2];
    var lum=(r*299+g*587+b*114)/1000;
    return lum<128;
  }catch(e){return true}
}

function dk(){return _detectThemeDark()}

// Grey outline brain SVG (native look, matches app iconography).
function BRAIN_ICON(color,size){
  size=size||14;
  return '<svg width="'+size+'" height="'+size+'" viewBox="0 0 24 24" fill="none" stroke="'+color+'" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block;vertical-align:-2px;flex-shrink:0">'+
    '<path d="M12 5a2.5 2.5 0 0 0-4.5-1.5A2.5 2.5 0 0 0 4 6a2.5 2.5 0 0 0-.5 4.5A2.5 2.5 0 0 0 5 15a2.5 2.5 0 0 0 2.5 2.5A2.5 2.5 0 0 0 12 19"/>'+
    '<path d="M12 5v14"/>'+
    '<path d="M12 5a2.5 2.5 0 0 1 4.5-1.5A2.5 2.5 0 0 1 20 6a2.5 2.5 0 0 1 .5 4.5A2.5 2.5 0 0 1 19 15a2.5 2.5 0 0 1-2.5 2.5A2.5 2.5 0 0 1 12 19"/>'+
    '<path d="M7.5 11.5h1"/><path d="M15.5 11.5h1"/>'+
    '</svg>';
}

function C(){
  var d=dk();
  return {
    dark:d,
    // Card & backgrounds
    cardBg:d?'#18181b':'#ffffff',
    cardBorder:d?'#27272a':'#e5e7eb',
    innerBg:d?'#09090b':'#fafafa',
    sub:d?'rgba(255,255,255,0.04)':'rgba(0,0,0,0.02)',
    divider:d?'#27272a':'#f1f5f9',
    // Text
    primary:d?'#fafafa':'#0f172a',
    secondary:d?'#a1a1aa':'#475569',
    muted:d?'#71717a':'#94a3b8',
    // Accent palette
    gold:'#eab308',
    goldBg:'rgba(234,179,8,0.10)',
    goldBorder:'rgba(234,179,8,0.35)',
    green:'#22c55e',
    red:'#ef4444',
    blue:'#60a5fa',
    orange:'#f97316',
    // Sparkline
    spark:d?'#a1a1aa':'#64748b',
    sparkProjected:'#60a5fa'
  };
}

function stateMeta(st){
  if(st==='ALIGNED')return {label:'ALIGNED',color:'#22c55e',bg:'rgba(34,197,94,0.10)',border:'rgba(34,197,94,0.35)',icon:'🎯'};
  if(st==='TENSION')return {label:'TENSION',color:'#f97316',bg:'rgba(249,115,22,0.10)',border:'rgba(249,115,22,0.35)',icon:'⚡'};
  if(st==='CONFLICT')return {label:'CONFLICT',color:'#eab308',bg:'rgba(234,179,8,0.10)',border:'rgba(234,179,8,0.35)',icon:'⚖'};
  return {label:st||'SCANNING',color:'#71717a',bg:'rgba(113,113,122,0.10)',border:'rgba(113,113,122,0.35)',icon:'○'};
}

function biasColor(bias,c){
  if((bias||'').toLowerCase()==='bullish')return c.green;
  if((bias||'').toLowerCase()==='bearish')return c.red;
  return c.secondary;
}

function biasArrow(bias){
  var b=(bias||'').toLowerCase();
  if(b==='bullish')return '↑';
  if(b==='bearish')return '↓';
  return '→';
}

function fmtPrice(n){
  if(!n&&n!==0)return '';
  if(n>=1000)return '$'+Math.round(n).toLocaleString();
  return '$'+n.toFixed(2);
}

function fmtK(n){
  if(!n&&n!==0)return '?';
  if(n>=1000)return '$'+(n/1000).toFixed(1)+'K';
  return '$'+n.toFixed(0);
}

function fmtPct(n){
  if(!n&&n!==0)return '0%';
  return (n>0?'+':'')+n.toFixed(2)+'%';
}

// ─── Sparkline SVG (compact) ─────────────────────────────
function buildSparkline(series,color,w,h){
  if(!series||series.length<2)return '';
  var vals=series.map(function(p){return +p.v||0}).filter(function(v){return v>0});
  if(vals.length<2)return '';
  var min=Math.min.apply(null,vals),max=Math.max.apply(null,vals);
  var range=max-min||1;
  var step=(w-2)/(vals.length-1);
  var pts=vals.map(function(v,i){
    var x=(1+i*step).toFixed(1);
    var y=(h-1-((v-min)/range)*(h-2)).toFixed(1);
    return x+','+y;
  }).join(' ');
  return '<svg width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'" style="display:block;overflow:visible">'+
    '<polyline points="'+pts+'" fill="none" stroke="'+color+'" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'+
    '</svg>';
}

// ─── Full chart SVG (details overlay) ────────────────────
function buildChart(history,projected,upperBand,lowerBand,c,W,H){
  if(!history&&!projected)return '';
  history=history||[];projected=projected||[];upperBand=upperBand||[];lowerBand=lowerBand||[];
  var all=[];
  history.forEach(function(p){all.push({t:p.t,v:+p.v||0,hist:true})});
  projected.forEach(function(p){all.push({t:p.t,v:+p.v||0,proj:true})});
  var bandAll=upperBand.concat(lowerBand).map(function(p){return +p.v||0});
  var vals=all.map(function(p){return p.v}).concat(bandAll).filter(function(v){return v>0});
  if(vals.length<2)return '';
  var min=Math.min.apply(null,vals),max=Math.max.apply(null,vals);
  var pad=(max-min)*0.05||1;
  min-=pad;max+=pad;
  var range=max-min||1;
  var paddingL=46,paddingR=16,paddingT=10,paddingB=24;
  var chartW=W-paddingL-paddingR,chartH=H-paddingT-paddingB;
  var step=chartW/(all.length-1);
  function mx(i){return (paddingL+i*step).toFixed(1)}
  function my(v){return (paddingT+chartH-((v-min)/range)*chartH).toFixed(1)}
  // Build uncertainty band area if projected
  var bandArea='';
  if(upperBand.length&&lowerBand.length){
    var histLen=history.length;
    var up=upperBand.map(function(p,i){return mx(histLen+i-1)+','+my(+p.v||0)}).join(' ');
    var lo=lowerBand.slice().reverse().map(function(p,i){return mx(histLen+lowerBand.length-1-i-1)+','+my(+p.v||0)}).join(' ');
    bandArea='<polygon points="'+up+' '+lo+'" fill="'+c.sparkProjected+'" fill-opacity="0.10" stroke="none"/>';
  }
  // History line
  var histPts=history.map(function(p,i){return mx(i)+','+my(+p.v||0)}).join(' ');
  // Projected line
  var projStart=history.length>0?history.length-1:0;
  var projPts=projected.map(function(p,i){return mx(projStart+i)+','+my(+p.v||0)}).join(' ');
  // Y-axis labels (4 ticks)
  var ticks='';
  for(var k=0;k<5;k++){
    var v=min+(range*(4-k)/4);
    var y=(paddingT+chartH*k/4).toFixed(1);
    ticks+='<text x="'+(paddingL-8)+'" y="'+(parseFloat(y)+3)+'" fill="'+c.muted+'" font-size="10" font-family="JetBrains Mono, monospace" text-anchor="end">'+fmtK(v)+'</text>';
    ticks+='<line x1="'+paddingL+'" y1="'+y+'" x2="'+(W-paddingR)+'" y2="'+y+'" stroke="'+c.divider+'" stroke-width="0.5" stroke-dasharray="2,3"/>';
  }
  // NOW marker
  var nowX=history.length>0?mx(history.length-1):paddingL;
  var currentPrice=history.length>0?+history[history.length-1].v:0;
  var nowY=my(currentPrice);
  var nowMarker='<line x1="'+nowX+'" y1="'+paddingT+'" x2="'+nowX+'" y2="'+(paddingT+chartH)+'" stroke="'+c.muted+'" stroke-width="0.5" stroke-dasharray="3,3"/>'+
    '<circle cx="'+nowX+'" cy="'+nowY+'" r="3.5" fill="'+c.cardBg+'" stroke="'+c.sparkProjected+'" stroke-width="1.5"/>'+
    '<text x="'+(parseFloat(nowX)+6)+'" y="'+(parseFloat(nowY)-6)+'" fill="'+c.secondary+'" font-size="9" font-family="JetBrains Mono, monospace">NOW</text>';
  // End price label for projected
  var endLabel='';
  if(projected.length>0){
    var lastProj=projected[projected.length-1];
    var endX=mx(projStart+projected.length-1);
    var endY=my(+lastProj.v||0);
    endLabel='<circle cx="'+endX+'" cy="'+endY+'" r="3" fill="'+c.sparkProjected+'"/>'+
      '<text x="'+(parseFloat(endX)-2)+'" y="'+(parseFloat(endY)-8)+'" fill="'+c.primary+'" font-size="11" font-weight="700" font-family="JetBrains Mono, monospace" text-anchor="end">'+fmtK(+lastProj.v||0)+'</text>';
  }
  return '<svg width="100%" height="'+H+'" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="display:block">'+
    ticks+bandArea+
    '<polyline points="'+histPts+'" fill="none" stroke="'+c.primary+'" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'+
    '<polyline points="'+projPts+'" fill="none" stroke="'+c.sparkProjected+'" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4,3"/>'+
    nowMarker+endLabel+
    '</svg>';
}

// ─── Data loader ─────────────────────────────────────────
function loadMB(asset,horizon,cb){
  var key='_mbcache_'+asset+'_'+horizon;
  try{
    var raw=sessionStorage.getItem(key);
    if(raw){
      var cached=JSON.parse(raw);
      if(cached&&cached.ts&&(Date.now()-cached.ts)<30000){cb(cached.data);return;}
    }
  }catch(e){}
  fetch('/api/mobile/prediction-chart?symbol='+asset+'&horizon='+horizon).then(function(r){return r.json()}).then(function(data){
    if(!data||data.ok===false){cb(null);return;}
    try{sessionStorage.setItem(key,JSON.stringify({ts:Date.now(),data:data}))}catch(e){}
    cb(data);
  }).catch(function(){cb(null);});
}

// ─── COMPACT SNAPSHOT CARD (Home) ────────────────────────
function buildSnapshotCard(data,asset,horizon){
  if(!data)return '';
  var c=C();
  var sum=data.summary||{};
  var state=sum.marketState||'SCANNING';
  var sm=stateMeta(state);
  var bias=sum.bias||'Neutral';
  var biasC=biasColor(bias,c);
  var arrow=biasArrow(bias);
  var conf=sum.confidence||0;
  var conv=sum.conviction||0;
  var expMove=sum.expectedMove||'±0%';
  var stateText=sum.marketStateText||'';
  var price=data.currentPrice||0;

  // Find sparkline series from active horizon timeframes or priceSeries
  var spark=null;
  var tfs=data.timeframes||[];
  for(var i=0;i<tfs.length;i++){
    if(tfs[i].key===horizon&&tfs[i].projectedSeries){spark=tfs[i].projectedSeries;break;}
  }
  if(!spark||spark.length<2)spark=data.priceSeries||[];
  // Use last ~20 points for compact sparkline
  if(spark.length>20)spark=spark.slice(-20);

  var html='<div id="_metabrain_layer" style="margin:8px 16px 0">';
  html+='<div style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:14px;padding:14px 16px;cursor:pointer" data-mb-open="1">';

  // Header row
  html+='<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">';
  html+='<span style="font-size:10px;font-weight:800;color:'+c.muted+';letter-spacing:0.15em;text-transform:uppercase;font-family:\'Manrope\',sans-serif">Prediction Snapshot</span>';
  html+='<div style="display:flex;align-items:center;gap:8px">';
  html+='<span style="font-size:10px;font-weight:800;color:'+sm.color+';background:'+sm.bg+';border:1px solid '+sm.border+';padding:3px 8px;border-radius:6px;letter-spacing:0.08em;font-family:\'JetBrains Mono\',monospace">'+sm.label+'</span>';
  html+='<span style="font-size:10px;color:'+c.muted+';font-family:\'Manrope\',sans-serif">'+horizon+' · MetaBrain</span>';
  html+='</div>';
  html+='</div>';

  // Bias + sparkline row
  html+='<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:8px">';
  html+='<div style="flex:1;min-width:0">';
  html+='<div style="font-size:24px;font-weight:800;color:'+c.primary+';line-height:1.15;font-family:\'Oswald\',sans-serif;letter-spacing:-0.01em">'+asset+' <span style="color:'+biasC+'">'+arrow+' '+bias+'</span></div>';
  html+='<div style="font-size:12px;color:'+c.muted+';margin-top:3px;font-family:\'Manrope\',sans-serif">Expected: <span style="color:'+c.primary+';font-weight:600">'+expMove+'</span></div>';
  html+='</div>';
  // Sparkline area
  if(spark&&spark.length>=2){
    html+='<div style="flex-shrink:0;opacity:0.9">'+buildSparkline(spark,c.spark,110,48)+'</div>';
  }
  html+='</div>';

  // Divider
  html+='<div style="height:1px;background:'+c.divider+';margin:10px -16px"></div>';

  // Metrics row (Agreement, Conviction, Details)
  html+='<div style="display:grid;grid-template-columns:1fr 1fr auto;gap:0;align-items:center;padding-top:2px">';
  html+='<div style="text-align:left;border-right:1px solid '+c.divider+'">';
  html+='<div style="font-size:20px;font-weight:800;color:'+c.primary+';line-height:1;font-family:\'Oswald\',sans-serif">'+conf+'%</div>';
  html+='<div style="font-size:9px;color:'+c.muted+';letter-spacing:0.14em;text-transform:uppercase;margin-top:4px;font-family:\'Manrope\',sans-serif">Agreement</div>';
  html+='</div>';
  html+='<div style="text-align:center;border-right:1px solid '+c.divider+'">';
  html+='<div style="font-size:20px;font-weight:800;color:'+c.primary+';line-height:1;font-family:\'Oswald\',sans-serif">'+conv+'%</div>';
  html+='<div style="font-size:9px;color:'+c.muted+';letter-spacing:0.14em;text-transform:uppercase;margin-top:4px;font-family:\'Manrope\',sans-serif">Conviction</div>';
  html+='</div>';
  html+='<div style="text-align:right;padding-left:14px">';
  html+='<div style="font-size:16px;color:'+c.secondary+';line-height:1">›</div>';
  html+='<div style="font-size:9px;color:'+c.muted+';letter-spacing:0.14em;text-transform:uppercase;margin-top:4px;font-family:\'Manrope\',sans-serif">Details</div>';
  html+='</div>';
  html+='</div>';

  // Narrative pill
  if(stateText){
    html+='<div style="margin-top:12px;background:'+sm.bg+';border:1px solid '+sm.border+';border-radius:10px;padding:8px 12px;display:flex;align-items:center;gap:8px">';
    html+='<span style="font-size:13px;color:'+sm.color+'">'+sm.icon+'</span>';
    html+='<span style="font-size:12px;color:'+c.primary+';line-height:1.35;font-family:\'Manrope\',sans-serif">'+stateText+'</span>';
    html+='</div>';
  }

  html+='</div>';
  html+='</div>';
  return html;
}

// ─── FULL DETAILS OVERLAY (modal) ────────────────────────
function buildDetailsOverlay(data,asset,horizon){
  if(!data)return '';
  var c=C();
  var sum=data.summary||{};
  var state=sum.marketState||'SCANNING';
  var sm=stateMeta(state);
  var bias=sum.bias||'Neutral';
  var biasC=biasColor(bias,c);
  var arrow=biasArrow(bias);
  var conf=sum.confidence||0;
  var conv=sum.conviction||0;
  var expMove=sum.expectedMove||'±0%';
  var stateText=sum.marketStateText||'';
  var actionVerb=sum.actionVerb||'';
  var actionHint=sum.actionHint||'';
  var price=data.currentPrice||0;
  var dailyChange=data.dailyChange||0;
  var confLabel=sum.confidenceLabel||'';
  var convLabel=sum.convictionLabel||'';
  var nextMove=data.nextMoveLevels||{};

  var html='<div id="_metabrain_overlay" style="position:fixed;inset:0;background:'+(c.dark?'#000000':'#f8fafc')+';z-index:9998;overflow-y:auto;-webkit-overflow-scrolling:touch">';
  // Centered constrained content column — looks native on mobile + sane on desktop.
  var CW='max-width:520px;margin:0 auto';
  // Top bar
  html+='<div style="position:sticky;top:0;background:'+(c.dark?'rgba(0,0,0,0.95)':'rgba(255,255,255,0.95)')+';backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-bottom:1px solid '+c.cardBorder+';z-index:10">';
  html+='<div style="'+CW+';padding:12px 16px;display:flex;align-items:center;justify-content:space-between">';
  html+='<div style="display:flex;align-items:center;gap:8px">';
  html+=BRAIN_ICON(c.secondary,16);
  html+='<span style="font-size:13px;font-weight:800;color:'+c.primary+';letter-spacing:0.02em;font-family:\'Manrope\',sans-serif">MetaBrain Prediction</span>';
  html+='</div>';
  html+='<button data-mb-close="1" style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:8px;width:32px;height:32px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:'+c.primary+';font-size:16px;line-height:1;padding:0">×</button>';
  html+='</div>';
  html+='</div>';

  // Content
  html+='<div style="'+CW+';padding:16px 16px 40px">';

  // ═══ Hero block ═══
  html+='<div style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:16px;padding:16px;margin-bottom:12px">';
  html+='<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">';
  html+='<div>';
  html+='<div style="font-size:28px;font-weight:800;color:'+c.primary+';line-height:1;font-family:\'Oswald\',sans-serif">'+fmtPrice(price)+'</div>';
  if(dailyChange!==undefined&&dailyChange!==null){
    var dc=dailyChange>=0?c.green:c.red;
    html+='<div style="font-size:12px;color:'+dc+';margin-top:4px;font-weight:700;font-family:\'JetBrains Mono\',monospace">'+(dailyChange>=0?'+':'')+(+dailyChange).toFixed(1)+'% 24h</div>';
  }
  html+='</div>';
  html+='<div style="text-align:right">';
  html+='<span style="display:inline-flex;align-items:center;gap:4px;background:'+c.innerBg+';border:1px solid '+c.cardBorder+';border-radius:999px;padding:6px 12px;font-size:13px;font-weight:700;color:'+biasC+';font-family:\'Manrope\',sans-serif">'+arrow+' '+bias+'</span>';
  html+='<div style="font-size:11px;color:'+c.muted+';margin-top:6px;font-family:\'Manrope\',sans-serif">'+conf+'% confidence</div>';
  html+='</div>';
  html+='</div>';
  // Expected move banner
  html+='<div style="margin-top:14px;background:'+c.innerBg+';border-radius:10px;padding:10px 12px">';
  html+='<div style="font-size:13px;font-weight:700;color:'+c.gold+';font-family:\'Manrope\',sans-serif">⚡ Expected move: <span style="color:'+c.primary+'">'+expMove+'</span></div>';
  if(sum.summaryText){
    html+='<div style="font-size:12px;color:'+c.secondary+';margin-top:4px;line-height:1.4;font-family:\'Manrope\',sans-serif">'+sum.summaryText+'</div>';
  }
  html+='</div>';
  html+='</div>';

  // ═══ Market State card ═══
  html+='<div style="background:'+c.cardBg+';border:1px solid '+sm.border+';border-radius:16px;padding:14px 16px;margin-bottom:12px">';
  html+='<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">';
  html+='<div style="display:flex;align-items:center;gap:8px">';
  html+='<span style="font-size:13px;color:'+sm.color+'">'+sm.icon+'</span>';
  html+='<span style="font-size:11px;font-weight:800;color:'+sm.color+';letter-spacing:0.15em;text-transform:uppercase;font-family:\'Manrope\',sans-serif">Market State</span>';
  html+='</div>';
  html+='<span style="font-size:10px;font-weight:800;color:'+sm.color+';background:'+sm.bg+';border:1px solid '+sm.border+';padding:3px 8px;border-radius:6px;letter-spacing:0.08em;font-family:\'JetBrains Mono\',monospace">'+sm.label+'</span>';
  html+='</div>';
  if(stateText){
    html+='<div style="font-size:14px;color:'+c.primary+';font-weight:600;margin-bottom:10px;font-family:\'Manrope\',sans-serif">'+stateText+'</div>';
  }
  if(actionVerb||actionHint){
    html+='<div style="background:'+sm.bg+';border:1px solid '+sm.border+';border-radius:10px;padding:10px 12px;display:flex;align-items:center;gap:10px;margin-bottom:12px">';
    if(actionVerb){
      html+='<div style="font-size:12px;font-weight:800;color:'+sm.color+';letter-spacing:0.1em;white-space:nowrap;font-family:\'Manrope\',sans-serif">→ '+actionVerb+'</div>';
    }
    if(actionHint){
      html+='<div style="font-size:12px;color:'+c.primary+';line-height:1.35;font-family:\'Manrope\',sans-serif">'+actionHint+'</div>';
    }
    html+='</div>';
  }
  // Agreement / Conviction split
  html+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 0;border-top:1px solid '+c.divider+'">';
  html+='<div style="text-align:center">';
  html+='<div style="font-size:22px;font-weight:800;color:'+c.primary+';line-height:1;font-family:\'Oswald\',sans-serif">'+conf+'%</div>';
  html+='<div style="font-size:9px;color:'+sm.color+';letter-spacing:0.15em;text-transform:uppercase;margin-top:6px;font-weight:700;font-family:\'Manrope\',sans-serif">'+(confLabel||'LOW')+' Agreement</div>';
  html+='</div>';
  html+='<div style="text-align:center;border-left:1px solid '+c.divider+'">';
  html+='<div style="font-size:22px;font-weight:800;color:'+c.primary+';line-height:1;font-family:\'Oswald\',sans-serif">'+conv+'%</div>';
  html+='<div style="font-size:9px;color:'+sm.color+';letter-spacing:0.15em;text-transform:uppercase;margin-top:6px;font-weight:700;font-family:\'Manrope\',sans-serif">'+(convLabel||'MEDIUM')+' Conviction</div>';
  html+='</div>';
  html+='</div>';
  // Module breakdown
  var mb=data.metabrain||{};
  var drv=mb.drivers||{};
  var moduleList=[
    {key:'exchange',label:'Exchange',subtitle:'flow balanced · no edge'},
    {key:'sentiment',label:'Sentiment',subtitle:'neutral mood · no conviction'},
    {key:'fractal',label:'Fractal',subtitle:'structure still ranging'},
    {key:'onchain',label:'Onchain',subtitle:'chain quiet · no signal'},
    {key:'metabrain',label:'Metabrain',subtitle:'modules not yet converging'}
  ];
  html+='<div style="border-top:1px solid '+c.divider+';padding-top:12px">';
  html+='<div style="font-size:10px;font-weight:700;color:'+c.muted+';letter-spacing:0.15em;text-transform:uppercase;margin-bottom:8px;font-family:\'Manrope\',sans-serif">Module Breakdown</div>';
  moduleList.forEach(function(m){
    var dinfo=drv[m.key]||{};
    var insight=(dinfo.insight||dinfo.reason||'').slice(0,50);
    if(!insight)insight=m.subtitle;
    html+='<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid '+c.divider+'">';
    html+='<div>';
    html+='<div style="font-size:14px;font-weight:700;color:'+c.primary+';line-height:1.2;font-family:\'Manrope\',sans-serif">'+m.label+'</div>';
    html+='<div style="font-size:11px;color:'+c.muted+';margin-top:2px;font-family:\'Manrope\',sans-serif">'+insight+'</div>';
    html+='</div>';
    html+='<span style="font-size:14px;color:'+c.muted+'">→</span>';
    html+='</div>';
  });
  html+='</div>';
  html+='</div>';

  // ═══ Horizons selector ═══
  html+='<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:12px">';
  HORIZONS.forEach(function(hz){
    var active=hz===horizon;
    var tf=null;
    for(var j=0;j<(data.timeframes||[]).length;j++){
      if(data.timeframes[j].key===hz){tf=data.timeframes[j];break;}
    }
    var hzConf=tf?Math.round((tf.confidence||0)*100):conf;
    html+='<button data-mb-horizon="'+hz+'" style="background:'+(active?c.cardBg:c.innerBg)+';border:1.5px solid '+(active?c.blue:c.cardBorder)+';border-radius:10px;padding:10px 4px;cursor:pointer;text-align:center;color:'+c.primary+';font-family:\'Manrope\',sans-serif">';
    html+='<div style="font-size:13px;font-weight:800;color:'+(active?c.primary:c.secondary)+';letter-spacing:0.02em">'+hz+'</div>';
    html+='<div style="font-size:10px;color:'+c.muted+';margin-top:3px;font-family:\'JetBrains Mono\',monospace">'+hzConf+'%</div>';
    if(active){html+='<div style="height:2px;background:'+c.blue+';border-radius:2px;margin-top:6px"></div>'}
    html+='</button>';
  });
  html+='</div>';

  // ═══ Chart ═══
  var history=data.priceSeries||[];
  var projected=[],upper=[],lower=[];
  (data.timeframes||[]).forEach(function(t){
    if(t.key===horizon){
      projected=t.projectedSeries||[];
      upper=t.upperBand||[];
      lower=t.lowerBand||[];
    }
  });
  if(history.length||projected.length){
    html+='<div style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:16px;padding:12px 14px;margin-bottom:12px">';
    html+='<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">';
    html+='<span style="font-size:10px;font-weight:700;color:'+c.muted+';letter-spacing:0.15em;text-transform:uppercase;font-family:\'Manrope\',sans-serif">Mode</span>';
    html+='<div style="display:flex;gap:4px">';
    html+='<span style="background:'+c.innerBg+';border:1px solid '+c.cardBorder+';border-radius:8px;padding:4px 10px;font-size:11px;font-weight:700;color:'+c.primary+';font-family:\'Manrope\',sans-serif">PATH</span>';
    html+='<span style="background:transparent;border:1px solid '+c.cardBorder+';border-radius:8px;padding:4px 10px;font-size:11px;color:'+c.muted+';font-family:\'Manrope\',sans-serif">RANGE</span>';
    html+='</div>';
    html+='</div>';
    html+='<div style="margin:0 -4px">'+buildChart(history,projected,upper,lower,c,340,180)+'</div>';
    html+='<div style="font-size:10px;color:'+c.muted+';text-align:center;margin-top:6px;font-style:italic;font-family:\'Manrope\',sans-serif">Most likely path · MetaBrain projection</div>';
    html+='</div>';
  }

  // ═══ Next Move Levels ═══
  var ba=nextMove.breakAbove,bb=nextMove.breakBelow;
  if(ba||bb){
    html+='<div style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:16px;padding:14px 16px;margin-bottom:12px">';
    html+='<div style="font-size:10px;font-weight:700;color:'+c.muted+';letter-spacing:0.15em;text-transform:uppercase;margin-bottom:10px;font-family:\'Manrope\',sans-serif">Next Move Levels</div>';
    html+='<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">';
    if(ba){
      html+='<div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.25);border-radius:10px;padding:10px 12px">';
      html+='<div style="font-size:10px;font-weight:800;color:'+c.green+';letter-spacing:0.08em;margin-bottom:4px;font-family:\'JetBrains Mono\',monospace">▲ BREAK ABOVE</div>';
      html+='<div style="font-size:15px;font-weight:800;color:'+c.primary+';line-height:1.1;font-family:\'Oswald\',sans-serif">'+fmtPrice(ba.price)+'</div>';
      html+='<div style="font-size:10px;color:'+c.muted+';margin-top:3px;font-family:\'JetBrains Mono\',monospace">'+fmtPct(ba.distancePct)+' away</div>';
      html+='</div>';
    }else{html+='<div></div>'}
    if(bb){
      html+='<div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);border-radius:10px;padding:10px 12px">';
      html+='<div style="font-size:10px;font-weight:800;color:'+c.red+';letter-spacing:0.08em;margin-bottom:4px;font-family:\'JetBrains Mono\',monospace">▼ BREAK BELOW</div>';
      html+='<div style="font-size:15px;font-weight:800;color:'+c.primary+';line-height:1.1;font-family:\'Oswald\',sans-serif">'+fmtPrice(bb.price)+'</div>';
      html+='<div style="font-size:10px;color:'+c.muted+';margin-top:3px;font-family:\'JetBrains Mono\',monospace">'+fmtPct(bb.distancePct)+' away</div>';
      html+='</div>';
    }else{html+='<div></div>'}
    html+='</div>';
    html+='</div>';
  }

  // ═══ Interpretation / Why ═══
  var interp=data.interpretation||[];
  if(interp.length>0){
    html+='<div style="background:'+c.cardBg+';border:1px solid '+c.cardBorder+';border-radius:16px;padding:14px 16px;margin-bottom:12px">';
    html+='<div style="font-size:10px;font-weight:700;color:'+c.muted+';letter-spacing:0.15em;text-transform:uppercase;margin-bottom:8px;font-family:\'Manrope\',sans-serif">Why · MetaBrain Read</div>';
    interp.slice(0,5).forEach(function(line){
      html+='<div style="font-size:12px;color:'+c.primary+';line-height:1.5;padding:3px 0;font-family:\'Manrope\',sans-serif">• '+line+'</div>';
    });
    html+='</div>';
  }

  html+='</div>';
  html+='</div>';
  return html;
}

// ─── Anchor & render ─────────────────────────────────────
function findAnchor(){
  var hero=document.querySelector('[data-testid="decision-hero-card"]');
  if(hero)return hero;
  var cards=document.querySelectorAll('[data-testid], div');
  for(var i=0;i<cards.length;i++){
    var d=cards[i],t=d.textContent||'';
    if((t.indexOf('BUY')!==-1||t.indexOf('SELL')!==-1||t.indexOf('WAIT')!==-1)&&
       t.indexOf('Confidence')!==-1&&d.offsetHeight>100&&d.offsetHeight<500&&d.offsetWidth>200){
      return d;
    }
  }
  return null;
}

function getAsset(){
  var p=new URLSearchParams(location.search);
  if(p.get('asset'))return p.get('asset').toUpperCase();
  var el=document.getElementById?document.getElementById('current-asset')||document.querySelector('[data-testid="asset-selector"]'):null;
  if(el)return (el.textContent||'BTC').trim().toUpperCase();
  return 'BTC';
}

function openOverlay(){
  closeOverlay();
  if(!mbPayload)return;
  var wrap=document.createElement('div');
  wrap.innerHTML=buildDetailsOverlay(mbPayload,getAsset(),mbHorizon);
  document.body.appendChild(wrap.firstChild);
  document.body.style.overflow='hidden';
  // Hook close
  var closeBtn=document.querySelector('[data-mb-close]');
  if(closeBtn)closeBtn.addEventListener('click',closeOverlay);
  // Hook horizon buttons inside overlay
  var hBtns=document.querySelectorAll('#_metabrain_overlay [data-mb-horizon]');
  for(var i=0;i<hBtns.length;i++){
    (function(btn){
      btn.addEventListener('click',function(ev){
        ev.stopPropagation();
        var hz=btn.getAttribute('data-mb-horizon');
        if(hz===mbHorizon)return;
        mbHorizon=hz;
        loadMB(getAsset(),mbHorizon,function(d){
          if(d){mbPayload=d;openOverlay();renderSnapshot();}
        });
      });
    })(hBtns[i]);
  }
}

function closeOverlay(){
  var ov=document.getElementById('_metabrain_overlay');
  if(ov)ov.parentNode.removeChild(ov);
  document.body.style.overflow='';
}

function renderSnapshot(){
  var existing=document.getElementById('_metabrain_layer');
  if(existing)existing.parentNode.removeChild(existing);
  if(!mbPayload)return;
  var anchor=findAnchor();
  if(!anchor)return;
  var wrap=document.createElement('div');
  wrap.innerHTML=buildSnapshotCard(mbPayload,getAsset(),mbHorizon);
  if(anchor.nextSibling){
    anchor.parentNode.insertBefore(wrap.firstChild,anchor.nextSibling);
  }else{
    anchor.parentNode.appendChild(wrap.firstChild);
  }
  // Click anywhere on the snapshot card opens overlay
  var layer=document.getElementById('_metabrain_layer');
  if(layer){
    var clickable=layer.querySelector('[data-mb-open]');
    if(clickable){
      clickable.addEventListener('click',function(ev){
        ev.stopPropagation();
        openOverlay();
      });
    }
  }
  mbDone=true;
}

function injectMB(){
  if(mbDone&&document.getElementById('_metabrain_layer'))return;
  var anchor=findAnchor();
  if(!anchor)return;
  if(mbPayload){renderSnapshot();return;}
  loadMB(getAsset(),mbHorizon,function(d){
    if(!d)return;
    mbPayload=d;
    renderSnapshot();
  });
}

var mbObs=new MutationObserver(function(){
  if(!document.getElementById('_metabrain_layer'))mbDone=false;
  if(!mbDone)injectMB();
});

// ─── Theme change watcher ────────────────────────────────
// Re-render snapshot & overlay when SPA flips light/dark.
var _mbLastTheme=null;
function _watchTheme(){
  try{
    var cur=_detectThemeDark();
    if(_mbLastTheme===null){_mbLastTheme=cur;return;}
    if(cur!==_mbLastTheme){
      _mbLastTheme=cur;
      if(document.getElementById('_metabrain_layer')){
        mbDone=false;
        renderSnapshot();
      }
      if(document.getElementById('_metabrain_overlay')){
        openOverlay(); // rebuilds overlay with fresh palette
      }
    }
  }catch(e){}
}
setInterval(_watchTheme,600);
// Also subscribe to Telegram theme events when available
try{
  if(window.Telegram&&Telegram.WebApp&&Telegram.WebApp.onEvent){
    Telegram.WebApp.onEvent('themeChanged',function(){setTimeout(_watchTheme,150)});
  }
}catch(e){}

function startMB(){
  try{mbObs.observe(document.body,{childList:true,subtree:true});}catch(e){}
  injectMB();
}

if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded',function(){setTimeout(startMB,3500)});
}else{
  setTimeout(startMB,3500);
}
})();
