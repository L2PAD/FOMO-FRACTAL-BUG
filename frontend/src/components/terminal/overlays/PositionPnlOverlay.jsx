import { useMemo } from "react";

function formatDuration(ts) {
  if (!ts) return "";
  const opened = new Date(ts).getTime();
  const now = Date.now();
  const ms = Math.max(0, now - opened);
  const m = Math.floor(ms / 60000);
  const h = Math.floor(m / 60);
  const mm = m % 60;
  return h > 0 ? `${h}h ${mm}m` : `${mm}m`;
}

export default function PositionPnlOverlay({ chart, position, currentPrice }) {
  if (!chart || !position || position.status !== "OPEN") return null;

  const entry = Number(position.entry_price || 0);
  const stop = Number(position.stop_loss || 0);
  const target = Number(position.take_profit || 0);
  const mark = Number(currentPrice || position.mark_price || 0);

  if (!entry || !mark) return null;

  let priceScale;
  try {
    priceScale = chart.priceScale("right");
    if (!priceScale || typeof priceScale.priceToCoordinate !== "function") {
      return null;
    }
  } catch (e) {
    return null;
  }

  const entryY = priceScale.priceToCoordinate(entry);
  const markY = priceScale.priceToCoordinate(mark);

  if (entryY == null || markY == null) return null;

  const isLong = String(position.side).toUpperCase() === "LONG";
  const pnlPositive = isLong ? mark >= entry : mark <= entry;

  const top = Math.min(entryY, markY);
  const height = Math.max(2, Math.abs(markY - entryY));

  const unrealized = Number(position.unrealized_pnl || 0);
  const unrealizedPct = Number(position.unrealized_pnl_pct || 0);

  const tpProgress =
    target && entry !== target
      ? Math.min(100, Math.max(0, ((mark - entry) / (target - entry)) * 100))
      : null;

  const slProgress =
    stop && entry !== stop
      ? Math.min(100, Math.max(0, ((entry - mark) / (entry - stop)) * 100))
      : null;

  const duration = formatDuration(position.opened_at);

  return (
    <div className="absolute inset-0 pointer-events-none">
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top,
          height,
          background: pnlPositive
            ? "rgba(0, 200, 83, 0.10)"
            : "rgba(255, 77, 79, 0.10)",
          borderTop: pnlPositive
            ? "1px solid rgba(0, 200, 83, 0.35)"
            : "1px solid rgba(255, 77, 79, 0.35)",
          borderBottom: pnlPositive
            ? "1px solid rgba(0, 200, 83, 0.35)"
            : "1px solid rgba(255, 77, 79, 0.35)",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: top + 8,
          right: 12,
          width: 230,
          background: "rgba(17,17,17,0.94)",
          color: "#fff",
          padding: "10px 12px",
          borderRadius: 8,
          fontSize: 12,
        }}
      >
        <div style={{ fontWeight: 700, marginBottom: 6 }}>
          POSITION · {position.side}
        </div>

        <div>
          Entry:{" "}
          <span style={{ color: "#2962FF" }}>{entry.toFixed(2)}</span>
        </div>

        <div>
          Mark:{" "}
          <span style={{ color: pnlPositive ? "#00C853" : "#FF4D4F" }}>
            {mark.toFixed(2)}
          </span>
        </div>

        {stop ? (
          <div>
            Stop:{" "}
            <span style={{ color: "#FF4D4F" }}>{stop.toFixed(2)}</span>
          </div>
        ) : null}

        {target ? (
          <div>
            Target:{" "}
            <span style={{ color: "#00C853" }}>{target.toFixed(2)}</span>
          </div>
        ) : null}

        <div style={{ marginTop: 8 }}>
          PnL:{" "}
          <span
            style={{
              color: pnlPositive ? "#00C853" : "#FF4D4F",
              fontWeight: 700,
            }}
          >
            {unrealized >= 0 ? "+" : ""}
            {unrealized.toFixed(2)} USD{" "}
            ({unrealizedPct >= 0 ? "+" : ""}
            {unrealizedPct.toFixed(2)}%)
          </span>
        </div>

        <div style={{ marginTop: 6, opacity: 0.85 }}>
          Status: OPEN {duration ? `• ${duration}` : ""}
        </div>

        {tpProgress != null && (
          <div style={{ marginTop: 6, opacity: 0.8 }}>
            To TP: {tpProgress.toFixed(0)}%
          </div>
        )}

        {slProgress != null && (
          <div style={{ opacity: 0.8 }}>
            To SL: {slProgress.toFixed(0)}%
          </div>
        )}
      </div>
    </div>
  );
}
