import { useState } from "react";
import { Button } from "@/components/ui/button";
import { CheckCircle, XCircle, Clock, TrendingUp, TrendingDown } from "lucide-react";
import { usePendingDecisions } from "../../../hooks/runtime/usePendingDecisions";
import { useRuntimeActions } from "../../../hooks/runtime/useRuntimeActions";

export default function PendingDecisionsPanel() {
  const { data, error, loading, refetch } = usePendingDecisions();
  const actions = useRuntimeActions();
  const [processingId, setProcessingId] = useState(null);

  const handleApprove = async (decisionId) => {
    setProcessingId(decisionId);
    await actions.approveDecision(decisionId);
    setProcessingId(null);
    refetch();
  };

  const handleReject = async (decisionId) => {
    setProcessingId(decisionId);
    await actions.rejectDecision(decisionId, "Manual rejection");
    setProcessingId(null);
    refetch();
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "—";
    const date = new Date(ts * 1000);
    return date.toLocaleTimeString("en-US", { hour12: false });
  };

  const formatExpiry = (ts) => {
    if (!ts) return "—";
    const now = Math.floor(Date.now() / 1000);
    const delta = ts - now;
    if (delta <= 0) return "EXPIRED";
    const mins = Math.floor(delta / 60);
    const secs = delta % 60;
    return `${mins}m ${secs}s`;
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4" style={{ fontFamily: "Gilroy, sans-serif" }}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-sm font-medium text-gray-900">Pending Decisions</div>
          <div className="text-xs text-gray-500">SEMI-AUTO approval queue</div>
        </div>
        <div className="flex items-center gap-2">
          {data.length > 0 && (
            <div className="px-2 py-1 bg-orange-50 border border-orange-200 rounded-lg">
              <span className="text-xs font-bold text-orange-700">{data.length} WAITING</span>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="text-sm text-red-600 mb-2">{error}</div>
      )}

      {loading && data.length === 0 && (
        <div className="text-sm text-gray-500">Loading pending decisions...</div>
      )}

      <div className="space-y-3">
        {data.length === 0 && !loading && (
          <div className="text-center py-8 text-sm text-gray-500">
            No pending decisions
          </div>
        )}

        {data.map((decision) => (
          <div
            key={decision.decision_id}
            className="border border-gray-200 rounded-lg p-3 hover:border-blue-300 transition-colors"
            data-testid={`pending-decision-${decision.decision_id}`}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                {decision.side === "BUY" ? (
                  <TrendingUp className="w-4 h-4 text-green-600" />
                ) : (
                  <TrendingDown className="w-4 h-4 text-red-600" />
                )}
                <div>
                  <div className="text-sm font-bold text-gray-900">
                    {decision.symbol} · {decision.side}
                  </div>
                  <div className="text-xs text-gray-500">
                    {decision.strategy || "—"} · Confidence: {(decision.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1.5 px-2 py-1 bg-orange-50 border border-orange-200 rounded">
                <Clock className="w-3 h-3 text-orange-600" />
                <span className="text-xs font-bold text-orange-700">WAITING APPROVAL</span>
              </div>
            </div>

            {/* Details */}
            <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
              <div>
                <span className="text-gray-500">Entry:</span>{" "}
                <span className="font-mono text-gray-900">${decision.entry_price?.toLocaleString() || "—"}</span>
              </div>
              <div>
                <span className="text-gray-500">Size:</span>{" "}
                <span className="font-mono text-gray-900">${decision.size_usd || 500}</span>
              </div>
              <div>
                <span className="text-gray-500">Stop:</span>{" "}
                <span className="font-mono text-gray-900">${decision.stop_price?.toLocaleString() || "—"}</span>
              </div>
              <div>
                <span className="text-gray-500">Target:</span>{" "}
                <span className="font-mono text-gray-900">${decision.target_price?.toLocaleString() || "—"}</span>
              </div>
            </div>

            {decision.thesis && (
              <div className="mb-3 text-xs text-gray-600 italic">
                "{decision.thesis}"
              </div>
            )}

            {/* Footer */}
            <div className="flex items-center justify-between pt-2 border-t border-gray-100">
              <div className="text-xs text-gray-500">
                Created: {formatTimestamp(decision.created_at)} · Expires: {formatExpiry(decision.expires_at)}
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={() => handleReject(decision.decision_id)}
                  disabled={processingId === decision.decision_id || actions.loading}
                  className="h-7 px-3 text-xs font-bold bg-red-600 hover:bg-red-700 text-white"
                  data-testid={`reject-decision-${decision.decision_id}`}
                >
                  <XCircle className="w-3 h-3 mr-1" />
                  REJECT
                </Button>
                <Button
                  size="sm"
                  onClick={() => handleApprove(decision.decision_id)}
                  disabled={processingId === decision.decision_id || actions.loading}
                  className="h-7 px-3 text-xs font-bold bg-green-600 hover:bg-green-700 text-white"
                  data-testid={`approve-decision-${decision.decision_id}`}
                >
                  <CheckCircle className="w-3 h-3 mr-1" />
                  APPROVE
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
