import useWsChannel from "@/ws/useWsChannel";
import { useOrders } from "@/hooks/execution/useOrders";
import { useFills } from "@/hooks/execution/useFills";

import EventTape from "@/components/terminal/execution/EventTape";
import OrdersTable from "@/components/terminal/execution/OrdersTable";
import FillsTable from "@/components/terminal/execution/FillsTable";
import ExecutionStatsBar from "@/components/terminal/execution/ExecutionStatsBar";

export default function ExecutionFeedWorkspace() {
  // WS-1: execution.feed via WebSocket (primary)
  const { messages: wsEvents, isConnected } = useWsChannel("execution.feed");
  
  // Polling fallback for stats (orders, fills)
  const { orders } = useOrders();
  const { fills } = useFills();

  return (
    <div className="p-6 space-y-6" data-testid="execution-feed-workspace">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white">Execution Feed</h2>
        <p className="text-sm text-gray-400 mt-1">
          Real-time execution pipeline monitoring
        </p>
      </div>

      {/* Stats Bar */}
      <ExecutionStatsBar events={wsEvents} orders={orders} fills={fills} />

      {/* Event Tape (WS-powered) */}
      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12">
          <EventTape events={wsEvents} isConnected={isConnected} />
        </div>

        {/* Orders and Fills Tables (polling) */}
        <div className="col-span-6">
          <OrdersTable orders={orders} />
        </div>

        <div className="col-span-6">
          <FillsTable fills={fills} />
        </div>
      </div>
    </div>
  );
}
