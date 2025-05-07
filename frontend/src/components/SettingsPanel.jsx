import { useState, useEffect } from 'react';

function SettingsPanel() {
  const [settings, setSettings] = useState({
    sonarr_url: '',
    sonarr_api_key: '',
    radarr_url: '',
    radarr_api_key: '',
    swears_file: 'swears.txt',
    output_prefix: 'clean_',
    output_directory: '',
    enable_auto_processing: true,
    poll_interval_seconds: 300,
    boost_db: 6,
    pre_buffer: 100,
    post_buffer: 100,
    bleeptool: 'S-M-FSM'
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingSonarr, setTestingSonarr] = useState(false);
  const [testingRadarr, setTestingRadarr] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState({
    sonarr: null,
    radarr: null
  });
  
  // Fetch existing settings on component mount
  useEffect(() => {
    fetchSettings();
    fetchConnectionStatus();
  }, []);
  
  const fetchSettings = async () => {
    try {
      // Normally would fetch from server, but using simulated data for now
      // const response = await fetch('/api/settings');
      // const data = await response.json();
      
      // Simulated delay for demo
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Simulated settings from server
      const data = {
        sonarr_url: 'http://localhost:8989',
        sonarr_api_key: 'abc123456789',
        radarr_url: 'http://localhost:7878',
        radarr_api_key: '',
        swears_file: 'swears.txt',
        output_prefix: 'clean_',
        output_directory: '',
        enable_auto_processing: true,
        poll_interval_seconds: 300,
        boost_db: 6,
        pre_buffer: 100,
        post_buffer: 100,
        bleeptool: 'S-M-FSM'
      };
      
      setSettings(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching settings:', error);
      setLoading(false);
    }
  };
  
  const fetchConnectionStatus = async () => {
    try {
      const sonarrResponse = await fetch('/api/sonarr/test');
      const sonarrData = await sonarrResponse.json();
      
      // Try to fetch Radarr status if URL is in settings
      let radarrData = { success: false, message: 'Not configured' };
      if (settings.radarr_url && settings.radarr_api_key) {
        const radarrResponse = await fetch('/api/radarr/test');
        radarrData = await radarrResponse.json();
      }
      
      setConnectionStatus({
        sonarr: sonarrData,
        radarr: radarrData
      });
    } catch (error) {
      console.error('Error testing connections:', error);
    }
  };
  
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };
  
  const handleNumberChange = (e) => {
    const { name, value } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: parseInt(value, 10) || 0
    }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    
    try {
      // Normally would save to server
      // await fetch('/api/settings', {
      //   method: 'POST',
      //   headers: {
      //     'Content-Type': 'application/json'
      //   },
      //   body: JSON.stringify(settings)
      // });
      
      // Simulated save delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      alert('Settings saved successfully!');
      
      // Refresh connection status with new settings
      await fetchConnectionStatus();
    } catch (error) {
      console.error('Error saving settings:', error);
      alert('Failed to save settings. Please try again.');
    } finally {
      setSaving(false);
    }
  };
  
  const testSonarrConnection = async () => {
    setTestingSonarr(true);
    
    try {
      const response = await fetch('/api/sonarr/test');
      const data = await response.json();
      
      setConnectionStatus(prev => ({
        ...prev,
        sonarr: data
      }));
      
      alert(data.message);
    } catch (error) {
      console.error('Error testing Sonarr connection:', error);
      alert('Failed to test Sonarr connection. Please check the console for details.');
    } finally {
      setTestingSonarr(false);
    }
  };
  
  const testRadarrConnection = async () => {
    setTestingRadarr(true);
    
    try {
      const response = await fetch('/api/radarr/test');
      const data = await response.json();
      
      setConnectionStatus(prev => ({
        ...prev,
        radarr: data
      }));
      
      alert(data.message);
    } catch (error) {
      console.error('Error testing Radarr connection:', error);
      alert('Failed to test Radarr connection. Please check the console for details.');
    } finally {
      setTestingRadarr(false);
    }
  };
  
  if (loading) {
    return <div className="mb-6">Loading settings...</div>;
  }
  
  return (
    <div className="mb-6">
      <h2 className="text-xl font-semibold mb-4">Settings</h2>
      
      <form className="space-y-6" onSubmit={handleSubmit}>
        {/* Sonarr Settings */}
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="text-lg font-medium mb-3">Sonarr Integration</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Sonarr URL
              </label>
              <input
                type="text"
                name="sonarr_url"
                value={settings.sonarr_url}
                onChange={handleChange}
                placeholder="http://localhost:8989"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="password"
                name="sonarr_api_key"
                value={settings.sonarr_api_key}
                onChange={handleChange}
                placeholder="Your Sonarr API Key"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="mt-3 flex items-center">
            <button
              type="button"
              onClick={testSonarrConnection}
              disabled={testingSonarr || !settings.sonarr_url || !settings.sonarr_api_key}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 disabled:opacity-50"
            >
              {testingSonarr ? 'Testing...' : 'Test Connection'}
            </button>
            
            {connectionStatus.sonarr && (
              <div className="ml-3">
                {connectionStatus.sonarr.success ? (
                  <span className="text-green-600 flex items-center">
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    Connected
                  </span>
                ) : (
                  <span className="text-red-600 flex items-center">
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    Failed
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* Radarr Settings */}
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="text-lg font-medium mb-3">Radarr Integration (Optional)</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Radarr URL
              </label>
              <input
                type="text"
                name="radarr_url"
                value={settings.radarr_url}
                onChange={handleChange}
                placeholder="http://localhost:7878"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                API Key
              </label>
              <input
                type="password"
                name="radarr_api_key"
                value={settings.radarr_api_key}
                onChange={handleChange}
                placeholder="Your Radarr API Key"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <div className="mt-3 flex items-center">
            <button
              type="button"
              onClick={testRadarrConnection}
              disabled={testingRadarr || !settings.radarr_url || !settings.radarr_api_key}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 disabled:opacity-50"
            >
              {testingRadarr ? 'Testing...' : 'Test Connection'}
            </button>
            
            {connectionStatus.radarr && (
              <div className="ml-3">
                {connectionStatus.radarr.success ? (
                  <span className="text-green-600 flex items-center">
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    Connected
                  </span>
                ) : (
                  <span className="text-red-600 flex items-center">
                    <svg className="w-5 h-5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    {settings.radarr_url && settings.radarr_api_key ? 'Failed' : 'Not Configured'}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* Bleeparr Settings */}
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="text-lg font-medium mb-3">Bleeparr Settings</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Swears File Path
              </label>
              <input
                type="text"
                name="swears_file"
                value={settings.swears_file}
                onChange={handleChange}
                placeholder="swears.txt"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Output Prefix
              </label>
              <input
                type="text"
                name="output_prefix"
                value={settings.output_prefix}
                onChange={handleChange}
                placeholder="clean_"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Output Directory (optional)
              </label>
              <input
                type="text"
                name="output_directory"
                value={settings.output_directory}
                onChange={handleChange}
                placeholder="Leave empty to use same directory as input"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Bleeptool Passes
              </label>
              <select
                name="bleeptool"
                value={settings.bleeptool}
                onChange={handleChange}
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="S-M-FSM">S-M-FSM (Most thorough, slowest)</option>
                <option value="S-FSM">S-FSM (Skip medium Whisper model)</option>
                <option value="S-M">S-M (Skip fallback subtitle mute)</option>
                <option value="S">S (Only small Whisper model)</option>
              </select>
            </div>
            
            <div>
              <label className="block font-medium text-gray-700 mb-1">
                Audio Boost (dB)
              </label>
              <input
                type="number"
                name="boost_db"
                value={settings.boost_db}
                onChange={handleNumberChange}
                min="0"
                max="20"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-sm text-gray-500 mt-1">Higher values improve detection</p>
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Pre-Buffer (ms)
                </label>
                <input
                  type="number"
                  name="pre_buffer"
                  value={settings.pre_buffer}
                  onChange={handleNumberChange}
                  min="0"
                  max="500"
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Post-Buffer (ms)
                </label>
                <input
                  type="number"
                  name="post_buffer"
                  value={settings.post_buffer}
                  onChange={handleNumberChange}
                  min="0"
                  max="500"
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>
        
        {/* Automation Settings */}
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="text-lg font-medium mb-3">Automation</h3>
          
          <div className="space-y-4">
            <div className="flex items-center">
              <input
                type="checkbox"
                id="enable_auto_processing"
                name="enable_auto_processing"
                checked={settings.enable_auto_processing}
                onChange={handleChange}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
              />
              <label htmlFor="enable_auto_processing" className="ml-2 block text-gray-700">
                Enable automatic processing of new downloads
              </label>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block font-medium text-gray-700 mb-1">
                  Poll Interval (seconds)
                </label>
                <input
                  type="number"
                  name="poll_interval_seconds"
                  value={settings.poll_interval_seconds}
                  onChange={handleNumberChange}
                  min="60"
                  max="3600"
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-sm text-gray-500 mt-1">How often to check for new downloads (60-3600 sec)</p>
              </div>
            </div>
          </div>
        </div>
        
        {/* Submit Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white rounded shadow hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default SettingsPanel;
