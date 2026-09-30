import { useState, useEffect } from 'react';

function Dashboard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processingStats, setProcessingStats] = useState({
    queue: [],
    history: []
  });
  const [refreshInterval, setRefreshInterval] = useState(10000); // 10 seconds
  
  // Fetch initial status
  useEffect(() => {
    fetchStatus();
    fetchProcessingStats();
  }, []);
  
  // Set up refresh interval for processing stats
  useEffect(() => {
    const intervalId = setInterval(() => {
      fetchProcessingStats();
      
      // Refresh status less frequently (every 30 seconds)
      if (Date.now() % (30000) < refreshInterval) {
        fetchStatus();
      }
    }, refreshInterval);
    
    return () => clearInterval(intervalId);
  }, [refreshInterval]);
  
  const fetchStatus = async () => {
    try {
      const response = await fetch('/api/status');
      if (!response.ok) throw new Error('Failed to fetch status');
      
      const data = await response.json();
      setStatus(data);
      setLoading(false);
    } catch (error) {
      console.error('Error fetching status:', error);
      setLoading(false);
    }
  };
  
  const fetchProcessingStats = async () => {
    try {
      const response = await fetch('/api/processing');
      if (!response.ok) throw new Error('Failed to fetch processing stats');
      
      const data = await response.json();
      setProcessingStats(data);
    } catch (error) {
      console.error('Error fetching processing stats:', error);
    }
  };
  
  // Calculate statistics
  const stats = {
    successRate: processingStats.history.length > 0
      ? (processingStats.history.filter(item => item.success).length / processingStats.history.length * 100).toFixed(0)
      : 0,
    totalProfanities: processingStats.history
      .filter(item => item.success)
      .reduce((total, item) => total + (item.result?.swears_found || 0), 0),
    totalProcessed: processingStats.history.length,
    queueCount: processingStats.queue.length,
    showsFiltered: processingStats.history
      .filter(item => item.type === 'show')
      .length,
    moviesFiltered: processingStats.history
      .filter(item => item.type === 'movie')
      .length
  };

  // Format timestamp to date/time
  const formatDateTime = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  return (
    <div className="mt-6">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-600">Auto-refresh:</span>
          <select 
            value={refreshInterval} 
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="border rounded text-sm p-1"
          >
            <option value={5000}>5 seconds</option>
            <option value={10000}>10 seconds</option>
            <option value={30000}>30 seconds</option>
            <option value={60000}>1 minute</option>
          </select>
          <button 
            onClick={() => {
              fetchStatus();
              fetchProcessingStats();
            }}
            className="ml-2 p-1 bg-gray-200 rounded hover:bg-gray-300"
            title="Refresh now"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>
      
      {loading ? (
        <div className="flex justify-center">
          <div className="animate-pulse flex space-x-4">
            <div className="rounded-full bg-gray-300 h-10 w-10"></div>
            <div className="flex-1 space-y-6 py-1">
              <div className="h-2 bg-gray-300 rounded"></div>
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-4">
                  <div className="h-2 bg-gray-300 rounded col-span-2"></div>
                  <div className="h-2 bg-gray-300 rounded col-span-1"></div>
                </div>
                <div className="h-2 bg-gray-300 rounded"></div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* System Status Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            {/* Sonarr Status */}
            <div className={`p-4 rounded-lg shadow flex flex-col ${
              status?.sonarr?.connected ? 'bg-green-50 border border-green-200' : 
              (status?.sonarr?.configured ? 'bg-red-50 border border-red-200' : 'bg-yellow-50 border border-yellow-200')
            }`}>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Sonarr</h3>
                <span className={`rounded-full h-3 w-3 ${
                  status?.sonarr?.connected ? 'bg-green-500' : 
                  (status?.sonarr?.configured ? 'bg-red-500' : 'bg-yellow-500')
                }`}></span>
              </div>
              <div className="mt-2 text-sm">
                {status?.sonarr?.connected ? (
                  <div className="text-green-700">
                    <p>Connected</p>
                    {status?.sonarr?.version && (
                      <p className="mt-1 text-xs">Version: {status.sonarr.version}</p>
                    )}
                  </div>
                ) : status?.sonarr?.configured ? (
                  <div className="text-red-700">
                    <p>Connection Failed</p>
                    <p className="mt-1 text-xs">Check settings and server</p>
                  </div>
                ) : (
                  <div className="text-yellow-700">
                    <p>Not Configured</p>
                    <p className="mt-1 text-xs">Set up in Settings</p>
                  </div>
                )}
              </div>
            </div>

            {/* Radarr Status */}
            <div className={`p-4 rounded-lg shadow flex flex-col ${
              status?.radarr?.connected ? 'bg-green-50 border border-green-200' : 
              (status?.radarr?.configured ? 'bg-red-50 border border-red-200' : 'bg-yellow-50 border border-yellow-200')
            }`}>
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Radarr</h3>
                <span className={`rounded-full h-3 w-3 ${
                  status?.radarr?.connected ? 'bg-green-500' : 
                  (status?.radarr?.configured ? 'bg-red-500' : 'bg-yellow-500')
                }`}></span>
              </div>
              <div className="mt-2 text-sm">
                {status?.radarr?.connected ? (
                  <div className="text-green-700">
                    <p>Connected</p>
                    {status?.radarr?.version && (
                      <p className="mt-1 text-xs">Version: {status.radarr.version}</p>
                    )}
                  </div>
                ) : status?.radarr?.configured ? (
                  <div className="text-red-700">
                    <p>Connection Failed</p>
                    <p className="mt-1 text-xs">Check settings and server</p>
                  </div>
                ) : (
                  <div className="text-yellow-700">
                    <p>Not Configured</p>
                    <p className="mt-1 text-xs">Set up in Settings</p>
                  </div>
                )}
              </div>
            </div>

            {/* Queue Status */}
            <div className="bg-blue-50 border border-blue-200 p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold text-blue-800">Queue</h3>
              <div className="mt-2">
                <div className="flex justify-between items-center">
                  <span className="text-blue-700">Pending</span>
                  <span className="text-blue-900 font-bold text-xl">{stats.queueCount}</span>
                </div>
                <div className="h-1 w-full bg-blue-200 rounded-full mt-2">
                  <div className="h-1 bg-blue-600 rounded-full" style={{ width: `${Math.min(stats.queueCount * 10, 100)}%` }}></div>
                </div>
              </div>
            </div>

            {/* Success Rate */}
            <div className="bg-purple-50 border border-purple-200 p-4 rounded-lg shadow">
              <h3 className="text-lg font-semibold text-purple-800">Success Rate</h3>
              <div className="mt-2">
                <div className="flex justify-between items-center">
                  <span className="text-purple-700">Processed</span>
                  <span className="text-purple-900 font-bold text-xl">{stats.totalProcessed}</span>
                </div>
                <div className="h-1 w-full bg-purple-200 rounded-full mt-1">
                  <div className="h-1 bg-purple-600 rounded-full" style={{ width: `${stats.successRate}%` }}></div>
                </div>
                <div className="flex justify-between items-center mt-2">
                  <span className="text-xs text-purple-700">Success Rate</span>
                  <span className="text-purple-900 font-semibold">{stats.successRate}%</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Statistics Summary */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-white p-4 border rounded-lg shadow">
              <h3 className="text-lg font-semibold mb-3">Profanity Statistics</h3>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span>Total Profanities Found:</span>
                  <span className="font-bold">{stats.totalProfanities}</span>
                </div>
                <div className="flex justify-between">
                  <span>TV Shows Processed:</span>
                  <span className="font-bold">{stats.showsFiltered}</span>
                </div>
                <div className="flex justify-between">
                  <span>Movies Processed:</span>
                  <span className="font-bold">{stats.moviesFiltered}</span>
                </div>
                <div className="flex justify-between">
                  <span>Total Media Processed:</span>
                  <span className="font-bold">{stats.totalProcessed}</span>
                </div>
              </div>
            </div>
            
            <div className="bg-white p-4 border rounded-lg shadow col-span-2">
              <h3 className="text-lg font-semibold mb-3">Processing Queue</h3>
              {processingStats.queue.length === 0 ? (
                <p className="text-gray-500 italic">No items in queue</p>
              ) : (
                <div className="overflow-auto max-h-40">
                  <table className="min-w-full border-collapse">
                    <thead>
                      <tr className="bg-gray-100">
                        <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Title</th>
                        <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 uppercase">Added</th>
                      </tr>
                    </thead>
                    <tbody>
                      {processingStats.queue.map((item, idx) => (
                        <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                          <td className="py-2 px-3 text-xs">
                            <span className={`px-2 py-1 inline-flex text-xs leading-4 font-medium rounded-full ${
                              item.item_type === 'show' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                            }`}>
                              {item.item_type === 'show' ? 'TV' : 'Movie'}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-sm">{item.title} <span className="text-xs text-gray-500">{item.detail}</span></td>
                          <td className="py-2 px-3 text-xs text-gray-500">{formatDateTime(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
          
          {/* Recent Processing History */}
          <div className="bg-white border rounded-lg shadow overflow-hidden">
            <div className="p-4 bg-gray-50 border-b">
              <h3 className="text-lg font-semibold">Recent Processing</h3>
            </div>
            {processingStats.history.length === 0 ? (
              <div className="p-4">
                <p className="text-gray-500 italic">No processing history</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Media</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Processed</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Profanities</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {processingStats.history.slice(0, 10).map((item, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3 whitespace-nowrap">
                          {item.success ? (
                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                              Success
                            </span>
                          ) : (
                            <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                              Failed
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`px-2 py-1 inline-flex text-xs leading-4 font-medium rounded-full ${
                            item.item_type === 'show' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                          }`}>
                            {item.item_type === 'show' ? 'TV' : 'Movie'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-sm font-medium text-gray-900">{item.title}</div>
                          <div className="text-xs text-gray-500">{item.detail}</div>
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                          {formatDateTime(item.processed_at)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm">
                          {item.success ? (
                            <span className="font-medium text-gray-900">{item.swears_found || 0}</span>
                          ) : (
                            <span className="text-red-600 text-xs">{item.error || 'Error'}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default Dashboard;
