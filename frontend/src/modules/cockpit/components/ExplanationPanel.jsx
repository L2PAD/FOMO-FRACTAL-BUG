/**
 * ExplanationPanel V2 — Ultra-Compact Trader Explanation
 * =======================================================
 * 
 * Only 3 lines, no water:
 * - Summary (what's happening)
 * - Action (what to do)
 * - Risk (when it's wrong)
 * 
 * Plus confidence badge and copy button.
 */

import React, { useState } from 'react';
import styled from 'styled-components';
import { Brain, Copy, Check, Share2, AlertCircle } from 'lucide-react';

// ============================================
// STYLED COMPONENTS
// ============================================

const Panel = styled.div`
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  border-radius: 16px;
  padding: 20px 24px;
  margin-top: 16px;
  border: 1px solid #312e81;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
`;

const Title = styled.h3`
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #a5b4fc;
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  svg {
    color: #8b5cf6;
  }
`;

const ConfidenceBadge = styled.span`
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  
  ${props => {
    if (props.$level === 'high') {
      return `
        background: rgba(34, 197, 94, 0.15);
        color: #4ade80;
        border: 1px solid rgba(34, 197, 94, 0.3);
      `;
    }
    if (props.$level === 'medium') {
      return `
        background: rgba(234, 179, 8, 0.15);
        color: #facc15;
        border: 1px solid rgba(234, 179, 8, 0.3);
      `;
    }
    return `
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
    `;
  }}
`;

const Content = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const Line = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 12px;
`;

const Label = styled.span`
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #6366f1;
  min-width: 60px;
  padding-top: 2px;
`;

const Text = styled.p`
  font-size: 15px;
  line-height: 1.5;
  color: #e2e8f0;
  margin: 0;
  flex: 1;
`;

const SummaryText = styled(Text)`
  font-size: 17px;
  font-weight: 500;
  color: #f8fafc;
`;

const ActionText = styled(Text)`
  color: #4ade80;
`;

const RiskText = styled(Text)`
  color: #fbbf24;
  display: flex;
  align-items: center;
  gap: 6px;
  
  svg {
    flex-shrink: 0;
    color: #f59e0b;
  }
`;

const Divider = styled.div`
  height: 1px;
  background: linear-gradient(90deg, transparent 0%, #312e81 50%, transparent 100%);
  margin: 12px 0;
`;

const Footer = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
`;

const ShareText = styled.div`
  font-size: 13px;
  color: #94a3b8;
  flex: 1;
  margin-right: 16px;
  font-family: 'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif;
  background: rgba(0, 0, 0, 0.2);
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid #1e293b;
`;

const ActionButtons = styled.div`
  display: flex;
  gap: 8px;
`;

const ActionBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: ${props => props.$primary ? '#6366f1' : 'rgba(99, 102, 241, 0.1)'};
  border: 1px solid ${props => props.$primary ? '#6366f1' : '#4f46e5'};
  border-radius: 8px;
  color: ${props => props.$primary ? '#ffffff' : '#a5b4fc'};
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  
  &:hover {
    background: ${props => props.$primary ? '#4f46e5' : 'rgba(99, 102, 241, 0.2)'};
    border-color: #4f46e5;
  }
  
  svg {
    width: 14px;
    height: 14px;
  }
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 24px;
  color: #64748b;
  font-size: 14px;
`;

// ============================================
// COMPONENT
// ============================================

const ExplanationPanel = ({ explanation }) => {
  const [copied, setCopied] = useState(false);

  if (!explanation) {
    return (
      <Panel data-testid="explanation-panel">
        <Header>
          <Title>
            <Brain size={16} />
            Analysis
          </Title>
        </Header>
        <EmptyState>No analysis available</EmptyState>
      </Panel>
    );
  }

  const {
    summary = '',
    action = '',
    risk = '',
    confidence = 'medium',
  } = explanation;

  // Build share text
  const shareText = `${summary} ${action} ${risk}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Market Analysis',
          text: shareText,
        });
      } catch (err) {
        // User cancelled
      }
    } else {
      handleCopy();
    }
  };

  return (
    <Panel data-testid="explanation-panel">
      <Header>
        <Title>
          <Brain size={16} />
          Analysis
        </Title>
        <ConfidenceBadge $level={confidence}>
          {confidence} confidence
        </ConfidenceBadge>
      </Header>

      <Content>
        {/* SUMMARY — What's happening */}
        <Line>
          <SummaryText>{summary}</SummaryText>
        </Line>

        {/* ACTION — What to do */}
        {action && (
          <Line>
            <Label>Action</Label>
            <ActionText>{action}</ActionText>
          </Line>
        )}

        {/* RISK — When it's wrong */}
        {risk && (
          <Line>
            <Label>Risk</Label>
            <RiskText>
              <AlertCircle size={14} />
              {risk}
            </RiskText>
          </Line>
        )}
      </Content>

      <Divider />

      <Footer>
        <ShareText>{shareText}</ShareText>
        <ActionButtons>
          <ActionBtn onClick={handleCopy}>
            {copied ? <Check /> : <Copy />}
            {copied ? 'Copied!' : 'Copy'}
          </ActionBtn>
          <ActionBtn $primary onClick={handleShare}>
            <Share2 />
            Share
          </ActionBtn>
        </ActionButtons>
      </Footer>
    </Panel>
  );
};

export default ExplanationPanel;
