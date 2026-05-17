// System Workspace — Operator Console

import React, { useState, useEffect } from 'react';
import TradingControlBar from '../system/TradingControlBar';
import AutoSafetyPanel from '../system/AutoSafetyPanel';
import SystemStatePanel from '../system/SystemStatePanel';
import RuntimeStatusPanel from '../system/RuntimeStatusPanel';
import ExchangeStatusPanel from '../system/ExchangeStatusPanel';
import RiskHealthPanel from '../system/RiskHealthPanel';
import SessionMetricsPanel from '../system/SessionMetricsPanel';
import AdaptationRecommendationsPanel from '../system/AdaptationRecommendationsPanel';

const backendUrl = process.env.REACT_APP_BACKEND_URL;

export default function SystemWorkspace() {
  const [systemState, setSystemState] = useState(null);
  const [exchangeStatus, setExchangeStatus] = useState(null);
  const [exchangeHealth, setExchangeHealth] = useState(null);
  const [riskHealth, setRiskHealth] = useState(null);
  const [sessionStats, setSessionStats] = useState(null);
  
  // Fetch all data
  const fetchData = async () => {
    try {
      const [system, exchange, health, risk, session] = await Promise.all([
        fetch(`${backendUrl}/api/system/state`).then(r => r.json()),
        fetch(`${backendUrl}/api/exchange/status`).then(r => r.json()),
        fetch(`${backendUrl}/api/exchange/health`).then(r => r.json()),
        fetch(`${backendUrl}/api/strategy/risk/health`).then(r => r.json()),
        fetch(`${backendUrl}/api/portfolio/session-stats`).then(r => r.json())
      ]);
      
      if (system.ok) setSystemState(system);
      if (exchange.ok) setExchangeStatus(exchange);
      if (health.ok) setExchangeHealth(health);
      if (risk.ok) setRiskHealth(risk);
      if (session.ok) setSessionStats(session);
    } catch (error) {
      console.error('[SystemWorkspace] Fetch failed:', error);
    }
  };
  
  useEffect(() => {
    fetchData();
    
    // Poll every 3 seconds
    const interval = setInterval(fetchData, 3000);
    
    return () => clearInterval(interval);
  }, []);
  
  return (
    <div className="h-full bg-white overflow-y-auto" data-testid="system-workspace" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      {/* Top: Control Bar */}
      <div className="border-b border-neutral-200 bg-white">
        <TradingControlBar 
          systemState={systemState} 
          onUpdate={fetchData}
        />
      </div>
      
      {/* Main Content */}
      <div className="p-4">
        {/* Sprint 7: ADAPTATION RECOMMENDATIONS — TOP PRIORITY */}
        <div className="mb-4">
          <AdaptationRecommendationsPanel />
        </div>
        
        {/* AUTO SAFETY — P0 BLOCK */}
        <div className="mb-4">
          <AutoSafetyPanel />
        </div>
        
        {/* Grid Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Row 1 */}
          <RuntimeStatusPanel />
          <SystemStatePanel systemState={systemState} />
          
          {/* Row 2 */}
          <ExchangeStatusPanel 
            exchangeStatus={exchangeStatus} 
            exchangeHealth={exchangeHealth}
          />
          <RiskHealthPanel riskHealth={riskHealth} />
          
          {/* Row 3 */}
          <SessionMetricsPanel sessionStats={sessionStats} />
        </div>
      </div>
    </div>
  );
}
