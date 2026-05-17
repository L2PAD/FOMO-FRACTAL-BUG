/**
 * Structure Overlay - Market structure visualization
 * ===================================================
 * 
 * Renders structure elements:
 * - Swing labels (HH, HL, LH, LL)
 * - BOS/CHOCH markers
 * - Range box
 */

import { useEffect, useRef } from 'react';

const StructureOverlay = ({ chart, candleSeries, structure }) => {
  const markersRef = useRef([]);

  useEffect(() => {
    if (!chart || !candleSeries || !structure) return;

    const newMarkers = [];

    // Render swing labels (HH, HL, LH, LL)
    if (structure.swings && structure.swings.length > 0) {
      structure.swings.forEach(swing => {
        if (!swing.time || !swing.price || !swing.type) return;

        newMarkers.push({
          time: swing.time,
          position: swing.type.startsWith('H') ? 'aboveBar' : 'belowBar',
          color: swing.type.startsWith('H') ? '#10B981' : '#EF4444',
          shape: 'circle',
          text: swing.type,
          size: 0.5,
        });
      });
    }

    // Render BOS/CHOCH markers
    if (structure.events && structure.events.length > 0) {
      structure.events.forEach(event => {
        if (!event.time || !event.type) return;

        newMarkers.push({
          time: event.time,
          position: event.direction === 'UP' ? 'belowBar' : 'aboveBar',
          color: event.type === 'BOS' ? '#3B82F6' : '#F59E0B',
          shape: 'arrowUp',
          text: event.type,
          size: 1,
        });
      });
    }

    // Set markers on candle series
    if (newMarkers.length > 0) {
      candleSeries.setMarkers(newMarkers);
      markersRef.current = newMarkers;
    }

    // Render range box using price lines
    if (structure.range && structure.range.high && structure.range.low) {
      const rangeHighLine = candleSeries.createPriceLine({
        price: structure.range.high,
        color: '#6B7280',
        lineWidth: 1,
        lineStyle: 1, // dotted
        axisLabelVisible: true,
        title: 'Range High',
      });

      const rangeLowLine = candleSeries.createPriceLine({
        price: structure.range.low,
        color: '#6B7280',
        lineWidth: 1,
        lineStyle: 1,
        axisLabelVisible: true,
        title: 'Range Low',
      });

      // Cleanup
      return () => {
        try {
          candleSeries.setMarkers([]);
          candleSeries.removePriceLine(rangeHighLine);
          candleSeries.removePriceLine(rangeLowLine);
        } catch (e) {
          // Already cleaned up
        }
      };
    }

    // Cleanup markers only
    return () => {
      try {
        candleSeries.setMarkers([]);
      } catch (e) {
        // Already cleaned up
      }
    };
  }, [chart, candleSeries, structure]);

  return null; // Non-rendering component
};

export default StructureOverlay;
