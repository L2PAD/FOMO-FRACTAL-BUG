/**
 * PLATFORM ADMIN LAYOUT
 * 
 * Collapsible sidebar (icons ↔ full labels) with localStorage persistence.
 * Content area fills remaining width.
 */

import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, ChevronLeft, ChevronRight, ChevronDown, Menu, X, PanelLeftClose, PanelLeft } from 'lucide-react';
import { cn } from '@/lib/utils';
import { ADMIN_NAV } from '@/config/adminNav.registry';

const STORAGE_KEY = 'admin_sidebar_collapsed';

// ── NavNode ─────────────────────────────────────────────────────
function NavNode({ node, level = 0, expandedSections, toggleSection, currentPath, collapsed }) {
  const hasChildren = node.children && node.children.length > 0;
  const isLeaf = !!node.path;
  const isExpanded = expandedSections[node.id];
  const isActive = node.path === currentPath;

  const hasActiveChild = hasChildren && node.children.some(child => {
    if (child.path === currentPath) return true;
    if (child.children) return child.children.some(c => c.path === currentPath);
    return false;
  });

  const Icon = node.icon;

  // ─── COLLAPSED MODE ───────────────────────────────────────
  if (collapsed && level === 0) {
    const targetPath = isLeaf
      ? node.path
      : hasChildren
        ? node.children.find(c => c.path)?.path || '#'
        : '#';

    return (
      <Link
        to={targetPath}
        title={node.label}
        className={cn(
          'flex items-center justify-center w-10 h-10 mx-auto rounded-lg transition-all mb-1',
          'hover:bg-gray-100',
          (isActive || hasActiveChild)
            ? 'bg-indigo-50 text-indigo-700'
            : 'text-gray-500'
        )}
        data-testid={`admin-nav-${node.id}`}
      >
        {Icon && <Icon className={cn('w-[18px] h-[18px]', (isActive || hasActiveChild) ? 'text-indigo-600' : 'text-gray-400')} />}
      </Link>
    );
  }

  // Don't render children at level > 0 in collapsed mode
  if (collapsed) return null;

  // ─── EXPANDED MODE ────────────────────────────────────────

  // Leaf node (actual page link)
  if (isLeaf) {
    return (
      <Link
        to={node.path}
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
          'hover:bg-gray-100',
          level === 0 && 'mt-0.5 font-semibold',
          level === 1 && 'ml-4 font-medium',
          level === 2 && 'ml-8 font-medium',
          isActive
            ? 'bg-indigo-50 text-indigo-700 border-l-2 border-indigo-600'
            : level === 0 ? 'text-gray-900' : 'text-gray-600'
        )}
        data-testid={`admin-nav-${node.id}`}
      >
        {Icon && <Icon className={cn('w-4 h-4', isActive ? 'text-indigo-600' : level === 0 ? 'text-gray-700' : 'text-gray-400')} />}
        <span className="flex-1 truncate">{node.label}</span>
        {node.badge && (
          <span className={cn(
            'px-1.5 py-0.5 text-[10px] font-semibold rounded',
            node.badge === 'ACTIVE' && 'bg-green-100 text-green-700',
            node.badge === 'NEW' && 'bg-blue-100 text-blue-700',
            node.badge === 'BETA' && 'bg-amber-100 text-amber-700',
            node.badge === 'SOON' && 'bg-gray-100 text-gray-500',
          )}>
            {node.badge}
          </span>
        )}
      </Link>
    );
  }

  // Disabled node
  if (node.disabled) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium',
          'text-gray-400 cursor-not-allowed',
          level === 0 && 'mt-0.5',
          level === 1 && 'ml-4',
        )}
      >
        {Icon && <Icon className="w-4 h-4 text-gray-300" />}
        <span className="flex-1">{node.label}</span>
        {node.badge && (
          <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-gray-100 text-gray-400">
            {node.badge}
          </span>
        )}
      </div>
    );
  }

  // Section node (has children, collapsible)
  return (
    <div className={cn(level === 0 && 'mb-1')}>
      <button
        onClick={() => toggleSection(node.id)}
        className={cn(
          'flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium transition-all',
          'hover:bg-gray-100',
          level === 0 && 'text-gray-900 font-semibold',
          level === 1 && 'ml-4 text-gray-700',
          (isExpanded || hasActiveChild) && level === 0 && 'bg-gray-50',
        )}
        data-testid={`admin-nav-section-${node.id}`}
      >
        {Icon && (
          <Icon className={cn(
            'w-4 h-4',
            level === 0 ? 'text-gray-700' : 'text-gray-400',
            hasActiveChild && 'text-indigo-600'
          )} />
        )}
        <span className="flex-1 text-left truncate">{node.label}</span>
        <ChevronRight className={cn(
          'w-4 h-4 text-gray-400 transition-transform flex-shrink-0',
          isExpanded && 'rotate-90'
        )} />
      </button>

      {isExpanded && hasChildren && (
        <div className="mt-0.5">
          {node.children.map(child => (
            <NavNode
              key={child.id || child.path || child.label}
              node={child}
              level={level + 1}
              expandedSections={expandedSections}
              toggleSection={toggleSection}
              currentPath={currentPath}
              collapsed={false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Layout ─────────────────────────────────────────────────
export function AdminLayout({ children }) {
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored !== null) return stored === 'true';
    return false;
  });

  const [mobileOpen, setMobileOpen] = useState(false);
  const [expandedSections, setExpandedSections] = useState({});

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  // Auto-collapse on small screens
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) setCollapsed(true);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Auto-expand sections based on current path - DISABLED by default
  // User manually opens sections, only expand if directly navigated
  useEffect(() => {
    // Don't auto-expand on initial load, only when explicitly navigated
    // This keeps all sections closed by default
  }, [location.pathname]);

  const toggleSection = (id) => {
    setExpandedSections(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const sidebarW = collapsed ? 'w-16' : 'w-56';

  return (
    <div className="min-h-screen bg-gray-50" data-testid="platform-admin-layout">
      {/* Top Bar */}
      <header className="bg-white border-b border-gray-200 h-12 flex items-center px-4 sticky top-0 z-30 shadow-sm">
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="lg:hidden mr-2 p-1.5 hover:bg-gray-100 rounded-lg"
        >
          {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>

        <Link
          to="/dashboard"
          className="flex items-center gap-1.5 text-gray-600 hover:text-gray-900 transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          <span className="text-xs">Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-1.5 ml-4">
          <Shield className="w-4 h-4 text-indigo-600" />
          <span className="font-semibold text-sm text-gray-900">Platform Admin</span>
        </div>

        <div className="ml-auto flex items-center gap-4">
          <span className="text-[10px] text-gray-400 hidden sm:block">
            Hierarchical Navigation
          </span>
        </div>
      </header>

      <div className="flex">
        {/* Sidebar — Desktop */}
        <aside
          className={cn(
            sidebarW,
            'bg-white border-r border-gray-200 min-h-[calc(100vh-3rem)] transition-all duration-200 ease-in-out shadow-lg',
            'hidden lg:flex lg:flex-col flex-shrink-0 z-10'
          )}
          data-testid="admin-sidebar"
        >
          {/* Toggle button */}
          <div className={cn('flex items-center border-b border-gray-100 h-10', collapsed ? 'justify-center' : 'justify-end px-3')}>
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors"
              data-testid="sidebar-collapse-toggle"
              title={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
            >
              {collapsed ? <PanelLeft className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          </div>

          {/* Nav items */}
          <div className={cn('flex-1 overflow-y-auto', collapsed ? 'px-1 py-2' : 'p-3 space-y-0.5')}>
            {ADMIN_NAV.map(node => (
              <NavNode
                key={node.id}
                node={node}
                level={0}
                expandedSections={expandedSections}
                toggleSection={toggleSection}
                currentPath={location.pathname}
                collapsed={collapsed}
              />
            ))}
          </div>
        </aside>

        {/* Sidebar — Mobile overlay */}
        {mobileOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/20 lg:hidden z-10"
              onClick={() => setMobileOpen(false)}
            />
            <aside className="fixed left-0 top-12 w-64 bg-white border-r border-gray-200 min-h-[calc(100vh-3rem)] z-20 lg:hidden overflow-y-auto">
              <div className="p-3 space-y-0.5">
                {ADMIN_NAV.map(node => (
                  <NavNode
                    key={node.id}
                    node={node}
                    level={0}
                    expandedSections={expandedSections}
                    toggleSection={toggleSection}
                    currentPath={location.pathname}
                    collapsed={false}
                  />
                ))}
              </div>
            </aside>
          </>
        )}

        {/* Main Content — fills remaining width */}
        <main className="flex-1 min-h-[calc(100vh-3rem)] min-w-0">
          {children}
        </main>
      </div>
    </div>
  );
}

export default AdminLayout;
