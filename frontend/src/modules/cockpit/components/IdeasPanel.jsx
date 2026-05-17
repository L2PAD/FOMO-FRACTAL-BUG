/**
 * IdeasPanel — Saved Ideas Management
 * ====================================
 * 
 * Features:
 * - List saved ideas
 * - View idea details and history
 * - Update idea (create new version)
 * - Validate predictions
 * - Track accuracy
 */

import React, { useState, useEffect, useCallback } from 'react';
import styled from 'styled-components';
import { 
  Bookmark, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronRight,
  History,
  Target,
  AlertCircle,
  Trash2,
  Eye,
  Loader2
} from 'lucide-react';
import setupService from '../../../services/setupService';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
`;

const Header = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
`;

const Title = styled.h3`
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  
  svg {
    width: 18px;
    height: 18px;
    color: #3b82f6;
  }
`;

const HeaderActions = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ActionBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: ${({ $primary }) => $primary ? '#3b82f6' : '#ffffff'};
  color: ${({ $primary }) => $primary ? '#ffffff' : '#64748b'};
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  
  svg {
    width: 14px;
    height: 14px;
  }
  
  &:hover:not(:disabled) {
    border-color: #3b82f6;
    color: ${({ $primary }) => $primary ? '#ffffff' : '#3b82f6'};
    background: ${({ $primary }) => $primary ? '#2563eb' : '#ffffff'};
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const Content = styled.div`
  padding: 16px 20px;
`;

const EmptyState = styled.div`
  text-align: center;
  padding: 40px 20px;
  color: #94a3b8;
  
  svg {
    width: 48px;
    height: 48px;
    margin-bottom: 12px;
    opacity: 0.5;
  }
  
  p {
    margin: 0;
    font-size: 14px;
  }
`;

const IdeaList = styled.div`
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const IdeaCard = styled.div`
  padding: 14px 16px;
  background: ${({ $active }) => $active ? '#f0f9ff' : '#f8fafc'};
  border: 1px solid ${({ $active }) => $active ? '#3b82f6' : '#e2e8f0'};
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.15s ease;
  
  &:hover {
    border-color: #3b82f6;
    background: #f0f9ff;
  }
`;

const IdeaHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
`;

const IdeaAsset = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  
  .symbol {
    font-size: 15px;
    font-weight: 700;
    color: #0f172a;
  }
  
  .timeframe {
    font-size: 11px;
    font-weight: 600;
    padding: 3px 8px;
    background: #e2e8f0;
    border-radius: 4px;
    color: #64748b;
  }
`;

const BiasIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 600;
  
  ${({ $bias }) => {
    if ($bias === 'bullish') return `
      background: #dcfce7;
      color: #16a34a;
    `;
    if ($bias === 'bearish') return `
      background: #fee2e2;
      color: #dc2626;
    `;
    return `
      background: #f1f5f9;
      color: #64748b;
    `;
  }}
  
  svg {
    width: 12px;
    height: 12px;
  }
`;

const IdeaDetails = styled.div`
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: #64748b;
  
  .detail {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .value {
    font-weight: 600;
    color: #0f172a;
  }
`;

const StatusBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  
  ${({ $status }) => {
    switch ($status) {
      case 'active':
        return `background: #dbeafe; color: #2563eb;`;
      case 'completed':
        return `background: #dcfce7; color: #16a34a;`;
      case 'invalidated':
        return `background: #fee2e2; color: #dc2626;`;
      case 'archived':
        return `background: #f1f5f9; color: #64748b;`;
      default:
        return `background: #f1f5f9; color: #64748b;`;
    }
  }}
`;

const IdeaActions = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e2e8f0;
`;

const SmallBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  color: #64748b;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  
  svg {
    width: 12px;
    height: 12px;
  }
  
  &:hover:not(:disabled) {
    border-color: #3b82f6;
    color: #3b82f6;
  }
  
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  &.danger:hover {
    border-color: #dc2626;
    color: #dc2626;
  }
`;

const ExpandedSection = styled.div`
  margin-top: 12px;
  padding: 12px;
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
`;

const TimelineItem = styled.div`
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
  
  &:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  
  .icon {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    
    ${({ $type }) => {
      if ($type === 'version') return `background: #dbeafe; color: #3b82f6;`;
      if ($type === 'validation') return `background: #dcfce7; color: #16a34a;`;
      return `background: #f1f5f9; color: #64748b;`;
    }}
    
    svg {
      width: 14px;
      height: 14px;
    }
  }
  
  .content {
    flex: 1;
    
    .title {
      font-size: 13px;
      font-weight: 600;
      color: #0f172a;
      margin-bottom: 2px;
    }
    
    .meta {
      font-size: 11px;
      color: #94a3b8;
    }
    
    .detail {
      font-size: 12px;
      color: #64748b;
      margin-top: 4px;
    }
  }
`;

const AccuracyBar = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
  
  .bar {
    flex: 1;
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    overflow: hidden;
    
    .fill {
      height: 100%;
      background: ${({ $value }) => 
        $value >= 0.7 ? '#16a34a' : 
        $value >= 0.5 ? '#f59e0b' : '#dc2626'
      };
      width: ${({ $value }) => Math.round($value * 100)}%;
      transition: width 0.3s ease;
    }
  }
  
  .label {
    font-size: 12px;
    font-weight: 600;
    color: ${({ $value }) => 
      $value >= 0.7 ? '#16a34a' : 
      $value >= 0.5 ? '#f59e0b' : '#dc2626'
    };
    min-width: 40px;
    text-align: right;
  }
`;

const LoadingOverlay = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  
  svg {
    animation: spin 1s linear infinite;
    color: #3b82f6;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
`;

// ============================================
// COMPONENT
// ============================================

const IdeasPanel = ({ 
  currentSymbol = 'BTCUSDT', 
  currentTimeframe = '4H',
  onIdeaSelect = null 
}) => {
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdea, setSelectedIdea] = useState(null);
  const [expandedIdea, setExpandedIdea] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  // Fetch ideas
  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    try {
      const result = await setupService.listIdeas({ limit: 20 });
      if (result.ok) {
        setIdeas(result.ideas || []);
      }
    } catch (err) {
      console.error('Failed to fetch ideas:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchIdeas();
  }, [fetchIdeas]);

  // Fetch timeline for expanded idea
  const fetchTimeline = useCallback(async (ideaId) => {
    try {
      const result = await setupService.getIdeaTimeline(ideaId);
      if (result.ok) {
        setTimeline(result);
      }
    } catch (err) {
      console.error('Failed to fetch timeline:', err);
    }
  }, []);

  // Toggle idea expansion
  const handleExpandIdea = (ideaId) => {
    if (expandedIdea === ideaId) {
      setExpandedIdea(null);
      setTimeline(null);
    } else {
      setExpandedIdea(ideaId);
      fetchTimeline(ideaId);
    }
  };

  // Update idea (create new version)
  const handleUpdateIdea = async (ideaId) => {
    setActionLoading(`update-${ideaId}`);
    try {
      const result = await setupService.updateIdea(ideaId);
      if (result.ok) {
        fetchIdeas();
        if (expandedIdea === ideaId) {
          fetchTimeline(ideaId);
        }
      }
    } catch (err) {
      console.error('Failed to update idea:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Validate idea
  const handleValidateIdea = async (ideaId) => {
    setActionLoading(`validate-${ideaId}`);
    try {
      const result = await setupService.validateIdea(ideaId);
      if (result.ok) {
        fetchIdeas();
        if (expandedIdea === ideaId) {
          fetchTimeline(ideaId);
        }
      }
    } catch (err) {
      console.error('Failed to validate idea:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Delete idea
  const handleDeleteIdea = async (ideaId) => {
    if (!window.confirm('Delete this idea?')) return;
    
    setActionLoading(`delete-${ideaId}`);
    try {
      const result = await setupService.deleteIdea(ideaId);
      if (result.ok) {
        fetchIdeas();
        if (expandedIdea === ideaId) {
          setExpandedIdea(null);
          setTimeline(null);
        }
      }
    } catch (err) {
      console.error('Failed to delete idea:', err);
    } finally {
      setActionLoading(null);
    }
  };

  // Get bias icon
  const getBiasIcon = (bias) => {
    if (bias === 'bullish') return <TrendingUp />;
    if (bias === 'bearish') return <TrendingDown />;
    return <Minus />;
  };

  // Format date
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Container data-testid="ideas-panel">
      <Header>
        <Title>
          <Bookmark />
          Saved Ideas
        </Title>
        <HeaderActions>
          <ActionBtn onClick={fetchIdeas} disabled={loading}>
            <RefreshCw size={14} />
            Refresh
          </ActionBtn>
        </HeaderActions>
      </Header>
      
      <Content>
        {loading && ideas.length === 0 ? (
          <LoadingOverlay>
            <Loader2 size={32} />
          </LoadingOverlay>
        ) : ideas.length === 0 ? (
          <EmptyState>
            <Bookmark />
            <p>No saved ideas yet</p>
            <p style={{ marginTop: 8, fontSize: 12, color: '#94a3b8' }}>
              Click "Save Idea" to save your analysis
            </p>
          </EmptyState>
        ) : (
          <IdeaList>
            {ideas.map(idea => (
              <IdeaCard 
                key={idea.idea_id}
                $active={expandedIdea === idea.idea_id}
                onClick={() => handleExpandIdea(idea.idea_id)}
                data-testid={`idea-card-${idea.idea_id}`}
              >
                <IdeaHeader>
                  <IdeaAsset>
                    <span className="symbol">{idea.asset}</span>
                    <span className="timeframe">{idea.timeframe}</span>
                    <StatusBadge $status={idea.status}>{idea.status}</StatusBadge>
                  </IdeaAsset>
                  <BiasIndicator $bias={idea.technical_bias}>
                    {getBiasIcon(idea.technical_bias)}
                    {(idea.technical_bias || 'neutral').toUpperCase()}
                  </BiasIndicator>
                </IdeaHeader>
                
                <IdeaDetails>
                  <div className="detail">
                    <Clock size={12} />
                    <span>{formatDate(idea.updated_at || idea.created_at)}</span>
                  </div>
                  <div className="detail">
                    <History size={12} />
                    <span>v{idea.current_version || 1}</span>
                  </div>
                  {idea.confidence > 0 && (
                    <div className="detail">
                      <Target size={12} />
                      <span className="value">{Math.round(idea.confidence * 100)}%</span>
                    </div>
                  )}
                  {idea.accuracy_score !== null && idea.accuracy_score !== undefined && (
                    <div className="detail">
                      <CheckCircle2 size={12} />
                      <span className="value">{Math.round(idea.accuracy_score * 100)}% accurate</span>
                    </div>
                  )}
                </IdeaDetails>
                
                {/* Expanded view with timeline */}
                {expandedIdea === idea.idea_id && (
                  <ExpandedSection onClick={e => e.stopPropagation()}>
                    {/* Accuracy bar */}
                    {idea.total_predictions > 0 && (
                      <AccuracyBar $value={idea.accuracy_score || 0}>
                        <span style={{ fontSize: 11, color: '#64748b' }}>Accuracy</span>
                        <div className="bar">
                          <div className="fill" />
                        </div>
                        <span className="label">{Math.round((idea.accuracy_score || 0) * 100)}%</span>
                      </AccuracyBar>
                    )}
                    
                    {/* Timeline */}
                    {timeline?.timeline && (
                      <div style={{ marginTop: 12 }}>
                        <div style={{ 
                          fontSize: 11, 
                          fontWeight: 600, 
                          color: '#64748b',
                          textTransform: 'uppercase',
                          marginBottom: 8 
                        }}>
                          History
                        </div>
                        {timeline.timeline.map((item, idx) => (
                          <TimelineItem key={idx} $type={item.type}>
                            <div className="icon">
                              {item.type === 'version' ? <History size={14} /> : <CheckCircle2 size={14} />}
                            </div>
                            <div className="content">
                              <div className="title">
                                {item.type === 'version' 
                                  ? `Version ${item.version}`
                                  : `Validation: ${item.result?.toUpperCase()}`
                                }
                              </div>
                              <div className="meta">{formatDate(item.timestamp)}</div>
                              {item.type === 'version' && (
                                <div className="detail">
                                  {item.technical_bias?.toUpperCase()} — {Math.round((item.confidence || 0) * 100)}% confidence
                                  {item.price && ` @ $${item.price.toLocaleString()}`}
                                </div>
                              )}
                              {item.type === 'validation' && item.price_change_pct !== undefined && (
                                <div className="detail">
                                  Price change: {item.price_change_pct > 0 ? '+' : ''}{item.price_change_pct.toFixed(2)}%
                                </div>
                              )}
                            </div>
                          </TimelineItem>
                        ))}
                      </div>
                    )}
                    
                    {/* Actions */}
                    <IdeaActions>
                      <SmallBtn 
                        onClick={() => handleUpdateIdea(idea.idea_id)}
                        disabled={actionLoading === `update-${idea.idea_id}`}
                      >
                        {actionLoading === `update-${idea.idea_id}` ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <RefreshCw size={12} />
                        )}
                        Update
                      </SmallBtn>
                      <SmallBtn 
                        onClick={() => handleValidateIdea(idea.idea_id)}
                        disabled={actionLoading === `validate-${idea.idea_id}` || idea.status !== 'active'}
                      >
                        {actionLoading === `validate-${idea.idea_id}` ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <CheckCircle2 size={12} />
                        )}
                        Validate
                      </SmallBtn>
                      {onIdeaSelect && (
                        <SmallBtn onClick={() => onIdeaSelect(idea)}>
                          <Eye size={12} />
                          View
                        </SmallBtn>
                      )}
                      <SmallBtn 
                        className="danger"
                        onClick={() => handleDeleteIdea(idea.idea_id)}
                        disabled={actionLoading === `delete-${idea.idea_id}`}
                      >
                        {actionLoading === `delete-${idea.idea_id}` ? (
                          <Loader2 size={12} className="animate-spin" />
                        ) : (
                          <Trash2 size={12} />
                        )}
                        Delete
                      </SmallBtn>
                    </IdeaActions>
                  </ExpandedSection>
                )}
              </IdeaCard>
            ))}
          </IdeaList>
        )}
      </Content>
    </Container>
  );
};

export default IdeasPanel;
