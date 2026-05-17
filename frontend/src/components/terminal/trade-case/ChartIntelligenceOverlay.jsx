import { useMemo } from 'react';

/**
 * Chart Intelligence Overlay - renders system logic on chart
 * Markers: Entry, Add, Exit, Partial Exit
 * Zones: Position zone, Stop, Target
 */
export default function ChartIntelligenceOverlay({ caseData, chart, currentPrice }) {
  // Calculate coordinates for price levels
  const getYCoordinate = (price) => {
    if (!chart || !price) return null;
    try {
      const priceScale = chart.priceScale('right');
      return priceScale.priceToCoordinate(price);
    } catch (e) {
      return null;
    }
  };

  const getXCoordinate = (time) => {
    if (!chart || !time) return null;
    try {
      return chart.timeScale().timeToCoordinate(time);
    } catch (e) {
      return null;
    }
  };

  // Calculate position zone
  const positionZone = useMemo(() => {
    if (!caseData?.avg_entry || !currentPrice) return null;
    
    const entryY = getYCoordinate(caseData.avg_entry);
    const currentY = getYCoordinate(currentPrice);
    
    if (!entryY || !currentY) return null;

    const isLong = caseData.direction === 'LONG';
    const top = Math.min(entryY, currentY);
    const height = Math.abs(entryY - currentY);

    return {
      top,
      height,
      color: isLong ? 'rgba(34, 197, 94, 0.08)' : 'rgba(239, 68, 68, 0.08)',
      borderColor: isLong ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'
    };
  }, [caseData, currentPrice, chart]);

  // Render markers
  const markers = useMemo(() => {
    if (!caseData) return [];

    const allMarkers = [];

    // Entry markers
    if (caseData.entries) {
      caseData.entries.forEach((entry, index) => {
        const x = getXCoordinate(entry.time);
        const y = getYCoordinate(entry.price);
        if (x !== null && y !== null) {
          allMarkers.push({
            type: 'entry',
            x,
            y,
            data: entry,
            index
          });
        }
      });
    }

    // Add markers
    if (caseData.adds) {
      caseData.adds.forEach((add, index) => {
        const x = getXCoordinate(add.time);
        const y = getYCoordinate(add.price);
        if (x !== null && y !== null) {
          allMarkers.push({
            type: 'add',
            x,
            y,
            data: add,
            index
          });
        }
      });
    }

    // Partial exit markers
    if (caseData.partial_exits) {
      caseData.partial_exits.forEach((exit, index) => {
        const x = getXCoordinate(exit.time);
        const y = getYCoordinate(exit.price);
        if (x !== null && y !== null) {
          allMarkers.push({
            type: 'partial_exit',
            x,
            y,
            data: exit,
            index
          });
        }
      });
    }

    // Full exit markers
    if (caseData.exits) {
      caseData.exits.forEach((exit, index) => {
        const x = getXCoordinate(exit.time);
        const y = getYCoordinate(exit.price);
        if (x !== null && y !== null) {
          allMarkers.push({
            type: 'exit',
            x,
            y,
            data: exit,
            index
          });
        }
      });
    }

    return allMarkers;
  }, [caseData, chart]);

  // Stop line
  const stopLine = useMemo(() => {
    if (!caseData?.stop) return null;
    const y = getYCoordinate(parseFloat(caseData.stop.replace(/,/g, '')));
    return y !== null ? { y, price: caseData.stop } : null;
  }, [caseData, chart]);

  // Target line
  const targetLine = useMemo(() => {
    if (!caseData?.target) return null;
    const y = getYCoordinate(caseData.target);
    return y !== null ? { y, price: caseData.target } : null;
  }, [caseData, chart]);

  if (!chart) return null;

  return (
    <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 5 }}>
      {/* Position Zone */}
      {positionZone && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 60,
            top: `${positionZone.top}px`,
            height: `${positionZone.height}px`,
            background: positionZone.color,
            borderTop: `1px dashed ${positionZone.borderColor}`,
            borderBottom: `1px dashed ${positionZone.borderColor}`
          }}
        />
      )}

      {/* Stop Line */}
      {stopLine && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 60,
            top: `${stopLine.y}px`,
            height: '1px',
            background: '#ef4444',
            borderTop: '2px solid #ef4444'
          }}
        >
          <div
            className="absolute right-0 top-0 transform -translate-y-1/2 px-2 py-0.5 bg-red-50 border border-red-300 rounded-lg text-xs font-bold text-red-700"
            style={{ pointerEvents: 'auto' }}
          >
            STOP {stopLine.price}
          </div>
        </div>
      )}

      {/* Target Line */}
      {targetLine && (
        <div
          style={{
            position: 'absolute',
            left: 0,
            right: 60,
            top: `${targetLine.y}px`,
            height: '1px',
            borderTop: '2px dashed #22c55e'
          }}
        >
          <div
            className="absolute right-0 top-0 transform -translate-y-1/2 px-2 py-0.5 bg-green-50 border border-green-300 rounded-lg text-xs font-bold text-green-700"
            style={{ pointerEvents: 'auto' }}
          >
            TARGET {targetLine.price}
          </div>
        </div>
      )}

      {/* Markers */}
      {markers.map((marker, index) => {
        let markerStyles = {};
        let label = '';
        let bgColor = '';
        let borderColor = '';

        switch (marker.type) {
          case 'entry':
            markerStyles = {
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              background: '#22c55e',
              border: '2px solid white',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            };
            label = 'ENTRY';
            bgColor = 'bg-green-50';
            borderColor = 'border-green-300';
            break;
          case 'add':
            markerStyles = {
              width: '10px',
              height: '10px',
              background: '#3b82f6',
              border: '2px solid white',
              borderRadius: '2px',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            };
            label = 'ADD';
            bgColor = 'bg-blue-50';
            borderColor = 'border-blue-300';
            break;
          case 'partial_exit':
            markerStyles = {
              width: '10px',
              height: '10px',
              background: '#f59e0b',
              border: '2px solid white',
              borderRadius: '50%',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            };
            label = 'PARTIAL';
            bgColor = 'bg-orange-50';
            borderColor = 'border-orange-300';
            break;
          case 'exit':
            markerStyles = {
              width: '12px',
              height: '12px',
              background: '#ef4444',
              border: '2px solid white',
              borderRadius: '50%',
              boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
            };
            label = 'EXIT';
            bgColor = 'bg-red-50';
            borderColor = 'border-red-300';
            break;
          default:
            break;
        }

        return (
          <div
            key={`${marker.type}-${index}`}
            className="group pointer-events-auto"
            style={{
              position: 'absolute',
              left: `${marker.x - 6}px`,
              top: `${marker.y - 6}px`
            }}
          >
            {/* Marker */}
            <div style={markerStyles} />
            
            {/* Tooltip on hover */}
            <div
              className={`absolute left-1/2 transform -translate-x-1/2 bottom-full mb-2 px-2 py-1 ${bgColor} border ${borderColor} rounded-lg text-xs font-bold whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none`}
            >
              {label}<br />
              {marker.data.price?.toLocaleString()}<br />
              {marker.data.size_pct && `${marker.data.size_pct}%`}
            </div>
          </div>
        );
      })}
    </div>
  );
}
