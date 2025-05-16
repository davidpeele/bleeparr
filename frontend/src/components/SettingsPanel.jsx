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
    bleeptool: 'S-M-FSM',
    // New options from bleeparr.py v1.2
    use_beep: false,
    beep_mode: 'words',
    temp_dir: '',
    retain_clips: false,
    // Path mapping settings
    path_mappings: [
      { host_path: '', container_path: '' }
    ]
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
  
  // Function to handle path mapping changes
  const handlePathMappingChange = (index, field, value) => {
    setSettings(prev => {
      const newMappings = [...prev.path_mappings];
      newMappings[index] = {
        ...newMappings[index],
        [field]: value
      };
      return {
        ...prev,
        path_mappings: newMappings
      };
    });
  };    

  const addPathMapping = () => {
    setSettings(prev => ({
      ...prev,
      path_mappings: [...prev.path_mappings, { host_path: '', container_path: '' }]
    }));
  };
  
  const removePathMapping = (index) => {
    setSettings(prev => {
      const newMappings = [...prev.path_mappings];
      newMappings.splice(index, 1);
      if (newMappings.length === 0) {
        newMappings.push({ host_path: '', container_path: '' });
      }
      return {
        ...prev,
        path_mappings: newMappings
      };
    });
  };

  const fetchSettings = async () => {
    try {
      console.log("Fetching settings from server");
      const response = await fetch('/api/settings');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      console.log("Settings received:", data);
      
      // Process path mappings
      let pathMappings = [];
      try {
        // Parse path_mappings if it exists
        if (data.path_mappings) {
          pathMappings = JSON.parse(data.path_mappings);
        }
      } catch (e) {
        console.error("Error parsing path mappings:", e);
      }
      
      // Ensure at least one empty mapping
      if (!pathMappings || pathMappings.length === 0) {
        pathMappings = [{ host_path: '', container_path: '' }];
      }
      
      setSettings({
        ...data,
        path_mappings: pathMappings
      });
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
  
    // Create a copy of settings to modify
    const settingsToSubmit = { ...settings };
    
    // Serialize path mappings to JSON string
    if (settingsToSubmit.path_mappings) {
      // Filter out empty mappings
      const validMappings = settingsToSubmit.path_mappings.filter(
        m => m.host_path.trim() && m.container_path.trim()
      );
      settingsToSubmit.path_mappings = JSON.stringify(validMappings);
    }
  
    console.log("Submitting settings:", settingsToSubmit);
  
    try {
      const response = await fetch('/api/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settingsToSubmit)
      });
    
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
    
      const result = await response.json();
      console.log("Settings saved response:", result);
    
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
          <h3 className="text-lg font-medium mb-3">Radarr Integration</h3>
          
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
                Temporary Directory (optional)
              </label>
              <input
                type="text"
                name="temp_dir"
                value={settings.temp_dir}
                onChange={handleChange}
                placeholder="Leave empty to use default clips folder"
                className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-sm text-gray-500 mt-1">Directory to store temporary audio clips</p>
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
          
          {/* Audio Processing Options */}
          <div className="mt-4 border-t pt-4">
            <h4 className="font-medium text-gray-700 mb-2">Audio Processing Options</h4>
            <div className="space-y-3">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="use_beep"
                  name="use_beep"
                  checked={settings.use_beep}
                  onChange={handleChange}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="use_beep" className="ml-2 block text-gray-700">
                  Use beep tone instead of muting
                </label>
              </div>
              
              {settings.use_beep && (
                <div>
                  <label className="block font-medium text-gray-700 mb-1">
                    Beep Mode
                  </label>
                  <select
                    name="beep_mode"
                    value={settings.beep_mode}
                    onChange={handleChange}
                    className="w-full md:w-1/2 border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="words">Words only (default)</option>
                    <option value="segments">Full subtitle segments</option>
                    <option value="both">Both words and segments</option>
                  </select>
                  <p className="text-sm text-gray-500 mt-1">Controls which detected sections receive beep tones</p>
                </div>
              )}
              
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="retain_clips"
                  name="retain_clips"
                  checked={settings.retain_clips}
                  onChange={handleChange}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                />
                <label htmlFor="retain_clips" className="ml-2 block text-gray-700">
                  Retain temporary audio clips after processing
                </label>
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
        
        {/* Path Mapping Settings */}
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="text-lg font-medium mb-3">Path Mapping</h3>
          <p className="text-sm text-gray-600 mb-3">
            Configure path mappings between your host system and the Docker container.
            These mappings are used to translate file paths from Sonarr/Radarr to paths accessible within the container.
          </p>
          
          {settings.path_mappings.map((mapping, index) => (
            <div key={index} className="grid grid-cols-1 md:grid-cols-8 gap-2 mb-2 items-center">
              <div className="md:col-span-3">
                <input
                  type="text"
                  placeholder="Host path (e.g., /mnt/storagepool/TV)"
                  value={mapping.host_path}
                  onChange={(e) => handlePathMappingChange(index, 'host_path', e.target.value)}
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="text-center md:col-span-1">
                <span className="text-gray-500">→</span>
              </div>
              <div className="md:col-span-3">
                <input
                  type="text"
                  placeholder="Container path (e.g., /app/media/tv)"
                  value={mapping.container_path}
                  onChange={(e) => handlePathMappingChange(index, 'container_path', e.target.value)}
                  className="w-full border px-3 py-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div className="md:col-span-1 flex justify-end">
                <button
                  type="button"
                  onClick={() => removePathMapping(index)}
                  className="px-2 py-1 bg-red-100 text-red-600 rounded hover:bg-red-200"
                  title="Remove mapping"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          ))}
          
          <div className="mt-2">
            <button
              type="button"
              onClick={addPathMapping}
              className="flex items-center px-3 py-1 bg-blue-100 text-blue-600 rounded hover:bg-blue-200"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 5a1 1 0 011 1v3h3a1 1 0 110 2h-3v3a1 1 0 11-2 0v-3H6a1 1 0 110-2h3V6a1 1 0 011-1z" clipRule="evenodd" />
              </svg>
              Add Mapping
            </button>
          </div>
          
          <div className="mt-3 text-sm">
            <p className="text-gray-600">
              <strong>Example:</strong> If Sonarr reports paths like <code>/mnt/storagepool/TV/ShowName</code> but your container 
              mounts that directory at <code>/app/media/tv/ShowName</code>, add the mapping:
              <br />
              Host: <code>/mnt/storagepool/TV</code> → Container: <code>/app/media/tv</code>
            </p>
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
