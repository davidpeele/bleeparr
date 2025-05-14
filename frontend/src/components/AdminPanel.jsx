import { useState, useEffect } from 'react';

function AdminPanel() {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [settings, setSettings] = useState({
    port: 5050,
    logLevel: 'INFO',
    maxHistoryItems: 100,
    maxQueueItems: 50
  });
  const [logsLoading, setLogsLoading] = useState(false);
  const [confirmReset, setConfirmReset] = useState({
    queue: false,
    history: false
  });

  useEffect(() => {
    // Load initial settings
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/admin/settings');
      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      }
    } catch (error) {
      console.error('Error fetching admin settings:', error);
    }
  };

  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      const response = await fetch('/api/admin/logs');
      if (response.ok) {
        const data = await response.json();
        setLogs(data.logs);
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLogsLoading(false);
    }
  };

  const handleSettingChange = (e) => {
    const { name, value, type } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: type === 'number' ? parseInt(value, 10) : value
    }));
  };

  const saveSettings = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/admin/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        alert('Settings saved successfully!');
      } else {
        alert('Failed to save settings');
      }
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Error saving settings');
    } finally {
      setLoading(false);
    }
  };

  const resetQueue = async () => {
    if (!confirmReset.queue) {
      setConfirmReset({ ...confirmReset, queue: true });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/admin/reset-queue', {
        method: 'POST'
      });

      if (response.ok) {
        alert('Processing queue has been reset');
        setConfirmReset({ ...confirmReset, queue: false });
      } else {
        alert('Failed to reset queue');
      }
    } catch (error) {
      console.error('Error resetting queue:', error);
      alert('Error resetting queue');
    } finally {
      setLoading(false);
    }
  };

  const resetHistory = async () => {
    if (!confirmReset.history) {
      setConfirmReset({ ...confirmReset, history: true });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/admin/reset-history', {
        method: 'POST'
      });

      if (response.ok) {
        alert('Processing history has been reset');
        setConfirmReset({ ...confirmReset, history: false });
      } else {
        alert('Failed to reset history');
      }
    } catch (error) {
      console.error('Error resetting history:', error);
      alert('Error resetting history');
    } finally {
      setLoading(false);
    }
  };

  const rebootApplication = async () => {
    if (!window.confirm('Are you sure you want to reboot the application? This will disconnect all users and stop ongoing processing.')) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/admin/reboot', {
        method: 'POST'
      });

      if (response.ok) {
        alert('Application is rebooting. This page will reload in 10 seconds.');
        setTimeout(() => {
          window.location.reload();
        }, 10000);
      } else {
        alert('Failed to reboot application');
      }
    } catch (error) {
      console.error('Error rebooting application:', error);
      alert('Error rebooting application');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-4">Admin Panel</h2>

      <div className="space-y-6">
        {/* System Actions Section */}
        <div className="bg-white p-4 border rounded-lg shadow">
          <h3 className="text-lg font-medium mb-3">System Actions</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <button
                  onClick={resetQueue}
                  disabled={loading}
                  className="w-full px-4 py-2 bg-yellow-600 text-white rounded shadow hover:bg-yellow-700 disabled:opacity-50"
                >
                  {confirmReset.queue ? 'Click again to confirm' : 'Reset Processing Queue'}
                </button>
                <p className="text-sm text-gray-500 mt-1">Removes all items from the processing queue</p>
              </div>
              
              <div>
                <button
                  onClick={resetHistory}
                  disabled={loading}
                  className="w-full px-4 py-2 bg-yellow-600 text-white rounded shadow hover:bg-yellow-700 disabled:opacity-50"
                >
                  {confirmReset.history ? 'Click again to confirm' : 'Reset Processing History'}
                </button>
                <p className="text-sm text-gray-500 mt-1">Clears all processing history records</p>
              </div>
            </div>
            
            <div>
              <button
                onClick={rebootApplication}
                disabled={loading}
                className="w-full px-4 py-2 bg-red-600 text-white rounded shadow hover:bg-red-700 disabled:opacity-50"
              >
                Reboot Application
              </button>
              <p className="text-sm text-gray-500 mt-1">Restarts the Bleeparr application (may take a few seconds)</p>
            </div>
          </div>
        </div>
        
        {/* Application Settings */}
        <div className="bg-white p-4 border rounded-lg shadow">
          <h3 className="text-lg font-medium mb-3">Application Settings</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Server Port
                </label>
                <input
                  type="number"
                  name="port"
                  value={settings.port}
                  onChange={handleSettingChange}
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">Application HTTP port (requires reboot)</p>
              </div>
              
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Log Level
                </label>
                <select
                  name="logLevel"
                  value={settings.logLevel}
                  onChange={handleSettingChange}
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="DEBUG">DEBUG</option>
                  <option value="INFO">INFO</option>
                  <option value="WARNING">WARNING</option>
                  <option value="ERROR">ERROR</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Max History Items
                </label>
                <input
                  type="number"
                  name="maxHistoryItems"
                  value={settings.maxHistoryItems}
                  onChange={handleSettingChange}
                  min="10"
                  max="1000"
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">Maximum number of history items to keep</p>
              </div>
              
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Max Queue Items
                </label>
                <input
                  type="number"
                  name="maxQueueItems"
                  value={settings.maxQueueItems}
                  onChange={handleSettingChange}
                  min="5"
                  max="500"
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">Maximum number of items in the processing queue</p>
              </div>
            </div>
            
            <div className="flex justify-end">
              <button
                onClick={saveSettings}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded shadow hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Saving...' : 'Save Settings'}
              </button>
            </div>
          </div>
        </div>
        
        {/* System Logs */}
        <div className="bg-white p-4 border rounded-lg shadow">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-lg font-medium">System Logs</h3>
            <button
              onClick={fetchLogs}
              disabled={logsLoading}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 disabled:opacity-50"
            >
              {logsLoading ? 'Loading...' : 'Refresh Logs'}
            </button>
          </div>
          
          <div className="bg-gray-100 p-2 rounded font-mono text-sm">
            <div className="h-64 overflow-auto">
              {logs.length === 0 ? (
                <p className="text-gray-500 p-2">Click "Refresh Logs" to view application logs.</p>
              ) : (
                logs.map((log, index) => (
                  <div 
                    key={index} 
                    className={`py-1 px-2 ${
                      log.level === 'ERROR' || log.level === 'CRITICAL' 
                        ? 'bg-red-100 text-red-800' 
                        : log.level === 'WARNING' 
                          ? 'bg-yellow-100 text-yellow-800' 
                          : ''
                    }`}
                  >
                    <span className="text-gray-600">{log.timestamp}</span> [{log.level}] {log.message}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;
