/**
 * TAPredictionTab.jsx
 * ====================
 * Thin wrapper around the shared <PredictionPage /> UI that points at the
 * TA prediction backend (/api/prediction/ta/*) instead of the exchange one.
 *
 * Reuses ALL UI logic (chart, right panel, rolling forecasts, horizon switcher).
 * Only swaps the data source.
 */

import React from 'react';
import { useMarket } from '../../../store/marketStore';
import PredictionPage from '../../../pages/PredictionPage';

const TAPredictionTab = () => {
  const market = useMarket();
  const symbol = market?.symbol || 'BTCUSDT';
  const timeframe = market?.timeframe || '4H';

  // Strip USDT/USD to get plain asset code for the API
  const asset = symbol.replace(/USDT$/i, '').replace(/USD$/i, '').toUpperCase();
  const tf = String(timeframe).toUpperCase();

  return (
    <PredictionPage
      apiPath="ta"
      asset={asset}
      assetLabel={asset}
      extraQuery={`&timeframe=${tf}`}
      title={`${asset} TA Prediction · ${tf}`}
    />
  );
};

export default TAPredictionTab;
