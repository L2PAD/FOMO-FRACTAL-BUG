// Config Workspace — Proxy & Exchange Settings

import React, { useState, useEffect } from 'react';
import { Globe, Check, X, AlertCircle } from 'lucide-react';

export default function ConfigWorkspace() {
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [proxyHost, setProxyHost] = useState('');
  const [proxyPort, setProxyPort] = useState('');
  const [proxyUsername, setProxyUsername] = useState('');
  const [proxyPassword, setProxyPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Load current config
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const res = await fetch('/api/exchange/proxy-config');
      if (res.ok) {
        const data = await res.json();
        if (data.proxy) {
          setProxyEnabled(data.proxy.enabled || false);
          setProxyHost(data.proxy.host || '');
          setProxyPort(data.proxy.port || '');
          setProxyUsername(data.proxy.username || '');
          setProxyPassword(data.proxy.password || '');
        }
      }
    } catch (e) {
      console.error('Failed to load proxy config:', e);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setTestResult(null);

    try {
      const config = {
        enabled: proxyEnabled,
        host: proxyHost,
        port: proxyPort,
        username: proxyUsername,
        password: proxyPassword,
      };

      const res = await fetch('/api/exchange/proxy-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proxy: config }),
      });

      if (res.ok) {
        setTestResult({ success: true, message: 'Proxy config saved. Restart backend to apply.' });
      } else {
        setTestResult({ success: false, message: 'Failed to save proxy config.' });
      }
    } catch (e) {
      setTestResult({ success: false, message: e.message });
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setTestResult(null);
    try {
      const res = await fetch('/api/exchange/test-connection');
      const data = await res.json();
      
      if (data.ok && data.connected) {
        setTestResult({ 
          success: true, 
          message: `Connected to ${data.mode || 'exchange'}` 
        });
      } else {
        setTestResult({ 
          success: false, 
          message: data.error || 'Connection failed' 
        });
      }
    } catch (e) {
      setTestResult({ success: false, message: e.message });
    }
  };

  return (
    <div className="p-6 space-y-6" data-testid="config-workspace">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Globe className="w-8 h-8 text-blue-500" />
        <div>
          <h2 className="text-2xl font-bold text-white">Exchange Configuration</h2>
          <p className="text-gray-400 text-sm">Configure proxy settings for Binance Testnet</p>
        </div>
      </div>

      {/* Proxy Settings Card */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Proxy Settings</h3>
          
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={proxyEnabled}
              onChange={(e) => setProxyEnabled(e.target.checked)}
              className="w-4 h-4"
              data-testid="proxy-enabled-toggle"
            />
            <span className="text-sm text-gray-300">Enable Proxy</span>
          </label>
        </div>

        {proxyEnabled && (
          <div className="grid grid-cols-2 gap-4">
            {/* Proxy Host */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Proxy Host</label>
              <input
                type="text"
                value={proxyHost}
                onChange={(e) => setProxyHost(e.target.value)}
                placeholder="proxy.example.com"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                data-testid="proxy-host-input"
              />
            </div>

            {/* Proxy Port */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Proxy Port</label>
              <input
                type="text"
                value={proxyPort}
                onChange={(e) => setProxyPort(e.target.value)}
                placeholder="8080"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                data-testid="proxy-port-input"
              />
            </div>

            {/* Proxy Username */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Username (optional)</label>
              <input
                type="text"
                value={proxyUsername}
                onChange={(e) => setProxyUsername(e.target.value)}
                placeholder="username"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                data-testid="proxy-username-input"
              />
            </div>

            {/* Proxy Password */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Password (optional)</label>
              <input
                type="password"
                value={proxyPassword}
                onChange={(e) => setProxyPassword(e.target.value)}
                placeholder="password"
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white text-sm"
                data-testid="proxy-password-input"
              />
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 pt-4 border-t border-gray-800">
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium text-sm disabled:opacity-50"
            data-testid="save-proxy-config-btn"
          >
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>

          <button
            onClick={handleTestConnection}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded font-medium text-sm"
            data-testid="test-connection-btn"
          >
            Test Connection
          </button>
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`flex items-center gap-2 p-3 rounded ${
            testResult.success ? 'bg-green-900/30 border border-green-800' : 'bg-red-900/30 border border-red-800'
          }`} data-testid="test-result">
            {testResult.success ? (
              <Check className="w-5 h-5 text-green-400" />
            ) : (
              <X className="w-5 h-5 text-red-400" />
            )}
            <span className={`text-sm ${testResult.success ? 'text-green-300' : 'text-red-300'}`}>
              {testResult.message}
            </span>
          </div>
        )}
      </div>

      {/* Info Card */}
      <div className="bg-blue-900/20 border border-blue-800 rounded-xl p-4 flex items-start gap-3">
        <AlertCircle className="w-5 h-5 text-blue-400 mt-0.5" />
        <div className="text-sm text-blue-200">
          <p className="font-medium mb-1">Important:</p>
          <ul className="list-disc list-inside space-y-1 text-blue-300">
            <li>Proxy settings require backend restart to take effect</li>
            <li>Use HTTPS/SOCKS5 proxy for Binance Testnet access</li>
            <li>Test connection after saving to verify proxy works</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
