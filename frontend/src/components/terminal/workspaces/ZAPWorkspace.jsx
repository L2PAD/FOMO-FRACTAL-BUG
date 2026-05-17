import ExecutionFeedPanel from "../zap/ExecutionFeedPanel";
import PendingDecisionsPanel from "../zap/PendingDecisionsPanel";
import OrdersPanel from "../zap/OrdersPanel";
import FillsPanel from "../zap/FillsPanel";
import RejectionsPanel from "../zap/RejectionsPanel";
import SyncHealthPanel from "../zap/SyncHealthPanel";

export default function ZAPWorkspace() {
  return (
    <div className="max-w-[1440px] mx-auto px-8 py-6 space-y-6" style={{ fontFamily: 'Gilroy, sans-serif' }}>
      <ExecutionFeedPanel />
      
      <PendingDecisionsPanel />

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-6">
          <OrdersPanel />
        </div>
        <div className="col-span-6">
          <FillsPanel />
        </div>

        <div className="col-span-6">
          <RejectionsPanel />
        </div>
        <div className="col-span-6">
          <SyncHealthPanel />
        </div>
      </div>
    </div>
  );
}
