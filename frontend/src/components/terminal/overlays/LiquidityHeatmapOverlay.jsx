export default function LiquidityHeatmapOverlay({ chart, heatmap }) {
  if (!chart || !heatmap?.buckets) return null;

  const bids = heatmap.buckets.bids || [];
  const asks = heatmap.buckets.asks || [];
  
  let priceScale;
  try {
    priceScale = chart.priceScale("right");
    if (!priceScale || typeof priceScale.priceToCoordinate !== "function") {
      return null;
    }
  } catch (e) {
    return null;
  }

  const renderRow = (row, color) => {
    const y = priceScale.priceToCoordinate(Number(row.price));
    if (y == null) return null;

    const intensity = Number(row.intensity || 0);
    const opacity = Math.max(0.08, Math.min(0.45, intensity * 0.45));

    return (
      <div
        key={`${color}-${row.price}`}
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: y - 3,
          height: 6,
          background:
            color === "bid"
              ? `rgba(0, 200, 83, ${opacity})`
              : `rgba(255, 77, 79, ${opacity})`,
          borderTop:
            color === "bid"
              ? `1px solid rgba(0, 200, 83, ${Math.min(opacity + 0.1, 0.55)})`
              : `1px solid rgba(255, 77, 79, ${Math.min(opacity + 0.1, 0.55)})`,
          borderBottom:
            color === "bid"
              ? `1px solid rgba(0, 200, 83, ${Math.min(opacity + 0.1, 0.55)})`
              : `1px solid rgba(255, 77, 79, ${Math.min(opacity + 0.1, 0.55)})`,
        }}
      />
    );
  };

  return (
    <div className="absolute inset-0 pointer-events-none">
      {bids.map((row) => renderRow(row, "bid"))}
      {asks.map((row) => renderRow(row, "ask"))}
    </div>
  );
}
