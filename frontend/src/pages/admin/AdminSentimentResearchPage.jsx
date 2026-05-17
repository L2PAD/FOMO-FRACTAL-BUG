/**
 * Sentiment Research — Analytics & Validation
 * ==============================================
 * 
 * Research layer: correlation analysis and statistical validation.
 * Tabs: Сигналы × Цена, Горизонты, Проводник, Уверенность, Упущенные, Валидация
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { useAdminAuth } from '../../context/AdminAuthContext';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../../components/ui/card';
import { Progress } from '../../components/ui/progress';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../../components/ui/select';
import {
  Activity, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  TrendingUp, TrendingDown, Minus, BarChart3, Target, Clock,
  Loader2, Filter, Search, X, Info, Zap, AlertCircle, Layers, Database,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============================================================
// Helpers
// ============================================================

const OutcomeBadge = ({ outcome }) => {
  const cfg = {
    TRUE_POSITIVE: 'text-emerald-600',
    TRUE_NEGATIVE: 'text-emerald-600',
    FALSE_POSITIVE: 'text-red-600',
    FALSE_NEGATIVE: 'text-red-600',
    MISSED_OPPORTUNITY: 'text-amber-600',
    NO_SIGNAL: 'text-slate-500',
    PENDING: 'text-blue-500',
  };
  return <span className={`${cfg[outcome] || cfg.PENDING} text-xs font-semibold`}>{outcome?.replace(/_/g, ' ')}</span>;
};

const SentimentBadge = ({ label }) => {
  const c = { POSITIVE: 'text-emerald-600', NEUTRAL: 'text-amber-600', NEGATIVE: 'text-red-600' };
  return <span className={`${c[label] || 'text-slate-500'} text-xs font-semibold`}>{label}</span>;
};

const DirectionBadge = ({ direction, delta }) => {
  const cls = { UP: 'text-emerald-600', DOWN: 'text-red-600', FLAT: 'text-slate-500' };
  const icons = { UP: <TrendingUp className="w-4 h-4" />, DOWN: <TrendingDown className="w-4 h-4" />, FLAT: <Minus className="w-4 h-4" /> };
  return <span className={`flex items-center gap-1 font-medium ${cls[direction]}`}>{icons[direction]}{delta !== undefined && `${delta > 0 ? '+' : ''}${delta.toFixed(2)}%`}</span>;
};

const CorrelationBadge = ({ value, indicator }) => {
  const cls = { gray: 'text-slate-500', yellow: 'text-amber-600', green: 'text-emerald-600' };
  return <span className={`${cls[indicator] || cls.gray} text-sm font-semibold`}>{value != null ? value.toFixed(3) : '—'}</span>;
};

const EdgeBadge = ({ strength }) => {
  const cls = { NONE: 'text-slate-500', WEAK: 'text-amber-600', MODERATE: 'text-blue-600', STRONG: 'text-emerald-600' };
  return <span className={`${cls[strength] || cls.NONE} text-sm font-semibold`}>{strength}</span>;
};

function getOutcomeLabel(sentimentLabel, direction, magnitude) {
  if (!direction) return 'PENDING';
  if (sentimentLabel === 'POSITIVE') return direction === 'UP' ? 'TRUE_POSITIVE' : 'FALSE_POSITIVE';
  if (sentimentLabel === 'NEGATIVE') return direction === 'DOWN' ? 'TRUE_NEGATIVE' : 'FALSE_NEGATIVE';
  if (direction === 'FLAT' || magnitude === 'NONE') return 'NO_SIGNAL';
  if (magnitude === 'STRONG') return 'MISSED_OPPORTUNITY';
  return 'NO_SIGNAL';
}

const Tooltip = ({ text, children }) => (
  <div className="group relative inline-flex items-center">
    {children}
    <div className="hidden group-hover:block absolute z-20 bottom-full left-0 mb-2 p-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg w-56 pointer-events-none">{text}</div>
  </div>
);

// ============================================================
// Main
// ============================================================

export default function AdminSentimentResearchPage() {
  const navigate = useNavigate();
  const { isAuthenticated } = useAdminAuth();
  
  // Price layer state
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState(null);
  const [signals, setSignals] = useState([]);
  const [selectedSignal, setSelectedSignal] = useState(null);
  const [selectedHorizon, setSelectedHorizon] = useState('1h');
  const [filterAsset, setFilterAsset] = useState('all');
  const [filterSentiment, setFilterSentiment] = useState('all');
  const [filterOutcome, setFilterOutcome] = useState('all');
  
  // Validation state
  const [summary, setSummary] = useState(null);
  const [correlationData, setCorrelationData] = useState([]);
  const [strengthData, setStrengthData] = useState(null);
  const [valHorizon, setValHorizon] = useState('7D');
  
  useEffect(() => { if (!isAuthenticated) navigate('/admin/login'); }, [isAuthenticated, navigate]);
  
  const fetchPriceData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, signalsRes] = await Promise.all([
        fetch(`${API_URL}/api/v5/price-layer/stats`),
        fetch(`${API_URL}/api/v5/price-layer/signals?limit=100`),
      ]);
      const statsData = await statsRes.json();
      const signalsData = await signalsRes.json();
      if (statsData.ok) setStats(statsData.data);
      if (signalsData.ok) setSignals(signalsData.data.signals || []);
    } catch (e) { console.error('Failed:', e); }
    finally { setLoading(false); }
  }, []);
  
  const fetchValidation = useCallback(async () => {
    try {
      const [sumRes, corrRes, strRes] = await Promise.all([
        fetch(`${API_URL}/api/admin/sentiment-ml/validation/summary`),
        fetch(`${API_URL}/api/admin/sentiment-ml/validation/correlation`),
        fetch(`${API_URL}/api/admin/sentiment-ml/validation/strength?horizon=${valHorizon}`),
      ]);
      const sumData = await sumRes.json();
      const corrData = await corrRes.json();
      const strData = await strRes.json();
      if (sumData.ok) setSummary(sumData.data);
      if (corrData.ok) setCorrelationData(corrData.data);
      if (strData.ok) setStrengthData(strData);
    } catch (e) { console.error('Validation fetch failed:', e); }
  }, [valHorizon]);
  
  useEffect(() => { fetchPriceData(); fetchValidation(); }, [fetchPriceData, fetchValidation]);
  useEffect(() => { fetchValidation(); }, [valHorizon, fetchValidation]);
  
  // Computed
  const filteredSignals = signals.filter(s => {
    if (filterAsset !== 'all' && s.asset !== filterAsset) return false;
    if (filterSentiment !== 'all' && s.sentiment?.label !== filterSentiment) return false;
    return true;
  });
  
  const horizonStats = ['5m', '15m', '1h', '4h', '24h'].map(h => {
    const withH = signals.filter(s => s.reactions?.some(r => r.horizon === h));
    let tp=0,fp=0,tn=0,fn=0,missed=0,noSignal=0,totalDelta=0;
    withH.forEach(s => {
      const r = s.reactions?.find(r => r.horizon === h); if (!r) return;
      const l=s.sentiment?.label, d=r.direction, m=r.magnitude;
      if(l==='POSITIVE'&&d==='UP'){tp++;totalDelta+=r.delta_pct;}
      else if(l==='POSITIVE')fp++;
      else if(l==='NEGATIVE'&&d==='DOWN')tn++;
      else if(l==='NEGATIVE')fn++;
      else if(l==='NEUTRAL'&&m==='STRONG')missed++;
      else noSignal++;
    });
    const total=tp+fp+tn+fn+missed+noSignal;
    return {horizon:h,tp,fp,tn,fn,missed,noSignal,total,accuracy:total>0?((tp+tn+noSignal)/total)*100:0,avgDelta:tp>0?totalDelta/tp:0};
  });
  
  const confidenceBuckets = [
    {label:'0.9-1.0',min:0.9,max:1.0},{label:'0.7-0.9',min:0.7,max:0.9},{label:'0.5-0.7',min:0.5,max:0.7},{label:'<0.5',min:0,max:0.5},
  ].map(b => {
    const inB = signals.filter(s => { const c=s.sentiment?.confidence||0; return c>=b.min&&c<b.max; });
    let tp=0,fp=0,fn=0,total=0;
    inB.forEach(s => {
      const r=s.reactions?.find(r=>r.horizon===selectedHorizon); if(!r)return; total++;
      const l=s.sentiment?.label,d=r.direction;
      if(l==='POSITIVE'&&d==='UP')tp++; else if(l==='POSITIVE')fp++; else if(l==='NEGATIVE'&&d!=='DOWN')fn++;
    });
    return {...b,tp,fp,fn,total,tpRate:total>0?(tp/total)*100:0};
  });
  
  const missedOpportunities = signals.filter(s => {
    const r=s.reactions?.find(r=>r.horizon===selectedHorizon);
    return s.sentiment?.label==='NEUTRAL'&&r?.magnitude==='STRONG';
  });
  
  const overall = summary?.overall || {};
  const byHorizon = summary?.byHorizon || [];

  if (loading) {
    return <AdminLayout><div className="flex items-center justify-center h-96"><Loader2 className="w-8 h-8 animate-spin text-indigo-500" /></div></AdminLayout>;
  }
  
  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-sentiment-research">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-50 rounded-lg"><Search className="w-6 h-6 text-indigo-500" /></div>
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Sentiment &mdash; Research</h1>
              <p className="text-sm text-gray-500">Корреляция сигналов с ценой и статистическая валидация</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-1">
              {['5m','15m','1h','4h','24h'].map(h => (
                <Button key={h} variant={selectedHorizon===h?'default':'outline'} size="sm" onClick={() => setSelectedHorizon(h)}>
                  {h}
                </Button>
              ))}
            </div>
            <Button variant="outline" size="sm" onClick={() => { fetchPriceData(); fetchValidation(); }} className="bg-white border-gray-300 text-gray-700 hover:bg-gray-50">
              <RefreshCw className="w-4 h-4 mr-2" /> Обновить
            </Button>
          </div>
        </div>

        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="bg-gray-100">
            <TabsTrigger value="overview" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Activity className="w-4 h-4 mr-2" /> Обзор сигналов
            </TabsTrigger>
            <TabsTrigger value="horizons" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Clock className="w-4 h-4 mr-2" /> Горизонты
            </TabsTrigger>
            <TabsTrigger value="explorer" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Search className="w-4 h-4 mr-2" /> Проводник
            </TabsTrigger>
            <TabsTrigger value="confidence" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <Target className="w-4 h-4 mr-2" /> Уверенность
            </TabsTrigger>
            <TabsTrigger value="missed" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <AlertCircle className="w-4 h-4 mr-2" /> Упущенные
            </TabsTrigger>
            <TabsTrigger value="validation" className="data-[state=active]:bg-white data-[state=active]:text-gray-800">
              <BarChart3 className="w-4 h-4 mr-2" /> Валидация
            </TabsTrigger>
          </TabsList>

          {/* ======================== Обзор сигналов ======================== */}
          <TabsContent value="overview" className="space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                {title:'Всего сигналов',value:stats?.totalSignals||0,icon:Zap,color:'indigo'},
                {title:'С результатами',value:stats?.totalOutcomes||0,icon:BarChart3,color:'slate'},
                {title:'Точность сигналов (Signal Accuracy)',value:`${((stats?.signalAccuracy||0)*100).toFixed(1)}%`,icon:Target,color:stats?.signalAccuracy>0.5?'emerald':'amber'},
                {title:'Полнота (Completeness)',value:`${((stats?.completenessRate||0)*100).toFixed(0)}%`,icon:CheckCircle,color:'indigo'},
              ].map(({title,value,icon:Icon,color}) => (
                <div key={title} className={`p-4 bg-${color}-50 rounded-lg`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs font-medium opacity-70">{title}</p>
                      <p className="text-2xl font-bold mt-1">{value}</p>
                    </div>
                    <Icon className="w-8 h-8 opacity-40" />
                  </div>
                </div>
              ))}
            </div>
            
            <div className="grid md:grid-cols-2 gap-6">
              <Card>
                <CardHeader><CardTitle className="text-lg">По активу (By Asset)</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {Object.entries(stats?.signalsByAsset||{}).map(([asset,count]) => (
                      <div key={asset} className="flex items-center justify-between">
                        <span className="font-medium">{asset}</span>
                        <div className="flex items-center gap-3">
                          <Progress value={(count/stats?.totalSignals)*100} className="w-24 h-2" />
                          <span className="text-sm text-slate-600 w-12 text-right">{count}</span>
                        </div>
                      </div>
                    ))}
                    {Object.keys(stats?.signalsByAsset||{}).length===0 && <p className="text-sm text-slate-400">Нет данных</p>}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader><CardTitle className="text-lg">По настроению (By Sentiment)</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {['POSITIVE','NEUTRAL','NEGATIVE'].map(label => {
                      const count=stats?.signalsBySentiment?.[label]||0;
                      const clr={POSITIVE:'bg-emerald-500',NEUTRAL:'bg-amber-500',NEGATIVE:'bg-red-500'};
                      return (
                        <div key={label} className="flex items-center justify-between">
                          <SentimentBadge label={label} />
                          <div className="flex items-center gap-3">
                            <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                              <div className={`h-full ${clr[label]} rounded-full`} style={{width:`${(count/(stats?.totalSignals||1))*100}%`}} />
                            </div>
                            <span className="text-sm text-slate-600 w-12 text-right">{count}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* ======================== Горизонты ======================== */}
          <TabsContent value="horizons" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Сравнение горизонтов (Horizon Comparison)</CardTitle>
                <CardDescription>На каком горизонте настроения имеют предсказательную силу?</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="">
                        <th className="text-left py-3 px-4 font-medium text-slate-600">Горизонт</th>
                        <th className="text-center py-3 px-4 font-medium text-emerald-600">TP</th>
                        <th className="text-center py-3 px-4 font-medium text-red-600">FP</th>
                        <th className="text-center py-3 px-4 font-medium text-emerald-600">TN</th>
                        <th className="text-center py-3 px-4 font-medium text-red-600">FN</th>
                        <th className="text-center py-3 px-4 font-medium text-amber-600">Упущ.</th>
                        <th className="text-center py-3 px-4 font-medium text-slate-600">Нет сигн.</th>
                        <th className="text-center py-3 px-4 font-medium text-slate-600">Всего</th>
                        <th className="text-center py-3 px-4 font-medium text-indigo-600">Точность</th>
                        <th className="text-center py-3 px-4 font-medium text-slate-600">Ср. &Delta;%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {horizonStats.map(h => (
                        <tr key={h.horizon} className={`hover:bg-slate-50 ${h.horizon===selectedHorizon?'bg-indigo-50':''}`}>
                          <td className="py-3 px-4 font-medium">{h.horizon}</td>
                          <td className="text-center py-3 px-4 text-emerald-600 font-medium">{h.tp}</td>
                          <td className="text-center py-3 px-4 text-red-600">{h.fp}</td>
                          <td className="text-center py-3 px-4 text-emerald-600 font-medium">{h.tn}</td>
                          <td className="text-center py-3 px-4 text-red-600">{h.fn}</td>
                          <td className="text-center py-3 px-4 text-amber-600">{h.missed}</td>
                          <td className="text-center py-3 px-4 text-slate-500">{h.noSignal}</td>
                          <td className="text-center py-3 px-4">{h.total}</td>
                          <td className="text-center py-3 px-4">
                            <span className={`font-bold ${h.accuracy>=50?'text-emerald-600':'text-red-600'}`}>{h.accuracy != null ? h.accuracy.toFixed(1) : '—'}%</span>
                          </td>
                          <td className="text-center py-3 px-4 text-slate-600">{h.avgDelta != null && h.avgDelta>0?`+${h.avgDelta.toFixed(2)}%`:'-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {horizonStats.every(h=>h.total===0) && (
                  <div className="text-center py-8 text-slate-400"><Clock className="w-8 h-8 mx-auto mb-2 opacity-50" /><p>Нет данных. Создайте сигналы и дождитесь сбора цен.</p></div>
                )}
              </CardContent>
            </Card>
            
            <Card className="bg-blue-50 ">
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Info className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-900">Как читать таблицу</p>
                    <ul className="text-sm text-blue-700 mt-2 space-y-1">
                      <li><strong>TP (True Positive):</strong> POSITIVE настроение &rarr; цена вверх</li>
                      <li><strong>FP (False Positive):</strong> POSITIVE настроение &rarr; цена вниз/без движения</li>
                      <li><strong>TN (True Negative):</strong> NEGATIVE настроение &rarr; цена вниз</li>
                      <li><strong>FN (False Negative):</strong> NEGATIVE настроение &rarr; цена вверх/без движения</li>
                      <li><strong>Упущенные:</strong> NEUTRAL настроение &rarr; сильное движение цены</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== Проводник ======================== */}
          <TabsContent value="explorer" className="space-y-6">
            <Card>
              <CardContent className="p-4">
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-2"><Filter className="w-4 h-4 text-slate-400" /><span className="text-sm font-medium text-slate-600">Фильтры:</span></div>
                  <Select value={filterAsset} onValueChange={setFilterAsset}><SelectTrigger className="w-32"><SelectValue placeholder="Актив" /></SelectTrigger>
                    <SelectContent><SelectItem value="all">Все активы</SelectItem><SelectItem value="BTC">BTC</SelectItem><SelectItem value="ETH">ETH</SelectItem><SelectItem value="SOL">SOL</SelectItem></SelectContent>
                  </Select>
                  <Select value={filterSentiment} onValueChange={setFilterSentiment}><SelectTrigger className="w-32"><SelectValue placeholder="Настроение" /></SelectTrigger>
                    <SelectContent><SelectItem value="all">Все</SelectItem><SelectItem value="POSITIVE">POSITIVE</SelectItem><SelectItem value="NEUTRAL">NEUTRAL</SelectItem><SelectItem value="NEGATIVE">NEGATIVE</SelectItem></SelectContent>
                  </Select>
                  {(filterAsset!=='all'||filterSentiment!=='all') && (
                    <Button variant="ghost" size="sm" onClick={() => {setFilterAsset('all');setFilterSentiment('all');}}><X className="w-4 h-4 mr-1" />Сбросить</Button>
                  )}
                  <span className="text-sm text-slate-500 ml-auto">{filteredSignals.length} сигналов</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="bg-slate-50">
                      <th className="text-left py-3 px-4 font-medium text-slate-600">Текст</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">Актив</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">Настроение</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">Увер.</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">&Delta;% ({selectedHorizon})</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">Результат</th>
                    </tr></thead>
                    <tbody>
                      {filteredSignals.slice(0,50).map(signal => {
                        const reaction=signal.reactions?.find(r=>r.horizon===selectedHorizon);
                        const outcome=getOutcomeLabel(signal.sentiment?.label,reaction?.direction,reaction?.magnitude);
                        return (
                          <tr key={signal.signal_id} className="hover:bg-slate-50 cursor-pointer" onClick={() => setSelectedSignal(signal)}>
                            <td className="py-3 px-4 max-w-xs truncate">{signal.meta?.text||'-'}</td>
                            <td className="text-center py-3 px-4 font-medium">{signal.asset}</td>
                            <td className="text-center py-3 px-4"><SentimentBadge label={signal.sentiment?.label} /></td>
                            <td className="text-center py-3 px-4">{((signal.sentiment?.confidence||0)*100).toFixed(0)}%</td>
                            <td className="text-center py-3 px-4">{reaction?<DirectionBadge direction={reaction.direction} delta={reaction.delta_pct} />:<span className="text-slate-400">ожидание</span>}</td>
                            <td className="text-center py-3 px-4">{reaction?<OutcomeBadge outcome={outcome} />:<OutcomeBadge outcome="PENDING" />}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                {filteredSignals.length===0 && <div className="text-center py-12 text-slate-400"><Search className="w-8 h-8 mx-auto mb-2 opacity-50" /><p>Нет сигналов по фильтрам</p></div>}
              </CardContent>
            </Card>
            
            {selectedSignal && (
              <Card className="bg-indigo-50/50">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-lg">Детали сигнала</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setSelectedSignal(null)}><X className="w-4 h-4" /></Button>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="font-medium text-slate-700 mb-2">Текст</h4>
                      <p className="text-sm bg-white p-3 rounded">{selectedSignal.meta?.text||'Нет текста'}</p>
                      <h4 className="font-medium text-slate-700 mt-4 mb-2">Настроение (Sentiment)</h4>
                      <div className="flex items-center gap-3">
                        <SentimentBadge label={selectedSignal.sentiment?.label} />
                        <span className="text-sm text-slate-600">Оценка: {selectedSignal.sentiment?.score?.toFixed(3)}</span>
                        <span className="text-sm text-slate-600">Уверенность: {((selectedSignal.sentiment?.confidence||0)*100).toFixed(0)}%</span>
                      </div>
                    </div>
                    <div>
                      <h4 className="font-medium text-slate-700 mb-2">Реакция цены (Price Reactions)</h4>
                      <div className="space-y-2">
                        {selectedSignal.reactions?.length>0 ? selectedSignal.reactions.map(r => (
                          <div key={r.horizon} className="flex items-center justify-between bg-white p-2 rounded">
                            <span className="font-medium">{r.horizon}</span>
                            <DirectionBadge direction={r.direction} delta={r.delta_pct} />
                            <span className="text-xs text-slate-600">{r.magnitude}</span>
                          </div>
                        )) : <p className="text-sm text-slate-400">Нет реакций</p>}
                      </div>
                      <h4 className="font-medium text-slate-700 mt-4 mb-2">Мета</h4>
                      <div className="text-sm text-slate-600 space-y-1">
                        <p>Актив: <strong>{selectedSignal.asset}</strong></p>
                        <p>Источник: {selectedSignal.source}</p>
                        <p>Создан: {new Date(selectedSignal.created_at).toLocaleString()}</p>
                        <p>Цена t0: ${selectedSignal.price_t0?.toLocaleString()||'Н/Д'}</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          {/* ======================== Уверенность ======================== */}
          <TabsContent value="confidence" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Матрица уверенности и результатов (Confidence &times; Outcome)</CardTitle>
                <CardDescription>Более высокая уверенность = лучшие результаты? Горизонт: {selectedHorizon}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="">
                      <th className="text-left py-3 px-4 font-medium text-slate-600">Уверенность</th>
                      <th className="text-center py-3 px-4 font-medium text-slate-600">Сигналы</th>
                      <th className="text-center py-3 px-4 font-medium text-emerald-600">TP</th>
                      <th className="text-center py-3 px-4 font-medium text-red-600">FP</th>
                      <th className="text-center py-3 px-4 font-medium text-red-600">FN</th>
                      <th className="text-center py-3 px-4 font-medium text-indigo-600">TP Rate</th>
                    </tr></thead>
                    <tbody>
                      {confidenceBuckets.map(b => (
                        <tr key={b.label} className="hover:bg-slate-50">
                          <td className="py-3 px-4 font-medium">{b.label}</td>
                          <td className="text-center py-3 px-4">{b.total}</td>
                          <td className="text-center py-3 px-4 text-emerald-600 font-medium">{b.tp}</td>
                          <td className="text-center py-3 px-4 text-red-600">{b.fp}</td>
                          <td className="text-center py-3 px-4 text-red-600">{b.fn}</td>
                          <td className="text-center py-3 px-4">
                            <div className="flex items-center justify-center gap-2">
                              <div className="w-16 h-2 bg-slate-100 rounded-full overflow-hidden">
                                <div className="h-full bg-indigo-500 rounded-full" style={{width:`${b.tpRate}%`}} />
                              </div>
                              <span className="font-medium">{b.tpRate != null ? b.tpRate.toFixed(0) : '—'}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== Упущенные ======================== */}
          <TabsContent value="missed" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                  Упущенные возможности (Missed Opportunities)
                </CardTitle>
                <CardDescription>NEUTRAL настроение + сильное движение цены. Горизонт: {selectedHorizon}</CardDescription>
              </CardHeader>
              <CardContent>
                {missedOpportunities.length>0 ? (
                  <div className="space-y-3">
                    {missedOpportunities.map(signal => {
                      const reaction=signal.reactions?.find(r=>r.horizon===selectedHorizon);
                      return (
                        <div key={signal.signal_id} className="p-4 bg-amber-50 rounded-lg">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <p className="text-sm text-slate-700 mb-2">{signal.meta?.text||'Нет текста'}</p>
                              <div className="flex items-center gap-3 text-xs">
                                <span className="font-medium">{signal.asset}</span>
                                <SentimentBadge label={signal.sentiment?.label} />
                                <span className="text-slate-500">Увер.: {((signal.sentiment?.confidence||0)*100).toFixed(0)}%</span>
                              </div>
                            </div>
                            <div className="text-right">
                              <DirectionBadge direction={reaction?.direction} delta={reaction?.delta_pct} />
                              <p className="text-xs text-slate-500 mt-1">{reaction?.magnitude} движение</p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-center py-12 text-slate-400">
                    <CheckCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>Нет упущенных возможностей на горизонте {selectedHorizon}</p>
                    <p className="text-xs mt-1">Это хорошо &mdash; NEUTRAL сигналы остались нейтральными</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* ======================== Валидация ======================== */}
          <TabsContent value="validation" className="space-y-6">
            {/* Summary */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">Статистическая валидация (Validation Summary)</CardTitle>
                    <CardDescription>Предсказывает ли смещение (bias) реальное движение цены?</CardDescription>
                  </div>
                  <EdgeBadge strength={overall.edgeStrength||'NONE'} />
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-4 gap-4">
                  {[
                    {title:'Выборка (Samples)',value:overall.totalSamples||0,icon:Database},
                    {title:'Ср. Hit Rate',value:`${((overall.avgHitRate||0)*100).toFixed(1)}%`,icon:Target},
                    {title:'Ср. корреляция (Correlation)',value:(overall.avgCorrelation||0).toFixed(3),icon:Activity},
                    {title:'Преимущество (Edge)',value:overall.hasEdge?'ДА':'НЕТ',icon:TrendingUp},
                  ].map(({title,value,icon:Icon}) => (
                    <div key={title} className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-500">{title}</span>
                        <Icon className="w-4 h-4 text-gray-400" />
                      </div>
                      <span className="text-2xl font-semibold text-gray-800">{value}</span>
                    </div>
                  ))}
                </div>
                {summary?.recommendation && (
                  <div className="bg-blue-50 rounded-lg p-4">
                    <div className="flex items-start gap-3">
                      <Info className="w-5 h-5 text-blue-500 mt-0.5" />
                      <div>
                        <div className="font-medium text-blue-800 text-sm">Рекомендация</div>
                        <div className="text-blue-700 text-sm mt-1">{summary.recommendation}</div>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
            
            {/* Correlation Monitor */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-gray-500" />
                  Монитор корреляции (Correlation Monitor)
                </CardTitle>
                <CardDescription>Корреляция Пирсона между смещением и форвардной доходностью</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-4">
                  {correlationData.map(item => (
                    <div key={item.horizon} className="bg-gray-50 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-lg font-semibold text-gray-800">{item.horizon}</span>
                        <CorrelationBadge value={item.correlation} indicator={item.indicator} />
                      </div>
                      <div className="text-sm text-gray-500">{item.sampleCount} выборок</div>
                      <div className="mt-2 h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div className={`h-full ${item.indicator==='green'?'bg-emerald-500':item.indicator==='yellow'?'bg-amber-500':'bg-gray-400'}`}
                          style={{width:`${Math.min(Math.abs(item.correlation)*500,100)}%`}} />
                      </div>
                      <div className="text-xs text-gray-400 mt-1">
                        {item.indicator==='green'?'>=0.10 Хороший сигнал':item.indicator==='yellow'?'0.05-0.10 Слабый сигнал':'<0.05 Нет сигнала'}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
            
            {/* Bias Strength */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Layers className="w-5 h-5 text-gray-500" />
                      Сила смещения (Bias Strength Segmentation)
                    </CardTitle>
                    <CardDescription>Сильнее смещение = лучше доходность?</CardDescription>
                  </div>
                  <div className="flex gap-2">
                    {['24H','7D','30D'].map(h => (
                      <Button key={h} variant={valHorizon===h?'default':'outline'} size="sm" onClick={() => setValHorizon(h)}>{h}</Button>
                    ))}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {strengthData?.sampleCount===0 ? (
                  <div className="text-center text-gray-500 py-8">Нет данных для {valHorizon}. Данные появятся после созревания окна.</div>
                ) : (
                  <>
                    <div className={`mb-4 p-3 rounded-lg ${strengthData?.hasGradient?'bg-emerald-50':'bg-gray-50'}`}>
                      <div className="flex items-center gap-2">
                        {strengthData?.hasGradient?<CheckCircle className="w-4 h-4 text-emerald-600" />:<AlertTriangle className="w-4 h-4 text-gray-500" />}
                        <span className={`text-sm font-medium ${strengthData?.hasGradient?'text-emerald-700':'text-gray-600'}`}>
                          {strengthData?.hasGradient?`Градиент обнаружен: +${strengthData.gradientStrength} улучшение hit rate`:'Нет чёткого градиента'}
                        </span>
                      </div>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead><tr className="">
                          <th className="text-left text-sm font-medium text-gray-500 py-2 px-3">Диапазон смещения</th>
                          <th className="text-right text-sm font-medium text-gray-500 py-2 px-3">Выборка</th>
                          <th className="text-right text-sm font-medium text-gray-500 py-2 px-3">Hit Rate</th>
                          <th className="text-right text-sm font-medium text-gray-500 py-2 px-3">Ср. доход</th>
                          <th className="text-left text-sm font-medium text-gray-500 py-2 px-3">Визуал</th>
                        </tr></thead>
                        <tbody>
                          {(strengthData?.buckets||[]).map(bucket => (
                            <tr key={bucket.range} className=" hover:bg-gray-50">
                              <td className="py-3 px-3"><span className="text-sm text-gray-700">{bucket.range}</span></td>
                              <td className="py-3 px-3 text-right text-sm text-gray-600">{bucket.samples}</td>
                              <td className="py-3 px-3 text-right">
                                <span className={`text-sm font-medium ${(bucket.hitRate||0)>0.55?'text-emerald-600':(bucket.hitRate||0)>0.50?'text-amber-600':'text-gray-600'}`}>
                                  {((bucket.hitRate||0)*100).toFixed(1)}%
                                </span>
                              </td>
                              <td className="py-3 px-3 text-right">
                                <span className={`text-sm font-medium ${(bucket.avgReturn||0)>0?'text-emerald-600':(bucket.avgReturn||0)<0?'text-red-600':'text-gray-600'}`}>
                                  {(bucket.avgReturn||0)>0?'+':''}{((bucket.avgReturn||0)*100).toFixed(2)}%
                                </span>
                              </td>
                              <td className="py-3 px-3">
                                <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
                                  <div className={`h-full ${(bucket.hitRate||0)>0.55?'bg-emerald-500':(bucket.hitRate||0)>0.50?'bg-amber-500':'bg-gray-400'}`}
                                    style={{width:`${(bucket.hitRate||0)*100}%`}} />
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
            
            {/* Per-Horizon */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Детализация по горизонтам (Per-Horizon Breakdown)</CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="24H" className="w-full">
                  <TabsList className="bg-gray-100">
                    <TabsTrigger value="24H" className="data-[state=active]:bg-white">24H</TabsTrigger>
                    <TabsTrigger value="7D" className="data-[state=active]:bg-white">7D</TabsTrigger>
                    <TabsTrigger value="30D" className="data-[state=active]:bg-white">30D</TabsTrigger>
                  </TabsList>
                  {byHorizon.map(s => (
                    <TabsContent key={s.horizon} value={s.horizon} className="mt-4">
                      {s.sampleCount===0 ? (
                        <div className="text-center text-gray-500 py-8">Нет данных для {s.horizon}</div>
                      ) : (
                        <div className="grid grid-cols-3 gap-4">
                          {[
                            {label:'Выборка',value:s.sampleCount},
                            {label:'Hit Rate',value:`${((s.hitRate||0)*100).toFixed(1)}%`,color:s.hitRate>0.55?'text-emerald-600':''},
                            {label:'Корреляция',value:(s.correlation != null ? s.correlation.toFixed(3) : '—'),color:s.correlation>0.10?'text-emerald-600':s.correlation>0.05?'text-amber-600':''},
                            {label:'Ср. форвардная доходность',value:`${(s.avgForwardReturn||0)>0?'+':''}${((s.avgForwardReturn||0)*100).toFixed(2)}%`,color:s.avgForwardReturn>0?'text-emerald-600':s.avgForwardReturn<0?'text-red-600':''},
                            {label:'Ср. доход LONG',value:`${(s.avgReturnIfLong||0)>0?'+':''}${((s.avgReturnIfLong||0)*100).toFixed(2)}%`,color:s.avgReturnIfLong>0?'text-emerald-600':s.avgReturnIfLong<0?'text-red-600':''},
                            {label:'Ср. доход SHORT',value:`${(s.avgReturnIfShort||0)>0?'+':''}${((s.avgReturnIfShort||0)*100).toFixed(2)}%`,color:s.avgReturnIfShort<0?'text-emerald-600':s.avgReturnIfShort>0?'text-red-600':''},
                          ].map(({label,value,color}) => (
                            <div key={label} className="bg-gray-50 rounded-lg p-4">
                              <div className="text-sm text-gray-500 mb-1">{label}</div>
                              <div className={`text-2xl font-semibold ${color||'text-gray-800'}`}>{value}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </TabsContent>
                  ))}
                </Tabs>
              </CardContent>
            </Card>
          </TabsContent>

        </Tabs>
      </div>
    </AdminLayout>
  );
}
