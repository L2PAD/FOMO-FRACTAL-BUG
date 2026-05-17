import React, { useState, useEffect } from 'react';
import { Layers, AlertTriangle, XCircle, Clock, Zap } from 'lucide-react';

const ExecutionQueueBlock = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/execution-reality/queue/metrics`);
        if (response.ok) {
          const data = await response.json();
          setMetrics(data);
        }
      } catch (error) {
        console.error('Failed to fetch queue metrics:', error);
      } finally {
        setLoading(false);
      }
    };

    // Initial fetch
    fetchMetrics();

    // Poll every 2 seconds
    const interval = setInterval(fetchMetrics, 2000);

    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="execution-queue-block">
        <div className="text-sm text-gray-500">Loading queue metrics...</div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="execution-queue-block">
        <div className="text-sm text-gray-500">Queue metrics unavailable</div>
      </div>
    );
  }

  // Determine status
  const queueDepth = metrics.queue_depth || 0;
  const dlqCount = metrics.dlq_count || 0;
  const retryCount = metrics.retry_count || 0;
  const processingCount = metrics.processing_count || 0;
  const workersActive = metrics.workers_active || 0;
  const workersTotal = metrics.workers_total || 0;
  const avgWaitMs = metrics.avg_wait_ms || 0;
  const avgProcessingMs = metrics.avg_processing_ms || 0;

  // Warning/Critical logic
  const isGrowing = queueDepth > 10; // Warning if queue depth > 10
  const hasDLQ = dlqCount > 0;       // Critical if DLQ has items

  let statusColor = 'text-green-400';
  let borderColor = 'border-green-800';
  let bgAccent = 'bg-green-950/20';
  let StatusIcon = Layers;
  let statusText = 'HEALTHY';
  let pulseClass = '';

  if (hasDLQ) {
    statusColor = 'text-red-500';
    borderColor = 'border-red-800';
    bgAccent = 'bg-red-950/30';
    StatusIcon = XCircle;
    statusText = 'CRITICAL';
    pulseClass = 'animate-pulse';
  } else if (isGrowing) {
    statusColor = 'text-amber-500';
    borderColor = 'border-amber-800';
    bgAccent = 'bg-amber-950/20';
    StatusIcon = AlertTriangle;
    statusText = 'WARNING';
  }

  return (
    <div 
      className={`bg-[#0A0E13] border ${borderColor} rounded-lg p-4`}
      data-testid="execution-queue-block"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-gray-300">Execution Queue (P1.1)</span>
        </div>
        <div className={`flex items-center gap-1.5 text-sm font-bold ${statusColor} ${pulseClass}`}>
          <StatusIcon className="w-4 h-4" />
          {statusText}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {/* Queue Depth */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Queued</div>
          <div className={`text-base font-semibold ${
            queueDepth > 10 ? 'text-amber-400' : 'text-green-400'
          }`} data-testid="queue-depth">
            {queueDepth}
          </div>
        </div>

        {/* Processing */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Processing</div>
          <div className="text-base font-semibold text-cyan-400" data-testid="processing-count">
            {processingCount}
          </div>
        </div>

        {/* Retries */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">
            <Clock className="w-3 h-3 inline mr-1" />
            Retries
          </div>
          <div className={`text-base font-semibold ${
            retryCount > 0 ? 'text-amber-400' : 'text-gray-500'
          }`} data-testid="retry-count">
            {retryCount}
          </div>
        </div>

        {/* DLQ */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">
            <XCircle className="w-3 h-3 inline mr-1" />
            DLQ
          </div>
          <div className={`text-base font-semibold ${
            dlqCount > 0 ? 'text-red-500 font-bold' : 'text-gray-500'
          }`} data-testid="dlq-count">
            {dlqCount}
          </div>
        </div>
      </div>

      {/* Workers & Latency */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Workers</div>
          <div className="text-gray-300 font-medium">
            <Zap className="w-3 h-3 inline mr-1 text-cyan-500" />
            {workersActive}/{workersTotal}
          </div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Avg Wait</div>
          <div className="text-gray-300 font-medium">{avgWaitMs.toFixed(0)}ms</div>
        </div>

        <div className="bg-gray-900/50 rounded p-1.5">
          <div className="text-gray-600 mb-0.5">Avg Proc</div>
          <div className="text-gray-300 font-medium">{avgProcessingMs.toFixed(0)}ms</div>
        </div>
      </div>

      {/* DLQ Warning */}
      {hasDLQ && (
        <div className="mt-3 p-2 bg-red-950/40 border border-red-800 rounded text-xs">
          <div className="flex items-center gap-1.5 text-red-400 font-medium mb-1">
            <XCircle className="w-3 h-3" />
            Dead Letter Queue Alert
          </div>
          <div className="text-gray-400">
            {dlqCount} order{dlqCount > 1 ? 's' : ''} failed after max retries. 
            <a 
              href={`${process.env.REACT_APP_BACKEND_URL}/api/execution-reality/queue/dlq`}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-1 text-red-300 underline hover:text-red-200"
            >
              View DLQ →
            </a>
          </div>
        </div>
      )}

      {/* Queue Growing Warning */}
      {isGrowing && !hasDLQ && (
        <div className="mt-3 p-2 bg-amber-950/40 border border-amber-800 rounded text-xs">
          <div className="flex items-center gap-1.5 text-amber-400 font-medium">
            <AlertTriangle className="w-3 h-3" />
            Queue depth growing ({queueDepth} items)
          </div>
        </div>
      )}
    </div>
  );
};

export default ExecutionQueueBlock;
