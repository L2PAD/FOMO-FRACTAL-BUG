import { useMemo, useState, useEffect } from "react";

export default function HeroCommandBlock({ decision, explainability, heatmap }) {
  const regime = explainability?.regime || "chop";
  const hasDecision = !!decision;
  
  // Thinking animation
  const [thinkingDots, setThinkingDots] = useState(0);
  
  useEffect(() => {
    if (!hasDecision) {
      const interval = setInterval(() => {
        setThinkingDots(prev => (prev + 1) % 4);
      }, 500);
      return () => clearInterval(interval);
    }
  }, [hasDecision]);

  // Background colors based on state
  const bgColors = useMemo(() => {
    if (!hasDecision) {
      return {
        bg: "bg-neutral-50",
        border: "border-neutral-200",
        leftAccent: "border-l-neutral-400"
      };
    }

    const side = decision.side;
    if (side === "SHORT") {
      return {
        bg: "bg-red-50",
        border: "border-red-100",
        leftAccent: "border-l-red-500"
      };
    }

    return {
      bg: "bg-green-50",
      border: "border-green-100",
      leftAccent: "border-l-green-500"
    };
  }, [hasDecision, decision]);

  // Status pills
  const statusPills = useMemo(() => {
    if (!hasDecision) {
      return [
        { label: "WAIT", color: "bg-neutral-100 text-neutral-700 border-neutral-300" },
        { label: "LOW OPPORTUNITY", color: "bg-orange-100 text-orange-700 border-orange-300" },
        { label: "RISK NORMAL", color: "bg-green-100 text-green-700 border-green-300" }
      ];
    }

    const confidence = Number(decision.confidence || 0.5) * 100;
    const rr = Number(decision.risk_reward || 1.5);
    
    return [
      { label: `${confidence.toFixed(0)}%`, color: "bg-blue-100 text-blue-700 border-blue-300" },
      { label: `RR ${rr.toFixed(1)}`, color: "bg-blue-100 text-blue-700 border-blue-300" },
      { label: confidence > 65 ? "STRONG EDGE" : "MODERATE EDGE", color: "bg-neutral-100 text-neutral-700 border-neutral-300" },
      { label: "EXECUTION OK", color: "bg-green-100 text-green-700 border-green-300" }
    ];
  }, [hasDecision, decision]);

  // Main message
  const message = useMemo(() => {
    if (!hasDecision) {
      return {
        title: "NO EDGE",
        subtitle: "Market is not tradable",
        description: "No directional advantage. Wait for expansion."
      };
    }

    const side = decision.side;
    const symbol = decision.symbol.replace("USDT", "");
    const stop = Number(decision.stop || 0);
    
    return {
      title: `${side} ${symbol}`,
      subtitle: "Failed breakout → rejection likely",
      description: `Invalidation ${side === "SHORT" ? "above" : "below"} ${stop.toFixed(0)}k`
    };
  }, [hasDecision, decision]);

  return (
    <div 
      className={`${bgColors.bg} rounded-2xl p-6 border ${bgColors.border} border-l-4 ${bgColors.leftAccent} shadow-sm transition-all duration-150 ease-out hover:shadow-md hover:-translate-y-0.5`}
      data-testid="hero-command-block"
    >
      {/* Live indicator */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-neutral-500 font-medium uppercase tracking-wide">LIVE</span>
      </div>

      {/* Main Message */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-neutral-900 mb-2">
          {message.title}
        </h1>
        <p className="text-base font-medium text-neutral-700 mb-1.5">
          {message.subtitle}
        </p>
        <p className="text-sm text-neutral-600">
          {message.description}
        </p>
      </div>

      {/* Thinking State (только когда нет решения) */}
      {!hasDecision && (
        <div className="mb-4 p-3 bg-white/60 rounded-lg border border-neutral-200">
          <div className="text-xs font-semibold text-neutral-600 mb-2">
            System scanning{'.'.repeat(thinkingDots)}
          </div>
          <ul className="text-xs text-neutral-500 space-y-1">
            <li>• analyzing volatility</li>
            <li>• checking liquidity</li>
            <li>• waiting for signal</li>
          </ul>
        </div>
      )}

      {/* Status Pills */}
      <div className="flex gap-2.5 flex-wrap">
        {statusPills.map((pill, i) => (
          <div 
            key={i} 
            className={`px-4 py-2 rounded-lg border ${pill.color} font-semibold text-xs uppercase tracking-wide transition-all duration-150 hover:scale-105`}
            data-testid={`status-pill-${i}`}
          >
            {pill.label}
          </div>
        ))}
      </div>
    </div>
  );
}
