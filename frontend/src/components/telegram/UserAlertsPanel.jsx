/**
 * UserAlertsPanel Component (BLOCK 5.2 UI)
 * Displays personalized alerts for the user
 */
import React from 'react';
import { Link } from 'react-router-dom';
import { 
  Bell, BellOff, TrendingUp, TrendingDown, AlertTriangle, 
  Star, ArrowUpRight, Check, Trash2, ExternalLink 
} from 'lucide-react';
import { Button } from '../ui/button';

function getAlertIcon(type) {
  switch (type) {
    case 'INTEL_SPIKE':
    case 'MOMENTUM_SPIKE':
      return <TrendingUp className="h-5 w-5 text-green-400" />;
    case 'INTEL_DUMP':
    case 'MOMENTUM_DUMP':
      return <TrendingDown className="h-5 w-5 text-red-400" />;
    case 'FRAUD_SPIKE':
      return <AlertTriangle className="h-5 w-5 text-red-500" />;
    case 'TIER_CHANGE':
      return <ArrowUpRight className="h-5 w-5 text-blue-400" />;
    case 'NEW_RISER':
      return <Star className="h-5 w-5 text-amber-400" />;
    default:
      return <Bell className="h-5 w-5 text-gray-400" />;
  }
}

function getSeverityColor(severity) {
  switch (severity) {
    case 'HIGH':
      return 'border-l-red-500 bg-red-500/5';
    case 'MEDIUM':
      return 'border-l-amber-500 bg-amber-500/5';
    case 'LOW':
      return 'border-l-blue-500 bg-blue-500/5';
    default:
      return 'border-l-gray-500 bg-gray-500/5';
  }
}

function AlertCard({ alert, onMarkRead, onDelete }) {
  return (
    <div
      className={`border-l-4 rounded-r-lg p-4 ${getSeverityColor(alert.severity)} ${
        !alert.read ? 'ring-1 ring-white/10' : 'opacity-75'
      }`}
      data-testid={`alert-card-${alert._id}`}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">
          {getAlertIcon(alert.type)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link
              to={`/telegram/${alert.username}`}
              className="font-medium hover:text-amber-400 transition-colors"
            >
              @{alert.username}
            </Link>
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              alert.severity === 'HIGH' ? 'bg-red-500/20 text-red-400' :
              alert.severity === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' :
              'bg-blue-500/20 text-blue-400'
            }`}>
              {alert.severity}
            </span>
            {!alert.read && (
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
            )}
          </div>
          <p className="text-sm text-gray-300">{alert.message}</p>
          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span>{new Date(alert.createdAt).toLocaleString('ru-RU')}</span>
            <span>{alert.type.replace(/_/g, ' ')}</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {!alert.read && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onMarkRead?.([alert._id])}
              className="text-gray-400 hover:text-green-400"
              title="Отметить как прочитанное"
            >
              <Check className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete?.(alert._id)}
            className="text-gray-400 hover:text-red-400"
            title="Удалить"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
          <Link to={`/telegram/${alert.username}`}>
            <Button
              variant="ghost"
              size="sm"
              className="text-gray-400 hover:text-amber-400"
              title="Перейти к каналу"
            >
              <ExternalLink className="h-4 w-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}

export function UserAlertsPanel({ 
  alerts, 
  stats, 
  loading, 
  onMarkRead, 
  onMarkAllRead, 
  onDelete,
  showFilters = true 
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
      </div>
    );
  }

  if (!alerts || alerts.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400" data-testid="alerts-empty">
        <BellOff className="h-12 w-12 mx-auto mb-4 opacity-30" />
        <p className="text-lg mb-2">Нет уведомлений</p>
        <p className="text-sm">Добавьте каналы в избранное, чтобы получать персональные алерты</p>
      </div>
    );
  }

  return (
    <div data-testid="user-alerts-panel">
      {/* Stats Bar */}
      {stats && (
        <div className="flex items-center gap-6 mb-6 p-4 bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-gray-400" />
            <span className="text-sm">
              <strong className="text-white">{stats.total}</strong> всего
            </span>
          </div>
          {stats.unread > 0 && (
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full" />
              <span className="text-sm">
                <strong className="text-blue-400">{stats.unread}</strong> непрочитанных
              </span>
            </div>
          )}
          <div className="flex items-center gap-4 text-sm">
            <span className="text-red-400">{stats.high} HIGH</span>
            <span className="text-amber-400">{stats.medium} MEDIUM</span>
            <span className="text-blue-400">{stats.low} LOW</span>
          </div>
          {stats.unread > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={onMarkAllRead}
              className="ml-auto"
              data-testid="mark-all-read"
            >
              <Check className="h-4 w-4 mr-2" />
              Прочитать все
            </Button>
          )}
        </div>
      )}

      {/* Alerts List */}
      <div className="space-y-3">
        {alerts.map((alert) => (
          <AlertCard
            key={alert._id}
            alert={alert}
            onMarkRead={onMarkRead}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}

export default UserAlertsPanel;
