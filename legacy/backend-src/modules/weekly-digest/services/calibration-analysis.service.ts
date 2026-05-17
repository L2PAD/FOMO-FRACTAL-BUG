/**
 * Calibration Analysis
 *
 * Tracks overconfidence, underconfidence, calibration error, and confidence drift.
 */

import type { CalibrationAnalysis } from '../types/digest.types.js';

interface ReviewData {
  calibration: {
    calibrationQuality?: string;
    errorScore?: number;
    overconfidenceScore?: number;
  };
  traces: { confidence: number }[];
}

class CalibrationAnalysisService {
  analyze(reviews: ReviewData[], prevAvgConfidence?: number): CalibrationAnalysis {
    let overconfident = 0, underconfident = 0, wellCalibrated = 0;
    let errorSum = 0;
    let confSum = 0;

    for (const r of reviews) {
      const cal = r.calibration;
      if (!cal) { wellCalibrated++; continue; }

      const quality = cal.calibrationQuality || 'OK';
      if (quality === 'GOOD' || quality === 'EXCELLENT') wellCalibrated++;
      else if ((cal.overconfidenceScore || 0) > 0.3) overconfident++;
      else underconfident++;

      errorSum += cal.errorScore || 0;
      confSum += r.traces?.[0]?.confidence || 0;
    }

    const total = reviews.length || 1;
    const avgConf = confSum / total;
    const prevConf = prevAvgConfidence || avgConf;
    const drift = avgConf - prevConf;

    return {
      overconfident,
      underconfident,
      wellCalibrated,
      avgCalibrationError: Math.round((errorSum / total) * 1000) / 1000,
      confidenceDrift: Math.round(drift * 1000) / 1000,
      driftDirection: drift > 0.02 ? 'UP' : drift < -0.02 ? 'DOWN' : 'STABLE',
    };
  }
}

export const calibrationAnalysisService = new CalibrationAnalysisService();
