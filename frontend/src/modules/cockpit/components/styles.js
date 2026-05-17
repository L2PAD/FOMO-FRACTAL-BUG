import styled from 'styled-components';

// ============================================
// LIGHT THEME COCKPIT STYLES
// Based on design_reference FOMO Arena
// Colors: #ffffff, #f5f7fa, #eef1f5, #05A584
// ============================================

// Main Layout
export const CockpitContainer = styled.div`
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f5f7fa;
  color: #0f172a;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
`;

export const TopBar = styled.header`
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
`;

export const TopBarLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

export const TopBarCenter = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

export const TopBarRight = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
`;

export const Logo = styled.div`
  font-size: 18px;
  font-weight: 700;
  color: #05A584;
  display: flex;
  align-items: center;
  gap: 8px;
`;

export const ModeBadge = styled.span`
  padding: 6px 12px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  ${({ $mode }) => {
    switch ($mode) {
      case 'LIVE':
        return 'background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2);';
      case 'APPROVAL':
        return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.2);';
      case 'PAPER':
      default:
        return 'background: #e8f9f1; color: #05A584; border: 1px solid rgba(5, 165, 132, 0.2);';
    }
  }}
`;

export const HealthIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  
  ${({ $status }) => {
    switch ($status) {
      case 'CRITICAL':
        return 'background: rgba(239, 68, 68, 0.1); color: #ef4444;';
      case 'DEGRADED':
        return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b;';
      case 'HEALTHY':
      default:
        return 'background: #e8f9f1; color: #05A584;';
    }
  }}
  
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    animation: pulse 2s infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }
`;

export const MetricPill = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: #f5f7fa;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  font-size: 13px;
  
  .label {
    color: #738094;
  }
  
  .value {
    font-weight: 600;
    color: ${({ $positive }) => $positive ? '#05A584' : '#ef4444'};
  }
`;

export const KillSwitch = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  
  ${({ $active }) => $active
    ? 'background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);'
    : 'background: #ffffff; color: #738094; border: 1px solid #eef1f5;'
  }
  
  &:hover {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border-color: rgba(239, 68, 68, 0.3);
  }
`;

export const AlertsBadge = styled.button`
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: #ffffff;
  border: 1px solid #eef1f5;
  cursor: pointer;
  color: #738094;
  transition: all 0.15s;
  
  &:hover {
    border-color: #d1d5db;
  }
  
  .count {
    position: absolute;
    top: -4px;
    right: -4px;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    background: #ff5858;
    color: white;
    font-size: 10px;
    font-weight: 600;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
`;

// Main Content Area
export const MainContent = styled.div`
  display: flex;
  flex: 1;
  overflow: hidden;
`;

export const LeftNavigation = styled.nav`
  width: 220px;
  background: #ffffff;
  border-right: 1px solid #eef1f5;
  padding: 20px 0;
  flex-shrink: 0;
  overflow-y: auto;
`;

export const NavSection = styled.div`
  padding: 0 16px;
  margin-bottom: 24px;
  
  .section-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9CA3AF;
    padding: 0 12px;
    margin-bottom: 8px;
  }
`;

export const NavItem = styled.button`
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  text-align: left;
  
  ${({ $active }) => $active
    ? 'background: #e8f9f1; color: #05A584;'
    : 'background: transparent; color: #738094;'
  }
  
  &:hover {
    background: ${({ $active }) => $active ? '#e8f9f1' : '#f5f7fa'};
    color: ${({ $active }) => $active ? '#05A584' : '#0f172a'};
  }
  
  svg {
    width: 18px;
    height: 18px;
  }
`;

export const Workspace = styled.main`
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f5f7fa;
`;

export const RightRail = styled.aside`
  width: 300px;
  background: #ffffff;
  border-left: 1px solid #eef1f5;
  padding: 20px;
  flex-shrink: 0;
  overflow-y: auto;
  
  @media (max-width: 1400px) {
    display: none;
  }
`;

export const RightRailSection = styled.div`
  margin-bottom: 24px;
  
  .section-title {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9CA3AF;
    margin-bottom: 12px;
  }
`;

// Cards & Widgets
export const Panel = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  overflow: hidden;
`;

export const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #eef1f5;
  
  .title {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
  }
  
  .subtitle {
    font-size: 12px;
    color: #9CA3AF;
    margin-top: 2px;
  }
`;

export const PanelContent = styled.div`
  padding: 20px;
`;

export const MetricCard = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 12px;
  padding: 16px;
  
  .label {
    font-size: 12px;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }
  
  .value {
    font-size: 22px;
    font-weight: 700;
    color: #0f172a;
  }
  
  .change {
    font-size: 13px;
    margin-top: 4px;
    color: ${({ $positive }) => $positive ? '#05A584' : '#ef4444'};
  }
`;

export const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  
  ${({ $status }) => {
    switch ($status) {
      case 'BULLISH':
      case 'LONG':
      case 'BUY':
      case 'HEALTHY':
      case 'APPROVED':
      case 'TRENDING_UP':
        return 'background: #e8f9f1; color: #05A584;';
      case 'BEARISH':
      case 'SHORT':
      case 'SELL':
      case 'CRITICAL':
      case 'REJECTED':
        return 'background: rgba(239, 68, 68, 0.1); color: #ef4444;';
      case 'NEUTRAL':
      case 'DEGRADED':
      case 'PENDING':
      case 'MEDIUM':
        return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b;';
      case 'LOW':
        return 'background: #e8f9f1; color: #05A584;';
      case 'HIGH':
        return 'background: rgba(239, 68, 68, 0.1); color: #ef4444;';
      default:
        return 'background: #f5f7fa; color: #738094;';
    }
  }}
`;

export const ProgressBar = styled.div`
  height: 6px;
  background: #eef1f5;
  border-radius: 3px;
  overflow: hidden;
  
  .fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease;
    background: ${({ $color }) => $color || '#05A584'};
    width: ${({ $value }) => `${$value}%`};
  }
`;

export const Table = styled.table`
  width: 100%;
  border-collapse: collapse;
  
  th {
    text-align: left;
    padding: 12px 16px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #9CA3AF;
    border-bottom: 1px solid #eef1f5;
    background: #f9fafb;
  }
  
  td {
    padding: 14px 16px;
    font-size: 14px;
    color: #0f172a;
    border-bottom: 1px solid #eef1f5;
  }
  
  tr:hover td {
    background: #f9fafb;
  }
  
  tr:last-child td {
    border-bottom: none;
  }
`;

export const Button = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  
  ${({ $variant }) => {
    switch ($variant) {
      case 'primary':
        return 'background: #05A584; color: white; &:hover { background: #048a6e; }';
      case 'danger':
        return 'background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); &:hover { background: rgba(239, 68, 68, 0.15); }';
      case 'warning':
        return 'background: rgba(245, 158, 11, 0.1); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.2); &:hover { background: rgba(245, 158, 11, 0.15); }';
      case 'ghost':
        return 'background: transparent; color: #738094; &:hover { background: #f5f7fa; color: #0f172a; }';
      default:
        return 'background: #f5f7fa; color: #0f172a; border: 1px solid #eef1f5; &:hover { background: #eef1f5; }';
    }
  }}
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

// Grid Layouts
export const Grid = styled.div`
  display: grid;
  grid-template-columns: repeat(${({ $cols }) => $cols || 3}, 1fr);
  gap: ${({ $gap }) => $gap || '16px'};
  
  @media (max-width: 1200px) {
    grid-template-columns: repeat(2, 1fr);
  }
  
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
`;

export const ChartLabLayout = styled.div`
  display: grid;
  grid-template-columns: 1fr 400px;
  gap: 20px;
  height: calc(100vh - 140px);
  
  @media (max-width: 1400px) {
    grid-template-columns: 1fr;
  }
`;

export const ResearchStack = styled.div`
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
`;

// Tabs
export const TabsContainer = styled.div`
  display: flex;
  gap: 2px;
  padding: 4px;
  background: #f5f7fa;
  border-radius: 12px;
  margin-bottom: 20px;
`;

export const TabButton = styled.button`
  flex: 1;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  
  ${({ $active }) => $active
    ? 'background: #ffffff; color: #0f172a; box-shadow: 0 1px 3px rgba(0,0,0,0.08);'
    : 'background: transparent; color: #738094; &:hover { color: #0f172a; }'
  }
`;

// Selectors
export const Select = styled.select`
  padding: 8px 14px;
  background: #f5f7fa;
  border: 1px solid #eef1f5;
  border-radius: 10px;
  color: #0f172a;
  font-size: 14px;
  cursor: pointer;
  outline: none;
  
  &:focus {
    border-color: #05A584;
  }
  
  option {
    background: #ffffff;
    color: #0f172a;
  }
`;

export const ToggleGroup = styled.div`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
`;

export const ToggleChip = styled.button`
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid ${({ $active }) => $active ? '#05A584' : '#eef1f5'};
  background: ${({ $active }) => $active ? '#e8f9f1' : '#ffffff'};
  color: ${({ $active }) => $active ? '#05A584' : '#738094'};
  
  &:hover {
    border-color: #05A584;
    color: #05A584;
  }
`;

// Alert Items
export const AlertItem = styled.div`
  display: flex;
  gap: 10px;
  padding: 12px;
  background: #f9fafb;
  border-radius: 10px;
  border-left: 3px solid ${({ $severity }) => {
    switch ($severity) {
      case 'CRITICAL': return '#ef4444';
      case 'WARNING': return '#f59e0b';
      default: return '#05A584';
    }
  }};
  margin-bottom: 10px;
  
  .content {
    flex: 1;
    
    .message {
      font-size: 13px;
      color: #0f172a;
      margin-bottom: 4px;
    }
    
    .time {
      font-size: 11px;
      color: #9CA3AF;
    }
  }
`;

// Hypothesis Card
export const HypothesisCard = styled.div`
  background: #ffffff;
  border: 1px solid ${({ $isTop }) => $isTop ? '#05A584' : '#eef1f5'};
  border-radius: 12px;
  padding: 16px;
  cursor: pointer;
  transition: all 0.15s;
  
  &:hover {
    border-color: #05A584;
    box-shadow: 0 2px 8px rgba(5, 165, 132, 0.1);
  }
  
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }
  
  .type {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
  }
  
  .metrics {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 12px;
  }
  
  .metric {
    .label {
      font-size: 11px;
      color: #9CA3AF;
      text-transform: uppercase;
      margin-bottom: 2px;
    }
    .value {
      font-size: 15px;
      font-weight: 600;
      color: #0f172a;
    }
  }
  
  .explanation {
    font-size: 13px;
    color: #738094;
    line-height: 1.5;
  }
`;

// Position Row
export const PositionRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #eef1f5;
  
  &:last-child {
    border-bottom: none;
  }
  
  .symbol {
    font-weight: 600;
    color: #0f172a;
  }
  
  .direction {
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 6px;
    font-weight: 600;
    background: ${({ $direction }) => $direction === 'LONG' ? '#e8f9f1' : 'rgba(239, 68, 68, 0.1)'};
    color: ${({ $direction }) => $direction === 'LONG' ? '#05A584' : '#ef4444'};
  }
  
  .pnl {
    font-weight: 600;
    color: ${({ $positive }) => $positive ? '#05A584' : '#ef4444'};
  }
`;
