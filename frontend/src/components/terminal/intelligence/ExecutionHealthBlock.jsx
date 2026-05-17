import React, { useState, useEffect } from 'react';
import { Activity, AlertTriangle, XCircle, Clock, Zap, TrendingUp } from 'lucide-react';

const ExecutionHealthBlock = () => {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/execution-reality/execution-health`);
        if (response.ok) {
          const data = await response.json();
          setHealth(data);
        }
      } catch (error) {
        console.error('Failed to fetch execution health:', error);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchHealth();

    // Poll every 2 seconds
    const interval = setInterval(fetchHealth, 2000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="execution-health-block">
        <div className="text-sm text-gray-500">Loading execution health...</div>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="execution-health-block">
        <div className="text-sm text-gray-500">Execution health unavailable</div>
      </div>
    );
  }

  const status = health.status || "HEALTHY";
  const latency = health.latency || {};
  const queue = health.queue || {};
  const execution = health.execution || {};
  const circuitBreaker = health.circuit_breaker || {};  // P1-B
  const rateLimiter = health.rate_limiter || {};        // P1-B

  // Determine visual style based on status
  let statusColor = 'text-green-400';
  let borderColor = 'border-green-800';
  let bgAccent = 'bg-green-950/20';
  let StatusIcon = Activity;
  let pulseClass = '';

  if (status === "CRITICAL") {
    statusColor = 'text-red-500';
    borderColor = 'border-red-800';
    bgAccent = 'bg-red-950/30';
    StatusIcon = XCircle;
    pulseClass = 'animate-pulse';
  } else if (status === "WARNING") {
    statusColor = 'text-amber-500';
    borderColor = 'border-amber-800';
    bgAccent = 'bg-amber-950/20';
    StatusIcon = AlertTriangle;
  }

  // Latency color logic
  const getLatencyColor = (ms, threshold = 200) => {
    if (ms < threshold) return 'text-green-400';
    if (ms < threshold * 2) return 'text-amber-400';
    return 'text-red-400';
  };

  return (
    <div 
      className={`bg-[#0A0E13] border ${borderColor} rounded-lg p-4`}
      data-testid="execution-health-block"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-gray-300">Execution Health (P1-B)</span>
        </div>
        <div className={`flex items-center gap-1.5 text-sm font-bold ${statusColor} ${pulseClass}`}>
          <StatusIcon className="w-4 h-4" />
          {status}
        </div>
      </div>

      {/* Latency Metrics */}
      <div className="mb-3">
        <div className="text-xs text-gray-500 mb-2 flex items-center gap-1">
          <Clock className="w-3 h-3" />
          Latency (ms)
        </div>
        <div className="grid grid-cols-3 gap-2">
          {/* Submit → ACK p50 */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">ACK p50</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.p50_submit_to_ack_ms || 0, 150)}`}
              data-testid="ack-p50"
            >
              {(latency.p50_submit_to_ack_ms || 0).toFixed(0)}
            </div>
          </div>

          {/* Submit → ACK p95 */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">ACK p95</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.p95_submit_to_ack_ms || 0, 300)}`}
              data-testid="ack-p95"
            >
              {(latency.p95_submit_to_ack_ms || 0).toFixed(0)}
            </div>
          </div>

          {/* Submit → ACK avg */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">ACK avg</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.avg_submit_to_ack_ms || 0, 200)}`}
              data-testid="ack-avg"
            >
              {(latency.avg_submit_to_ack_ms || 0).toFixed(0)}
            </div>
          </div>

          {/* Submit → Fill p50 */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">Fill p50</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.p50_submit_to_fill_ms || 0, 500)}`}
              data-testid="fill-p50"
            >
              {(latency.p50_submit_to_fill_ms || 0).toFixed(0)}
            </div>
          </div>

          {/* Submit → Fill p95 */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">Fill p95</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.p95_submit_to_fill_ms || 0, 1000)}`}
              data-testid="fill-p95"
            >
              {(latency.p95_submit_to_fill_ms || 0).toFixed(0)}
            </div>
          </div>

          {/* Submit → Fill avg */}
          <div className={`rounded p-2 ${bgAccent}`}>
            <div className="text-xs text-gray-600 mb-0.5">Fill avg</div>
            <div 
              className={`text-sm font-semibold ${getLatencyColor(latency.avg_submit_to_fill_ms || 0, 600)}`}
              data-testid="fill-avg"
            >
              {(latency.avg_submit_to_fill_ms || 0).toFixed(0)}
            </div>
          </div>
        </div>
      </div>

      {/* Queue & Execution Metrics */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Queue Depth */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Queue Depth</div>
          <div 
            className={`text-base font-semibold ${
              (queue.queue_depth || 0) > 50 ? 'text-red-400' :
              (queue.queue_depth || 0) > 20 ? 'text-amber-400' : 'text-green-400'
            }`}
            data-testid="queue-depth"
          >
            {queue.queue_depth || 0}
          </div>
        </div>

        {/* Inflight Orders */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">
            <Zap className="w-3 h-3 inline mr-1" />
            Inflight
          </div>
          <div 
            className="text-base font-semibold text-cyan-400"
            data-testid="inflight-orders"
          >
            {queue.inflight_orders || 0}
          </div>
        </div>

        {/* Reject Rate */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Reject Rate</div>
          <div 
            className={`text-base font-semibold ${
              (execution.reject_rate || 0) > 0.1 ? 'text-red-400' :
              (execution.reject_rate || 0) > 0.05 ? 'text-amber-400' : 'text-green-400'
            }`}
            data-testid="reject-rate"
          >
            {((execution.reject_rate || 0) * 100).toFixed(1)}%
          </div>
        </div>

        {/* Timeout Rate */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">
            <Clock className="w-3 h-3 inline mr-1" />
            Timeout Rate
          </div>
          <div 
            className={`text-base font-semibold ${
              (execution.timeout_rate || 0) > 0.05 ? 'text-red-400' :
              (execution.timeout_rate || 0) > 0.02 ? 'text-amber-400' : 'text-green-400'
            }`}
            data-testid="timeout-rate"
          >
            {((execution.timeout_rate || 0) * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Execution Counters (compact) */}
      <div className="grid grid-cols-5 gap-1.5 text-xs">
        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Submits</div>
          <div className="text-gray-300 font-medium" data-testid="total-submits">
            {execution.total_submits || 0}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">ACKs</div>
          <div className="text-green-400 font-medium" data-testid="total-acks">
            {execution.total_acks || 0}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Fills</div>
          <div className="text-cyan-400 font-medium" data-testid="total-fills">
            {execution.total_fills || 0}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Rejects</div>
          <div className="text-red-400 font-medium" data-testid="total-rejects">
            {execution.total_rejects || 0}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Timeouts</div>
          <div className="text-amber-400 font-medium" data-testid="total-timeouts">
            {execution.total_timeouts || 0}
          </div>
        </div>
      </div>

      {/* P1-B: Circuit Breaker & Rate Limiter Status */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
        {/* Circuit Breaker */}
        <div className={`rounded p-2 ${
          circuitBreaker.state === 'OPEN' ? 'bg-red-950/40 border border-red-800' :
          circuitBreaker.state === 'HALF_OPEN' ? 'bg-amber-950/40 border border-amber-800' :
          'bg-gray-900/50'
        }`}>
          <div className="text-gray-500 mb-1 flex items-center gap-1">
            <Zap className="w-3 h-3" />
            Circuit Breaker
          </div>
          <div className={`text-sm font-semibold ${
            circuitBreaker.state === 'CLOSED' ? 'text-green-400' :
            circuitBreaker.state === 'HALF_OPEN' ? 'text-amber-400' :
            'text-red-400'
          }`} data-testid="circuit-breaker-state">
            {circuitBreaker.state || 'CLOSED'}
          </div>
          {circuitBreaker.state === 'OPEN' && (
            <div className="text-xs text-gray-500 mt-1">
              Failures: {circuitBreaker.consecutive_failures || 0}
            </div>
          )}
        </div>

        {/* Rate Limiter */}
        <div className="bg-gray-900/50 rounded p-2">
          <div className="text-gray-500 mb-1">Rate Limit Budget</div>
          <div 
            className={`text-sm font-semibold ${
              (rateLimiter.utilization || 0) > 0.8 ? 'text-red-400' :
              (rateLimiter.utilization || 0) > 0.5 ? 'text-amber-400' :
              'text-green-400'
            }`}
            data-testid="rate-limit-tokens"
          >
            {Math.round(rateLimiter.available_tokens || 0)}/{rateLimiter.capacity || 1200}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {((1 - (rateLimiter.utilization || 0)) * 100).toFixed(0)}% available
          </div>
        </div>
      </div>

      {/* Critical Warning */}
      {status === "CRITICAL" && (
        <div className="mt-3 p-2 bg-red-950/40 border border-red-800 rounded text-xs">
          <div className="flex items-center gap-1.5 text-red-400 font-medium mb-1">
            <XCircle className="w-3 h-3" />
            Critical Execution Health
          </div>
          <div className="text-gray-400">
            {circuitBreaker.state === 'OPEN' && "⚠️ Circuit breaker OPEN - all orders blocked. "}
            {execution.reject_rate > 0.3 && "High reject rate detected. "}
            {execution.timeout_rate > 0.2 && "High timeout rate detected. "}
            {queue.queue_depth > 100 && "Queue depth critical. "}
            Check system logs immediately.
          </div>
        </div>
      )}

      {/* Warning */}
      {status === "WARNING" && (
        <div className="mt-3 p-2 bg-amber-950/40 border border-amber-800 rounded text-xs">
          <div className="flex items-center gap-1.5 text-amber-400 font-medium">
            <AlertTriangle className="w-3 h-3" />
            Degraded execution performance
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutionHealthBlock;
