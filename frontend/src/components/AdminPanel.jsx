// frontend/src/components/AdminPanel.jsx
import { useState } from 'react';

function AdminPanel() {
  const [activeSection, setActiveSection] = useState('logs');

  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-4">Administration</h2>
      
      <div className="mb-6">
        <div className="flex border-b">
          <button
            className={`py-2 px-4 font-medium ${
              activeSection === 'logs'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-blue-500'
            }`}
            onClick={() => setActiveSection('logs')}
          >
            System Logs
          </button>
          <button
            className={`py-2 px-4 font-medium ${
              activeSection === 'maintenance'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-blue-500'
            }`}
            onClick={() => setActiveSection('maintenance')}
          >
            Maintenance
          </button>
          <button
            className={`py-2 px-4 font-medium ${
              activeSection === 'stats'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-blue-500'
            }`}
            onClick={() => setActiveSection('stats')}
          >
            Statistics
          </button>
        </div>
      </div>
      
      {activeSection === 'logs' && (
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="font-medium mb-2">System Logs</h3>
          <textarea
            className="w-full h-64 p-2 font-mono text-sm border rounded"
            readOnly
            value="Log entries will appear here..."
          ></textarea>
          <div className="mt-2 flex justify-end">
            <button className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600">
              Refresh Logs
            </button>
          </div>
        </div>
      )}
      
      {activeSection === 'maintenance' && (
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="font-medium mb-3">System Maintenance</h3>
          
          <div className="space-y-4">
            <div className="p-3 bg-gray-50 rounded border">
              <h4 className="font-medium">Database Cleanup</h4>
              <p className="text-sm text-gray-600 mt-1 mb-2">
                Remove old processing history and clean up the database.
              </p>
              <button className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600">
                Run Cleanup
              </button>
            </div>
            
            <div className="p-3 bg-gray-50 rounded border">
              <h4 className="font-medium">Synchronize Media Libraries</h4>
              <p className="text-sm text-gray-600 mt-1 mb-2">
                Synchronize Sonarr and Radarr libraries with Bleeparr.
              </p>
              <button className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600">
                Start Sync
              </button>
            </div>
          </div>
        </div>
      )}
      
      {activeSection === 'stats' && (
        <div className="bg-white p-4 border rounded-lg">
          <h3 className="font-medium mb-3">System Statistics</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-3 bg-gray-50 rounded border">
              <h4 className="font-medium">Processing Statistics</h4>
              <div className="mt-2 space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm">Total Files Processed:</span>
                  <span className="font-medium">0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Success Rate:</span>
                  <span className="font-medium">0%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Average Processing Time:</span>
                  <span className="font-medium">0 sec</span>
                </div>
              </div>
            </div>
            
            <div className="p-3 bg-gray-50 rounded border">
              <h4 className="font-medium">System Information</h4>
              <div className="mt-2 space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm">Version:</span>
                  <span className="font-medium">2.0.0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Database Size:</span>
                  <span className="font-medium">0 MB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm">Last Backup:</span>
                  <span className="font-medium">Never</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminPanel;