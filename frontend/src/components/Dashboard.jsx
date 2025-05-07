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
    const intervalId = setInterval(fetchProcessingStats, refreshInterval);
    
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
  
  // Calculate success rate from history
  const successRate = processingStats.history.length > 0
    ? (processingStats.history.filter(item => item.success).length / processingStats.history.length * 100).toFixed(0)
    : 0;
  
  // Count total profanities found
  const totalProfanities = processingStats.history
    .filter(item => item.success)
    .reduce((total, item) => total + (item.result?.swears_found || 0), 0);
  
  return (
    <div className="mt-6">
      <h2 className="text-2xl font-semibold mb-4">Dashboard</h2>
      
      {loading ? (
        <p>Loading status...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div className="bg-white p-4 border rounded-lg shadow">
            <h3 className="text-lg font-medium mb-2">Sonarr</h3>
            {status?.sonarr?.connected ? (
              <div className="text-green-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                Not Configured
              </div>
            )}
          </div>
          
          <div className="bg-white p-4 border rounded-lg shadow">
            <h3 className="text-lg font-medium mb-2">Radarr</h3>
            {status?.radarr?.connected ? (
              <div className="text-green-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                </svg>
                Connected
                {status?.radarr?.version && (
                  <span className="ml-2 text-gray-500 text-sm">v{status.radarr.version}</span>
                )}
              </div>
            ) : status?.radarr?.configured ? (
              <div className="text-red-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                Not Connected
              </div>
            ) : (
              <div className="text-yellow-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path>
                </svg>
                Not Configured
              </div>
            )}
          </div>
          
          <div className="bg-white p-4 border rounded-lg shadow">
            <h3 className="text-lg font-medium mb-2">Processing Status</h3>
            <div className="grid grid-cols-2 gap-2">
              <div className="text-sm">
                <div className="font-medium">Queue:</div>
                <div className="text-lg">{processingStats.queue.length} items</div>
              </div>
              <div className="text-sm">
                <div className="font-medium">Success Rate:</div>
                <div className="text-lg">{successRate}%</div>
              </div>
              <div className="text-sm">
                <div className="font-medium">Processed:</div>
                <div className="text-lg">{processingStats.history.length} files</div>
              </div>
              <div className="text-sm">
                <div className="font-medium">Profanities Found:</div>
                <div className="text-lg">{totalProfanities}</div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* Processing Queue */}
      <div className="mb-8">
        <h3 className="text-xl font-semibold mb-2">Processing Queue</h3>
        {processingStats.queue.length === 0 ? (
          <p className="text-gray-500">No items in queue</p>
        ) : (
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Added</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {processingStats.queue.map((item, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{item.title}</div>
                      <div className="text-sm text-gray-500">{item.detail}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.type === 'show' ? 'TV Episode' : 'Movie'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      
      {/* Recent Processing History */}
      <div>
        <h3 className="text-xl font-semibold mb-2">Recent Processing</h3>
        {processingStats.history.length === 0 ? (
          <p className="text-gray-500">No processing history</p>
        ) : (
          <div className="bg-white border rounded-lg overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Item</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Profanities</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Processed</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {processingStats.history.slice(0, 5).map((item, index) => (
                  <tr key={index}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="font-medium text-gray-900">{item.title}</div>
                      <div className="text-sm text-gray-500">{item.detail}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {item.success ? (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                          Successful
                        </span>
                      ) : (
                        <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-red-100 text-red-800">
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {item.success ? item.result?.swears_found || 0 : '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(item.processed_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default Dashboard;svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                </svg>
                Connected
                {status?.sonarr?.version && (
                  <span className="ml-2 text-gray-500 text-sm">v{status.sonarr.version}</span>
                )}
              </div>
            ) : status?.sonarr?.configured ? (
              <div className="text-red-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12"></path>
                </svg>
                Not Connected
              </div>
            ) : (
              <div className="text-yellow-600 font-medium flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/
