/**
 * Telegram Bot Connect Component (PHASE 6)
 * Allows users to connect their Telegram account for push notifications
 */
import { useState, useEffect } from 'react';
import { Bell, BellOff, Settings, ExternalLink, CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/api/client';

const ALERT_TYPES = [
  { value: 'INTEL_SPIKE', label: 'Intel Score вырос', emoji: '📈' },
  { value: 'INTEL_DUMP', label: 'Intel Score упал', emoji: '📉' },
  { value: 'MOMENTUM_SPIKE', label: 'Momentum вырос', emoji: '🚀' },
  { value: 'MOMENTUM_DUMP', label: 'Momentum упал', emoji: '⚠️' },
  { value: 'FRAUD_SPIKE', label: 'Fraud Risk увеличился', emoji: '🚨' },
  { value: 'TIER_CHANGE', label: 'Изменение Tier', emoji: '⬆️' },
  { value: 'NEW_RISER', label: 'Новый Rising Star', emoji: '🌟' },
];

const SEVERITY_LEVELS = [
  { value: 'LOW', label: 'Все', color: 'text-green-500' },
  { value: 'MEDIUM', label: 'Средние и важные', color: 'text-yellow-500' },
  { value: 'HIGH', label: 'Только важные', color: 'text-red-500' },
];

export function TelegramBotConnect() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [connectUrl, setConnectUrl] = useState(null);
  const [savingPrefs, setSavingPrefs] = useState(false);
  const [testingNotification, setTestingNotification] = useState(false);

  // Preferences form
  const [prefs, setPrefs] = useState({
    enabled: true,
    minSeverity: 'MEDIUM',
    alertTypes: ['INTEL_SPIKE', 'INTEL_DUMP', 'MOMENTUM_SPIKE', 'TIER_CHANGE'],
    quietHours: { enabled: false, start: 22, end: 8 },
  });

  // Fetch connection status
  const fetchStatus = async () => {
    try {
      const response = await api.get('/api/telegram-intel/bot/status');
      setStatus(response.data);
      if (response.data.connection?.preferences) {
        setPrefs(response.data.connection.preferences);
      }
    } catch (err) {
      console.error('Failed to fetch bot status:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  // Generate connect link
  const handleConnect = async () => {
    setConnecting(true);
    try {
      const response = await api.post('/api/telegram-intel/bot/connect');
      setConnectUrl(response.data.connectUrl);
      
      // Open Telegram link in new tab
      window.open(response.data.connectUrl, '_blank');
      
      // Poll for connection status
      const checkConnection = setInterval(async () => {
        const statusResponse = await api.get('/api/telegram-intel/bot/status');
        if (statusResponse.data.connection?.status === 'active') {
          clearInterval(checkConnection);
          setStatus(statusResponse.data);
          setConnectUrl(null);
          setConnecting(false);
        }
      }, 3000);

      // Stop polling after 5 minutes
      setTimeout(() => {
        clearInterval(checkConnection);
        setConnecting(false);
      }, 5 * 60 * 1000);

    } catch (err) {
      console.error('Failed to generate connect link:', err);
      setConnecting(false);
    }
  };

  // Disconnect
  const handleDisconnect = async () => {
    if (!confirm('Отключить Telegram уведомления?')) return;
    
    try {
      await api.delete('/api/telegram-intel/bot/disconnect');
      await fetchStatus();
    } catch (err) {
      console.error('Failed to disconnect:', err);
    }
  };

  // Save preferences
  const savePreferences = async () => {
    setSavingPrefs(true);
    try {
      await api.patch('/api/telegram-intel/bot/preferences', prefs);
      await fetchStatus();
    } catch (err) {
      console.error('Failed to save preferences:', err);
    } finally {
      setSavingPrefs(false);
    }
  };

  // Send test notification
  const sendTestNotification = async () => {
    setTestingNotification(true);
    try {
      const response = await api.post('/api/telegram-intel/bot/test');
      if (response.data.ok) {
        alert('✅ Тестовое уведомление отправлено!');
      } else {
        alert(`❌ Ошибка: ${response.data.error}`);
      }
    } catch (err) {
      console.error('Failed to send test notification:', err);
      alert('❌ Ошибка отправки уведомления');
    } finally {
      setTestingNotification(false);
    }
  };

  // Toggle alert type
  const toggleAlertType = (type) => {
    setPrefs(prev => ({
      ...prev,
      alertTypes: prev.alertTypes.includes(type)
        ? prev.alertTypes.filter(t => t !== type)
        : [...prev.alertTypes, type],
    }));
  };

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 flex items-center justify-center">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  const isConnected = status?.connection?.status === 'active';
  const botUsername = status?.bot?.username || 'TelegramIntelBot';

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={cn(
            'w-10 h-10 rounded-full flex items-center justify-center',
            isConnected ? 'bg-blue-500/20' : 'bg-gray-800'
          )}>
            {isConnected ? (
              <Bell className="w-5 h-5 text-blue-400" />
            ) : (
              <BellOff className="w-5 h-5 text-gray-500" />
            )}
          </div>
          <div>
            <h3 className="font-medium text-white">Telegram уведомления</h3>
            <p className="text-sm text-gray-400">
              {isConnected
                ? `Подключен: @${status.connection.telegramUsername || 'user'}`
                : 'Получайте алерты в Telegram'
              }
            </p>
          </div>
        </div>

        {isConnected && (
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={cn(
              'p-2 rounded-lg transition-colors',
              showSettings ? 'bg-gray-700' : 'hover:bg-gray-800'
            )}
          >
            <Settings className="w-5 h-5 text-gray-400" />
          </button>
        )}
      </div>

      {/* Connection Status / Actions */}
      <div className="p-4">
        {!isConnected ? (
          <div className="space-y-4">
            <p className="text-sm text-gray-400">
              Подключите Telegram бот чтобы получать push-уведомления о каналах в вашем Watchlist.
            </p>

            {connectUrl ? (
              <div className="bg-gray-800 rounded-lg p-4 space-y-3">
                <p className="text-sm text-gray-300">
                  Нажмите кнопку "Start" в Telegram для завершения подключения:
                </p>
                <a
                  href={connectUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 text-white py-2 px-4 rounded-lg font-medium transition-colors"
                >
                  Открыть @{botUsername}
                  <ExternalLink className="w-4 h-4" />
                </a>
                <p className="text-xs text-gray-500 text-center">
                  Ссылка действительна 15 минут
                </p>
              </div>
            ) : (
              <button
                onClick={handleConnect}
                disabled={connecting}
                className={cn(
                  'w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-colors',
                  'bg-blue-600 hover:bg-blue-500 text-white'
                )}
              >
                {connecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Подключение...
                  </>
                ) : (
                  <>
                    <Bell className="w-4 h-4" />
                    Подключить Telegram
                  </>
                )}
              </button>
            )}

            {!status?.bot?.configured && (
              <p className="text-xs text-yellow-500 text-center">
                ⚠️ Telegram Bot не настроен на сервере
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Connection Info */}
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Статус</span>
              <span className="flex items-center gap-1 text-green-400">
                <CheckCircle className="w-4 h-4" />
                Активен
              </span>
            </div>

            {status.connection.stats && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-400">Отправлено алертов</span>
                <span className="text-white">{status.connection.stats.alertsSent || 0}</span>
              </div>
            )}

            {/* Quick Actions */}
            <div className="flex gap-2">
              <button
                onClick={sendTestNotification}
                disabled={testingNotification}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition-colors"
              >
                {testingNotification ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Bell className="w-4 h-4" />
                )}
                Тест
              </button>
              <button
                onClick={handleDisconnect}
                className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded-lg text-sm transition-colors"
              >
                <XCircle className="w-4 h-4" />
                Отключить
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Settings Panel */}
      {showSettings && isConnected && (
        <div className="p-4 border-t border-gray-800 space-y-4">
          {/* Enable/Disable */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-300">Уведомления включены</span>
            <button
              onClick={() => setPrefs(prev => ({ ...prev, enabled: !prev.enabled }))}
              className={cn(
                'w-12 h-6 rounded-full transition-colors relative',
                prefs.enabled ? 'bg-blue-600' : 'bg-gray-700'
              )}
            >
              <span className={cn(
                'absolute top-1 w-4 h-4 bg-white rounded-full transition-all',
                prefs.enabled ? 'left-7' : 'left-1'
              )} />
            </button>
          </div>

          {/* Min Severity */}
          <div className="space-y-2">
            <span className="text-sm text-gray-300">Минимальная важность</span>
            <div className="flex gap-2">
              {SEVERITY_LEVELS.map(level => (
                <button
                  key={level.value}
                  onClick={() => setPrefs(prev => ({ ...prev, minSeverity: level.value }))}
                  className={cn(
                    'flex-1 py-2 px-3 rounded-lg text-sm transition-colors',
                    prefs.minSeverity === level.value
                      ? 'bg-gray-700 text-white border border-gray-600'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                  )}
                >
                  {level.label}
                </button>
              ))}
            </div>
          </div>

          {/* Alert Types */}
          <div className="space-y-2">
            <span className="text-sm text-gray-300">Типы алертов</span>
            <div className="grid grid-cols-2 gap-2">
              {ALERT_TYPES.map(type => (
                <button
                  key={type.value}
                  onClick={() => toggleAlertType(type.value)}
                  className={cn(
                    'flex items-center gap-2 py-2 px-3 rounded-lg text-sm transition-colors text-left',
                    prefs.alertTypes.includes(type.value)
                      ? 'bg-gray-700 text-white'
                      : 'bg-gray-800/50 text-gray-500 hover:bg-gray-800'
                  )}
                >
                  <span>{type.emoji}</span>
                  <span className="truncate">{type.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Quiet Hours */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-300">Тихие часы</span>
              <button
                onClick={() => setPrefs(prev => ({
                  ...prev,
                  quietHours: { ...prev.quietHours, enabled: !prev.quietHours.enabled }
                }))}
                className={cn(
                  'w-10 h-5 rounded-full transition-colors relative',
                  prefs.quietHours.enabled ? 'bg-blue-600' : 'bg-gray-700'
                )}
              >
                <span className={cn(
                  'absolute top-0.5 w-4 h-4 bg-white rounded-full transition-all',
                  prefs.quietHours.enabled ? 'left-5' : 'left-0.5'
                )} />
              </button>
            </div>
            
            {prefs.quietHours.enabled && (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                <span>С</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={prefs.quietHours.start}
                  onChange={(e) => setPrefs(prev => ({
                    ...prev,
                    quietHours: { ...prev.quietHours, start: Number(e.target.value) }
                  }))}
                  className="w-14 px-2 py-1 bg-gray-800 rounded text-white"
                />
                <span>до</span>
                <input
                  type="number"
                  min="0"
                  max="23"
                  value={prefs.quietHours.end}
                  onChange={(e) => setPrefs(prev => ({
                    ...prev,
                    quietHours: { ...prev.quietHours, end: Number(e.target.value) }
                  }))}
                  className="w-14 px-2 py-1 bg-gray-800 rounded text-white"
                />
                <span>часов (UTC)</span>
              </div>
            )}
          </div>

          {/* Save Button */}
          <button
            onClick={savePreferences}
            disabled={savingPrefs}
            className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
          >
            {savingPrefs ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Сохранение...
              </>
            ) : (
              'Сохранить настройки'
            )}
          </button>
        </div>
      )}
    </div>
  );
}

export default TelegramBotConnect;
