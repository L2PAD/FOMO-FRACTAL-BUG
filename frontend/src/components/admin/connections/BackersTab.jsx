/**
 * Backers Tab - Phase 1
 * 
 * Admin panel for managing Backers (Funds, Projects, DAOs)
 * that provide seed authority independent of Twitter.
 * 
 * Design: Matches existing Admin Connections style (light theme)
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../../components/ui/card';
import { Button } from '../../../components/ui/button';
import { Badge } from '../../../components/ui/badge';
import { Input } from '../../../components/ui/input';
import { 
  Building2, 
  Plus, 
  Link2, 
  Lock, 
  Unlock, 
  Trash2, 
  ChevronDown, 
  ChevronUp,
  Globe,
  Twitter,
  BarChart3,
  Shield,
  Users,
  AlertCircle,
  CheckCircle,
  Search,
  RefreshCw,
  X
} from 'lucide-react';
import { IconFund, IconProject, IconDAO, IconEcosystem, IconCompany } from '../../icons/FomoIcons';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// ============================================================
// CONSTANTS
// ============================================================

const BACKER_TYPES = [
  { value: 'FUND', label: 'Fund', Icon: IconFund, color: 'green' },
  { value: 'PROJECT', label: 'Project', Icon: IconProject, color: 'blue' },
  { value: 'DAO', label: 'DAO', Icon: IconDAO, color: 'purple' },
  { value: 'ECOSYSTEM', label: 'Ecosystem', Icon: IconEcosystem, color: 'yellow' },
  { value: 'COMPANY', label: 'Company', Icon: IconCompany, color: 'gray' },
];

const BACKER_CATEGORIES = [
  'DEFI', 'INFRA', 'NFT', 'TRADING', 'GAMING', 
  'SECURITY', 'LAYER1', 'LAYER2', 'SOCIAL', 'DATA', 'ORACLE'
];

const BINDING_RELATIONS = [
  { value: 'OWNER', label: 'Owner (100%)', weight: 1.0 },
  { value: 'BUILDER', label: 'Builder (80%)', weight: 0.8 },
  { value: 'INVESTOR', label: 'Investor (60%)', weight: 0.6 },
  { value: 'AFFILIATED', label: 'Affiliated (40%)', weight: 0.4 },
  { value: 'ECOSYSTEM', label: 'Ecosystem (30%)', weight: 0.3 },
];

// ============================================================
// UI COMPONENTS (matching existing style)
// ============================================================

const StatCard = ({ label, value, icon, color = 'gray' }) => {
  const colors = {
    blue: 'bg-blue-50/70 text-blue-600',
    green: 'bg-emerald-50/70 text-emerald-600',
    yellow: 'bg-amber-50/70 text-amber-600',
    purple: 'bg-purple-50/70 text-purple-600',
    gray: 'bg-slate-50 text-slate-600 ',
    rose: 'bg-rose-50 text-rose-600 border-rose-100',
  };
  
  return (
    <div className={`rounded-lg p-4 ${colors[color]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium opacity-75">{label}</span>
        {icon}
      </div>
      <span className="text-2xl font-bold">{value}</span>
    </div>
  );
};

const Section = ({ title, icon, badge, expanded = true, onToggle, children }) => (
  <Card>
    <CardHeader 
      className={`cursor-pointer ${onToggle ? 'hover:bg-slate-50' : ''}`}
      onClick={onToggle}
    >
      <div className="flex items-center justify-between">
        <CardTitle className="text-sm flex items-center gap-2">
          {icon}
          {title}
          {badge && <Badge variant="secondary" className="text-xs">{badge}</Badge>}
        </CardTitle>
        {onToggle && (
          expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />
        )}
      </div>
    </CardHeader>
    {expanded && <CardContent>{children}</CardContent>}
  </Card>
);

const TypeBadge = ({ type }) => {
  const config = BACKER_TYPES.find(t => t.value === type) || BACKER_TYPES[0];
  const colors = {
    green: 'text-emerald-600 border-green-200',
    blue: 'text-blue-600 border-blue-200',
    purple: 'bg-purple-100 text-purple-700 border-purple-200',
    yellow: 'text-amber-600 border-yellow-200',
    gray: 'bg-slate-100 text-slate-700 ',
  };
  
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${colors[config.color]}`}>
      {config.Icon && <config.Icon size={14} />} {config.label}
    </span>
  );
};

// ============================================================
// MAIN COMPONENT
// ============================================================

export default function BackersTab({ token }) {
  const [backers, setBackers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  
  // UI State
  const [expandedBackers, setExpandedBackers] = useState({});
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBindModal, setShowBindModal] = useState(null);
  const [filters, setFilters] = useState({ type: '', search: '' });
  const [expandedSections, setExpandedSections] = useState({
    list: true,
    info: true,
  });

  // Toast auto-hide
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // ============================================================
  // DATA FETCHING
  // ============================================================

  const fetchBackers = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filters.type) params.append('type', filters.type);
      if (filters.search) params.append('search', filters.search);
      
      const res = await fetch(`${API_URL}/api/admin/connections/backers?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      
      if (data.ok) {
        setBackers(data.data.backers);
        setStats(data.data.stats);
        setError(null);
      } else {
        setError(data.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token, filters]);

  useEffect(() => {
    fetchBackers();
  }, [fetchBackers]);

  // ============================================================
  // ACTIONS
  // ============================================================

  const createBacker = async (formData) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/connections/backers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });
      const data = await res.json();
      
      if (data.ok) {
        setShowCreateModal(false);
        setToast({ message: `✅ Backer "${data.data.name}" created`, type: 'success' });
        fetchBackers();
        return { ok: true };
      }
      return { ok: false, error: data.error || data.message };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  };

  const freezeBacker = async (backerId, freeze = true) => {
    try {
      const res = await fetch(
        `${API_URL}/api/admin/connections/backers/${backerId}/${freeze ? 'freeze' : 'unfreeze'}`,
        {
          method: 'POST',
          headers: { 
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}` 
          },
          body: JSON.stringify({}),
        }
      );
      const data = await res.json();
      if (data.ok) {
        setToast({ message: freeze ? '🔒 Backer frozen' : '🔓 Backer unfrozen', type: 'success' });
        fetchBackers();
      }
    } catch (err) {
      console.error('Freeze error:', err);
    }
  };

  const deleteBacker = async (backerId) => {
    if (!window.confirm('Are you sure you want to archive this backer?')) return;
    
    try {
      const res = await fetch(`${API_URL}/api/admin/connections/backers/${backerId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.ok) {
        setToast({ message: '🗑️ Backer archived', type: 'success' });
        fetchBackers();
      }
    } catch (err) {
      console.error('Delete error:', err);
    }
  };

  const createBinding = async (backerId, bindingData) => {
    try {
      const res = await fetch(`${API_URL}/api/admin/connections/backers/${backerId}/bind`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(bindingData),
      });
      const data = await res.json();
      
      if (data.ok) {
        setShowBindModal(null);
        setToast({ message: '🔗 Binding created', type: 'success' });
        fetchBackers();
        return { ok: true };
      }
      return { ok: false, error: data.error || data.message };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  };

  const toggleExpand = (backerId) => {
    setExpandedBackers(prev => ({
      ...prev,
      [backerId]: !prev[backerId],
    }));
  };

  // ============================================================
  // RENDER
  // ============================================================

  if (loading && backers.length === 0) {
    return (
      <div className="flex items-center justify-center p-12" data-testid="backers-loading">
        <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="backers-tab">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg  ${
          toast.type === 'success' ? 'bg-green-100 text-green-800 ' : 'bg-red-100 text-red-800 '
        }`}>
          {toast.message}
        </div>
      )}

      {/* Header Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Building2 className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <CardTitle className="text-lg">Backers Registry</CardTitle>
                <p className="text-sm text-slate-500 mt-0.5">
                  Real-world entities that provide seed authority
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchBackers}
                disabled={loading}
              >
                <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button
                size="sm"
                onClick={() => setShowCreateModal(true)}
                className="bg-green-600 hover:bg-green-700"
                data-testid="create-backer-btn"
              >
                <Plus className="w-4 h-4 mr-1" />
                Add Backer
              </Button>
            </div>
          </div>
        </CardHeader>

        {/* Stats */}
        {stats && (
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4" data-testid="backers-stats">
              <StatCard 
                label="Total Backers" 
                value={stats.total} 
                icon={<Building2 className="w-4 h-4" />}
                color="green"
              />
              <StatCard 
                label="Funds" 
                value={stats.byType?.FUND || 0} 
                icon={<BarChart3 className="w-4 h-4" />}
                color="blue"
              />
              <StatCard 
                label="Projects" 
                value={stats.byType?.PROJECT || 0} 
                icon={<Globe className="w-4 h-4" />}
                color="purple"
              />
              <StatCard 
                label="Frozen" 
                value={stats.frozen} 
                icon={<Lock className="w-4 h-4" />}
                color="yellow"
              />
              <StatCard 
                label="Avg Authority" 
                value={Math.round(stats.avgAuthority)} 
                icon={<Shield className="w-4 h-4" />}
                color="rose"
              />
            </div>
          </CardContent>
        )}
      </Card>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4">
          <div className="flex gap-4 items-center">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
              <Input
                type="text"
                placeholder="Search backers..."
                value={filters.search}
                onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                className="pl-10"
                data-testid="backers-search"
              />
            </div>
            
            <select
              value={filters.type}
              onChange={(e) => setFilters(prev => ({ ...prev, type: e.target.value }))}
              className="px-4 py-2  rounded-lg text-sm focus:border-blue-500 focus:outline-none bg-white"
              data-testid="backers-type-filter"
            >
              <option value="">All Types</option>
              {BACKER_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50  rounded-lg text-red-700 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Backers List */}
      <Section 
        title="Backers List" 
        icon={<Building2 className="w-4 h-4 text-green-600" />}
        badge={`${backers.length}`}
        expanded={expandedSections.list}
        onToggle={() => setExpandedSections(p => ({ ...p, list: !p.list }))}
      >
        <div className="space-y-3" data-testid="backers-list">
          {backers.length === 0 ? (
            <div className="text-center py-8 text-slate-500">
              <Building2 className="w-12 h-12 mx-auto mb-4 opacity-30" />
              <p>No backers found. Create your first backer to get started.</p>
            </div>
          ) : (
            backers.map(backer => (
              <BackerCard
                key={backer.id}
                backer={backer}
                expanded={expandedBackers[backer.id]}
                onToggle={() => toggleExpand(backer.id)}
                onFreeze={(freeze) => freezeBacker(backer.id, freeze)}
                onDelete={() => deleteBacker(backer.id)}
                onBind={() => setShowBindModal(backer.id)}
                token={token}
              />
            ))
          )}
        </div>
      </Section>

      {/* Info Banner */}
      <Section 
        title="About Seed Authority Layer" 
        icon={<Shield className="w-4 h-4 text-blue-600" />}
        badge="Phase 1"
        expanded={expandedSections.info}
        onToggle={() => setExpandedSections(p => ({ ...p, info: !p.info }))}
      >
        <div className="text-sm text-slate-600 space-y-2">
          <p>
            <strong>Backers</strong> — это якоря реального мира (фонды, проекты, DAO), которые существуют независимо от Twitter.
          </p>
          <p>
            Twitter аккаунты <strong>наследуют</strong> авторитет от Backers через привязки (bindings).
            Network v2 использует Backers как anchors для валидации графа.
          </p>
          <div className="mt-3 p-3 bg-blue-50 rounded-lg ">
            <strong className="text-blue-700">Key principle:</strong>
            <span className="text-blue-600"> Twitter never creates authority — it only inherits and amplifies.</span>
          </div>
        </div>
      </Section>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateBackerModal
          onClose={() => setShowCreateModal(false)}
          onCreate={createBacker}
        />
      )}

      {/* Bind Modal */}
      {showBindModal && (
        <BindingModal
          backerId={showBindModal}
          backerName={backers.find(b => b.id === showBindModal)?.name}
          onClose={() => setShowBindModal(null)}
          onBind={(data) => createBinding(showBindModal, data)}
        />
      )}
    </div>
  );
}

// ============================================================
// BACKER CARD
// ============================================================

function BackerCard({ backer, expanded, onToggle, onFreeze, onDelete, onBind, token }) {
  const [bindings, setBindings] = useState([]);
  const [loadingBindings, setLoadingBindings] = useState(false);

  useEffect(() => {
    if (expanded && bindings.length === 0) {
      loadBindings();
    }
  }, [expanded]);

  const loadBindings = async () => {
    setLoadingBindings(true);
    try {
      const res = await fetch(`${API_URL}/api/admin/connections/backers/${backer.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (data.ok) {
        setBindings(data.data.bindings || []);
      }
    } catch (err) {
      console.error('Load bindings error:', err);
    } finally {
      setLoadingBindings(false);
    }
  };

  return (
    <div 
      className={`bg-white border rounded-lg overflow-hidden transition-all ${
        backer.frozen ? 'border-yellow-300 bg-yellow-50/30' : ' hover:'
      }`}
      data-testid={`backer-card-${backer.slug}`}
    >
      {/* Header */}
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-slate-50"
        onClick={onToggle}
      >
        <div className="flex items-center gap-4">
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-slate-400" />
          ) : (
            <ChevronDown className="w-5 h-5 text-slate-400" />
          )}
          
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-slate-900">{backer.name}</h3>
              <TypeBadge type={backer.type} />
              {backer.frozen && (
                <Badge variant="outline" className="text-yellow-700 border-yellow-300 bg-yellow-100">
                  <Lock className="w-3 h-3 mr-1" />
                  FROZEN
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
              {backer.categories?.slice(0, 3).map(cat => (
                <span key={cat} className="px-1.5 py-0.5 bg-slate-100 rounded text-xs">{cat}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Authority Score */}
          <div className="text-right">
            <div className="text-2xl font-bold text-green-600">
              {backer.seedAuthority}
            </div>
            <div className="text-xs text-slate-500">
              Confidence: {(backer.confidence * 100).toFixed(0)}%
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onBind()}
              title="Add Binding"
              data-testid={`bind-${backer.slug}`}
            >
              <Link2 className="w-4 h-4 text-blue-600" />
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onFreeze(!backer.frozen)}
              title={backer.frozen ? 'Unfreeze' : 'Freeze'}
              data-testid={`freeze-${backer.slug}`}
            >
              {backer.frozen ? (
                <Unlock className="w-4 h-4 text-yellow-600" />
              ) : (
                <Lock className="w-4 h-4 text-slate-500" />
              )}
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onDelete()}
              title="Archive"
              data-testid={`delete-${backer.slug}`}
            >
              <Trash2 className="w-4 h-4 text-red-500" />
            </Button>
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className=" p-4 bg-slate-50/50">
          {backer.description && (
            <p className="text-sm text-slate-600 mb-4">{backer.description}</p>
          )}

          {/* External Refs */}
          {backer.externalRefs?.website && (
            <div className="flex gap-4 mb-4">
              <a 
                href={backer.externalRefs.website} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline flex items-center gap-1"
              >
                <Globe className="w-3 h-3" /> Website
              </a>
            </div>
          )}

          {/* Bindings */}
          <div className="mt-4">
            <h4 className="text-sm font-medium text-slate-700 mb-2 flex items-center gap-2">
              <Link2 className="w-4 h-4" />
              Linked Accounts ({bindings.length})
            </h4>
            
            {loadingBindings ? (
              <div className="text-sm text-slate-500">Загрузка...</div>
            ) : bindings.length === 0 ? (
              <div className="text-sm text-slate-500">No bindings yet</div>
            ) : (
              <div className="space-y-2">
                {bindings.map(binding => (
                  <div 
                    key={binding.id}
                    className="flex items-center justify-between p-2 bg-white rounded "
                  >
                    <div className="flex items-center gap-2">
                      {binding.targetType === 'TWITTER' ? (
                        <Twitter className="w-4 h-4 text-blue-500" />
                      ) : (
                        <Users className="w-4 h-4 text-purple-500" />
                      )}
                      <span className="text-sm font-medium text-slate-800">
                        {binding.targetHandle || binding.targetId}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {binding.relation}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2">
                      {binding.verified && (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      )}
                      <span className="text-xs text-slate-500">
                        {(binding.weight * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================
// CREATE BACKER MODAL
// ============================================================

function CreateBackerModal({ onClose, onCreate }) {
  const [formData, setFormData] = useState({
    slug: '',
    name: '',
    description: '',
    type: 'FUND',
    categories: [],
    seedAuthority: 50,
    confidence: 0.8,
    source: 'MANUAL',
    externalRefs: { website: '' },
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    const result = await onCreate(formData);
    
    if (!result.ok) {
      setError(result.error);
    }
    setLoading(false);
  };

  const toggleCategory = (cat) => {
    setFormData(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat],
    }));
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="create-backer-modal">
      <div className="bg-white rounded-lg w-full max-w-xl max-h-[90vh] overflow-y-auto shadow-xl">
        <div className="p-6 border-b  flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-slate-900">Create New Backer</h3>
            <p className="text-sm text-slate-500 mt-0.5">Add a real-world entity to the seed authority layer</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50  rounded-lg text-red-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {/* Name & Slug */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Name *</label>
              <Input
                required
                value={formData.name}
                onChange={(e) => {
                  setFormData(prev => ({
                    ...prev,
                    name: e.target.value,
                    slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, ''),
                  }));
                }}
                placeholder="a16z Crypto"
                data-testid="backer-name-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Slug *</label>
              <Input
                required
                value={formData.slug}
                onChange={(e) => setFormData(prev => ({ ...prev, slug: e.target.value }))}
                placeholder="a16z-crypto"
                data-testid="backer-slug-input"
              />
            </div>
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Type *</label>
            <div className="flex gap-2 flex-wrap">
              {BACKER_TYPES.map(t => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setFormData(prev => ({ ...prev, type: t.value }))}
                  className={`px-3 py-2 rounded-lg flex items-center gap-2 border transition-colors ${
                    formData.type === t.value
                      ? 'text-emerald-600 border-green-300'
                      : 'bg-slate-50 text-slate-700  hover:bg-slate-100'
                  }`}
                  data-testid={`backer-type-${t.value}`}
                >
                  {t.Icon && <t.Icon size={16} />}
                  <span className="text-sm">{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Categories */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Categories</label>
            <div className="flex gap-2 flex-wrap">
              {BACKER_CATEGORIES.map(cat => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className={`px-2 py-1 text-xs rounded border transition-colors ${
                    formData.categories.includes(cat)
                      ? 'text-blue-600 border-blue-300'
                      : 'bg-slate-50 text-slate-600  hover:bg-slate-100'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Authority & Confidence */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Seed Authority (0-100) *
              </label>
              <Input
                type="number"
                required
                min={0}
                max={100}
                value={formData.seedAuthority}
                onChange={(e) => setFormData(prev => ({ ...prev, seedAuthority: parseInt(e.target.value) }))}
                data-testid="backer-authority-input"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Confidence (0-1) *
              </label>
              <Input
                type="number"
                required
                min={0}
                max={1}
                step={0.1}
                value={formData.confidence}
                onChange={(e) => setFormData(prev => ({ ...prev, confidence: parseFloat(e.target.value) }))}
                data-testid="backer-confidence-input"
              />
            </div>
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Описание</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              className="w-full px-3 py-2  rounded-lg text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none"
              rows={2}
              placeholder="Brief description of this entity..."
              data-testid="backer-description-input"
            />
          </div>

          {/* Website */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Website</label>
            <Input
              type="url"
              value={formData.externalRefs.website}
              onChange={(e) => setFormData(prev => ({ 
                ...prev, 
                externalRefs: { ...prev.externalRefs, website: e.target.value }
              }))}
              placeholder="https://example.com"
              data-testid="backer-website-input"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 ">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="bg-green-600 hover:bg-green-700"
              data-testid="create-backer-submit"
            >
              {loading ? 'Creating...' : 'Create Backer'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============================================================
// BINDING MODAL
// ============================================================

function BindingModal({ backerId, backerName, onClose, onBind }) {
  const [formData, setFormData] = useState({
    targetType: 'TWITTER',
    targetId: '',
    targetHandle: '',
    relation: 'OWNER',
    weight: 1.0,
  });
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    
    const result = await onBind(formData);
    
    if (!result.ok) {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="binding-modal">
      <div className="bg-white rounded-lg w-full max-w-md shadow-xl">
        <div className="p-6 border-b  flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-slate-900">Create Binding</h3>
            <p className="text-sm text-slate-500 mt-0.5">Link <strong>{backerName}</strong> to an account</p>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50  rounded-lg text-red-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {/* Target Type */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Target Type</label>
            <select
              value={formData.targetType}
              onChange={(e) => setFormData(prev => ({ ...prev, targetType: e.target.value }))}
              className="w-full px-3 py-2  rounded-lg text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="TWITTER">Twitter Account</option>
              <option value="ACTOR">Actor</option>
            </select>
          </div>

          {/* Target ID */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              {formData.targetType === 'TWITTER' ? 'Twitter ID *' : 'Actor ID *'}
            </label>
            <Input
              required
              value={formData.targetId}
              onChange={(e) => setFormData(prev => ({ ...prev, targetId: e.target.value }))}
              placeholder="1234567890"
              data-testid="binding-target-id"
            />
          </div>

          {/* Handle */}
          {formData.targetType === 'TWITTER' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Handle</label>
              <Input
                value={formData.targetHandle}
                onChange={(e) => setFormData(prev => ({ ...prev, targetHandle: e.target.value }))}
                placeholder="@a16zcrypto"
                data-testid="binding-handle"
              />
            </div>
          )}

          {/* Relation */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Relation</label>
            <select
              value={formData.relation}
              onChange={(e) => {
                const rel = BINDING_RELATIONS.find(r => r.value === e.target.value);
                setFormData(prev => ({ 
                  ...prev, 
                  relation: e.target.value,
                  weight: rel?.weight || 1.0,
                }));
              }}
              className="w-full px-3 py-2  rounded-lg text-sm focus:border-blue-500 focus:outline-none"
              data-testid="binding-relation"
            >
              {BINDING_RELATIONS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 ">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700"
              data-testid="create-binding-submit"
            >
              {loading ? 'Creating...' : 'Create Binding'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
